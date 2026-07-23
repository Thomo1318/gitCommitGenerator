"""Model-facing strict intent validation (Issue #161 Slice 2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from git_cg.models import (
    CommitIntent,
    CommitType,
    ModelCommitIntent,
    ModelCommitPlan,
    SemVerImpact,
)


@pytest.fixture(autouse=True)
def mock_matrix(monkeypatch):
    """Provide a fixed gitmoji intent matrix for tests.
    
    Parameters:
    	monkeypatch: Pytest monkeypatch fixture used to replace the matrix provider.
    
    Returns:
    	list: The configured intent matrix.
    """
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "code": ":sparkles:",
            "cc_type": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
        },
        {
            "intent_id": "bug_fix",
            "emoji": "🐛",
            "code": ":bug:",
            "cc_type": "fix",
            "semver_impact": "PATCH",
            "changelog_group": "Fixed",
        },
        {
            "intent_id": "generic_chore",
            "emoji": "🔧",
            "code": ":wrench:",
            "cc_type": "chore",
            "semver_impact": "NONE",
            "changelog_group": "Miscellaneous",
        },
    ]
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: matrix)
    return matrix


def test_model_commit_intent_accepts_known_intent_id():
    intent = ModelCommitIntent(
        intent_id="bug_fix",
        gitmoji="🐛",
        cc_type=CommitType.FIX,
        description="fix the parser",
        semver_impact=SemVerImpact.PATCH,
        changelog_group="Fixed",
    )
    assert intent.intent_id == "bug_fix"


def test_model_commit_intent_rejects_unknown_intent_id():
    with pytest.raises(ValidationError, match="Unknown intent_id"):
        ModelCommitIntent(
            intent_id="totally_hallucinated_intent",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            description="do a thing",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        )


def test_internal_commit_intent_still_coerces_unknown_off_llm_path():
    """Internal CommitIntent may still coerce; that path is not LLM success."""
    intent = CommitIntent(
        intent_id="totally_hallucinated_intent",
        gitmoji="❓",  # unknown emoji so lookup cannot match by glyph either
        cc_type=CommitType.FEAT,
        description="do a thing",
        semver_impact=SemVerImpact.MINOR,
        changelog_group="Added",
    )
    assert intent.intent_id == "generic_chore"
    assert intent.gitmoji == "🔧"
    assert intent.cc_type == CommitType.CHORE


def test_model_commit_plan_to_commit_plan_maps_intents():
    plan = ModelCommitPlan(
        primary_intent=ModelCommitIntent(
            intent_id="feature_addition",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            description="add endpoint",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Added",
        ),
        rationale="Feature.",
        body_summary="Added an endpoint.",
    )
    internal = plan.to_commit_plan()
    assert internal.primary_intent.intent_id == "feature_addition"
    assert internal.rationale == "Feature."


def test_model_commit_plan_requires_breaking_description():
    with pytest.raises(ValidationError, match="breaking_change_description"):
        ModelCommitPlan(
            primary_intent=ModelCommitIntent(
                intent_id="feature_addition",
                gitmoji="✨",
                cc_type=CommitType.FEAT,
                description="add endpoint",
                semver_impact=SemVerImpact.MINOR,
                changelog_group="Added",
            ),
            rationale="break",
            breaking_change=True,
            breaking_change_description=None,
        )


def test_model_commit_intent_allows_when_matrix_unavailable(monkeypatch):
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: [])
    intent = ModelCommitIntent(
        intent_id="anything",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        description="x",
        semver_impact=SemVerImpact.MINOR,
        changelog_group="Added",
    )
    assert intent.intent_id == "anything"
