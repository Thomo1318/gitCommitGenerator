"""S3 Slice 0 — accept-path binder core (Issue #231, S3-contract-v1.4).

Covers the binding contract surface:

* final-bytes binding delegates hashing to the product authority
  (``git_cg.telemetry.compute_diff_hash``) — no eval-only hash fork;
* provenance delegates to product ``classify_edit`` and returns the product
  ``Provenance`` closed enum — no local string re-derivation;
* trajectory evidence covers exactly the five hook stages with precise,
  non-decreasing monotonic capture timing;
* local session-thread idempotency: pure function, identical inputs bind
  identically;
* fail-closed on empty/blank required fields, unknown/duplicate/missing
  stages, and non-monotonic capture timing.
"""

from __future__ import annotations

import pytest

from git_cg.eval.binding import (
    STAGE_ORDER,
    AcceptPathBindingError,
    AcceptPathBindingV1,
    BindingStatus,
    HookStage,
    StageCaptureV1,
    bind_accept_path,
    binder as binder_mod,
    project_trajectory_evidence,
)
from git_cg.telemetry import Provenance, classify_edit, compute_diff_hash

GENERATED = (
    "✨ feat(eval): add accept-path binder\n\n"
    "Body line.\n\n"
    "Refs: #231\n"
    "SemVer-Impact: MINOR\n"
    "Change-Types: feat\n"
    "Changelog-Groups: Added\n"
)
FINAL_ACCEPTED = GENERATED
FINAL_REFS_ONLY = GENERATED.replace("Refs: #231", "Refs: #231\nCloses: #217")
FINAL_MINOR_EDIT = GENERATED.replace("add accept-path binder", "add accept path binder")
FINAL_REWRITE = "🔧 chore(eval): completely different subject\n\nDifferent body.\n"

TRACE = "trace-abc123"
SESSION = "session-local-01"
THREAD = "thread-local-01"


def _captures(*, mono_base: int = 1_000_000) -> list[StageCaptureV1]:
    """Five ordered stage captures with increasing monotonic timing."""
    return [
        StageCaptureV1(stage=stage, t_mono_ns=mono_base + i * 1_000, t_wall_utc="2026-08-16T00:00:00+00:00")
        for i, stage in enumerate(STAGE_ORDER)
    ]


# ---------------------------------------------------------------------------
# Product-authority wrapping (no eval-only forks)
# ---------------------------------------------------------------------------


def test_binder_wraps_product_hash_and_provenance_authorities() -> None:
    """Binder must reference product functions/enums — not local forks."""
    assert binder_mod.compute_diff_hash is compute_diff_hash
    assert binder_mod.classify_edit is classify_edit
    assert binder_mod.Provenance is Provenance


def test_binding_hashes_match_product_authority() -> None:
    b = bind_accept_path(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    assert b.final_bytes_sha256 == compute_diff_hash(FINAL_ACCEPTED)
    assert b.generated_sha256 == compute_diff_hash(GENERATED)
    assert b.binding_id == compute_diff_hash(f"{TRACE}|{SESSION}|{THREAD}|{compute_diff_hash(FINAL_ACCEPTED)}")


def test_provenance_is_product_enum_not_string() -> None:
    b = bind_accept_path(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    assert isinstance(b.provenance, Provenance)
    assert b.provenance is Provenance.AI_ACCEPTED
    assert b.provenance == classify_edit(GENERATED, FINAL_ACCEPTED)


@pytest.mark.parametrize(
    ("final", "expected"),
    [
        (FINAL_ACCEPTED, Provenance.AI_ACCEPTED),
        (FINAL_REFS_ONLY, Provenance.AI_ACCEPTED_REFS_ONLY),
        (FINAL_MINOR_EDIT, Provenance.AI_EDITED_MINOR),
        (FINAL_REWRITE, Provenance.AI_EDITED_SUBSTANTIVE),
    ],
)
def test_provenance_matches_product_classification(final: str, expected: Provenance) -> None:
    b = bind_accept_path(
        final_bytes=final,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    assert b.provenance is expected
    assert b.provenance is classify_edit(GENERATED, final)


# ---------------------------------------------------------------------------
# Binding record shape and serialisation
# ---------------------------------------------------------------------------


def test_binding_record_is_frozen_and_serialisable() -> None:
    b = bind_accept_path(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
        stage_captures=_captures(),
    )
    assert isinstance(b, AcceptPathBindingV1)
    assert b.status is BindingStatus.BOUND
    assert b.stage_count == 5
    assert b.trajectory_sha256 is not None
    d = b.to_dict()
    assert d["provenance"] == "ai_accepted"
    assert d["status"] == "bound"
    assert d["trace_id"] == TRACE
    assert d["session_id"] == SESSION
    assert d["thread_id"] == THREAD
    with pytest.raises(AttributeError):
        b.status = BindingStatus.UNBOUND  # type: ignore[misc]


def test_binding_without_trajectory_has_no_trajectory_hash() -> None:
    b = bind_accept_path(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    assert b.stage_count == 0
    assert b.trajectory_sha256 is None


# ---------------------------------------------------------------------------
# Local session-thread idempotency (pure / deterministic)
# ---------------------------------------------------------------------------


def test_binding_is_idempotent_for_identical_inputs() -> None:
    kwargs = dict(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
        stage_captures=_captures(),
    )
    first = bind_accept_path(**kwargs)
    second = bind_accept_path(**kwargs)
    assert first == second
    assert first.binding_id == second.binding_id
    assert first.trajectory_sha256 == second.trajectory_sha256


def test_binding_id_changes_with_lineage_or_bytes() -> None:
    base = bind_accept_path(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    other_thread = bind_accept_path(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id="thread-local-02",
    )
    other_bytes = bind_accept_path(
        final_bytes=FINAL_MINOR_EDIT,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    assert base.binding_id != other_thread.binding_id
    assert base.binding_id != other_bytes.binding_id


# ---------------------------------------------------------------------------
# Trajectory evidence: stage coverage and precise capture timing
# ---------------------------------------------------------------------------


def test_trajectory_orders_all_five_stages() -> None:
    caps = _captures()
    # Supply out of order; projection must restore canonical stage order.
    shuffled = [caps[2], caps[0], caps[4], caps[1], caps[3]]
    ordered = project_trajectory_evidence(shuffled)
    assert [c.stage for c in ordered] == list(STAGE_ORDER)


def test_trajectory_capture_to_dict_serialises_stage_value() -> None:
    cap = _captures()[0]
    d = cap.to_dict()
    assert d["stage"] == "prepare"
    assert d["t_mono_ns"] == cap.t_mono_ns
    assert d["t_wall_utc"] == cap.t_wall_utc
    assert d["detail"] == {}


def test_trajectory_accepts_mapping_captures() -> None:
    caps = [
        {"stage": stage.value, "t_mono_ns": 1_000_000 + i * 1_000, "t_wall_utc": "2026-08-16T00:00:00+00:00"}
        for i, stage in enumerate(STAGE_ORDER)
    ]
    ordered = project_trajectory_evidence(caps)
    assert [c.stage for c in ordered] == list(STAGE_ORDER)
    assert all(isinstance(c, StageCaptureV1) for c in ordered)


def test_trajectory_missing_stage_fails_closed() -> None:
    caps = _captures()[:4]  # drop finalize
    with pytest.raises(AcceptPathBindingError, match="missing hook stage"):
        project_trajectory_evidence(caps)


def test_trajectory_duplicate_stage_fails_closed() -> None:
    caps = _captures()
    caps.append(StageCaptureV1(stage=HookStage.EDIT, t_mono_ns=9_999_999, t_wall_utc="2026-08-16T00:00:01+00:00"))
    with pytest.raises(AcceptPathBindingError, match="duplicate hook stage"):
        project_trajectory_evidence(caps)


def test_trajectory_unknown_stage_fails_closed() -> None:
    caps = _captures()
    caps[0] = {"stage": "not_a_stage", "t_mono_ns": 1, "t_wall_utc": "2026-08-16T00:00:00+00:00"}
    with pytest.raises(AcceptPathBindingError, match="unknown stage"):
        project_trajectory_evidence(caps)


def test_trajectory_non_monotonic_timing_fails_closed() -> None:
    caps = _captures()
    caps[3] = StageCaptureV1(stage=HookStage.VALIDATE, t_mono_ns=1, t_wall_utc="2026-08-16T00:00:00+00:00")
    with pytest.raises(AcceptPathBindingError, match="non-monotonic"):
        project_trajectory_evidence(caps)


def test_trajectory_empty_fails_closed() -> None:
    with pytest.raises(AcceptPathBindingError, match="no stage captures"):
        project_trajectory_evidence([])


def test_trajectory_rejects_negative_or_bool_mono_ns() -> None:
    caps = _captures()
    caps[0] = {"stage": "prepare", "t_mono_ns": -5, "t_wall_utc": "2026-08-16T00:00:00+00:00"}
    with pytest.raises(AcceptPathBindingError, match="t_mono_ns"):
        project_trajectory_evidence(caps)
    caps2 = _captures()
    caps2[0] = {"stage": "prepare", "t_mono_ns": True, "t_wall_utc": "2026-08-16T00:00:00+00:00"}
    with pytest.raises(AcceptPathBindingError, match="t_mono_ns"):
        project_trajectory_evidence(caps2)


def test_trajectory_rejects_non_mapping_non_capture() -> None:
    with pytest.raises(AcceptPathBindingError, match="must be StageCaptureV1 or a mapping"):
        project_trajectory_evidence(["prepare"])


def test_trajectory_rejects_non_mapping_detail() -> None:
    caps = _captures()
    caps[0] = {
        "stage": "prepare",
        "t_mono_ns": 1,
        "t_wall_utc": "2026-08-16T00:00:00+00:00",
        "detail": ["not", "a", "mapping"],
    }
    with pytest.raises(AcceptPathBindingError, match="detail must be a mapping"):
        project_trajectory_evidence(caps)


def test_trajectory_rejects_blank_wall_clock() -> None:
    caps = _captures()
    caps[0] = {"stage": "prepare", "t_mono_ns": 1, "t_wall_utc": "   "}
    with pytest.raises(AcceptPathBindingError, match="t_wall_utc"):
        project_trajectory_evidence(caps)


def test_utc_now_iso_returns_utc_iso8601() -> None:
    from git_cg.eval.binding.binder import utc_now_iso

    stamp = utc_now_iso()
    assert isinstance(stamp, str)
    assert stamp.endswith("+00:00")


# ---------------------------------------------------------------------------
# Fail-closed required-field validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["final_bytes", "generated_message", "trace_id", "session_id", "thread_id"],
)
def test_bind_fails_closed_on_blank_required_fields(field: str) -> None:
    kwargs = dict(
        final_bytes=FINAL_ACCEPTED,
        generated_message=GENERATED,
        trace_id=TRACE,
        session_id=SESSION,
        thread_id=THREAD,
    )
    kwargs[field] = "   "
    with pytest.raises(AcceptPathBindingError, match=field):
        bind_accept_path(**kwargs)


def test_bind_fails_closed_on_invalid_trajectory() -> None:
    with pytest.raises(AcceptPathBindingError, match="missing hook stage"):
        bind_accept_path(
            final_bytes=FINAL_ACCEPTED,
            generated_message=GENERATED,
            trace_id=TRACE,
            session_id=SESSION,
            thread_id=THREAD,
            stage_captures=_captures()[:3],
        )
