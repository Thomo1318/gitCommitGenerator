"""S3 accept-path final-bytes binding and trajectory evidence (Issue #231).

S3-contract-v1.4 / N1-N20 authority. This module is the Lane A local source of
truth for:

* binding the accept-path final bytes (``COMMIT_EDITMSG`` content) to the
  generation lineage (``trace_id`` / ``session_id`` / ``thread_id``) before any
  Opik write — the binding is computed locally and is network-free;
* projecting per-stage trajectory evidence for the five hook stages
  (``prepare`` → ``generate`` → ``edit`` → ``validate`` → ``finalize``) with
  precise capture timing (monotonic nanoseconds plus a UTC wall clock).

Policy wrapping (no eval-only forks):

* final-bytes hashing delegates to the product authority
  :func:`git_cg.telemetry.compute_diff_hash` (SHA-256, truncated to 16 hex
  chars) so eval and product hashing can never drift;
* provenance classification delegates to the product authority
  :func:`git_cg.telemetry.classify_edit`, returning the product
  :class:`git_cg.telemetry.Provenance` closed enum — never a local string
  re-derivation.

Fail-closed rules (per contract):

* ``final_bytes`` must be non-empty after ``strip()``;
* ``generated_message`` must be non-empty after ``strip()`` (the lineage anchor
  for edit classification);
* stage captures must cover exactly the five ordered stages with
  non-decreasing ``t_mono_ns`` (precise hook-stage capture timing);
* idempotency: :func:`bind_accept_path` is pure — identical inputs produce an
  identical :class:`AcceptPathBindingV1` (no clocks, no randomness), so a local
  session-thread replay binds deterministically.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import pairwise

from git_cg.telemetry import Provenance, classify_edit, compute_diff_hash

__all__ = [
    "STAGE_ORDER",
    "AcceptPathBindingError",
    "AcceptPathBindingV1",
    "BindingStatus",
    "HookStage",
    "StageCaptureV1",
    "bind_accept_path",
    "project_trajectory_evidence",
    "utc_now_iso",
]


class AcceptPathBindingError(ValueError):
    """Accept-path binding / trajectory evidence failure (fail-closed)."""


class HookStage(enum.StrEnum):
    """The five accept-path hook stages, in capture order (closed vocabulary)."""

    PREPARE = "prepare"
    GENERATE = "generate"
    EDIT = "edit"
    VALIDATE = "validate"
    FINALIZE = "finalize"


#: Canonical ordered tuple of the five hook stages.
STAGE_ORDER: tuple[HookStage, ...] = (
    HookStage.PREPARE,
    HookStage.GENERATE,
    HookStage.EDIT,
    HookStage.VALIDATE,
    HookStage.FINALIZE,
)


class BindingStatus(enum.StrEnum):
    """Closed binding-outcome vocabulary (never free text)."""

    BOUND = "bound"
    UNBOUND = "unbound"


@dataclass(frozen=True)
class StageCaptureV1:
    """One hook-stage capture with precise timing.

    Attributes:
        stage: The hook stage (closed :class:`HookStage` vocabulary).
        t_mono_ns: Monotonic clock reading in nanoseconds at capture time
            (e.g. ``time.monotonic_ns()``); used for ordering and durations.
        t_wall_utc: UTC wall-clock reading at capture time, ISO-8601 formatted
            (e.g. from ``datetime.now(UTC)``); evidence only, never ordering.
        detail: Optional non-content metadata (e.g. ``{"editor": "vim"}``).
            Must never carry secrets, raw diffs, or message bodies.
    """

    stage: HookStage
    t_mono_ns: int
    t_wall_utc: str
    detail: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable projection (stage rendered as its value)."""
        out = asdict(self)
        out["stage"] = str(self.stage)
        return out


@dataclass(frozen=True)
class AcceptPathBindingV1:
    """Local accept-path binding record (pre-Opik-write).

    Attributes:
        binding_id: Deterministic binding identifier —
            ``compute_diff_hash(f"{trace_id}|{session_id}|{thread_id}|{final_bytes_sha256}")``.
        final_bytes_sha256: Product-authority hash of the exact final bytes
            (``compute_diff_hash``; SHA-256 truncated to 16 hex chars).
        generated_sha256: Product-authority hash of the generated message the
            accept path started from (edit-classification anchor).
        provenance: Product :class:`git_cg.telemetry.Provenance` from
            :func:`git_cg.telemetry.classify_edit` — never a local string.
        status: Closed :class:`BindingStatus` outcome.
        trace_id: Generation trace identifier (lineage).
        session_id: Local session identifier (lineage).
        thread_id: Local thread identifier (lineage).
        stage_count: Number of stage captures projected into this binding.
        trajectory_sha256: Product-authority hash over the ordered stage
            captures, or ``None`` when no trajectory was supplied.
    """

    binding_id: str
    final_bytes_sha256: str
    generated_sha256: str
    provenance: Provenance
    status: BindingStatus
    trace_id: str
    session_id: str
    thread_id: str
    stage_count: int
    trajectory_sha256: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable projection (enums rendered as values)."""
        out = asdict(self)
        out["provenance"] = str(self.provenance)
        out["status"] = str(self.status)
        return out


def _require_non_empty(value: object, field_name: str) -> str:
    """Return ``value`` when it is a non-blank string, else fail closed."""
    if not isinstance(value, str) or not value.strip():
        raise AcceptPathBindingError(f"missing or empty required field: {field_name}")
    return value


def _coerce_stage_capture(raw: object, index: int) -> StageCaptureV1:
    """Validate and normalise one stage capture (fail-closed)."""
    if isinstance(raw, StageCaptureV1):
        capture = raw
    elif isinstance(raw, Mapping):
        stage_raw = raw.get("stage")
        try:
            stage = stage_raw if isinstance(stage_raw, HookStage) else HookStage(str(stage_raw))
        except (ValueError, TypeError) as exc:
            raise AcceptPathBindingError(f"stage capture {index}: unknown stage {stage_raw!r}") from exc
        t_mono_ns = raw.get("t_mono_ns")
        if isinstance(t_mono_ns, bool) or not isinstance(t_mono_ns, int) or t_mono_ns < 0:
            raise AcceptPathBindingError(f"stage capture {index}: t_mono_ns must be a non-negative int")
        t_wall_utc = _require_non_empty(raw.get("t_wall_utc"), f"stage[{index}].t_wall_utc")
        detail = raw.get("detail") or {}
        if not isinstance(detail, Mapping):
            raise AcceptPathBindingError(f"stage capture {index}: detail must be a mapping")
        capture = StageCaptureV1(
            stage=stage,
            t_mono_ns=t_mono_ns,
            t_wall_utc=t_wall_utc,
            detail=dict(detail),
        )
    else:
        raise AcceptPathBindingError(
            f"stage capture {index}: must be StageCaptureV1 or a mapping, got {type(raw).__name__}"
        )

    if isinstance(capture.t_mono_ns, bool) or not isinstance(capture.t_mono_ns, int) or capture.t_mono_ns < 0:
        raise AcceptPathBindingError(f"stage capture {index}: t_mono_ns must be a non-negative int")
    _require_non_empty(capture.t_wall_utc, f"stage[{index}].t_wall_utc")
    if not isinstance(capture.detail, dict):
        raise AcceptPathBindingError(f"stage capture {index}: detail must be a mapping")
    return capture


def project_trajectory_evidence(captures: Sequence[object]) -> list[StageCaptureV1]:
    """Validate and order the five hook-stage captures (precise timing).

    Fail-closed rules:

    * exactly the five :data:`STAGE_ORDER` stages, each captured exactly once,
      in capture order;
    * ``t_mono_ns`` non-decreasing across the ordered captures.

    Returns the captures in canonical stage order.
    """
    normalised = [_coerce_stage_capture(c, i) for i, c in enumerate(captures)]
    if not normalised:
        raise AcceptPathBindingError("no stage captures supplied")

    stages = [c.stage for c in normalised]
    missing = [s for s in STAGE_ORDER if s not in stages]
    if missing:
        raise AcceptPathBindingError("missing hook stage captures: " + ",".join(str(s) for s in missing))
    seen: set[HookStage] = set()
    for s in stages:
        if s in seen:
            raise AcceptPathBindingError(f"duplicate hook stage capture: {s}")
        seen.add(s)

    ordered = sorted(normalised, key=lambda c: STAGE_ORDER.index(c.stage))
    for prev, cur in pairwise(ordered):
        if cur.t_mono_ns < prev.t_mono_ns:
            raise AcceptPathBindingError(
                f"non-monotonic capture timing: {cur.stage} t_mono_ns {cur.t_mono_ns} < {prev.stage} {prev.t_mono_ns}"
            )
    return ordered


def _trajectory_hash(ordered: Sequence[StageCaptureV1]) -> str:
    """Deterministic product-authority hash over ordered stage captures."""
    material = "|".join(f"{c.stage}:{c.t_mono_ns}:{c.t_wall_utc}" for c in ordered)
    return compute_diff_hash(material)


def bind_accept_path(
    *,
    final_bytes: str,
    generated_message: str,
    trace_id: str,
    session_id: str,
    thread_id: str,
    stage_captures: Sequence[object] | None = None,
) -> AcceptPathBindingV1:
    """Bind accept-path final bytes to generation lineage (pre-Opik, local-only).

    This function is pure and deterministic: identical inputs produce an
    identical binding (local session-thread idempotency). It performs no
    network, Opik, filesystem, or clock I/O.

    Parameters:
        final_bytes: Exact content of ``COMMIT_EDITMSG`` at accept time.
        generated_message: The generated message the accept path started from.
        trace_id: Generation trace identifier.
        session_id: Local session identifier.
        thread_id: Local thread identifier.
        stage_captures: Optional hook-stage captures; when supplied they are
            validated via :func:`project_trajectory_evidence`.

    Returns:
        A frozen :class:`AcceptPathBindingV1` record.

    Raises:
        AcceptPathBindingError: On any contract violation (fail-closed).
    """
    final = _require_non_empty(final_bytes, "final_bytes")
    generated = _require_non_empty(generated_message, "generated_message")
    trace = _require_non_empty(trace_id, "trace_id")
    session = _require_non_empty(session_id, "session_id")
    thread = _require_non_empty(thread_id, "thread_id")

    final_sha = compute_diff_hash(final)
    generated_sha = compute_diff_hash(generated)
    provenance = classify_edit(generated, final)

    ordered: list[StageCaptureV1] = []
    trajectory_sha: str | None = None
    if stage_captures is not None:
        ordered = project_trajectory_evidence(stage_captures)
        trajectory_sha = _trajectory_hash(ordered)

    binding_id = compute_diff_hash(f"{trace}|{session}|{thread}|{final_sha}")

    return AcceptPathBindingV1(
        binding_id=binding_id,
        final_bytes_sha256=final_sha,
        generated_sha256=generated_sha,
        provenance=provenance,
        status=BindingStatus.BOUND,
        trace_id=trace,
        session_id=session,
        thread_id=thread,
        stage_count=len(ordered),
        trajectory_sha256=trajectory_sha,
    )


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 (helper for capture call sites)."""
    return datetime.now(UTC).isoformat()
