"""S3 Slice 3 — minimal product accept-path emit hooks (Issue #231, N19 F8).

Narrow integration between the product ``record-telemetry`` accept path and the
Lane A binding package. This module is the **only** composition point: it binds
the exact accepted ``COMMIT_EDITMSG`` bytes, emits the ``trajectory_evidence_v1``
record under ``bundle.meta.trajectory``, and writes the additive
``commit_session_thread_v1`` twin with chronological ``message_versions``.

Contract locks honoured here:

* **N19 F8** — binding must occur **even when telemetry state is absent**;
  state-derived fields (draft, score card, trace/thread ids, edit provenance)
  are optional enrichment, never a precondition.
* **D1 / N19.5** — the whole hook is gated by :func:`profiles.capture_enabled`;
  when off, zero writes and ``hook_status="capture_disabled"``.
* **N2 / D4** — the exact final bytes are the scored artifact; text projection
  is derived, never the other way round.
* **D9 / N18** — the session id is always a minted/scoped-reuse ``sess_`` id;
  ``GenerationTelemetry.thread_id`` (``repo-…``) is correlation-only.
* **D12 / M7** — ``message_versions`` carries only versions with real evidence
  (generated draft, edit evidence, final accept) — never invented.
* **N19.6** — trajectory evidence lives under ``bundle.meta.trajectory``;
  Family H owns its policy. This module never scores.
* **Best-effort** — the hook never raises for product-accept reasons and never
  touches the network or Opik; failures are reported on the result.

No product-accept blocking. No Opik import. No network.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_cg.eval.binding.binder import BindInput, bind_final_accept
from git_cg.eval.binding.message_versions import build_message_versions
from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.binding.session_thread import write_session_twin
from git_cg.eval.binding.trajectory import build_trajectory_evidence

__all__ = [
    "AcceptBindResult",
    "bind_accept_path",
    "mint_accept_event_token",
]

#: Observed stage names recorded for a completed accept-path hook run. These
#: are a subset of the D3 declared vocabulary; the hook only observes the
#: accept-path finalization slice (generation stages are product-side and are
#: not re-declared here). ``accept_path_finalization`` is always observed when
#: the hook runs. Do **not** infer ``opik_export`` from telemetry-state presence:
#: export runs later on the product path and may be skipped or fail (N19 F7).
_ACCEPT_OBSERVED_STAGES: tuple[str, ...] = ("accept_path_finalization",)


def mint_accept_event_token(git_dir: str, final_bytes: bytes) -> str:
    """Derive a deterministic accept-event token for scoped reuse (N19.2/N20.1).

    The token is stable for a given ``(git_dir, final_bytes)`` accept episode so
    that a re-invoked hook for the *same* accept event reuses identity, while a
    new accept event (different bytes) yields a new session. It is **not** a
    secret and carries no content beyond the already-recorded final bytes hash.
    """
    digest = hashlib.sha256(final_bytes).hexdigest()
    return f"accept:{git_dir}:{digest}"


@dataclass(frozen=True, slots=True)
class AcceptBindResult:
    """Outcome of an accept-path bind attempt. Never raises for product reasons."""

    attempted: bool
    bound: bool = False
    hook_status: str = "not_attempted"
    session_thread_id: str | None = None
    paths_written: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def bind_accept_path(
    *,
    final_bytes: bytes,
    git_dir: str,
    repo_root: Path | None = None,
    telemetry_state: Any | None = None,
    edit_provenance: str | None = None,
    write: bool = True,
) -> AcceptBindResult:
    """Bind the accepted final bytes + emit trajectory/session twin (Slice 3).

    Parameters:
        final_bytes: Exact ``COMMIT_EDITMSG`` bytes (authoritative).
        git_dir: Resolved git dir (used for the accept-event token).
        repo_root: Optional repo root override (tests); resolved when omitted.
        telemetry_state: Optional ``GenerationTelemetry`` (or mapping) — when
            present, supplies the redacted draft, score card, and correlation
            ids. Absent state must not prevent binding (N19 F8).
        edit_provenance: Optional product ``classify_edit`` value.
        write: When ``False``, build + validate only (no filesystem I/O).

    Returns:
        :class:`AcceptBindResult` with bind status, written paths, and errors.

    Never raises for product-accept reasons.
    """
    if not capture_enabled():
        return AcceptBindResult(attempted=False, hook_status="capture_disabled")

    if not final_bytes:
        return AcceptBindResult(attempted=False, hook_status="final_message_absent")

    # --- Extract optional state-derived enrichment (never a precondition). ---
    generated_message: str | None = None
    score_card: dict[str, Any] | None = None
    trace_id: str | None = None
    thread_id: str | None = None
    if telemetry_state is not None:
        generated_message = getattr(telemetry_state, "generated_message", None) or None
        raw_card = getattr(telemetry_state, "score_card", None)
        if isinstance(raw_card, dict) and raw_card:
            score_card = dict(raw_card)
        trace_id = getattr(telemetry_state, "trace_id", None) or None
        thread_id = getattr(telemetry_state, "thread_id", None) or None

    token = mint_accept_event_token(git_dir, final_bytes)

    # --- Trajectory evidence (D3/D10) under bundle.meta.trajectory. ---
    observed = list(_ACCEPT_OBSERVED_STAGES)
    # Token format is accept:{git_dir}:{digest}; derive id from the digest only
    # so per-event ids stay distinct and local filesystem paths are not persisted.
    traj_id = f"traj_{token.rpartition(':')[2][:32]}"
    try:
        trajectory = build_trajectory_evidence(
            traj_id,
            observed,
        )
    except Exception as exc:
        trajectory = None
        traj_error: str | None = f"trajectory_build_error: {exc}"
    else:
        traj_error = None

    meta: dict[str, Any] = {}
    if trajectory is not None:
        meta["trajectory"] = trajectory

    # --- Bind the exact final bytes (D4). ---
    try:
        bind_result = bind_final_accept(
            BindInput(
                final_message=final_bytes,
                generated_message=generated_message,
                score_card=score_card,
                trace_id=trace_id,
                thread_id=thread_id,
                accept_event_token=token,
                edit_provenance=edit_provenance,
                meta=meta or None,
            ),
            repo_root=repo_root,
            write=write,
        )
    except Exception as exc:
        return AcceptBindResult(
            attempted=True,
            bound=False,
            hook_status="bind_error",
            errors=(f"bind_error: {exc}",),
        )

    errors: list[str] = list(bind_result.errors)
    if traj_error is not None:
        errors.append(traj_error)

    if not bind_result.bound or bind_result.bundle is None:
        return AcceptBindResult(
            attempted=True,
            bound=False,
            hook_status=bind_result.unbound_reason or "unbound",
            paths_written=bind_result.paths_written,
            errors=tuple(errors),
        )

    session_id = bind_result.bundle.get("session_thread_id")
    session_id = session_id if isinstance(session_id, str) else None

    # --- Additive session twin with chronological message_versions (D12/M7). ---
    paths_written: list[str] = list(bind_result.paths_written)
    if session_id:
        final_text = bind_result.bundle.get("final_message")
        final_text = final_text if isinstance(final_text, str) else None
        try:
            versions = build_message_versions(
                generated_message=generated_message,
                final_message=final_text,
                edited=(edit_provenance not in (None, "ai_accepted", "ai_accepted_refs_only")),
            )
        except Exception as exc:
            versions = []
            errors.append(f"message_versions_error: {exc}")

        twin_result = write_session_twin(
            session_id,
            lifecycle="closed",
            repo_root=repo_root,
            write=write,
            attempt_ids=[trace_id] if trace_id else None,
            message_versions=versions,
            trace_id=trace_id,
            generation_thread_id=thread_id,
        )
        if twin_result.written and twin_result.path_written:
            paths_written.append(twin_result.path_written)
        if twin_result.errors:
            errors.extend(twin_result.errors)

    return AcceptBindResult(
        attempted=True,
        bound=True,
        hook_status="bound",
        session_thread_id=session_id,
        paths_written=tuple(paths_written),
        errors=tuple(errors),
    )
