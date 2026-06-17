import os
import sys

import pytest

# Add scripts directory to path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
from opik_metrics import FormatMetric


@pytest.fixture
def format_metric():
    return FormatMetric()


def test_perfect_commit_message(format_metric):
    msg = """✨ feat(eval): integrate atomic metrics

Adds `FormatMetric` to `opik_metrics.py` and runs it side-by-side with GEval.

Included changes:
- 🐛 fix(main): do something
- ✨ feat(eval): atomic metrics

SemVer-Impact: MINOR
Change-Types: feat, fix
Changelog-Groups: Added, Fixed
"""
    result = format_metric.score(msg)
    assert result.value == 1.0
    assert "Perfect formatting" in result.reason


def test_missing_emoji(format_metric):
    msg = """feat(eval): integrate atomic metrics

This is missing an emoji.
"""
    result = format_metric.score(msg)
    assert result.value < 1.0
    assert "does not match convention" in result.reason


def test_long_subject_line(format_metric):
    msg = f"✨ feat(eval): {'a' * 80}\n\nBody"
    result = format_metric.score(msg)
    assert result.value < 1.0
    assert "exceeds 72 characters" in result.reason


def test_missing_trailers_on_substantive_commit(format_metric):
    msg = """✨ feat(eval): integrate atomic metrics

This is a substantive commit but lacks trailers.
More lines.
"""
    result = format_metric.score(msg)
    assert result.value < 1.0
    assert "Missing required trailers" in result.reason


def test_completely_broken_message(format_metric):
    msg = f"i just fixed a bug here {'a' * 80}\n\nand no trailers"
    result = format_metric.score(msg)
    # Penalized for long subject (-0.3), no convention (-0.5), missing trailers (-0.2)
    # Should equal exactly 0.0
    assert result.value == 0.0


# --- Input validation / edge cases ---


def test_empty_string_input(format_metric):
    """Empty string triggers the guard clause and returns 0.0 with specific reason."""
    result = format_metric.score("")
    assert result.value == 0.0
    assert "empty or not a string" in result.reason


def test_none_input(format_metric):
    """None triggers the guard clause and returns 0.0 with specific reason."""
    result = format_metric.score(None)
    assert result.value == 0.0
    assert "empty or not a string" in result.reason


def test_non_string_input_int(format_metric):
    """An integer input triggers the guard clause."""
    result = format_metric.score(42)
    assert result.value == 0.0
    assert "empty or not a string" in result.reason


def test_non_string_input_list(format_metric):
    """A list input triggers the guard clause."""
    result = format_metric.score(["✨ feat: something"])
    assert result.value == 0.0
    assert "empty or not a string" in result.reason


def test_whitespace_only_input(format_metric):
    """Whitespace-only string passes the guard but subject is empty after strip; bad format penalised."""
    result = format_metric.score("   ")
    # subject = "", len 0 (no length penalty), regex fails (-0.5), single line (no trailer check)
    assert result.value == pytest.approx(0.5)
    assert "does not match convention" in result.reason


# --- Constructor / naming ---


def test_default_metric_name(format_metric):
    """Default name is CommitFormatQuality."""
    assert format_metric.name == "CommitFormatQuality"


def test_custom_metric_name():
    """Custom name is stored and reflected in ScoreResult."""
    metric = FormatMetric(name="MyCustomMetric")
    assert metric.name == "MyCustomMetric"
    result = metric.score("✨ feat: something")
    assert result.name == "MyCustomMetric"


def test_score_result_name_matches_metric(format_metric):
    """ScoreResult.name must always equal the metric's name."""
    result = format_metric.score("✨ feat: something")
    assert result.name == format_metric.name


# --- Subject length boundary conditions ---


def test_subject_exactly_72_chars_no_penalty(format_metric):
    """Subject line of exactly 72 characters should NOT trigger the length penalty."""
    # Build a valid header prefix and pad to exactly 72 chars total
    prefix = "✨ feat(eval): "
    # len(prefix.encode()) chars - but we want Python len() == 72
    padding = "a" * (72 - len(prefix))
    msg = prefix + padding
    assert len(msg) == 72
    result = format_metric.score(msg)
    assert "exceeds 72 characters" not in result.reason


def test_subject_exactly_73_chars_triggers_penalty(format_metric):
    """Subject line of exactly 73 characters should trigger the length penalty."""
    prefix = "✨ feat(eval): "
    padding = "a" * (73 - len(prefix))
    msg = prefix + padding
    assert len(msg) == 73
    result = format_metric.score(msg)
    assert result.value < 1.0
    assert "exceeds 72 characters" in result.reason


# --- Trailer check logic ---


def test_only_semver_impact_satisfies_trailer_check(format_metric):
    """Having SemVer-Impact: alone satisfies the trailer check (no Change-Types needed)."""
    msg = """✨ feat(eval): integrate atomic metrics

Body line here.

SemVer-Impact: MINOR
"""
    result = format_metric.score(msg)
    assert "Missing required trailers" not in result.reason


def test_only_change_types_satisfies_trailer_check(format_metric):
    """Having Change-Types: alone satisfies the trailer check (no SemVer-Impact needed)."""
    msg = """✨ feat(eval): integrate atomic metrics

Body line here.

Change-Types: feat
"""
    result = format_metric.score(msg)
    assert "Missing required trailers" not in result.reason


def test_two_line_commit_skips_trailer_check(format_metric):
    """A commit with exactly 2 lines (subject + blank or subject + body) skips trailer check.

    len(lines) > 2 is required to trigger check 3; with 2 lines it must not fire.
    """
    msg = "✨ feat(eval): add something\nThis is only two lines total"
    assert len(msg.split("\n")) == 2
    result = format_metric.score(msg)
    assert "Missing required trailers" not in result.reason


def test_three_line_commit_triggers_trailer_check(format_metric):
    """A commit with 3+ lines and no trailers must trigger the trailer penalty."""
    msg = "✨ feat(eval): add something\n\nBody without trailers"
    assert len(msg.split("\n")) == 3
    result = format_metric.score(msg)
    assert "Missing required trailers" in result.reason


# --- Regex / commit type variations ---


@pytest.mark.parametrize(
    "commit_type",
    ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert", "init"],
)
def test_all_valid_commit_types_match_regex(format_metric, commit_type):
    """Every type listed in the header_regex should pass format check."""
    msg = f"✨ {commit_type}(scope): subject line"
    result = format_metric.score(msg)
    assert "does not match convention" not in result.reason, (
        f"Type '{commit_type}' should be accepted but was rejected"
    )


def test_format_without_scope(format_metric):
    """Scope is optional; a header without scope should match the regex."""
    msg = "✨ feat: add new feature"
    result = format_metric.score(msg)
    assert "does not match convention" not in result.reason


def test_format_with_hyphenated_scope(format_metric):
    """Scope may contain hyphens (e.g. git-cg) and should still match."""
    msg = "✨ feat(git-cg): support hyphenated scopes"
    result = format_metric.score(msg)
    assert "does not match convention" not in result.reason


def test_invalid_commit_type_triggers_penalty(format_metric):
    """An unrecognised commit type (e.g. 'update') must fail the format check."""
    msg = "✨ update(scope): changed some things"
    result = format_metric.score(msg)
    assert result.value < 1.0
    assert "does not match convention" in result.reason


# --- Scoring arithmetic ---


def test_score_only_bad_format(format_metric):
    """Only the format penalty (-0.5) applied: single line, valid length, wrong type."""
    msg = "✨ invalid: short subject"
    result = format_metric.score(msg)
    assert result.value == pytest.approx(0.5)


def test_score_only_long_subject(format_metric):
    """Only the length penalty (-0.3) applied: long valid-format single-line commit."""
    prefix = "✨ feat(eval): "
    msg = prefix + "a" * (73 - len(prefix))
    result = format_metric.score(msg)
    assert result.value == pytest.approx(0.7)


def test_score_only_missing_trailers(format_metric):
    """Only the trailer penalty (-0.2) applied: valid header but missing trailers."""
    msg = "✨ feat(eval): integrate metrics\n\nBody without trailers."
    result = format_metric.score(msg)
    assert result.value == pytest.approx(0.8)


def test_score_long_and_bad_format_single_line(format_metric):
    """Length (-0.3) + format (-0.5) = 0.2; single line so no trailer check."""
    msg = f"i just fixed a bug {'a' * 80}"
    result = format_metric.score(msg)
    assert result.value == pytest.approx(0.2)


# --- Reason string format ---


def test_single_failure_reason_has_no_pipe_separator(format_metric):
    """A single check failure should produce a plain reason string without ' | '."""
    msg = "✨ invalid: short subject"
    result = format_metric.score(msg)
    assert " | " not in result.reason


def test_multiple_failures_use_pipe_separator(format_metric):
    """Multiple check failures should be joined with ' | '."""
    # Trigger both length and format failures
    msg = f"i just fixed a bug {'a' * 80}"
    result = format_metric.score(msg)
    assert " | " in result.reason


def test_perfect_message_reason_string(format_metric):
    """A perfect message should return 'Perfect formatting.' as the reason."""
    msg = "✨ feat(eval): short and correct subject\n\nBody.\n\nSemVer-Impact: MINOR\n"
    result = format_metric.score(msg)
    assert result.reason == "Perfect formatting."


# --- Regression / additional confidence ---


def test_leading_trailing_whitespace_in_message(format_metric):
    """Leading/trailing whitespace around the whole message is stripped; scoring still works."""
    msg = "\n\n✨ feat(eval): clean subject\n\nSemVer-Impact: MINOR\n\n"
    result = format_metric.score(msg)
    # After strip(), first line is the subject; should pass all checks
    assert result.value == 1.0


def test_score_clamped_above_zero(format_metric):
    """Score must never go below 0.0 even when all three penalties apply."""
    msg = f"i just fixed a bug here {'a' * 80}\n\nand no trailers"
    result = format_metric.score(msg)
    assert result.value >= 0.0


def test_score_clamped_at_one_for_perfect(format_metric):
    """Score must never exceed 1.0."""
    msg = "✨ feat(eval): perfect short subject"
    result = format_metric.score(msg)
    assert result.value <= 1.0
