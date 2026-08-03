"""Display-only ranking confidence status line (Issue #195 nice-to-have)."""

from __future__ import annotations

from git_cg.interaction import format_ranking_confidence_status


def test_high_is_silent() -> None:
    assert format_ranking_confidence_status("high", 40.0, []) == ""


def test_missing_level_is_silent() -> None:
    assert format_ranking_confidence_status(None) == ""
    assert format_ranking_confidence_status("") == ""


def test_unknown_level_is_silent() -> None:
    assert format_ranking_confidence_status("critical", 1.0) == ""


def test_medium_status_line() -> None:
    line = format_ranking_confidence_status(
        "medium",
        12.0,
        [],
        top_intent_id="feature_addition",
        runner_up_intent_id="feature_refinement",
    )
    assert line.startswith("Ranking confidence: medium")
    assert "margin=12.0" in line
    assert "top=feature_addition vs feature_refinement" in line
    assert "reasons=" not in line


def test_low_status_line_includes_reasons() -> None:
    line = format_ranking_confidence_status(
        "low",
        6.2,
        ["margin_below_low_threshold", "near_tie_top3"],
        top_intent_id="feature_addition",
        runner_up_intent_id="bug_fix",
    )
    assert "Ranking confidence: low" in line
    assert "margin=6.2" in line
    assert "reasons=margin_below_low_threshold,near_tie_top3" in line
    assert "top=feature_addition vs bug_fix" in line


def test_medium_without_optional_fields() -> None:
    line = format_ranking_confidence_status("medium")
    assert line == "Ranking confidence: medium"
