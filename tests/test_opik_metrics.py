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
