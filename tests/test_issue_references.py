import pytest

from git_cg.interaction import format_issue_reference_status
from git_cg.main import ReviewState
from git_cg.models import (
    CommitIntent,
    CommitPlan,
    CommitType,
    IssueReference,
    IssueReferenceKind,
    SemVerImpact,
)


@pytest.fixture(autouse=True)
def disable_matrix_validation(monkeypatch):
    """
    Disable gitmoji matrix validation for tests by monkeypatching git_cg.sop.get_gitmoji_matrix to return an empty list.
    
    Used as an autouse pytest fixture so tests run without requiring gitmoji matrix data.
    """
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: [])


def _make_intent(
    *,
    intent_id: str,
    gitmoji: str,
    cc_type: CommitType,
    description: str,
    semver_impact: SemVerImpact,
    changelog_group: str,
    scope: str | None = None,
) -> CommitIntent:
    """
    Create a CommitIntent test helper populated with the provided fields.
    
    Parameters:
        intent_id (str): Identifier for the intent.
        gitmoji (str): Gitmoji string associated with the intent.
        cc_type (CommitType): Conventional commit type for the intent.
        description (str): Short description of the intent.
        semver_impact (SemVerImpact): SemVer impact level for the intent.
        changelog_group (str): Changelog group name for the intent.
        scope (str | None): Optional scope for the intent; pass None if not applicable.
    
    Returns:
        CommitIntent: A CommitIntent instance initialised with the supplied values.
    """
    return CommitIntent(
        intent_id=intent_id,
        gitmoji=gitmoji,
        cc_type=cc_type,
        scope=scope,
        description=description,
        semver_impact=semver_impact,
        changelog_group=changelog_group,
    )


def _make_commit_plan() -> CommitPlan:
    """
    Create a sample CommitPlan for tests with one primary FIX intent and one secondary DOCS intent.
    
    Returns:
        CommitPlan: A plan containing a primary intent (scope "main", SemVer impact PATCH, changelog group "Bug Fixes"), a single secondary intent (scope "readme", SemVer impact NONE, changelog group "Documentation"), and fixed `rationale` and `body_summary`.
    """
    return CommitPlan(
        primary_intent=_make_intent(
            intent_id="primary_fix",
            gitmoji="🥅",
            cc_type=CommitType.FIX,
            scope="main",
            description="add exception handling",
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Bug Fixes",
        ),
        secondary_intents=[
            _make_intent(
                intent_id="secondary_docs",
                gitmoji="📝",
                cc_type=CommitType.DOCS,
                scope="readme",
                description="document review flow",
                semver_impact=SemVerImpact.NONE,
                changelog_group="Documentation",
            )
        ],
        rationale="Primary fix dominates; docs are secondary.",
        body_summary="Explain the why and how.",
    )


@pytest.mark.parametrize("reference_kind", list(IssueReferenceKind))
def test_issue_reference_renders_above_trailers(reference_kind: IssueReferenceKind):
    commit_plan = _make_commit_plan()
    rendered = commit_plan.render(issue_references=[IssueReference(kind=reference_kind, issue_number=26)])
    lines = rendered.splitlines()

    issue_line = f"{reference_kind.value} #26"
    assert lines.index("Included changes:") < lines.index(issue_line) < lines.index("SemVer-Impact: PATCH")
    assert lines.index(issue_line) < lines.index("Change-Types: fix, docs")
    assert lines.index(issue_line) < lines.index("Changelog-Groups: Bug Fixes, Documentation")


def test_render_without_issue_reference_adds_nothing_extra():
    """
    Verify that rendering a CommitPlan with no issue references omits issue-reference trailers while still including SemVer and changelog trailers.
    
    Asserts that the rendered output does not contain any issue-reference prefixes ("Resolves #", "Refs #", "Closes #", "Fixes #") and that "SemVer-Impact: PATCH" and "Changelog-Groups: Bug Fixes, Documentation" are present.
    """
    commit_plan = _make_commit_plan()
    rendered = commit_plan.render()

    assert "Resolves #" not in rendered
    assert "Refs #" not in rendered
    assert "Closes #" not in rendered
    assert "Fixes #" not in rendered
    assert "SemVer-Impact: PATCH" in rendered
    assert "Changelog-Groups: Bug Fixes, Documentation" in rendered


def test_format_issue_reference_status_handles_empty_and_single_state():
    assert format_issue_reference_status([]) == "Current issue reference: None"
    assert (
        format_issue_reference_status([IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=48)])
        == "Current issue reference: Resolves #48"
    )


def test_review_state_add_issue_reference_updates_state():
    state = ReviewState(commit_plan=_make_commit_plan())
    issue_reference = IssueReference(kind=IssueReferenceKind.REFS, issue_number=26)

    added = state.add_issue_reference(issue_reference)

    assert added is True
    assert state.issue_references == [issue_reference]


def test_review_state_render_is_deterministic_and_state_is_unchanged():
    state = ReviewState(commit_plan=_make_commit_plan())
    issue_reference = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80)
    state.add_issue_reference(issue_reference)
    before_state = list(state.issue_references)

    first_render = state.render()
    second_render = state.render()

    assert first_render == second_render
    assert state.issue_references == before_state


def test_review_state_add_issue_reference_is_idempotent():
    state = ReviewState(commit_plan=_make_commit_plan())
    issue_reference = IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=26)

    first_add = state.add_issue_reference(issue_reference)
    second_add = state.add_issue_reference(issue_reference)

    assert first_add is True
    assert second_add is False
    assert state.issue_references == [issue_reference]


def test_review_state_uses_list_backing_even_for_phase_one_ui():
    state = ReviewState(commit_plan=_make_commit_plan())

    assert isinstance(state.issue_references, list)
    assert state.issue_references == []
