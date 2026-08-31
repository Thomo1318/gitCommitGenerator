"""Optional online Opik verification (S7-1b / S7-2b, Issue #254).

Explicitly gated, non-authoritative remote checks for:

* four-lane project existence (and optional create)
* Tier-1 Feedback Definition drift vs the local vocabulary map

Law:

* **Never** called from ``run_opik_doctor`` / promote / gates / product accept.
* Network is **opt-in only** (``remote=True`` / CLI ``--remote``).
* Network/auth failure is **warning-only** (never flips doctor green, never a
  CI/product-accept gate, never authoritative).
* Project creation requires a second explicit opt-in (``create_missing``).
* No secrets are logged, serialised, or returned in the public report.
* Client is injectable for offline unit tests; the real SDK path is lazy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol, runtime_checkable

from git_cg.eval.mirror.transport import scrub_export_note

__all__ = [
    "OPIK_VERIFY_AUTHORITY",
    "PROJECT_LANES",
    "OpikVerifyClient",
    "OpikVerifyReport",
    "OpikVerifyRow",
    "run_opik_verify",
]

OPIK_VERIFY_AUTHORITY: Final[str] = "advisory_non_sot"
PROJECT_LANES: Final[tuple[str, ...]] = ("live", "eval", "ci", "import")

_MAX_NOTES: Final = 32
_MAX_NOTE_LEN: Final = 200


@runtime_checkable
class OpikVerifyClient(Protocol):
    """Minimal injectable client for online project/FD verification."""

    def list_projects(self) -> Sequence[str]:
        """Return remote project names visible to the caller."""

    def create_project(self, name: str) -> None:
        """Create one remote project (explicit opt-in only)."""

    def list_feedback_definitions(self) -> Mapping[str, Mapping[str, Any]]:
        """Return remote FD name → metadata mapping."""


@dataclass(frozen=True, slots=True)
class OpikVerifyRow:
    """One machine-readable online verification row."""

    check_id: str
    status: str  # pass | warn | fail | skip
    message: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize one verification row."""
        out: dict[str, Any] = {
            "check_id": self.check_id,
            "status": self.status,
            "message": self.message,
        }
        if self.hint is not None:
            out["hint"] = self.hint
        return out


def _scrub_notes(notes: Sequence[str] | None) -> tuple[str, ...]:
    """Scrub and bound operator-facing notes (max length, max count)."""
    if not notes:
        return ()
    out: list[str] = []
    for note in notes:
        text = scrub_export_note(str(note), limit=_MAX_NOTE_LEN)
        if not text:
            continue
        out.append(text)
        if len(out) >= _MAX_NOTES:
            break
    return tuple(out)


@dataclass(frozen=True, slots=True)
class OpikVerifyReport:
    """Structured online verification outcome (always non-authoritative)."""

    ok: bool
    remote: bool
    create_missing: bool
    rows: tuple[OpikVerifyRow, ...] = ()
    notes: tuple[str, ...] = ()
    exit_code: int = 0
    authority: str = field(default=OPIK_VERIFY_AUTHORITY, init=False)
    product_accept_blocked: bool = field(default=False, init=False)
    doctor_authority: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "authority", OPIK_VERIFY_AUTHORITY)
        object.__setattr__(self, "product_accept_blocked", False)
        object.__setattr__(self, "doctor_authority", False)
        object.__setattr__(self, "notes", _scrub_notes(self.notes))

    def to_data(self) -> dict[str, Any]:
        """Envelope ``data`` payload for CLI output."""
        return {
            "ok": self.ok,
            "remote": self.remote,
            "create_missing": bool(self.create_missing),
            "exit_code": int(self.exit_code),
            "authority": OPIK_VERIFY_AUTHORITY,
            "product_accept_blocked": False,
            "doctor_authority": False,
            "rows": [r.to_dict() for r in self.rows],
            "notes": list(self.notes),
        }


def _lane_projects(config: Mapping[str, Any] | None) -> dict[str, str]:
    """Extract four-lane project pins from resolved config (EVAL bootstrap aware)."""
    out: dict[str, str] = {}
    if not isinstance(config, Mapping):
        return out
    projects = config.get("projects")
    if isinstance(projects, Mapping):
        for lane in PROJECT_LANES:
            val = projects.get(lane)
            if isinstance(val, str) and val.strip():
                out[lane] = val.strip()
    if not out:
        legacy = config.get("project_name")
        if isinstance(legacy, str) and legacy.strip():
            name = legacy.strip()
            for lane in PROJECT_LANES:
                out[lane] = name
    return out


def _fd_signature(meta: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize comparable FD fields (type + optional scale/categories)."""
    sig: dict[str, Any] = {"type": str(meta.get("type") or "").strip().lower()}
    if "scale_min" in meta:
        sig["scale_min"] = meta.get("scale_min")
    if "scale_max" in meta:
        sig["scale_max"] = meta.get("scale_max")
    cats = meta.get("categories")
    if isinstance(cats, list):
        sig["categories"] = sorted(str(c) for c in cats)
    return sig


def _compare_feedback_definitions(
    *,
    local: Mapping[str, Any],
    remote: Mapping[str, Mapping[str, Any]],
) -> list[OpikVerifyRow]:
    """Compare local Tier-1 FD vocabulary against remote workspace definitions."""
    rows: list[OpikVerifyRow] = []
    local_defs = local.get("definitions") if isinstance(local.get("definitions"), dict) else {}
    local_names = set(local_defs) if isinstance(local_defs, dict) else set()
    remote_names = set(remote)

    missing = sorted(local_names - remote_names)
    extra = sorted(remote_names - local_names)
    shared = sorted(local_names & remote_names)

    if missing:
        rows.append(
            OpikVerifyRow(
                "opik.fd.missing",
                "warn",
                f"remote missing Tier-1 definitions: {', '.join(missing)}",
                hint="Create matching Feedback Definitions in the Opik workspace (optional).",
            )
        )
    if extra:
        rows.append(
            OpikVerifyRow(
                "opik.fd.extra",
                "warn",
                f"remote has extra definitions not in local map: {', '.join(extra)}",
                hint="Extra remote FDs are informational only; local map remains vocabulary SoT.",
            )
        )

    mismatches: list[str] = []
    for name in shared:
        local_sig = _fd_signature(local_defs[name] if isinstance(local_defs.get(name), dict) else {})
        remote_sig = _fd_signature(remote.get(name) or {})
        if local_sig != remote_sig:
            mismatches.append(name)
    if mismatches:
        rows.append(
            OpikVerifyRow(
                "opik.fd.mismatch",
                "warn",
                f"definition shape drift for: {', '.join(mismatches)}",
                hint="Align remote FD type/scale/categories with config/feedback_definitions.json.",
            )
        )
    if not missing and not extra and not mismatches:
        rows.append(
            OpikVerifyRow(
                "opik.fd.aligned",
                "pass",
                f"remote Feedback Definitions align with local map ({len(shared)} names)",
            )
        )
    return rows


def _default_client_factory() -> OpikVerifyClient:
    """Build a real Opik-backed client (lazy SDK import; secrets ephemeral)."""
    from git_cg.eval.mirror.secrets import resolve_opik_secrets

    secrets = resolve_opik_secrets(require_key=True)

    import opik  # lazy; allowlisted import site

    client = opik.Opik(
        workspace=secrets.workspace,
        host=secrets.base_url,
        api_key=secrets.api_key or None,
    )

    class _SdkClient:
        def list_projects(self) -> Sequence[str]:
            names: list[str] = []
            # Prefer rest_client when present (SDK surface varies by version).
            rest = getattr(client, "rest_client", None)
            projects_api = getattr(rest, "projects", None) if rest is not None else None
            if projects_api is not None and hasattr(projects_api, "find_projects"):
                page = projects_api.find_projects(page=1, size=100)
                content = getattr(page, "content", None) or getattr(page, "data", None) or []
                for item in content:
                    name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
                    if isinstance(name, str) and name.strip():
                        names.append(name.strip())
                return names
            raise RuntimeError("opik SDK projects listing surface unavailable")

        def create_project(self, name: str) -> None:
            rest = getattr(client, "rest_client", None)
            projects_api = getattr(rest, "projects", None) if rest is not None else None
            if projects_api is not None and hasattr(projects_api, "create_project"):
                projects_api.create_project(name=name)
                return
            raise RuntimeError("opik SDK project create surface unavailable")

        def list_feedback_definitions(self) -> Mapping[str, Mapping[str, Any]]:
            rest = getattr(client, "rest_client", None)
            fd_api = getattr(rest, "feedback_definitions", None) if rest is not None else None
            if fd_api is None or not hasattr(fd_api, "find_feedback_definitions"):
                raise RuntimeError("opik SDK feedback-definition listing surface unavailable")
            page = fd_api.find_feedback_definitions(page=1, size=100)
            content = getattr(page, "content", None) or getattr(page, "data", None) or []
            out: dict[str, dict[str, Any]] = {}
            for item in content:
                if isinstance(item, dict):
                    name = item.get("name")
                    payload = item
                else:
                    name = getattr(item, "name", None)
                    payload = {
                        "type": getattr(item, "type", None),
                        "details": getattr(item, "details", None),
                    }
                if not isinstance(name, str) or not name.strip():
                    continue
                details = payload.get("details") if isinstance(payload, dict) else None
                meta: dict[str, Any] = {
                    "type": str((payload.get("type") if isinstance(payload, dict) else "") or "").lower()
                }
                if isinstance(details, dict):
                    if "min" in details:
                        meta["scale_min"] = details.get("min")
                    if "max" in details:
                        meta["scale_max"] = details.get("max")
                    if "categories" in details:
                        cats = details.get("categories")
                        if isinstance(cats, dict):
                            meta["categories"] = sorted(str(k) for k in cats)
                        elif isinstance(cats, list):
                            meta["categories"] = [str(c) for c in cats]
                out[name.strip()] = meta
            return out

    return _SdkClient()


def run_opik_verify(
    *,
    remote: bool = False,
    create_missing: bool = False,
    config: Mapping[str, Any] | None = None,
    client: OpikVerifyClient | None = None,
    client_factory: Callable[[], OpikVerifyClient] | None = None,
    local_feedback_definitions: Mapping[str, Any] | None = None,
) -> OpikVerifyReport:
    """Run optional online Opik project/FD verification.

    Offline default (``remote=False``) returns a skipped advisory report with
    exit 0. Online failures are warning-class and never product-blocking.
    """
    notes: list[str] = []
    rows: list[OpikVerifyRow] = []

    if not remote:
        rows.append(
            OpikVerifyRow(
                "opik.verify.remote",
                "skip",
                "online verify skipped (pass remote=True / --remote to enable)",
                hint="Optional maintainer surface only; never a CI gate.",
            )
        )
        return OpikVerifyReport(
            ok=True,
            remote=False,
            create_missing=False,
            rows=tuple(rows),
            notes=("online verify disabled",),
            exit_code=0,
        )

    resolved_config: Mapping[str, Any] | None = config
    if resolved_config is None:
        try:
            from git_cg.eval.mirror.config import resolve_opik_config

            resolved_config = resolve_opik_config()
        except Exception as exc:  # config errors are warning-only here
            msg = scrub_export_note(f"config resolve failed: {exc}")
            rows.append(
                OpikVerifyRow(
                    "opik.verify.config",
                    "warn",
                    msg,
                    hint="Fix local Opik config, then re-run with --remote.",
                )
            )
            return OpikVerifyReport(
                ok=True,
                remote=True,
                create_missing=bool(create_missing),
                rows=tuple(rows),
                notes=(msg,),
                exit_code=0,
            )

    lanes = _lane_projects(resolved_config)
    if not lanes:
        rows.append(
            OpikVerifyRow(
                "opik.verify.projects",
                "warn",
                "no local project lane pins to verify",
                hint="Set GIT_CG_OPIK_PROJECT_{LIVE,EVAL,CI,IMPORT} (or EVAL bootstrap).",
            )
        )

    active_client = client
    if active_client is None:
        factory = client_factory or _default_client_factory
        try:
            active_client = factory()
        except Exception as exc:
            msg = scrub_export_note(f"remote client unavailable: {exc}")
            rows.append(
                OpikVerifyRow(
                    "opik.verify.client",
                    "warn",
                    msg,
                    hint="Network/auth failure is warning-only; doctor remains offline authority.",
                )
            )
            return OpikVerifyReport(
                ok=True,
                remote=True,
                create_missing=bool(create_missing),
                rows=tuple(rows),
                notes=(msg,),
                exit_code=0,
            )

    try:
        remote_projects = {str(p).strip() for p in active_client.list_projects() if str(p).strip()}
    except Exception as exc:
        msg = scrub_export_note(f"project list failed: {exc}")
        rows.append(
            OpikVerifyRow(
                "opik.verify.projects.list",
                "warn",
                msg,
                hint="Remote listing failed; local pins remain authoritative.",
            )
        )
        remote_projects = set()
        notes.append(msg)

    for lane, name in lanes.items():
        if name in remote_projects:
            rows.append(
                OpikVerifyRow(
                    f"opik.verify.project.{lane}",
                    "pass",
                    f"lane {lane} project exists: {name}",
                )
            )
            continue
        if create_missing:
            try:
                active_client.create_project(name)
                rows.append(
                    OpikVerifyRow(
                        f"opik.verify.project.{lane}",
                        "pass",
                        f"lane {lane} project created: {name}",
                    )
                )
                remote_projects.add(name)
            except Exception as exc:
                msg = scrub_export_note(f"create failed for {lane}/{name}: {exc}")
                rows.append(
                    OpikVerifyRow(
                        f"opik.verify.project.{lane}",
                        "warn",
                        msg,
                        hint="Creation is optional; create the project manually in Opik if needed.",
                    )
                )
                notes.append(msg)
        else:
            rows.append(
                OpikVerifyRow(
                    f"opik.verify.project.{lane}",
                    "warn",
                    f"lane {lane} project missing remotely: {name}",
                    hint="Re-run with --create-missing to attempt optional creation.",
                )
            )

    local_fd = local_feedback_definitions
    if local_fd is None:
        try:
            from git_cg.eval.feedback_definitions import load_feedback_definitions

            local_fd = load_feedback_definitions()
        except Exception as exc:
            msg = scrub_export_note(f"local FD map load failed: {exc}")
            rows.append(OpikVerifyRow("opik.fd.local", "warn", msg))
            local_fd = {"schema_version": "feedback_definition_v1", "definitions": {}}
            notes.append(msg)

    try:
        remote_fd = dict(active_client.list_feedback_definitions())
        rows.extend(_compare_feedback_definitions(local=local_fd, remote=remote_fd))
    except Exception as exc:
        msg = scrub_export_note(f"feedback definition list failed: {exc}")
        rows.append(
            OpikVerifyRow(
                "opik.fd.list",
                "warn",
                msg,
                hint="FD remote verify is optional; local map remains vocabulary SoT.",
            )
        )
        notes.append(msg)

    if not notes:
        notes.append("online verify completed (advisory_non_sot)")
    return OpikVerifyReport(
        ok=True,
        remote=True,
        create_missing=bool(create_missing),
        rows=tuple(rows),
        notes=tuple(notes),
        exit_code=0,
    )
