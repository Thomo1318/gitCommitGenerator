"""S6 Slice 7 local session/thread readers (Issue #246 / R13 / S6-F).

Read-only show/map over S3-landed ``commit_session_thread_v1`` twins under
``.eval/sessions/``. S3 owns writing (``binding.session_thread``); this module
never mutates twins, never opens network/Opik, and never builds a chat timeline
or graph browser.

Laws:
* Session id contract is ``sess_<uuid>`` (D9) — reject other prefixes fail-closed.
* Lifecycle lives under ``meta.lifecycle`` ∈ {open, closed} (D12).
* Missing twin / path escape / containment failure → exit class 4.
* Invalid id shape → exit class 2 (usage).
* Optional non-authoritative ``opik_thread_ref`` is surfaced when present.

Import law: import-light. Path / schema helpers are lazy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

from git_cg.eval.binding.session_thread import SESSION_LIFECYCLE_STATES

SCHEMA_VERSION: Final[str] = "commit_session_thread_v1"
_SESS_PREFIX: Final[str] = "sess_"
# Allow sess_ + uuid-ish / hex / safe tokens (writer uses sess_<uuid4>).
_SAFE_SESS_ID: Final[re.Pattern[str]] = re.compile(r"^sess_[A-Za-z0-9][A-Za-z0-9._:-]*$")


class SessionsError(ValueError):
    """Deterministic session/thread reader failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _sessions_dir(repo: Path) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, sessions_dir

    try:
        return sessions_dir(repo)
    except LayerAPathError as exc:
        raise SessionsError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SessionsError(
            f"cannot read session twin {path.name}: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="Inspect .eval/sessions/ for corrupt or unreadable twins.",
        ) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SessionsError(
            f"{path.name} is not valid JSON: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc
    if not isinstance(obj, dict):
        raise SessionsError(
            f"{path.name} must contain a JSON object",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )
    return obj


def _normalize_session_id(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        raise SessionsError(
            "session/thread id is required",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass --id sess_<uuid> from a prior capture episode.",
        )
    sid = str(raw).strip()
    # Accept sessmeta_<id> alias (twin id) by stripping the prefix.
    if sid.startswith("sessmeta_"):
        sid = sid.removeprefix("sessmeta_")
    if not sid.startswith(_SESS_PREFIX):
        raise SessionsError(
            f"session_thread_id must start with 'sess_': {sid!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="D9: session ids are sess_<uuid>; repo-… generation threads are correlation-only.",
        )
    if not _SAFE_SESS_ID.fullmatch(sid):
        raise SessionsError(
            f"invalid session_thread_id shape: {sid!r}",
            code="EVAL_USAGE",
            exit_code=2,
        )
    return sid


def _validate_twin(twin: dict[str, Any], *, expected_id: str) -> None:
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    if twin.get("schema_version") != SCHEMA_VERSION:
        raise SessionsError(
            f"unexpected schema_version {twin.get('schema_version')!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="Only commit_session_thread_v1 twins are readable here.",
        )
    try:
        validate_instance(SCHEMA_VERSION, twin)
    except SchemaPackError as exc:
        raise SessionsError(
            f"session twin failed schema validation: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc

    sid = str(twin.get("session_thread_id") or "")
    if sid != expected_id:
        raise SessionsError(
            f"session_thread_id mismatch: file claims {sid!r}, requested {expected_id!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )
    if not sid.startswith(_SESS_PREFIX):
        raise SessionsError(
            f"landed twin violates sess_ id law: {sid!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )

    meta = twin.get("meta") if isinstance(twin.get("meta"), dict) else {}
    lifecycle = meta.get("lifecycle")
    if lifecycle not in SESSION_LIFECYCLE_STATES:
        raise SessionsError(
            f"session twin missing/invalid meta.lifecycle (want open|closed): {lifecycle!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="S3 writer stamps meta.lifecycle; repair or recapture the twin.",
        )


def read_session_twin(repo: Path, session_thread_id: str | None) -> dict[str, Any]:
    """Load + validate one local session twin (fail-closed).

    Returns a projection dict suitable for CLI envelope ``data``.
    """
    sid = _normalize_session_id(session_thread_id)
    root = _sessions_dir(repo)
    path = root / f"{sid}.json"

    # Containment: resolved path must stay under sessions dir.
    try:
        resolved = path.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        # Also allow exact file under root when root doesn't exist yet.
        if (
            not str(resolved).startswith(str(root_resolved) + "/")
            and resolved != root_resolved
            and root_resolved not in resolved.parents
            and resolved.parent != root_resolved
        ):
            raise SessionsError(
                "session path escapes .eval/sessions/ (containment)",
                code="EVAL_STORE_INTEGRITY",
                exit_code=4,
            )
    except OSError as exc:
        raise SessionsError(
            f"session path resolution failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc

    if not path.is_file():
        raise SessionsError(
            f"session twin not found: {sid!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Capture must be on (GIT_CG_EVAL_CAPTURE) and a prior accept-path write must exist.",
        )

    twin = _load_json(path)
    _validate_twin(twin, expected_id=sid)

    meta = twin.get("meta") if isinstance(twin.get("meta"), dict) else {}
    message_versions = list(twin.get("message_versions") or [])
    opik_ref = twin.get("opik_thread_ref")

    return {
        "session_thread_id": sid,
        "id": twin.get("id"),
        "lifecycle": meta.get("lifecycle"),
        "redaction_profile": twin.get("redaction_profile"),
        "attempt_ids": list(twin.get("attempt_ids") or []),
        "message_versions": message_versions,
        "message_version_count": len(message_versions),
        "preference_pairs": list(twin.get("preference_pairs") or []),
        "opened_at": meta.get("opened_at"),
        "closed_at": meta.get("closed_at"),
        "trace_id": meta.get("trace_id"),
        "generation_thread_id": meta.get("generation_thread_id"),
        "opik_thread_ref": opik_ref if isinstance(opik_ref, (str, dict)) else None,
        "path": path.as_posix(),
        "twin": twin,
        "authority": "local_layer_a",
        "network": False,
    }


def show_session(repo: Path, session_thread_id: str | None) -> dict[str, Any]:
    """CLI ``eval session show`` envelope over a local twin.

    Returns ``data.session`` as the raw ``commit_session_thread_v1`` twin plus
    operator-facing projection fields. Read/map only — no network, no chat
    timeline, no graph browser (S6-F06 / S6-F07).
    """
    data = read_session_twin(repo, session_thread_id)
    twin = data["twin"]
    return {
        "session": twin,
        "session_thread_id": data["session_thread_id"],
        "lifecycle": data["lifecycle"],
        "message_version_count": data["message_version_count"],
        "preference_pairs": list(data.get("preference_pairs") or []),
        "opik_thread_ref": data.get("opik_thread_ref"),
        "path": data["path"],
        "authority": data["authority"],
        "network": False,
        "surface": "show_map_only",
    }


def show_thread(repo: Path, thread_id: str | None) -> dict[str, Any]:
    """CLI ``eval thread show`` map over the same ``sess_`` capture episode.

    Exposes message_versions / preference_pairs as store fields only — not a
    chat timeline or graph browser (S6-F scope lock).
    """
    data = read_session_twin(repo, thread_id)
    twin = data["twin"]
    meta = twin.get("meta") if isinstance(twin.get("meta"), dict) else {}
    thread = {
        "id": twin.get("id"),
        "session_thread_id": data["session_thread_id"],
        "schema_version": twin.get("schema_version"),
        "message_versions": list(data.get("message_versions") or []),
        "message_version_count": data["message_version_count"],
        "preference_pairs": list(data.get("preference_pairs") or []),
        "attempt_ids": list(data.get("attempt_ids") or []),
        "meta": dict(meta),
        "redaction_profile": twin.get("redaction_profile"),
    }
    return {
        "thread": thread,
        "session_thread_id": data["session_thread_id"],
        "lifecycle": data["lifecycle"],
        "opik_thread_ref": data.get("opik_thread_ref"),
        "path": data["path"],
        "authority": data["authority"],
        "network": False,
        "surface": "show_map_only",
    }


__all__ = [
    "SCHEMA_VERSION",
    "SessionsError",
    "read_session_twin",
    "show_session",
    "show_thread",
]
