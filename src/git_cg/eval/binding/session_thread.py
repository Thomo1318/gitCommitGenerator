"""S3 commit-session thread twin (R13 / N8 / D12).

Emits schema-valid ``commit_session_thread_v1`` local twins: one session thread
per commit unit of work (start → accept), with the lifecycle carried under
``meta.lifecycle`` (D12 — there is **no** top-level open/closed enum). The twin
is **additive** (N8): it links existing ``trace_id`` / span ids when present and
never deletes or replaces existing Opik/product telemetry to "make room".

Contract locks honoured here:

* **D12** — required fields ``schema_version`` / ``id`` / ``session_thread_id``
  / ``redaction_profile``; ``id = sessmeta_<session_thread_id>``; lifecycle +
  timestamps + correlation ids live under ``meta``.
* **D9 / N18** — ``session_thread_id`` is always a ``sess_<uuid4>`` capture
  episode id; ``GenerationTelemetry.thread_id`` (``repo-…``) is correlation-only
  and is recorded under ``meta.generation_thread_id``, never as the session id.
* **N8 / R13** — additive; ``existing_trace_span_ids`` may be empty when spans
  are unavailable — never invent ids.
* **N19.3 / N20.5** — persistence is atomic + contained under ``.eval/sessions/``;
  an unresolvable repo root surfaces ``repo_root_unresolved`` (no product fail).
* **N19.5** — capture gated by :func:`profiles.capture_enabled`; when off,
  ``write_session_twin`` performs zero writes and returns ``None``.

No network. No Opik import. No product-accept blocking.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_cg.eval.binding import paths
from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.enums import RedactionProfile
from git_cg.eval.schema_pack import SchemaPackError, validate_instance

__all__ = [
    "SESSION_LIFECYCLE_STATES",
    "SessionTwinError",
    "SessionTwinResult",
    "build_session_twin",
    "write_session_twin",
]

#: D12 — allowed ``meta.lifecycle`` values (no top-level enum exists).
SESSION_LIFECYCLE_STATES: frozenset[str] = frozenset({"open", "closed"})

#: Default redaction profile when none is supplied (D6).
_DEFAULT_REDACTION = RedactionProfile.DEFAULT_SCRUB.value


class SessionTwinError(ValueError):
    """Session-twin construction failure (fail closed)."""


@dataclass(frozen=True, slots=True)
class SessionTwinResult:
    """Outcome of a session-twin write attempt. Never raises for product reasons."""

    written: bool
    session_thread: dict[str, Any] | None = None
    path_written: str | None = None
    reason: str | None = None
    errors: tuple[str, ...] = ()


def _clean_str_list(values: Iterable[str] | None, *, field_name: str) -> list[str]:
    """Normalise an optional iterable of ids to a list of non-empty strings."""
    if values is None:
        return []
    out: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise SessionTwinError(f"{field_name} entries must be non-empty strings")
        out.append(item.strip())
    return out


def build_session_twin(
    session_thread_id: str,
    *,
    lifecycle: str,
    redaction_profile: str | None = None,
    attempt_ids: Iterable[str] | None = None,
    message_versions: list[dict[str, Any]] | None = None,
    opened_at: str | None = None,
    closed_at: str | None = None,
    trace_id: str | None = None,
    generation_thread_id: str | None = None,
    existing_trace_span_ids: Iterable[str] | None = None,
    notes: str | None = None,
    metric_catalog: str | None = None,
    schema_pack: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``commit_session_thread_v1`` twin (D12).

    ``lifecycle`` is carried under ``meta.lifecycle`` and must be ``open`` or
    ``closed``. Correlation ids (``trace_id`` / ``generation_thread_id`` /
    ``existing_trace_span_ids``) are recorded under ``meta`` only — they never
    become the session id (D9). No ids are invented: omit what is not known.
    """
    if not isinstance(session_thread_id, str) or not session_thread_id.strip():
        raise SessionTwinError("session_thread_id must be a non-empty string")
    session_id = session_thread_id.strip()
    if not session_id.startswith("sess_"):
        raise SessionTwinError(f"session_thread_id must be a sess_ capture-episode id (D9): {session_id!r}")
    if lifecycle not in SESSION_LIFECYCLE_STATES:
        raise SessionTwinError(f"lifecycle must be one of {sorted(SESSION_LIFECYCLE_STATES)}: {lifecycle!r}")

    meta_out: dict[str, Any] = {"lifecycle": lifecycle}
    if opened_at is not None:
        meta_out["opened_at"] = opened_at
    if closed_at is not None:
        meta_out["closed_at"] = closed_at
    if trace_id is not None:
        meta_out["trace_id"] = trace_id
    if generation_thread_id is not None:
        meta_out["generation_thread_id"] = generation_thread_id
    span_ids = _clean_str_list(existing_trace_span_ids, field_name="existing_trace_span_ids")
    if span_ids:
        meta_out["existing_trace_span_ids"] = span_ids
    if meta:
        # Additive non-authoritative fields; never let caller override lifecycle
        # or correlation keys with non-string types silently.
        for key, value in meta.items():
            meta_out.setdefault(key, value)

    twin: dict[str, Any] = {
        "schema_version": "commit_session_thread_v1",
        "id": f"sessmeta_{session_id}",
        "session_thread_id": session_id,
        "redaction_profile": redaction_profile or _DEFAULT_REDACTION,
        "attempt_ids": _clean_str_list(attempt_ids, field_name="attempt_ids"),
        "message_versions": list(message_versions) if message_versions else [],
        "meta": meta_out,
    }
    if notes is not None:
        twin["notes"] = notes
    if metric_catalog is not None:
        twin["metric_catalog"] = metric_catalog
    if schema_pack is not None:
        twin["schema_pack"] = schema_pack

    # Fail closed: the twin we claim must validate against the frozen schema.
    validate_instance("commit_session_thread_v1", twin)
    return twin


def write_session_twin(
    session_thread_id: str,
    *,
    lifecycle: str,
    repo_root: Path | None = None,
    write: bool = True,
    **kwargs: Any,
) -> SessionTwinResult:
    """Build and (optionally) persist a session twin under ``.eval/sessions/``.

    Never raises for product-accept reasons. Behaviour:

    * Capture disabled ⇒ ``written=False, reason="capture_disabled"``, zero
      writes (D1/N19.5).
    * ``write=False`` ⇒ build + validate only; no filesystem I/O.
    * Repo root unresolvable ⇒ ``written=False, reason="repo_root_unresolved"``
      (N20.5), no product fail.
    * Persistence failure is reported via ``errors`` and never blocks accept.
    """
    if not capture_enabled():
        return SessionTwinResult(written=False, reason="capture_disabled")

    try:
        twin = build_session_twin(session_thread_id, lifecycle=lifecycle, **kwargs)
    except (SessionTwinError, SchemaPackError) as exc:
        return SessionTwinResult(written=False, reason="invalid_twin", errors=(str(exc),))

    if not write:
        return SessionTwinResult(written=False, session_thread=twin, reason="write_disabled")

    try:
        root = Path(repo_root).resolve() if repo_root is not None else paths.resolve_repo_root()
    except paths.RepoRootUnresolvedError:
        return SessionTwinResult(written=False, session_thread=twin, reason="repo_root_unresolved")

    try:
        out = paths.sessions_dir(root) / f"{twin['session_thread_id']}.json"
        paths.atomic_write_json(out, twin)
        return SessionTwinResult(
            written=True,
            session_thread=twin,
            path_written=out.relative_to(root).as_posix(),
        )
    except (OSError, paths.LayerAPathError) as exc:
        return SessionTwinResult(
            written=False,
            session_thread=twin,
            reason="write_error",
            errors=(f"session_write_error: {exc}",),
        )
