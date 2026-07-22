"""
Regression tests for hk.pkl profile contract (Issue #170 Slice 2).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HK_PKL = REPO_ROOT / "hk.pkl"


def _step_block(text: str, step_name: str) -> str:
    """
    Extract the body of a named step block using brace matching.

    Parameters:
        text (str): Text containing the step block.
        step_name (str): Name of the step block to extract.

    Returns:
        str: Contents of the block excluding its outer braces.

    Raises:
        AssertionError: If the block or its matching braces cannot be found.
    """
    needle = f'["{step_name}"]'
    start = text.find(needle)
    if start < 0:
        raise AssertionError(f"{step_name} step block not found")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"{step_name} opening brace not found")
    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : i]
    raise AssertionError(f"{step_name} block was not closed")


def _hook_maps_to_linters(text: str, hook_name: str) -> bool:
    """
    Determine whether a hook assigns the shared linters steps.

    Parameters:
        text (str): The configuration text containing the hook definition.
        hook_name (str): The name of the hook to inspect.

    Returns:
        bool: `True` if the hook assigns `steps = linters`, `False` otherwise.
    """
    body = _step_block(text, hook_name)
    for line in body.splitlines():
        code = line.split("//", 1)[0].strip()
        if re.fullmatch(r"steps\s*=\s*linters", code):
            return True
    return False


class TestHkPklContract:
    def _text(self) -> str:
        """Read and return the hk.pkl file contents.

        Returns:
            str: The UTF-8 text read from the hk.pkl file.
        """
        return HK_PKL.read_text(encoding="utf-8")

    def test_file_exists(self):
        assert HK_PKL.is_file()

    def test_min_hk_version(self):
        """Verify that the configuration specifies the minimum supported hk version.

        The configuration must declare hk version 1.45.0 as the minimum supported version.
        """
        text = self._text()
        assert 'min_hk_version = "1.45.0"' in text

    def test_amends_exact_package_aligned_with_mise_pin(self):
        """Verify that the hk package reference matches the pinned version and excludes the older version."""
        text = self._text()
        # Exact Pkl package version must match mise.toml hk pin (1.51.0).
        assert "hk/releases/download/v1.51.0/hk@1.51.0" in text
        assert "v1.45.0/hk@1.45.0" not in text

    def test_pytest_cov_renamed_not_codecov_step(self):
        text = self._text()
        assert '["pytest-cov"]' in text
        assert '["codecov"]' not in text

    def test_pytest_cov_is_slow_profile_only(self):
        block = _step_block(self._text(), "pytest-cov")
        assert 'profiles = List("slow")' in block
        assert "uv run pytest --cov=src/git_cg" in block

    def test_default_fast_steps_present(self):
        text = self._text()
        for step in ("ruff", "ruff-format", "betterleaks", "gen-docs", "gen-toc"):
            assert f'["{step}"]' in text, step

    def test_prepare_and_commit_msg_hooks_still_defined(self):
        text = self._text()
        assert '["prepare-commit-msg"]' in text
        assert '["commit-msg"]' in text
        assert "git-cg" in text
        assert "validate-commit" in text

    def test_pytest_cov_has_no_fix_command(self):
        """pytest-cov is check-only; it must not define a `fix` action."""
        block = _step_block(self._text(), "pytest-cov")
        assert "fix = " not in block

    def test_pre_commit_fix_and_check_hooks_reference_linters_mapping(self):
        """The pre-commit/fix/check hooks must still be wired to the shared `linters` mapping."""
        text = self._text()
        assert _hook_maps_to_linters(text, "pre-commit")
        assert _hook_maps_to_linters(text, "fix")
        assert _hook_maps_to_linters(text, "check")

    def test_pre_commit_hook_still_stashes_and_fixes(self):
        """pre-commit hook must keep `fix = true` and the git stash mechanism."""
        block = _step_block(self._text(), "pre-commit")
        assert "fix = true" in block
        assert 'stash = "git"' in block

    def test_min_hk_version_precedes_linters_mapping(self):
        """min_hk_version must be declared before the linters mapping for readability."""
        text = self._text()
        assert text.index("min_hk_version") < text.index("local linters")

    def test_no_stray_codecov_references_outside_comments(self):
        """Ensure the configuration contains no stray `codecov` step references."""
        text = self._text()
        assert '["codecov"]' not in text
