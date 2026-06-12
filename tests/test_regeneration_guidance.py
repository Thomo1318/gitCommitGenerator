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
