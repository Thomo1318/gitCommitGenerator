import contextlib
import importlib.metadata
import os
from pathlib import Path
from urllib.parse import urlparse

import sentry_sdk

# Companion vars injected by host apps (Raycast Beta, some Electron shells).
# When present, ambient SENTRY_DSN is treated as untrusted host telemetry — not git-cg's.
_HOST_INJECTED_SENTRY_MARKERS: tuple[str, ...] = (
    "SENTRY_DISTRIBUTION",
    "SENTRY_STARTUP_TRACE_ID",
    "SENTRY_STARTUP_BAGGAGE",
    "SENTRY_PROFILER_BINARY_DIR",
    "SENTRY_USER_ID",
)

_DOTENV_CANDIDATES: tuple[str, ...] = (".env", "manual.env")


def _strip_env(value: str | None) -> str | None:
    """Strip whitespace from an environment variable value, returning None for empty strings."""
    if value is None:
        return None
    text = value.strip()
    return text or None


def host_injected_sentry_env(environ: os._Environ[str] | dict[str, str] | None = None) -> bool:
    """Return True when the process env looks like a host app's Sentry bootstrap."""
    env = os.environ if environ is None else environ
    return any(_strip_env(env.get(key)) for key in _HOST_INJECTED_SENTRY_MARKERS)


def _parse_dotenv_keys(path: Path, keys: set[str]) -> dict[str, str]:
    """Minimal KEY=VALUE reader for allowlisted keys only (no export/expansion)."""
    found: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return found
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in keys or key in found:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if value:
            found[key] = value
    return found


def dsn_from_dotenv_files(
    *,
    cwd: Path | None = None,
    filenames: tuple[str, ...] = _DOTENV_CANDIDATES,
) -> str | None:
    """Read GIT_CG_SENTRY_DSN / SENTRY_DSN from local dotenv files (gitignored)."""
    root = cwd if cwd is not None else Path.cwd()
    wanted = {"GIT_CG_SENTRY_DSN", "SENTRY_DSN"}
    # Prefer product key across all candidate files before ambient SENTRY_DSN.
    for key in ("GIT_CG_SENTRY_DSN", "SENTRY_DSN"):
        for name in filenames:
            parsed = _parse_dotenv_keys(root / name, wanted)
            value = _strip_env(parsed.get(key))
            if value:
                return value
    return None


def resolve_sentry_dsn(environ: os._Environ[str] | dict[str, str] | None = None) -> str | None:
    """Resolve the DSN git-cg should use.

    Precedence:
    1. ``GIT_CG_SENTRY_DSN`` (explicit product override — always wins)
    2. Ambient ``SENTRY_DSN`` when the env does **not** look host-injected
    3. Project ``.env`` / ``manual.env`` when host injection is detected (or ambient absent)
    4. ``None`` (Sentry stays inactive)

    This prevents Raycast/Electron from silently shipping git-cg events to the host app's
    Sentry project when those apps export their own ``SENTRY_DSN``.
    """
    env = os.environ if environ is None else environ

    explicit = _strip_env(env.get("GIT_CG_SENTRY_DSN"))
    if explicit:
        return explicit

    ambient = _strip_env(env.get("SENTRY_DSN"))
    injected = host_injected_sentry_env(env)

    if ambient and not injected:
        return ambient

    from_files = dsn_from_dotenv_files()
    if from_files:
        return from_files

    # Do not fall back to host-injected ambient DSN.
    if injected:
        return None
    return ambient


def dsn_project_id(dsn: str | None) -> str | None:
    """Return the Sentry project id path segment from a DSN, if parseable."""
    text = _strip_env(dsn)
    if not text:
        return None
    try:
        path = urlparse(text).path.lstrip("/")
    except Exception:
        return None
    return path or None


def init_sentry():
    """
    Initialise Sentry telemetry for the application.

    Sentry setup can be disabled by setting ``GIT_CG_DISABLE_SENTRY`` to ``"1"``.
    When enabled, captured git diff output in Sentry event contexts is scrubbed before sending.

    DSN resolution prefers ``GIT_CG_SENTRY_DSN``, then a non-host-injected ``SENTRY_DSN``,
    then project dotenv files — see :func:`resolve_sentry_dsn`.
    """
    if os.environ.get("GIT_CG_DISABLE_SENTRY", "0") == "1":
        return

    try:
        version = importlib.metadata.version("gitcommitgenerator")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    def scrub_data(event, hint):
        # Prevent massive diffs from overflowing the 8kb context limit or leaking source code
        """
        Scrub git diff output from a Sentry event.

        Parameters:
                event: The event payload to sanitise.

        Returns:
                The event payload with any git_cg diff output replaced with "[SCRUBBED]".
        """
        if "contexts" in event and "git_cg" in event["contexts"] and "diff_output" in event["contexts"]["git_cg"]:
            event["contexts"]["git_cg"]["diff_output"] = "[SCRUBBED]"

        # Scrub local variables that could contain large strings, source code, paths or PII
        if "exception" in event and "values" in event["exception"]:
            for exc in event["exception"]["values"]:
                if "stacktrace" in exc and "frames" in exc["stacktrace"]:
                    for frame in exc["stacktrace"]["frames"]:
                        if "vars" in frame:
                            for var_name in [
                                "diff_output",
                                "system_prompt",
                                "prompt",
                                "messages",
                                "result_string",
                                "commit_msg_file",
                                "git_dir",
                                "cwd",
                                "file_path",
                                # Phase 9 free-text / path-bearing locals (Issue #163).
                                "scoped_history_guidance",
                                "scoped_history_split_rationale",
                                "scoped_history_rename_rationale",
                                "flows_payload_for_evidence",
                                "file_to_flow_ids",
                                "old_bytes",
                                "new_bytes",
                                "staged_files",
                                "analysis_diff",
                                "evidence",
                                "evidence_dict",
                                "_scoped_history_file_to_flow_ids",
                                "renamed_paths",
                                "changed_files",
                                "parser_batch_results",
                                # Phase 7.30 presentation locals (Issue #204) — closed
                                # enums are safe as tags, but scrub free-text guidance.
                                "low_confidence_guidance",
                                "body_skeleton",
                                # Slice 10 / D26 — scrub presentation locals; closed tags only via set_tag.
                                "presentation_fallback_reason",
                                "path_class_gate",
                                "changelog_antisignal_applied",
                                "hallucination_guard_fired",
                                "scope_normalised_from",
                                "preferred_scope",
                                "preferred_scope_raw",
                                "force_scope",
                                "scope_hint",
                                "guard_report",
                                "claim_tags",
                                "harvested_claim_tags",
                                # Slice 7 blueprint — never ship payload/content.
                                "blueprint",
                                "blueprint_raw",
                                "blueprint_source",
                                "blueprint_guidance",
                                "parsed_blueprint",
                                "commit_blueprint",
                                # Slice 5.5 lifecycle — keep tags only; scrub any locals.
                                "commit_plan",
                                "commit_plan_json",
                                "llm_raw_plan",
                                "contract_lifecycle",
                            ]:
                                if var_name in frame["vars"]:
                                    frame["vars"][var_name] = "[SCRUBBED]"

        return event

    dsn = resolve_sentry_dsn()

    with contextlib.suppress(Exception):
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "local"),
            release=f"gitCommitGenerator@{version}",
            send_default_pii=False,
            before_send=scrub_data,
            traces_sample_rate=0.0,
        )


def report_commit_plan_contract_violation(
    *,
    locked_semver: str | None,
    persisted_semver: str | None,
    lift_applied: bool = False,
    lift_from_semver: str | None = None,
    normaliser_reason: str = "none",
    diff_hash: str | None = None,
) -> None:
    """Emit errors-only Sentry event for a locked-vs-persisted contract violation.

    Issue #204 · Slice 5.5. Fingerprint ``commit_plan_contract_violation``.
    Tags are closed enum / hash identifiers only — never prompts, diffs, bodies,
    blueprint JSON, or free-text plan content.
    """
    # Local import keeps module import light when Sentry is disabled.
    import sentry_sdk

    def _sem(value: object) -> str:
        """Normalize a SemVer value to a standard string representation."""
        if value is None or value == "":
            return "unknown"
        if hasattr(value, "value"):
            value = value.value
        raw = str(value).strip().upper()
        return raw if raw in {"NONE", "PATCH", "MINOR", "MAJOR"} else "unknown"

    locked = _sem(locked_semver)
    persisted = _sem(persisted_semver)
    from_sem = _sem(lift_from_semver) if lift_from_semver not in (None, "") else "none"
    reason = str(normaliser_reason or "none").strip().lower()
    allowed_reasons = {
        "none",
        "contract_lift",
        "presentation_clamp",
        "matrix_reconstruction",
        "malformed_semver",
        "residual_violation",
    }
    if reason not in allowed_reasons:
        reason = "none"
    dhash = str(diff_hash or "").strip().lower()
    # Allow only short hex hashes; drop anything else.
    if not dhash or len(dhash) > 64 or any(c not in "0123456789abcdef" for c in dhash):
        dhash = "none"

    with sentry_sdk.new_scope() as scope:
        scope.set_tag("event_name", "commit_plan_contract_violation")
        scope.set_tag("contract_locked_semver", locked)
        scope.set_tag("plan_persisted_semver", persisted)
        scope.set_tag("contract_lift_applied", "true" if lift_applied else "false")
        scope.set_tag("contract_lift_from_semver", from_sem)
        scope.set_tag("plan_normaliser_reason", reason)
        scope.set_tag("diff_hash", dhash)
        scope.fingerprint = [
            "commit_plan_contract_violation",
            locked,
            persisted,
            reason,
        ]
        sentry_sdk.capture_message("commit_plan_contract_violation", level="error")
