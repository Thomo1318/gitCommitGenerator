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
        """
        Read the hk.pkl profile as UTF-8 text.
        
        Returns:
        	str: The complete contents of the hk.pkl profile.
        """
        return HK_PKL.read_text(encoding="utf-8")

    def test_file_exists(self):
        assert HK_PKL.is_file()

    def test_min_hk_version(self):
        text = self._text()
        assert 'min_hk_version = "1.45.0"' in text

    def test_amends_exact_package_aligned_with_mise_pin(self):
        """Verify that the hk package download version matches the pinned mise version."""
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
        """Verify that all required default fast-profile steps are defined."""
        text = self._text()
        for step in ("ruff", "ruff-format", "betterleaks", "gen-docs", "gen-toc"):
            assert f'["{step}"]' in text, step

    def test_prepare_and_commit_msg_hooks_still_defined(self):
        """Verify that the prepare-commit-msg and commit-msg hooks, including their required commands, are defined.
        
        Raises:
        	AssertionError: If either hook or either required command is missing.
        """
        text = self._text()
        assert '["prepare-commit-msg"]' in text
        assert '["commit-msg"]' in text
        assert "git-cg" in text
        assert "validate-commit" in text
