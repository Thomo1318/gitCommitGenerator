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

    # Ranked feature_addition is disallowed and no other feat rows exist. Previous plan bug_fix is also outside
    # allowed_intent_ids, so the resolver must fall through to the allowed ranked/matrix path (documentation_update).
    assert contract.primary_intent_id == "documentation_update"
    assert contract.cc_type == "docs"


def test_resolve_semantic_contract_first_pass_locks_top_ranked_intent():
    """Without previous_plan, contract locks to the top ranked SOP intent."""
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
            ),
            RankedIntent(
                intent_id="bug_fix",
                emoji="🐛",
                code=":bug:",
                cc_type="fix",
                description="",
                semver_impact="PATCH",
                changelog_group="Fixed",
                intent_group="bugfix",
                score=10.0,
                priority=50,
                specificity=50,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(previous_plan=None, active_directives={})

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "feature_addition"
    assert contract.cc_type == "feat"
    assert contract.gitmoji == "✨"
    assert contract.semver_impact == "MINOR"
    assert contract.secondary_intent_ids == []


def test_resolve_semantic_contract_first_pass_respects_allowed_constraints():
    context = GenerationContext(
        diff_signals=DiffSignals(only_docs=True),
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
            ),
            RankedIntent(
                intent_id="documentation_update",
                emoji="📝",
                code=":memo:",
                cc_type="docs",
                description="",
                semver_impact="NONE",
                changelog_group="Documentation",
                intent_group="docs",
                score=40.0,
                priority=40,
                specificity=40,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(allowed_intent_ids=["documentation_update"]),
    )
    state = RegenerationState(previous_plan=None, active_directives={})

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "documentation_update"
    assert contract.cc_type == "docs"


def test_enforce_semantic_contract_locks_primary_and_scope():
    from git_cg.regeneration import ResolvedCommitContract, enforce_semantic_contract

    plan = _make_commit_plan(intent_id="bug_fix", cc_type=CommitType.FIX)
    contract = ResolvedCommitContract(
        primary_intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        semver_impact="MINOR",
        changelog_group="Added",
        secondary_intent_ids=[],
    )
    out = enforce_semantic_contract(plan, contract, active_directives={"preferred_scope": "api"})
    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    assert out.primary_intent.cc_type == CommitType.FEAT
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR
    assert out.primary_intent.changelog_group == "Added"
    assert out.primary_intent.scope == "api"


def test_resolve_semantic_contract_empty_matrix_fallback(monkeypatch):
    monkeypatch.setattr("git_cg.regeneration.get_gitmoji_matrix", lambda: [])
    context = GenerationContext(
        diff_signals=DiffSignals(),
        ranked_intents=[],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(previous_plan=None, active_directives={})
    contract = resolve_semantic_contract(context, state)
    assert contract.primary_intent_id == "unknown"
    assert contract.cc_type == "chore"
    assert contract.secondary_intent_ids == []


def test_resolve_semantic_contract_first_pass_falls_back_to_allowed_matrix_row():
    """When ranked intents miss allowed set, pick first allowed matrix row."""
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
        constraints=IntentSelectionConstraints(allowed_intent_ids=["documentation_update"]),
    )
    state = RegenerationState(previous_plan=None, active_directives={})
    contract = resolve_semantic_contract(context, state)
    assert contract.primary_intent_id == "documentation_update"


def test_resolve_semantic_contract_previous_plan_respects_allowed_constraints():
    """Previous-plan anchor is skipped when that intent is outside allowed_intent_ids."""
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
                score=10.0,
                priority=100,
                specificity=100,
                split_weight=50,
            ),
            RankedIntent(
                intent_id="documentation_update",
                emoji="📝",
                code=":memo:",
                cc_type="docs",
                description="",
                semver_impact="PATCH",
                changelog_group="Changed",
                intent_group="docs",
                score=5.0,
                priority=50,
                specificity=50,
                split_weight=25,
            ),
        ],
        constraints=IntentSelectionConstraints(allowed_intent_ids=["documentation_update"]),
    )
    state = RegenerationState(
        previous_plan=_make_commit_plan(intent_id="bug_fix", cc_type=CommitType.FIX),
        active_directives={},
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "documentation_update"
    assert contract.cc_type == "docs"


def test_resolve_semantic_contract_nonempty_matrix_falls_back_to_first_row():
    """With ranked intents empty and no constraints, lock to matrix[0]."""
    context = GenerationContext(
        diff_signals=DiffSignals(),
        ranked_intents=[],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(previous_plan=None, active_directives={})
    contract = resolve_semantic_contract(context, state)

    # mock_matrix fixture orders feature_addition first
    assert contract.primary_intent_id == "feature_addition"
    assert contract.cc_type == "feat"
    assert contract.gitmoji == "✨"
    assert contract.semver_impact == "MINOR"
    assert contract.changelog_group == "Added"
    assert contract.secondary_intent_ids == []


def test_resolve_semantic_contract_locked_intent_wins_when_allowed():
    """A_11/A_15: eligible locked_intent_id is selected over ranked top."""
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
            ),
            RankedIntent(
                intent_id="bug_fix",
                emoji="🐛",
                code=":bug:",
                cc_type="fix",
                description="",
                semver_impact="PATCH",
                changelog_group="Fixed",
                intent_group="bugfix",
                score=10.0,
                priority=50,
                specificity=50,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(previous_plan=None, active_directives={}, locked_intent_id="bug_fix")

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "bug_fix"
    assert contract.cc_type == "fix"
    assert contract.lock_resolution == "accepted"


def test_resolve_semantic_contract_locked_intent_beats_previous_plan():
    """A_15: lock sits before previous_plan (regen retry hazard)."""
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
            ),
            RankedIntent(
                intent_id="documentation_update",
                emoji="📝",
                code=":memo:",
                cc_type="docs",
                description="",
                semver_impact="NONE",
                changelog_group="Documentation",
                intent_group="docs",
                score=40.0,
                priority=40,
                specificity=40,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(
        previous_plan=_make_commit_plan(intent_id="bug_fix", cc_type=CommitType.FIX),
        active_directives={},
        locked_intent_id="documentation_update",
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "documentation_update"
    assert contract.lock_resolution == "accepted"


def test_resolve_semantic_contract_locked_intent_ignored_when_not_allowed():
    """A_11: lock outside allowed_ids falls through; never widens eligible set."""
    context = GenerationContext(
        diff_signals=DiffSignals(only_docs=True),
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
            ),
            RankedIntent(
                intent_id="documentation_update",
                emoji="📝",
                code=":memo:",
                cc_type="docs",
                description="",
                semver_impact="NONE",
                changelog_group="Documentation",
                intent_group="docs",
                score=40.0,
                priority=40,
                specificity=40,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(allowed_intent_ids=["documentation_update"]),
    )
    state = RegenerationState(
        previous_plan=None,
        active_directives={},
        locked_intent_id="feature_addition",
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "documentation_update"
    assert contract.lock_resolution == "rejected_not_allowed"


def test_resolve_semantic_contract_locked_intent_unknown_is_hard_veto():
    """A_22: lock id absent from SOP matrix falls through with lock_resolution=rejected_hard_veto."""
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
            ),
        ],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(
        previous_plan=None,
        active_directives={},
        locked_intent_id="not_a_real_matrix_intent",
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "feature_addition"
    assert contract.lock_resolution == "rejected_hard_veto"


def test_resolve_semantic_contract_preferred_type_cannot_discard_eligible_lock():
    """A_17: preferred_type must not silently discard an eligible human lock."""
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
            ),
            RankedIntent(
                intent_id="bug_fix",
                emoji="🐛",
                code=":bug:",
                cc_type="fix",
                description="",
                semver_impact="PATCH",
                changelog_group="Fixed",
                intent_group="bugfix",
                score=80.0,
                priority=50,
                specificity=50,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
    )
    state = RegenerationState(
        previous_plan=None,
        active_directives={"preferred_type": "feat"},
        locked_intent_id="bug_fix",
    )

    contract = resolve_semantic_contract(context, state)

    assert contract.primary_intent_id == "bug_fix"
    assert contract.cc_type == "fix"
    assert contract.lock_resolution == "accepted"


def test_resolve_semantic_contract_absent_lock_resolution_when_unset():
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
    state = RegenerationState(previous_plan=None, active_directives={})
    contract = resolve_semantic_contract(context, state)
    assert contract.primary_intent_id == "feature_addition"
    assert contract.lock_resolution == "absent"


def test_path_class_envelope_demotes_contaminated_fix_patch_for_fixtures():
    """P-S12: pure fixtures must not lock fix/PATCH when ranking is contaminated."""
    from git_cg.commit_quality import constraints_from_paths
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.regeneration import (
        GenerationContext,
        RegenerationState,
        lift_plan_to_contract_semver,
        resolve_semantic_contract,
    )

    paths = ["tests/fixtures/commit_quality/README.md"]
    cons = constraints_from_paths(paths)
    context = GenerationContext(
        diff_signals=DiffSignals(files=paths, only_tests=True, only_fixtures=True),
        ranked_intents=[
            RankedIntent(
                intent_id="bug_fix",
                emoji="🐛",
                code=":bug:",
                cc_type="fix",
                description="",
                semver_impact="PATCH",
                changelog_group="Fixed",
                intent_group="bugfix",
                score=100.0,
                priority=100,
                specificity=100,
                split_weight=50,
            ),
            RankedIntent(
                intent_id="tests_update",
                emoji="✅",
                code=":white_check_mark:",
                cc_type="test",
                description="",
                semver_impact="NONE",
                changelog_group="Tests",
                intent_group="tests",
                score=20.0,
                priority=40,
                specificity=40,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
        presentation_constraints=cons,
    )
    state = RegenerationState(previous_plan=None, active_directives={})
    contract = resolve_semantic_contract(context, state)

    # Identity stays ranked; presentation fields follow path-class envelope.
    assert contract.primary_intent_id == "bug_fix"
    assert contract.gitmoji == "🐛"
    assert contract.cc_type == "test"
    assert contract.semver_impact == "NONE"
    assert contract.changelog_group == "Tests"

    # CommitIntent matrix validator canonicalises matrix-owned fields from intent_id.
    # Use a test-family identity so the plan under lift is not re-expanded to fix/PATCH.
    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="tests_update",
            gitmoji="✅",
            cc_type=CommitType.TEST,
            scope="fixtures",
            description="cover fixture evidence",
            semver_impact=SemVerImpact.NONE,
            changelog_group="Tests",
        ),
        rationale="path-class envelope",
        body_summary="Cover staged fixture evidence.",
    )
    assert plan.primary_intent.semver_impact == SemVerImpact.NONE
    assert plan.primary_intent.cc_type == CommitType.TEST
    lifted, applied, _from = lift_plan_to_contract_semver(plan, contract)
    assert applied is False
    assert lifted.primary_intent.semver_impact == SemVerImpact.NONE


def test_path_class_envelope_empty_unknown_preserves_fix_patch():
    """Empty path class must not demote matrix fix/PATCH to NONE."""
    from git_cg.commit_quality import apply_presentation_overlay, constraints_from_paths
    from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
    from git_cg.regeneration import (
        GenerationContext,
        RegenerationState,
        lift_plan_to_contract_semver,
        resolve_semantic_contract,
    )

    cons = constraints_from_paths([])
    assert cons.diff_class == "empty"
    assert cons.force_semver is None

    context = GenerationContext(
        diff_signals=DiffSignals(files=[]),
        ranked_intents=[
            RankedIntent(
                intent_id="bug_fix",
                emoji="🐛",
                code=":bug:",
                cc_type="fix",
                description="",
                semver_impact="PATCH",
                changelog_group="Fixed",
                intent_group="bugfix",
                score=100.0,
                priority=100,
                specificity=100,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
        presentation_constraints=cons,
    )
    state = RegenerationState(previous_plan=None, active_directives={})
    contract = resolve_semantic_contract(context, state)

    # Identity + matrix SemVer survive empty/unknown path class.
    assert contract.primary_intent_id == "bug_fix"
    assert contract.cc_type == "fix"
    assert contract.semver_impact == "PATCH"
    assert contract.changelog_group == "Fixed"

    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="bug_fix",
            gitmoji="🐛",
            cc_type=CommitType.FIX,
            scope="intent",
            description="preserve matrix patch under empty paths",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Fixed",
        ),
        rationale="empty-unknown envelope",
        body_summary="Keep fix/PATCH when path evidence is unknown.",
    )
    lifted, applied, _from = lift_plan_to_contract_semver(plan, contract)
    assert applied is False
    assert lifted.primary_intent.semver_impact == SemVerImpact.PATCH

    # Overlay must also preserve PATCH under empty/unknown constraints.
    overlaid = apply_presentation_overlay(
        plan,
        paths=[],
        signals=DiffSignals(files=[]),
        constraints=cons,
    )
    assert overlaid.primary_intent.semver_impact == SemVerImpact.PATCH
    assert overlaid.primary_intent.cc_type == CommitType.FIX


def test_path_class_envelope_product_mixed_preserves_patch():
    """Product source + tests must not force NONE via path-class envelope."""
    from git_cg.commit_quality import constraints_from_paths
    from git_cg.regeneration import (
        GenerationContext,
        RegenerationState,
        resolve_semantic_contract,
    )

    paths = ["src/git_cg/intent.py", "tests/test_intent.py"]
    cons = constraints_from_paths(paths)
    assert cons.force_semver is None

    context = GenerationContext(
        diff_signals=DiffSignals(files=paths, touches_tests=True),
        ranked_intents=[
            RankedIntent(
                intent_id="bug_fix",
                emoji="🐛",
                code=":bug:",
                cc_type="fix",
                description="",
                semver_impact="PATCH",
                changelog_group="Fixed",
                intent_group="bugfix",
                score=90.0,
                priority=90,
                specificity=90,
                split_weight=50,
            ),
        ],
        constraints=IntentSelectionConstraints(),
        presentation_constraints=cons,
    )
    contract = resolve_semantic_contract(context, RegenerationState(previous_plan=None, active_directives={}))
    assert contract.primary_intent_id == "bug_fix"
    assert contract.semver_impact == "PATCH"
    assert contract.cc_type == "fix"
