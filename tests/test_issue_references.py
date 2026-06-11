import pytest

from git_cg.interaction import format_issue_reference_status
from git_cg.main import ReviewState, ReviewStateMutationResult
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

    result = state.add_issue_reference(issue_reference)

    assert result == ReviewStateMutationResult.ADDED
    assert state.issue_references == [issue_reference]


def test_review_state_render_is_deterministic_and_state_is_unchanged():
    state = ReviewState(commit_plan=_make_commit_plan())
    issue_reference = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80)
    assert state.add_issue_reference(issue_reference) == ReviewStateMutationResult.ADDED
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

    assert first_add == ReviewStateMutationResult.ADDED
    assert second_add == ReviewStateMutationResult.DUPLICATE
    assert state.issue_references == [issue_reference]


def test_review_state_uses_list_backing_even_for_phase_one_ui():
    state = ReviewState(commit_plan=_make_commit_plan())

    assert isinstance(state.issue_references, list)
    assert state.issue_references == []


# ---------------------------------------------------------------------------
# IssueReference.__str__
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, issue_number, expected",
    [
        (IssueReferenceKind.RESOLVES, 1, "Resolves #1"),
        (IssueReferenceKind.REFS, 99, "Refs #99"),
        (IssueReferenceKind.CLOSES, 100, "Closes #100"),
        (IssueReferenceKind.FIXES, 9999, "Fixes #9999"),
    ],
)
def test_issue_reference_str(kind: IssueReferenceKind, issue_number: int, expected: str):
    """__str__ must produce 'Verb #<number>' for every supported kind."""
    assert str(IssueReference(kind=kind, issue_number=issue_number)) == expected


# ---------------------------------------------------------------------------
# IssueReferenceKind enum contract
# ---------------------------------------------------------------------------


def test_issue_reference_kind_string_values():
    """IssueReferenceKind must expose the exact verb strings used in commit messages."""
    assert IssueReferenceKind.RESOLVES.value == "Resolves"
    assert IssueReferenceKind.REFS.value == "Refs"
    assert IssueReferenceKind.CLOSES.value == "Closes"
    assert IssueReferenceKind.FIXES.value == "Fixes"


def test_issue_reference_kind_has_exactly_four_members():
    assert len(list(IssueReferenceKind)) == 4


# ---------------------------------------------------------------------------
# IssueReference dataclass properties
# ---------------------------------------------------------------------------


def test_issue_reference_equality():
    """Two IssueReferences with identical fields must be equal."""
    a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=42)
    b = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=42)
    assert a == b


def test_issue_reference_inequality_on_different_kind():
    a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=42)
    b = IssueReference(kind=IssueReferenceKind.FIXES, issue_number=42)
    assert a != b


def test_issue_reference_inequality_on_different_number():
    a = IssueReference(kind=IssueReferenceKind.REFS, issue_number=1)
    b = IssueReference(kind=IssueReferenceKind.REFS, issue_number=2)
    assert a != b


def test_issue_reference_is_hashable():
    """frozen=True must make IssueReference usable in sets and as dict keys."""
    refs = {
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=1),
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=1),  # duplicate
        IssueReference(kind=IssueReferenceKind.FIXES, issue_number=2),
    }
    assert len(refs) == 2


def test_issue_reference_is_immutable():
    """frozen=True must prevent attribute mutation."""
    import dataclasses

    ref = IssueReference(kind=IssueReferenceKind.REFS, issue_number=5)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        ref.issue_number = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# format_issue_reference_status - all branches
# ---------------------------------------------------------------------------


def test_format_issue_reference_status_with_none():
    assert format_issue_reference_status(None) == "Current issue reference: None"


def test_format_issue_reference_status_with_multiple_references():
    refs = [
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=10),
        IssueReference(kind=IssueReferenceKind.REFS, issue_number=20),
    ]
    result = format_issue_reference_status(refs)
    assert result == "Current issue references: Resolves #10, Refs #20"


def test_format_issue_reference_status_plural_label_for_two_items():
    """The plural label 'Current issue references:' must be used for two or more items."""
    refs = [
        IssueReference(kind=IssueReferenceKind.FIXES, issue_number=5),
        IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=6),
    ]
    assert format_issue_reference_status(refs).startswith("Current issue references:")


def test_format_issue_reference_status_singular_label_for_one_item():
    """The singular label 'Current issue reference:' must be used for exactly one item."""
    refs = [IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=7)]
    assert format_issue_reference_status(refs).startswith("Current issue reference:")
    assert not format_issue_reference_status(refs).startswith("Current issue references:")


# ---------------------------------------------------------------------------
# CommitPlan.render - issue_references edge cases
# ---------------------------------------------------------------------------


def test_render_with_empty_list_omits_issue_references():
    """Passing an empty list must produce the same output as passing None."""
    commit_plan = _make_commit_plan()
    rendered_none = commit_plan.render(issue_references=None)
    rendered_empty = commit_plan.render(issue_references=[])
    assert rendered_none == rendered_empty


def test_render_with_multiple_issue_references_preserves_insertion_order():
    """Multiple issue references must appear in the order they were supplied."""
    commit_plan = _make_commit_plan()
    refs = [
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80),
        IssueReference(kind=IssueReferenceKind.REFS, issue_number=42),
    ]
    rendered = commit_plan.render(issue_references=refs)
    lines = rendered.splitlines()

    resolves_idx = lines.index("Resolves #80")
    refs_idx = lines.index("Refs #42")
    assert resolves_idx < refs_idx


def test_render_with_multiple_issue_references_all_above_trailers():
    """All issue references must appear before SemVer-Impact regardless of count."""
    commit_plan = _make_commit_plan()
    refs = [
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80),
        IssueReference(kind=IssueReferenceKind.REFS, issue_number=42),
    ]
    rendered = commit_plan.render(issue_references=refs)
    lines = rendered.splitlines()

    semver_idx = lines.index("SemVer-Impact: PATCH")
    for ref in refs:
        assert lines.index(str(ref)) < semver_idx


def test_render_with_single_issue_reference_explicit_none_is_same_as_omit():
    commit_plan = _make_commit_plan()
    assert commit_plan.render(issue_references=None) == commit_plan.render()


# ---------------------------------------------------------------------------
# ReviewState - multiple distinct issue references
# ---------------------------------------------------------------------------


def test_review_state_add_multiple_distinct_references():
    """Adding two distinct references must keep both in insertion order."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=10)
    ref_b = IssueReference(kind=IssueReferenceKind.FIXES, issue_number=20)

    assert state.add_issue_reference(ref_a) == ReviewStateMutationResult.ADDED
    assert state.add_issue_reference(ref_b) == ReviewStateMutationResult.ADDED
    assert state.issue_references == [ref_a, ref_b]


def test_review_state_render_includes_all_references():
    """render() must forward all attached issue references to CommitPlan.render()."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80)
    ref_b = IssueReference(kind=IssueReferenceKind.REFS, issue_number=42)
    assert state.add_issue_reference(ref_a) == ReviewStateMutationResult.ADDED
    assert state.add_issue_reference(ref_b) == ReviewStateMutationResult.ADDED

    rendered = state.render()
    assert "Resolves #80" in rendered
    assert "Refs #42" in rendered


def test_review_state_render_no_references():
    """render() with no references should not include any issue-reference lines."""
    state = ReviewState(commit_plan=_make_commit_plan())
    rendered = state.render()

    for kind in IssueReferenceKind:
        assert f"{kind.value} #" not in rendered


# ---------------------------------------------------------------------------
# interaction module constants
# ---------------------------------------------------------------------------


def test_actions_tuple_includes_add_issue_reference():
    from git_cg.interaction import ACTIONS

    assert "Add issue reference" in ACTIONS


def test_actions_tuple_contains_all_expected_actions():
    from git_cg.interaction import ACTIONS

    expected = {"Commit", "Edit", "Regenerate", "Add issue reference", "Cancel"}
    assert set(ACTIONS) == expected


def test_issue_reference_type_choices_contains_all_verbs_and_back():
    from git_cg.interaction import ISSUE_REFERENCE_TYPE_CHOICES

    expected = {"Resolves", "Refs", "Closes", "Fixes", "Back"}
    assert set(ISSUE_REFERENCE_TYPE_CHOICES) == expected


def test_review_state_rejects_same_issue_number_with_different_verb():
    """Re-adding the same issue number with a different verb must be rejected conservatively."""
    state = ReviewState(commit_plan=_make_commit_plan())
    existing_reference = IssueReference(kind=IssueReferenceKind.REFS, issue_number=80)
    conflicting_reference = IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=80)

    assert state.add_issue_reference(existing_reference) == ReviewStateMutationResult.ADDED
    assert state.add_issue_reference(conflicting_reference) == ReviewStateMutationResult.CONFLICTING_ISSUE_NUMBER
    assert state.issue_references == [existing_reference]


def test_review_state_get_issue_reference_by_issue_number_returns_match():
    state = ReviewState(commit_plan=_make_commit_plan())
    existing_reference = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=12)
    assert state.add_issue_reference(existing_reference) == ReviewStateMutationResult.ADDED

    assert state.get_issue_reference_by_issue_number(12) == existing_reference
    assert state.get_issue_reference_by_issue_number(99) is None


def test_render_with_three_issue_references_preserves_order_above_trailers():
    commit_plan = _make_commit_plan()
    refs = [
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80),
        IssueReference(kind=IssueReferenceKind.REFS, issue_number=81),
        IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=82),
    ]
    rendered = commit_plan.render(issue_references=refs)
    lines = rendered.splitlines()

    assert (
        lines.index("Resolves #80")
        < lines.index("Refs #81")
        < lines.index("Closes #82")
        < lines.index("SemVer-Impact: PATCH")
    )


def test_format_issue_reference_status_with_three_references():
    refs = [
        IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=80),
        IssueReference(kind=IssueReferenceKind.REFS, issue_number=81),
        IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=82),
    ]
    assert format_issue_reference_status(refs) == "Current issue references: Resolves #80, Refs #81, Closes #82"


# ---------------------------------------------------------------------------
# ReviewStateMutationResult enum contract
# ---------------------------------------------------------------------------


def test_review_state_mutation_result_has_exactly_three_members():
    """ReviewStateMutationResult must have exactly ADDED, DUPLICATE, and CONFLICTING_ISSUE_NUMBER."""
    assert len(list(ReviewStateMutationResult)) == 3


def test_review_state_mutation_result_string_values():
    """ReviewStateMutationResult must expose the exact lowercase string values."""
    assert ReviewStateMutationResult.ADDED == "added"
    assert ReviewStateMutationResult.DUPLICATE == "duplicate"
    assert ReviewStateMutationResult.CONFLICTING_ISSUE_NUMBER == "conflicting_issue_number"


def test_review_state_mutation_result_is_str_enum():
    """ReviewStateMutationResult is a StrEnum so instances compare equal to their string values."""
    result = ReviewStateMutationResult.ADDED
    assert result == "added"
    assert isinstance(result, str)


def test_review_state_mutation_result_all_members_present():
    """All three expected member names must exist on the enum."""
    assert hasattr(ReviewStateMutationResult, "ADDED")
    assert hasattr(ReviewStateMutationResult, "DUPLICATE")
    assert hasattr(ReviewStateMutationResult, "CONFLICTING_ISSUE_NUMBER")


# ---------------------------------------------------------------------------
# add_issue_reference – conflict detection across all verb pairs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "first_kind, second_kind",
    [
        (IssueReferenceKind.RESOLVES, IssueReferenceKind.REFS),
        (IssueReferenceKind.RESOLVES, IssueReferenceKind.CLOSES),
        (IssueReferenceKind.RESOLVES, IssueReferenceKind.FIXES),
        (IssueReferenceKind.REFS, IssueReferenceKind.RESOLVES),
        (IssueReferenceKind.REFS, IssueReferenceKind.CLOSES),
        (IssueReferenceKind.REFS, IssueReferenceKind.FIXES),
        (IssueReferenceKind.CLOSES, IssueReferenceKind.RESOLVES),
        (IssueReferenceKind.CLOSES, IssueReferenceKind.FIXES),
        (IssueReferenceKind.FIXES, IssueReferenceKind.REFS),
    ],
)
def test_review_state_conflict_all_verb_pairs(
    first_kind: IssueReferenceKind, second_kind: IssueReferenceKind
):
    """Any attempt to attach the same issue number with a different verb must return CONFLICTING_ISSUE_NUMBER."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_first = IssueReference(kind=first_kind, issue_number=42)
    ref_conflicting = IssueReference(kind=second_kind, issue_number=42)

    assert state.add_issue_reference(ref_first) == ReviewStateMutationResult.ADDED
    assert state.add_issue_reference(ref_conflicting) == ReviewStateMutationResult.CONFLICTING_ISSUE_NUMBER


def test_review_state_conflict_does_not_modify_state():
    """A CONFLICTING_ISSUE_NUMBER result must leave the issue_references list unchanged."""
    state = ReviewState(commit_plan=_make_commit_plan())
    existing = IssueReference(kind=IssueReferenceKind.REFS, issue_number=55)
    conflicting = IssueReference(kind=IssueReferenceKind.FIXES, issue_number=55)

    state.add_issue_reference(existing)
    snapshot = list(state.issue_references)

    state.add_issue_reference(conflicting)

    assert state.issue_references == snapshot
    assert len(state.issue_references) == 1
    assert state.issue_references[0] == existing


def test_review_state_add_third_distinct_reference():
    """Adding a third distinct issue reference must succeed and preserve insertion order."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=10)
    ref_b = IssueReference(kind=IssueReferenceKind.REFS, issue_number=20)
    ref_c = IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=30)

    assert state.add_issue_reference(ref_a) == ReviewStateMutationResult.ADDED
    assert state.add_issue_reference(ref_b) == ReviewStateMutationResult.ADDED
    assert state.add_issue_reference(ref_c) == ReviewStateMutationResult.ADDED
    assert state.issue_references == [ref_a, ref_b, ref_c]


def test_review_state_conflict_on_second_of_multiple_refs():
    """A conflict must be detected correctly when the conflicting number matches the second of two stored refs."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=10)
    ref_b = IssueReference(kind=IssueReferenceKind.REFS, issue_number=20)
    conflicting = IssueReference(kind=IssueReferenceKind.FIXES, issue_number=20)

    state.add_issue_reference(ref_a)
    state.add_issue_reference(ref_b)
    result = state.add_issue_reference(conflicting)

    assert result == ReviewStateMutationResult.CONFLICTING_ISSUE_NUMBER
    assert state.issue_references == [ref_a, ref_b]


def test_review_state_duplicate_after_failed_conflict_attempt():
    """After a rejected conflict attempt, re-adding the original exact reference must still return DUPLICATE."""
    state = ReviewState(commit_plan=_make_commit_plan())
    original = IssueReference(kind=IssueReferenceKind.REFS, issue_number=77)
    conflicting = IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=77)

    state.add_issue_reference(original)
    state.add_issue_reference(conflicting)  # rejected
    result = state.add_issue_reference(original)  # exact duplicate of original

    assert result == ReviewStateMutationResult.DUPLICATE
    assert state.issue_references == [original]


# ---------------------------------------------------------------------------
# get_issue_reference_by_issue_number – extended coverage
# ---------------------------------------------------------------------------


def test_get_issue_reference_by_issue_number_on_empty_state():
    """Querying an empty ReviewState must return None for any issue number."""
    state = ReviewState(commit_plan=_make_commit_plan())
    assert state.get_issue_reference_by_issue_number(1) is None
    assert state.get_issue_reference_by_issue_number(0) is None


def test_get_issue_reference_by_issue_number_returns_correct_ref_from_multiple():
    """When multiple refs are present, the lookup must return the one with the matching issue number."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=10)
    ref_b = IssueReference(kind=IssueReferenceKind.REFS, issue_number=20)
    ref_c = IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=30)

    state.add_issue_reference(ref_a)
    state.add_issue_reference(ref_b)
    state.add_issue_reference(ref_c)

    assert state.get_issue_reference_by_issue_number(10) == ref_a
    assert state.get_issue_reference_by_issue_number(20) == ref_b
    assert state.get_issue_reference_by_issue_number(30) == ref_c
    assert state.get_issue_reference_by_issue_number(99) is None


def test_get_issue_reference_by_issue_number_does_not_mutate_state():
    """Calling get_issue_reference_by_issue_number must never mutate the issue_references list."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref = IssueReference(kind=IssueReferenceKind.FIXES, issue_number=5)
    state.add_issue_reference(ref)
    snapshot = list(state.issue_references)

    state.get_issue_reference_by_issue_number(5)
    state.get_issue_reference_by_issue_number(999)

    assert state.issue_references == snapshot


# ---------------------------------------------------------------------------
# Insertion-order preservation across add / conflict / duplicate sequences
# ---------------------------------------------------------------------------


def test_insertion_order_preserved_after_duplicate_and_conflict_attempts():
    """Duplicate and conflict rejections must not reorder or alter existing references."""
    state = ReviewState(commit_plan=_make_commit_plan())
    ref_a = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=1)
    ref_b = IssueReference(kind=IssueReferenceKind.REFS, issue_number=2)
    ref_c = IssueReference(kind=IssueReferenceKind.CLOSES, issue_number=3)

    state.add_issue_reference(ref_a)
    state.add_issue_reference(ref_b)
    state.add_issue_reference(ref_c)

    # Attempt duplicate of ref_b
    state.add_issue_reference(IssueReference(kind=IssueReferenceKind.REFS, issue_number=2))
    # Attempt conflict on ref_a's number
    state.add_issue_reference(IssueReference(kind=IssueReferenceKind.FIXES, issue_number=1))

    assert state.issue_references == [ref_a, ref_b, ref_c]


def test_render_reflects_state_after_conflict_rejection():
    """The rendered output must not include a conflicting reference that was rejected."""
    state = ReviewState(commit_plan=_make_commit_plan())
    original = IssueReference(kind=IssueReferenceKind.RESOLVES, issue_number=99)
    state.add_issue_reference(original)
    state.add_issue_reference(IssueReference(kind=IssueReferenceKind.FIXES, issue_number=99))

    rendered = state.render()
    assert "Resolves #99" in rendered
    assert "Fixes #99" not in rendered
