"""Slice 5 hotfix (#204): post-presentation contract SemVer lift guard."""

from __future__ import annotations

import pytest

from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
from git_cg.regeneration import ResolvedCommitContract, lift_plan_to_contract_semver
from git_cg.telemetry import GenerationTelemetry, coerce_presentation_fallback_reason


def _plan(*, semver: SemVerImpact, cc_type: CommitType = CommitType.FEAT) -> CommitPlan:
    """Build a plan then force *semver* post-init.

    ``CommitIntent`` matrix validators rewrite SemVer from the SOP row for
    ``intent_id`` on construction. Presentation demotion happens *after*
    construction, so tests must mutate the field the same way overlay/seed do.
    """
    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=cc_type,
            scope="main",
            description="add something",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="Feature.",
        body_summary="Did a feature.",
    )
    # Simulate post-construction presentation demotion / clamp.
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


def test_contract_lift_repairs_overlay_demotion_none_to_minor():
    """Locked MINOR + plan NONE (overlay ceiling) → lift to MINOR."""
    plan = _plan(semver=SemVerImpact.NONE)
    assert plan.primary_intent.semver_impact == SemVerImpact.NONE  # demotion stuck
    contract = _contract(semver="MINOR")

    out, applied, from_semver = lift_plan_to_contract_semver(plan, contract)

    assert applied is True
    assert from_semver == "NONE"
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR
    # Identity fields untouched.
    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    assert out.primary_intent.cc_type == CommitType.FEAT
    assert out.primary_intent.changelog_group == "Added"


def test_contract_lift_repairs_seed_demotion_patch_to_minor():
    """Locked MINOR + plan PATCH (low-confidence generic seed) → lift to MINOR."""
    plan = _plan(semver=SemVerImpact.PATCH)
    assert plan.primary_intent.semver_impact == SemVerImpact.PATCH
    contract = _contract(semver="MINOR")

    out, applied, from_semver = lift_plan_to_contract_semver(plan, contract)

    assert applied is True
    assert from_semver == "PATCH"
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR


def test_contract_lift_noop_when_aligned():
    """Locked MINOR + plan already MINOR → no-op."""
    plan = _plan(semver=SemVerImpact.MINOR)
    contract = _contract(semver="MINOR")

    out, applied, from_semver = lift_plan_to_contract_semver(plan, contract)

    assert applied is False
    assert from_semver is None
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR


def test_contract_lift_never_lowers():
    """Locked PATCH + plan MINOR (higher rank) → never lower."""
    plan = _plan(semver=SemVerImpact.MINOR)
    contract = _contract(semver="PATCH")

    out, applied, from_semver = lift_plan_to_contract_semver(plan, contract)

    assert applied is False
    assert from_semver is None
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR


def test_contract_lift_survives_bad_contract_semver():
    """Malformed contract SemVer → no-op, never raises."""
    plan = _plan(semver=SemVerImpact.NONE)
    assert plan.primary_intent.semver_impact == SemVerImpact.NONE
    contract = _contract(semver="NOT_A_REAL_IMPACT")

    out, applied, from_semver = lift_plan_to_contract_semver(plan, contract)

    assert applied is False
    assert from_semver is None
    assert out.primary_intent.semver_impact == SemVerImpact.NONE


def test_generation_telemetry_defaults_contract_lift_fields():
    """GenerationTelemetry carries Slice 5 lift breadcrumbs with safe defaults."""
    tel = GenerationTelemetry(
        trace_id=None,
        diff_hash="abc",
        diff_output="",
        repo_name="repo",
        engine="local",
        model_name="m",
        system_prompt_hash="h",
        generated_message="",
        commit_plan_json={},
        score_card={},
    )
    assert tel.contract_lift_applied is False
    assert tel.contract_lift_from_semver is None
    # Existing closed-vocab helper still works.
    assert coerce_presentation_fallback_reason("low_confidence") == "low_confidence"


@pytest.mark.parametrize(
    ("plan_semver", "contract_semver", "expect_applied", "expect_from"),
    [
        (SemVerImpact.NONE, "PATCH", True, "NONE"),
        (SemVerImpact.PATCH, "MAJOR", True, "PATCH"),
        (SemVerImpact.MAJOR, "MAJOR", False, None),
        (SemVerImpact.NONE, "NONE", False, None),
    ],
)
def test_contract_lift_rank_matrix(plan_semver, contract_semver, expect_applied, expect_from):
    plan = _plan(semver=plan_semver)
    assert plan.primary_intent.semver_impact == plan_semver
    contract = _contract(semver=contract_semver)
    out, applied, from_semver = lift_plan_to_contract_semver(plan, contract)
    assert applied is expect_applied
    assert from_semver == expect_from
    if expect_applied:
        assert out.primary_intent.semver_impact.value == contract_semver
