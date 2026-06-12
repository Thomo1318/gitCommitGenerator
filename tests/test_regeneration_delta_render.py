from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
from git_cg.regeneration import ResolvedCommitContract, enforce_semantic_contract


def test_enforce_semantic_contract_overwrites_hallucination():
    # Simulate an LLM hallucinating a 'feat' when it should be a 'fix'
    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="feature",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="ui",
            description="Add a shiny new feature",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Features",
        ),
        secondary_intents=[],
        split_recommended=False,
        rationale="Did what you asked.",
        body_summary=None,
        breaking_change=False,
        breaking_change_description=None,
    )

    # The locked semantic contract says it MUST be a bug fix
    contract = ResolvedCommitContract(
        primary_intent_id="bug",
        gitmoji="🐛",
        cc_type="fix",
        semver_impact="PATCH",
        changelog_group="Bug Fixes",
        secondary_intent_ids=[],
    )

    enforced_plan = enforce_semantic_contract(plan, contract, active_directives={})

    assert enforced_plan.primary_intent.intent_id == "bug"
    assert enforced_plan.primary_intent.gitmoji == "🐛"
    assert enforced_plan.primary_intent.cc_type == CommitType.FIX
    assert enforced_plan.primary_intent.semver_impact == SemVerImpact.PATCH
    assert enforced_plan.primary_intent.changelog_group == "Bug Fixes"

    # Ensure other fields aren't randomly destroyed
    assert enforced_plan.primary_intent.scope == "ui"
    assert enforced_plan.primary_intent.description == "Add a shiny new feature"


def test_enforce_semantic_contract_applies_preferred_scope():
    plan = CommitPlan(
        primary_intent=CommitIntent(
            intent_id="bug",
            gitmoji="🐛",
            cc_type=CommitType.FIX,
            scope="ui",
            description="Fix a bug",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Bug Fixes",
        ),
        secondary_intents=[],
        split_recommended=False,
        rationale="Fix.",
        body_summary=None,
        breaking_change=False,
        breaking_change_description=None,
    )

    contract = ResolvedCommitContract(
        primary_intent_id="bug",
        gitmoji="🐛",
        cc_type="fix",
        semver_impact="PATCH",
        changelog_group="Bug Fixes",
        secondary_intent_ids=[],
    )

    # User provided explicit preferred_scope override via guidance
    active_directives = {"preferred_scope": "api"}

    enforced_plan = enforce_semantic_contract(plan, contract, active_directives=active_directives)

    assert enforced_plan.primary_intent.scope == "api"
    assert enforced_plan.primary_intent.cc_type == CommitType.FIX
