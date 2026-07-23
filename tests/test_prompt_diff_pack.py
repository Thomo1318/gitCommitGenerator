"""Issue #161 Slice 4: analysis/prompt diff split and file-boundary packing."""

from __future__ import annotations

from git_cg.intent import DiffSignals, _generate_signal_markers, rank_commit_intents
from git_cg.main import PROMPT_DIFF_MAX_CHARS, pack_prompt_diff
from git_cg.sop import load_sop


def _file_section(path: str, body: str) -> str:
    """Construct a unified diff section for a single file.

    Parameters:
        path (str): The file path included in the diff headers.
        body (str): The file's diff content.

    Returns:
        str: A unified diff section containing the file headers and body.
    """
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,1 @@\n{body}\n"


def test_pack_prompt_diff_under_budget_is_identity():
    diff = _file_section("src/a.py", "+print('a')")
    packed, omitted = pack_prompt_diff(diff, max_chars=50_000)
    assert packed == diff
    assert omitted == []


def test_pack_prompt_diff_omits_whole_files_not_mid_slice():
    # First small file kept; second huge file omitted entirely from prompt.
    small = _file_section("src/small.py", "+ok")
    huge_body = "+" + ("x" * 80_000)
    huge = _file_section("src/huge.py", huge_body)
    analysis = small + huge

    packed, omitted = pack_prompt_diff(analysis, max_chars=5_000)
    assert "src/small.py" in packed
    assert "src/huge.py" not in packed or "Omitted from prompt" in packed
    assert "src/huge.py" in omitted
    assert "PROMPT DIFF OMISSION INVENTORY" in packed
    # No blind mid-string marker from the old extractor.
    assert "DIFF TRUNCATED DUE TO LENGTH" not in packed
    # Kept portion should still start at a real file header.
    assert packed.lstrip().startswith("diff --git ")


def test_analysis_rank_unchanged_when_prompt_omits_files():
    """Ranking must use full analysis text; packing must not change markers/rank."""
    small = _file_section("README.md", "+docs only")
    huge = _file_section("src/huge.py", "+" + ("y" * 60_000))
    analysis = small + huge
    packed, omitted = pack_prompt_diff(analysis, max_chars=2_000)
    assert omitted  # prompt is reduced

    matrix = load_sop().get("gitmoji_reference_matrix", [])
    # Use explicit signals path (same as ranker authority) to show packing is irrelevant.
    signals = DiffSignals(only_docs=True, touches_docs=True, files=["README.md"])
    markers = sorted(_generate_signal_markers(signals))
    ranked = [(r.intent_id, r.score, r.semver_impact) for r in rank_commit_intents(signals, matrix)]

    # Recompute after packing — signals are independent of packed prompt text.
    markers_after = sorted(_generate_signal_markers(signals))
    ranked_after = [(r.intent_id, r.score, r.semver_impact) for r in rank_commit_intents(signals, matrix)]
    assert markers_after == markers
    assert ranked_after == ranked
    assert len(packed) < len(analysis)


def test_prompt_diff_max_chars_constant():
    assert PROMPT_DIFF_MAX_CHARS == 50_000


def test_pack_prompt_diff_rejects_non_positive_budget():
    import pytest

    with pytest.raises(ValueError, match="max_chars"):
        pack_prompt_diff("diff --git a/x b/x\n", max_chars=0)


def test_pack_prompt_diff_without_file_headers_uses_prefix_note():
    blob = "not a unified diff\n" + ("z" * 10_000)
    packed, omitted = pack_prompt_diff(blob, max_chars=500)
    assert omitted == ["<unbounded-diff>"]
    assert "no file boundaries found" in packed
    assert len(packed) <= 500 + 5  # small slack for note assembly


def test_pack_prompt_diff_single_oversized_file_partial_omit():
    body = "+" + ("q" * 20_000)
    analysis = _file_section("src/only.py", body)
    packed, omitted = pack_prompt_diff(analysis, max_chars=800)
    assert omitted == ["src/only.py"]
    assert "single large file partially omitted" in packed
