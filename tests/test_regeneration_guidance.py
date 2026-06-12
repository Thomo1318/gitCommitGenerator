import pytest

from git_cg.interaction import ACTIONS, format_regeneration_guidance_status
from git_cg.main import ReviewState
from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact


@pytest.fixture(autouse=True)
def disable_matrix_validation(monkeypatch):
    monkeypatch.setattr("git_cg.sop.get_gitmoji_matrix", lambda: [])


def _make_commit_plan() -> CommitPlan:
    return CommitPlan(
        primary_intent=CommitIntent(
            intent_id="primary_feat",
            gitmoji="✨",
            cc_type=CommitType.FEAT,
            scope="tui",
            description="add guided regeneration",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Features",
        ),
        rationale="Primary feature dominates.",
        body_summary="Adds review-time regeneration guidance.",
    )


def test_actions_tuple_includes_guidance_actions():
    assert "Add regenerate guidance" in ACTIONS
    assert "Clear regenerate guidance" in ACTIONS


def test_format_regeneration_guidance_status_with_none():
    assert format_regeneration_guidance_status(None) == "Regeneration guidance: None"


def test_format_regeneration_guidance_status_with_short_guidance():
    assert (
        format_regeneration_guidance_status("This is a feature, not a fix.")
        == "Regeneration guidance: This is a feature, not a fix."
    )


def test_format_regeneration_guidance_status_truncates_long_guidance():
    long_guidance = "x" * 120
    result = format_regeneration_guidance_status(long_guidance, max_length=40)

    assert result.startswith("Regeneration guidance: ")
    assert result.endswith("...")
    assert len(result) <= len("Regeneration guidance: ") + 40


def test_review_state_set_regeneration_guidance_normalizes_whitespace():
    state = ReviewState(commit_plan=_make_commit_plan())

    changed = state.set_regeneration_guidance("  This   is   a   feature.  ")

    assert changed is True
    assert state.regeneration_guidance == "This is a feature."


def test_review_state_extracts_directives():
    state = ReviewState(commit_plan=_make_commit_plan())

    changed = state.set_regeneration_guidance("This is a feat. Make sure to use scope tui. And keep it short.")

    assert changed is True
    assert state.active_directives.get("preferred_type") == "feat"
    assert state.active_directives.get("preferred_scope") == "tui"
    assert state.residual_guidance == ". Make sure to . And keep it short."


def test_review_state_set_regeneration_guidance_noops_when_unchanged():
    state = ReviewState(commit_plan=_make_commit_plan(), regeneration_guidance="Use scope tui.")

    changed = state.set_regeneration_guidance("Use   scope   tui.")

    assert changed is False
    assert state.regeneration_guidance == "Use scope tui."


def test_review_state_clear_regeneration_guidance_noops_when_empty():
    state = ReviewState(commit_plan=_make_commit_plan())

    changed = state.clear_regeneration_guidance()

    assert changed is False
    assert state.regeneration_guidance is None


def test_review_state_render_does_not_include_regeneration_guidance():
    state = ReviewState(
        commit_plan=_make_commit_plan(),
        regeneration_guidance="This is a feature, not a fix.",
    )

    rendered = state.render()

    assert "This is a feature, not a fix." not in rendered
    assert "Regeneration guidance:" not in rendered


def test_review_state_render_is_deterministic_with_guidance_present():
    state = ReviewState(
        commit_plan=_make_commit_plan(),
        regeneration_guidance="Use scope tui.",
    )

    first_render = state.render()
    second_render = state.render()

    assert first_render == second_render
    assert state.regeneration_guidance == "Use scope tui."


# ---------------------------------------------------------------------------
# format_regeneration_guidance_status - boundary and edge cases
# ---------------------------------------------------------------------------


def test_format_regeneration_guidance_status_with_empty_string():
    """Empty string is falsy and must return the 'None' status form."""
    assert format_regeneration_guidance_status("") == "Regeneration guidance: None"


def test_format_regeneration_guidance_status_with_whitespace_only():
    """Whitespace-only string normalizes to empty, producing a blank trailing status line."""
    # "   " is truthy so it bypasses the `if not` check; after normalization it becomes "".
    # len("") <= max_length so the function returns "Regeneration guidance: " (empty suffix).
    result = format_regeneration_guidance_status("   ")
    assert result == "Regeneration guidance: "
    assert result.startswith("Regeneration guidance: ")


def test_format_regeneration_guidance_status_exactly_at_max_length():
    """Guidance exactly equal to max_length must NOT be truncated."""
    guidance = "x" * 80
    result = format_regeneration_guidance_status(guidance, max_length=80)
    assert result == f"Regeneration guidance: {'x' * 80}"
    assert not result.endswith("...")


def test_format_regeneration_guidance_status_one_over_max_length():
    """Guidance one character over max_length must be truncated with ellipsis."""
    guidance = "x" * 81
    result = format_regeneration_guidance_status(guidance, max_length=80)
    assert result.endswith("...")
    # Total display portion after prefix must be at most max_length chars
    prefix = "Regeneration guidance: "
    display = result[len(prefix):]
    assert len(display) <= 80


def test_format_regeneration_guidance_status_normalizes_whitespace_in_long_text():
    """Extra internal whitespace must be collapsed before truncation is applied."""
    # 40 "x" words with extra spaces = 40 chars after normalization, well under 80
    guidance = "  x   " * 20
    result = format_regeneration_guidance_status(guidance, max_length=80)
    # After normalization: "x x x ... x" (40 chars of x + spaces)
    assert "  " not in result  # no double-spaces in output
    assert not result.endswith("...")


def test_format_regeneration_guidance_status_custom_small_max_length():
    """Custom small max_length must clamp the display window correctly."""
    result = format_regeneration_guidance_status("Hello world this is guidance", max_length=10)
    prefix = "Regeneration guidance: "
    display = result[len(prefix):]
    assert len(display) <= 10
    assert result.endswith("...")


def test_format_regeneration_guidance_status_prefix_always_present():
    """The 'Regeneration guidance: ' prefix must be present for any input."""
    for guidance in [None, "", "short text", "x" * 200]:
        result = format_regeneration_guidance_status(guidance)
        assert result.startswith("Regeneration guidance: ")


# ---------------------------------------------------------------------------
# ReviewState._extract_directives - additional commit-type patterns
# ---------------------------------------------------------------------------


def test_extract_directives_make_it_a_fix():
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("make it a fix please")
    assert state.active_directives.get("preferred_type") == "fix"


def test_extract_directives_use_type_docs():
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("use type docs for this change")
    assert state.active_directives.get("preferred_type") == "docs"


def test_extract_directives_type_is_refactor():
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("type is refactor and keep it simple")
    assert state.active_directives.get("preferred_type") == "refactor"


def test_extract_directives_case_insensitive():
    """Pattern matching must be case-insensitive."""
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("THIS IS A FEAT change")
    assert state.active_directives.get("preferred_type") == "feat"


def test_extract_directives_scope_only_no_type():
    """Scope directive without a type directive must populate only preferred_scope."""
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("use scope api for this")
    assert state.active_directives.get("preferred_scope") == "api"
    assert "preferred_type" not in state.active_directives


def test_extract_directives_no_directives_leaves_full_residual():
    """Text with no recognized patterns must leave the full text as residual."""
    state = ReviewState(commit_plan=_make_commit_plan())
    guidance = "Keep it focused on user-facing behavior."
    state.set_regeneration_guidance(guidance)
    assert state.active_directives == {}
    assert state.residual_guidance == guidance


def test_extract_directives_empty_residual_when_fully_extracted():
    """If everything in the text is a recognized directive, residual must be None."""
    state = ReviewState(commit_plan=_make_commit_plan())
    # The phrase "This is a feat" is the entire text
    state.set_regeneration_guidance("This is a feat")
    assert state.active_directives.get("preferred_type") == "feat"
    # After extraction and normalization the leftover is empty -> residual is None
    assert state.residual_guidance is None


def test_extract_directives_all_supported_types():
    """Each supported commit type keyword must be extracted correctly."""
    supported_types = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert", "init", "release"]
    state = ReviewState(commit_plan=_make_commit_plan())
    for commit_type in supported_types:
        changed = state.set_regeneration_guidance(f"this is a {commit_type} change")
        assert state.active_directives.get("preferred_type") == commit_type, f"Failed for type: {commit_type}"


# ---------------------------------------------------------------------------
# ReviewState.set_regeneration_guidance - additional edge cases
# ---------------------------------------------------------------------------


def test_set_regeneration_guidance_empty_string_returns_false():
    state = ReviewState(commit_plan=_make_commit_plan())
    result = state.set_regeneration_guidance("")
    assert result is False
    assert state.regeneration_guidance is None


def test_set_regeneration_guidance_whitespace_only_returns_false():
    state = ReviewState(commit_plan=_make_commit_plan())
    result = state.set_regeneration_guidance("   \t  ")
    assert result is False
    assert state.regeneration_guidance is None


def test_set_regeneration_guidance_second_call_with_different_value_updates():
    state = ReviewState(commit_plan=_make_commit_plan())

    state.set_regeneration_guidance("First guidance.")
    assert state.regeneration_guidance == "First guidance."

    changed = state.set_regeneration_guidance("Second guidance.")
    assert changed is True
    assert state.regeneration_guidance == "Second guidance."


def test_set_regeneration_guidance_updates_active_directives_on_second_call():
    state = ReviewState(commit_plan=_make_commit_plan())

    state.set_regeneration_guidance("this is a feat")
    assert state.active_directives.get("preferred_type") == "feat"

    state.set_regeneration_guidance("this is a fix")
    assert state.active_directives.get("preferred_type") == "fix"


def test_set_regeneration_guidance_clears_directives_when_no_new_directives():
    state = ReviewState(commit_plan=_make_commit_plan())

    state.set_regeneration_guidance("this is a feat")
    assert state.active_directives != {}

    state.set_regeneration_guidance("Focus on the user experience.")
    assert state.active_directives == {}


# ---------------------------------------------------------------------------
# ReviewState.clear_regeneration_guidance - state cleanup verification
# ---------------------------------------------------------------------------


def test_clear_regeneration_guidance_also_clears_active_directives():
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("this is a feat")
    assert state.active_directives != {}

    state.clear_regeneration_guidance()
    assert state.active_directives == {}


def test_clear_regeneration_guidance_also_clears_residual_guidance():
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("Keep the scope narrow.")
    assert state.residual_guidance is not None

    state.clear_regeneration_guidance()
    assert state.residual_guidance is None


def test_clear_regeneration_guidance_returns_true_when_guidance_present():
    state = ReviewState(commit_plan=_make_commit_plan())
    state.set_regeneration_guidance("Some guidance.")

    result = state.clear_regeneration_guidance()
    assert result is True


def test_clear_then_set_cycle_works_correctly():
    """After clearing, setting new guidance must work correctly."""
    state = ReviewState(commit_plan=_make_commit_plan())

    state.set_regeneration_guidance("First guidance.")
    state.clear_regeneration_guidance()

    changed = state.set_regeneration_guidance("New guidance after clear.")
    assert changed is True
    assert state.regeneration_guidance == "New guidance after clear."


# ---------------------------------------------------------------------------
# ReviewState new fields - default values and construction
# ---------------------------------------------------------------------------


def test_review_state_active_directives_defaults_to_empty_dict():
    state = ReviewState(commit_plan=_make_commit_plan())
    assert state.active_directives == {}
    assert isinstance(state.active_directives, dict)


def test_review_state_residual_guidance_defaults_to_none():
    state = ReviewState(commit_plan=_make_commit_plan())
    assert state.residual_guidance is None


def test_review_state_regeneration_guidance_defaults_to_none():
    state = ReviewState(commit_plan=_make_commit_plan())
    assert state.regeneration_guidance is None


def test_review_state_constructed_with_explicit_regeneration_guidance():
    """ReviewState can be initialized with regeneration_guidance without calling set_regeneration_guidance."""
    state = ReviewState(commit_plan=_make_commit_plan(), regeneration_guidance="Explicit guidance.")
    assert state.regeneration_guidance == "Explicit guidance."
    # active_directives are NOT auto-extracted on __init__; they require set_regeneration_guidance
    assert state.active_directives == {}
    assert state.residual_guidance is None
