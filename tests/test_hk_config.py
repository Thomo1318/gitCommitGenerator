"""
Regression tests for hk.pkl profile contract (Issue #170 Slice 2).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HK_PKL = REPO_ROOT / "hk.pkl"


class TestHkPklContract:
    def _text(self) -> str:
        return HK_PKL.read_text(encoding="utf-8")

    def test_file_exists(self):
        assert HK_PKL.is_file()

    def test_min_hk_version(self):
        text = self._text()
        assert 'min_hk_version = "1.45.0"' in text

    def test_amends_exact_package_aligned_with_mise_pin(self):
        text = self._text()
        # Exact Pkl package version must match mise.toml hk pin (1.51.0).
        assert "hk/releases/download/v1.51.0/hk@1.51.0" in text
        assert "v1.45.0/hk@1.45.0" not in text

    def test_pytest_cov_renamed_not_codecov_step(self):
        text = self._text()
        assert '["pytest-cov"]' in text
        assert '["codecov"]' not in text

    def test_pytest_cov_is_slow_profile_only(self):
        text = self._text()
        # Extract the pytest-cov block roughly
        m = re.search(r'\["pytest-cov"\]\s*\{(.*?)\n    \}', text, re.S)
        assert m, "pytest-cov step block not found"
        block = m.group(1)
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
        text = self._text()
        m = re.search(r'\["pytest-cov"\]\s*\{(.*?)\n    \}', text, re.S)
        assert m, "pytest-cov step block not found"
        block = m.group(1)
        assert "fix = " not in block

    def test_pre_commit_fix_and_check_hooks_reference_linters_mapping(self):
        """The pre-commit/fix/check hooks must still be wired to the shared `linters` mapping."""
        text = self._text()
        assert re.search(r'\["pre-commit"\]\s*\{[^}]*steps = linters', text, re.S)
        assert re.search(r'\["fix"\]\s*\{[^}]*steps = linters', text, re.S)
        assert re.search(r'\["check"\]\s*\{[^}]*steps = linters', text, re.S)

    def test_pre_commit_hook_still_stashes_and_fixes(self):
        """pre-commit hook must keep `fix = true` and the git stash mechanism."""
        text = self._text()
        m = re.search(r'\["pre-commit"\]\s*\{(.*?)\n    \}', text, re.S)
        assert m, "pre-commit hook block not found"
        block = m.group(1)
        assert "fix = true" in block
        assert 'stash = "git"' in block

    def test_min_hk_version_precedes_linters_mapping(self):
        """min_hk_version must be declared before the linters mapping for readability."""
        text = self._text()
        assert text.index("min_hk_version") < text.index("local linters")

    def test_no_stray_codecov_references_outside_comments(self):
        """Only the renamed pytest-cov step comment references coverage; no leftover `codecov` step."""
        text = self._text()
        assert 'Step {\n    ["codecov"]' not in text
        assert text.count('["codecov"]') == 0
