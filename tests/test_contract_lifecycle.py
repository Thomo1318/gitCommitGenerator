"""Slice 5.5 (#204): contract lifecycle observability + normaliser governance."""

from __future__ import annotations

from unittest.mock import patch

from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
from git_cg.regeneration import (
    ContractLifecycleSnapshot,
    ResolvedCommitContract,
    evaluate_contract_lifecycle,
    lift_plan_to_contract_semver,
)
from git_cg.telemetry import (
    GenerationTelemetry,
    PlanNormaliserReason,
    coerce_closed_semver,
    coerce_plan_normaliser_reason,
    contract_consistent_feedback_score,
    get_state_file_path,
    read_telemetry_state,
    write_telemetry_state,
)


def _plan(*, semver: SemVerImpact) -> CommitPlan:
    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="main",
            description="add something",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="Feature.",
        body_summary="Did a feature.",
    )
    plan.primary_intent.semver_impact = semver
    return plan


def _contract(*, semver: str = "MINOR") -> ResolvedCommitContract:
    return ResolvedCommitContract(
        primary_intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        semver_impact=semver,
        changelog_group="Added",
        secondary_intent_ids=[],
        lock_resolution="accepted",
    )


def _minimal_telemetry(**overrides) -> GenerationTelemetry:
    defaults = dict(
        trace_id=None,
        diff_hash="abc123",
        diff_output="diff --git a/x.py b/x.py\n+new",
        repo_name="my-repo",
        engine="mtplx",
        model_name="gemma-3-4b",
        system_prompt_hash="deadbeef",
        generated_message="feat: add feature",
        commit_plan_json={"primary_intent": {}},
        score_card={"header_length_ok": True},
    )
    defaults.update(overrides)
    return GenerationTelemetry(**defaults)


# ---------------------------------------------------------------------------
# Coercion / score boundary
# ---------------------------------------------------------------------------


def test_coerce_closed_semver_accepts_vocab_and_drops_free_text():
    assert coerce_closed_semver("minor") == "MINOR"
    assert coerce_closed_semver(SemVerImpact.PATCH) == "PATCH"
    assert coerce_closed_semver(None) is None
    assert coerce_closed_semver("") is None
    assert coerce_closed_semver("not-a-semver") is None
    assert coerce_closed_semver("MAJOR!") is None


def test_coerce_plan_normaliser_reason_closed_vocab():
    assert coerce_plan_normaliser_reason("CONTRACT_LIFT") == "contract_lift"
    assert coerce_plan_normaliser_reason(PlanNormaliserReason.RESIDUAL_VIOLATION) == "residual_violation"
    assert coerce_plan_normaliser_reason("free text") == "none"
    assert coerce_plan_normaliser_reason(None) == "none"


def test_contract_consistent_feedback_score_boundary():
    assert contract_consistent_feedback_score(False) == 1.0
    assert contract_consistent_feedback_score(True) == 0.0


def test_generation_telemetry_defaults_lifecycle_fields():
    tel = _minimal_telemetry()
    assert tel.contract_locked_semver is None
    assert tel.llm_raw_semver is None
    assert tel.plan_persisted_semver is None
    assert tel.contract_violation is False
    assert tel.plan_normaliser_applied is False
    assert tel.plan_normaliser_reason == "none"
    assert tel.contract_lift_applied is False
    assert tel.contract_lift_from_semver is None


# ---------------------------------------------------------------------------
# evaluate_contract_lifecycle
# ---------------------------------------------------------------------------


def test_lifecycle_aligned_no_normaliser():
    snap = evaluate_contract_lifecycle(
        locked_semver="MINOR",
        llm_raw_semver="MINOR",
        persisted_semver="MINOR",
        lift_applied=False,
    )
    assert isinstance(snap, ContractLifecycleSnapshot)
    assert snap.contract_violation is False
    assert snap.contract_consistent is True
    assert snap.plan_normaliser_applied is False
    assert snap.plan_normaliser_reason == "none"
    assert snap.contract_locked_semver == "MINOR"
    assert snap.llm_raw_semver == "MINOR"
    assert snap.plan_persisted_semver == "MINOR"


def test_lifecycle_lift_repairs_demotion_no_violation():
    """Incident class: locked MINOR, presentation demoted to NONE, lift repairs."""
    snap = evaluate_contract_lifecycle(
        locked_semver="MINOR",
        llm_raw_semver="MINOR",
        persisted_semver="MINOR",
        lift_applied=True,
        lift_from_semver="NONE",
        presentation_touched=True,
    )
    assert snap.contract_violation is False
    assert snap.contract_consistent is True
    assert snap.plan_normaliser_applied is True
    assert snap.plan_normaliser_reason == "contract_lift"
    assert snap.contract_lift_from_semver == "NONE"


def test_lifecycle_residual_violation_when_persisted_below_floor():
    """If lift fails or residual demotion remains, mark violation."""
    snap = evaluate_contract_lifecycle(
        locked_semver="MINOR",
        llm_raw_semver="MINOR",
        persisted_semver="NONE",
        lift_applied=False,
        presentation_touched=True,
    )
    assert snap.contract_violation is True
    assert snap.contract_consistent is False
    assert snap.plan_normaliser_reason == "residual_violation"
    assert snap.plan_normaliser_applied is True


def test_lifecycle_incident_locked_minor_cannot_persist_none_after_lift_path():
    """Characterisation: after successful lift, persisted must not stay NONE."""
    plan = _plan(semver=SemVerImpact.NONE)
    contract = _contract(semver="MINOR")
    out, applied, from_sem = lift_plan_to_contract_semver(plan, contract)
    assert applied is True
    assert from_sem == "NONE"
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR

    snap = evaluate_contract_lifecycle(
        locked_semver=contract.semver_impact,
        llm_raw_semver="MINOR",
        persisted_semver=out.primary_intent.semver_impact,
        lift_applied=applied,
        lift_from_semver=from_sem,
        presentation_touched=True,
    )
    assert snap.plan_persisted_semver == "MINOR"
    assert snap.contract_violation is False
    assert snap.contract_consistent is True
    assert contract_consistent_feedback_score(snap.contract_violation) == 1.0


def test_lifecycle_presentation_clamp_without_demotion_below_floor():
    snap = evaluate_contract_lifecycle(
        locked_semver="NONE",
        llm_raw_semver="PATCH",
        persisted_semver="NONE",
        lift_applied=False,
        presentation_touched=True,
    )
    # persisted == locked floor; presentation changed raw→persisted but not a violation
    assert snap.contract_violation is False
    assert snap.plan_normaliser_reason == "presentation_clamp"
    assert snap.plan_normaliser_applied is True


def test_lifecycle_malformed_semver_reason():
    snap = evaluate_contract_lifecycle(
        locked_semver="NOT_REAL",
        llm_raw_semver="MINOR",
        persisted_semver="MINOR",
        lift_applied=False,
    )
    assert snap.contract_locked_semver is None
    assert snap.plan_normaliser_reason == "malformed_semver"
    # Cannot compare ranks → not a hard violation
    assert snap.contract_violation is False


# ---------------------------------------------------------------------------
# Telemetry round-trip / legacy defaults
# ---------------------------------------------------------------------------


def test_write_then_read_preserves_lifecycle_fields(tmp_path, monkeypatch):
    import git_cg.telemetry as telemetry_mod

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = _minimal_telemetry(
        contract_locked_semver="MINOR",
        llm_raw_semver="MINOR",
        plan_persisted_semver="MINOR",
        contract_lift_applied=True,
        contract_lift_from_semver="NONE",
        contract_violation=False,
        plan_normaliser_applied=True,
        plan_normaliser_reason="contract_lift",
    )
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.contract_locked_semver == "MINOR"
    assert result.llm_raw_semver == "MINOR"
    assert result.plan_persisted_semver == "MINOR"
    assert result.contract_lift_applied is True
    assert result.contract_lift_from_semver == "NONE"
    assert result.contract_violation is False
    assert result.plan_normaliser_applied is True
    assert result.plan_normaliser_reason == "contract_lift"


def test_write_coerces_unknown_lifecycle_vocab(tmp_path, monkeypatch):
    import git_cg.telemetry as telemetry_mod

    monkeypatch.setattr(telemetry_mod, "redact_payload", lambda payload: payload)

    tel = _minimal_telemetry(
        contract_locked_semver="minor-ish",
        llm_raw_semver="PATCH",
        plan_persisted_semver="wat",
        plan_normaliser_reason="something_else",
        contract_violation=1,  # truthy non-bool
    )
    write_telemetry_state(str(tmp_path), tel)
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.contract_locked_semver is None
    assert result.llm_raw_semver == "PATCH"
    assert result.plan_persisted_semver is None
    assert result.plan_normaliser_reason == "none"
    assert result.contract_violation is True


def test_read_telemetry_state_defaults_lifecycle_for_legacy(tmp_path):
    import json

    state_path = get_state_file_path(str(tmp_path))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trace_id": None,
        "diff_hash": "abc",
        "diff_output": "diff",
        "repo_name": "r",
        "engine": "mtplx",
        "model_name": "m",
        "system_prompt_hash": "h",
        "generated_message": "msg",
        "commit_plan_json": {},
        "score_card": {},
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    result = read_telemetry_state(str(tmp_path))
    assert result is not None
    assert result.contract_locked_semver is None
    assert result.llm_raw_semver is None
    assert result.plan_persisted_semver is None
    assert result.contract_violation is False
    assert result.plan_normaliser_applied is False
    assert result.plan_normaliser_reason == "none"


# ---------------------------------------------------------------------------
# Sentry companion event
# ---------------------------------------------------------------------------


def test_report_commit_plan_contract_violation_closed_tags_only():
    from git_cg.sentry_config import report_commit_plan_contract_violation

    captured = {}

    class FakeScope:
        def __init__(self):
            self.tags = {}
            self.fingerprint = None

        def set_tag(self, k, v):
            self.tags[k] = v

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_scope = FakeScope()

    def fake_capture_message(msg, level="error"):
        captured["message"] = msg
        captured["level"] = level
        captured["tags"] = dict(fake_scope.tags)
        captured["fingerprint"] = list(fake_scope.fingerprint or [])

    with (
        patch("sentry_sdk.new_scope", return_value=fake_scope),
        patch("sentry_sdk.capture_message", side_effect=fake_capture_message),
    ):
        report_commit_plan_contract_violation(
            locked_semver="MINOR",
            persisted_semver="NONE",
            lift_applied=False,
            lift_from_semver=None,
            normaliser_reason="residual_violation",
            diff_hash="deadbeefcafebabe",
        )

    assert captured["message"] == "commit_plan_contract_violation"
    assert captured["level"] == "error"
    assert captured["fingerprint"][0] == "commit_plan_contract_violation"
    tags = captured["tags"]
    assert tags["event_name"] == "commit_plan_contract_violation"
    assert tags["contract_locked_semver"] == "MINOR"
    assert tags["plan_persisted_semver"] == "NONE"
    assert tags["contract_lift_applied"] == "false"
    assert tags["plan_normaliser_reason"] == "residual_violation"
    assert tags["diff_hash"] == "deadbeefcafebabe"
    # No free-text / body / prompt keys
    forbidden = {"prompt", "diff_output", "body", "commit_plan", "message_body", "system_prompt"}
    assert forbidden.isdisjoint(tags.keys())


def test_report_strips_non_hash_diff_and_unknown_reason():
    from git_cg.sentry_config import report_commit_plan_contract_violation

    captured = {}

    class FakeScope:
        def __init__(self):
            self.tags = {}
            self.fingerprint = None

        def set_tag(self, k, v):
            self.tags[k] = v

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_scope = FakeScope()

    def fake_capture_message(msg, level="error"):
        captured["tags"] = dict(fake_scope.tags)

    with (
        patch("sentry_sdk.new_scope", return_value=fake_scope),
        patch("sentry_sdk.capture_message", side_effect=fake_capture_message),
    ):
        report_commit_plan_contract_violation(
            locked_semver="not-real",
            persisted_semver="also-bad",
            normaliser_reason="please demote this feat",
            diff_hash="NOT A HASH!!",
        )

    tags = captured["tags"]
    assert tags["contract_locked_semver"] == "unknown"
    assert tags["plan_persisted_semver"] == "unknown"
    assert tags["plan_normaliser_reason"] == "none"
    assert tags["diff_hash"] == "none"


# ---------------------------------------------------------------------------
# Residual lift still wins
# ---------------------------------------------------------------------------


def test_normaliser_cannot_leave_locked_minor_as_none():
    """Unit: lift is the hard floor — locked MINOR never persists as NONE."""
    plan = _plan(semver=SemVerImpact.NONE)
    contract = _contract(semver="MINOR")
    # Simulate a second residual clamp after first lift (should still repair).
    out, applied, _ = lift_plan_to_contract_semver(plan, contract)
    assert applied and out.primary_intent.semver_impact == SemVerImpact.MINOR
    out.primary_intent.semver_impact = SemVerImpact.NONE
    out2, applied2, from2 = lift_plan_to_contract_semver(out, contract)
    assert applied2 is True
    assert from2 == "NONE"
    assert out2.primary_intent.semver_impact == SemVerImpact.MINOR
