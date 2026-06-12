import pytest

from git_cg.intent import DiffSignals, IntentSelectionConstraints, RankedIntent
from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
from git_cg.regeneration import GenerationContext, RegenerationState, resolve_semantic_contract


@pytest.fixture(autouse=True)
def mock_matrix(monkeypatch):
    """
    Provide a deterministic gitmoji matrix for tests by monkeypatching git_cg.regeneration.get_gitmoji_matrix.

    Patches get_gitmoji_matrix to return a fixed list of three intent entries (feature_addition, bug_fix, documentation_update) including their emoji, code, conventional-commit type (`cc_type`), semantic version impact (`semver_impact`), changelog group and intent group. Intended for use as an autouse pytest fixture to control intent/type resolution in tests.
    """
    matrix = [
        {
            "intent_id": "feature_addition",
            "emoji": "✨",
            "code": ":sparkles:",
            "cc_type": "feat",
            "semver_impact": "MINOR",
            "changelog_group": "Added",
            "intent_group": "feature",
        },
        {
            "intent_id": "bug_fix",
            "emoji": "🐛",
            "code": ":bug:",
            "cc_type": "fix",
            "semver_impact": "PATCH",
            "changelog_group": "Fixed",
            "intent_group": "bugfix",
        },
        {
            "intent_id": "documentation_update",
            "emoji": "📝",
            "code": ":memo:",
            "cc_type": "docs",
            "semver_impact": "NONE",
            "changelog_group": "Documentation",
            "intent_group": "docs",
        },
    ]
    monkeypatch.setattr("git_cg.regeneration.get_gitmoji_matrix", lambda: matrix)


def _make_commit_plan(intent_id: str = "bug_fix", cc_type: CommitType = CommitType.FIX) -> CommitPlan:
    """
    Create a reusable CommitPlan for tests with a primary intent set to the given intent identifier and commit type.

    Parameters:
        intent_id (str): Identifier to set on the primary intent.
        cc_type (CommitType): Commit classification to assign to the primary intent.

    Returns:
        CommitPlan: A CommitPlan whose `primary_intent` uses the provided `intent_id` and `cc_type`, with fixed test values for `gitmoji`, `scope`, `description`, `semver_impact`, and `changelog_group`, and simple `rationale` and `body_summary`.
    """
    return CommitPlan(
        primary_intent=CommitIntent(
            intent_id=intent_id,
            gitmoji="🐛",
            cc_type=cc_type,
            scope="main",
            description="fix something",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Fixed",
        ),
        rationale="Fix.",
        body_summary="Did a fix.",
    )


def test_resolve_semantic_contract_anchors_to_previous_plan_when_no_directives():
    """When no explicit preferred_type is provided, the contract must strictly lock to the previous plan's intent."""
    context = GenerationContext(diff_signals=DiffSignals(), ranked_intents=[], constraints=IntentSelectionConstraints())
    state = RegenerationState(
        previous_plan=_make_commit_plan(intent_id="bug_fix", cc_type=CommitType.FIX), active_directives={}
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "bug_fix"
    assert contract.cc_type == "fix"
    assert contract.gitmoji == "🐛"
    assert contract.semver_impact == "PATCH"
    assert contract.changelog_group == "Fixed"


def test_resolve_semantic_contract_follows_preferred_type_directive():
    """When a preferred_type is provided, the contract must find the best matching intent from the ranker."""
    context = GenerationContext(
        diff_signals=DiffSignals(),
        ranked_intents=[
            RankedIntent(
                intent_id="feature_addition",
                emoji="✨",
                code=":sparkles:",
                cc_type="feat",
                description="",
                semver_impact="MINOR",
                changelog_group="Added",
                intent_group="feature",
                score=100.0,
                priority=100,
                specificity=100,
                split_weight=50,
            )
        ],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(
        previous_plan=_make_commit_plan(intent_id="bug_fix", cc_type=CommitType.FIX),
        active_directives={"preferred_type": "feat"},
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "feature_addition"
    assert contract.cc_type == "feat"
    assert contract.gitmoji == "✨"
    assert contract.semver_impact == "MINOR"
    assert contract.changelog_group == "Added"


def test_resolve_semantic_contract_respects_allowed_constraints_when_directive_provided():
    """If a preferred_type is given but the top ranked intent is disallowed by constraints, it must skip it."""
    context = GenerationContext(
        diff_signals=DiffSignals(),
        ranked_intents=[
            RankedIntent(
                intent_id="feature_addition",
                emoji="✨",
                code=":sparkles:",
                cc_type="feat",
                description="",
                semver_impact="MINOR",
                changelog_group="Added",
                intent_group="feature",
                score=100.0,
                priority=100,
                specificity=100,
                split_weight=50,
            )
        ],
        constraints=IntentSelectionConstraints(
            allowed_intent_ids=["documentation_update"]  # feature_addition is disallowed!
        ),
    )
    state = RegenerationState(
        previous_plan=_make_commit_plan(intent_id="bug_fix", cc_type=CommitType.FIX),
        active_directives={"preferred_type": "feat"},
    )

    contract = resolve_semantic_contract(context, state)

    # Since the ranked "feature_addition" is disallowed, it should fallback to the first matrix row that matches the type
    # and is allowed. Our mock matrix has "feature_addition", but it's disallowed. There are no other "feat" rows.
    # Therefore, it will fall through to the stable anchor (previous plan), which is "bug_fix".
    assert contract.primary_intent_id == "bug_fix"
    assert contract.cc_type == "fix"
