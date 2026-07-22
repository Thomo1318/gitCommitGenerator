"""
Tests for documentation changes introduced by Issue #170 pipeline hardening:
  - DEVELOPMENT.md                                  (canonical `mise` quality task docs)
  - docs/ADRs/0002-adopt-gitleaks-and-trufflehog.md  (Update 4 / v1.4.0 pin posture)
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEVELOPMENT_MD = REPO_ROOT / "DEVELOPMENT.md"
ADR_0002 = REPO_ROOT / "docs/ADRs/0002-adopt-gitleaks-and-trufflehog.md"


# ===========================================================================
# DEVELOPMENT.md
# ===========================================================================


class TestDevelopmentMdCanonicalQualitySection:
    """Tests for the new '📏 Canonical quality commands' section."""

    def _content(self) -> str:
        """Read and return the contents of the development documentation file."""
        return DEVELOPMENT_MD.read_text(encoding="utf-8")

    def test_file_exists(self):
        assert DEVELOPMENT_MD.is_file()

    def test_canonical_section_heading_present(self):
        content = self._content()
        assert "## 📏 Canonical quality commands (`mise` vs `just`)" in content

    def test_just_lint_and_test_meanings_documented_as_unchanged(self):
        content = self._content()
        assert "`just lint` | Zsh syntax check of legacy scripts" in content
        assert "`just test` | Temporary-repo `git-cg` smoke dry-run" in content

    def test_do_not_redefine_warning_present(self):
        content = self._content()
        assert "**Do not redefine** `just lint` / `just test`" in content

    def test_mise_run_lint_documented(self):
        content = self._content()
        assert "`mise run lint`" in content
        assert "HK_SKIP_STEPS=pytest-cov,betterleaks,gen-docs,gen-toc" in content

    def test_mise_run_test_documented(self):
        content = self._content()
        assert "`mise run test`" in content
        assert "Full project `pytest` suite" in content

    def test_mise_run_cov_documented(self):
        content = self._content()
        assert "`mise run cov`" in content
        assert "--cov=src/git_cg --cov-branch" in content

    def test_mise_run_security_documented(self):
        content = self._content()
        assert "`mise run security`" in content
        assert "SBOM + Grant + Grype" in content

    def test_hk_profiles_subsection_present(self):
        content = self._content()
        assert "### `hk` profiles" in content
        assert "**Fast (default pre-commit):**" in content
        assert "**Slow:**" in content
        assert "**CI lint:**" in content
        assert "**PR CI:**" in content
        assert "**Version contract:**" in content
        assert 'min_hk_version = "1.45.0"' in content

    def test_codecov_upload_policy_subsection_present(self):
        content = self._content()
        assert "### Codecov upload policy" in content
        assert "**Same-repository** uploads only" in content
        assert "use_oidc: true" in content
        assert "`id-token: write` is scoped **only** to the coverage upload job" in content
        assert "**Fork PRs skip upload**" in content

    def test_security_sbom_subsection_present(self):
        content = self._content()
        assert "### Security / SBOM" in content
        assert "TruffleHog Action is **SHA-pinned**" in content
        assert "no `curl \\| sh`" in content
        assert "if: ${{ env.ACT != 'true' }}" in content

    def test_evidence_expectations_subsection_present(self):
        content = self._content()
        assert "### Evidence expectations (Issue #170 close-out)" in content
        assert "Same-repo PR with successful OIDC Codecov upload" in content
        assert "Fork PR with upload skipped and CI green" in content
        assert "Security workflow success with SBOM artifact + Grype threshold" in content


class TestDevelopmentMdGitHooksSectionUpdated:
    """The pre-commit hook description must reflect the fast/slow profile split."""

    def _content(self) -> str:
        """Read and return the contents of the development documentation file."""
        return DEVELOPMENT_MD.read_text(encoding="utf-8")

    def test_pre_commit_description_mentions_fast_local_path(self):
        content = self._content()
        assert "Fast local path" in content
        assert "`ruff`, `ruff-format`, `betterleaks`" in content

    def test_pre_commit_description_mentions_slow_profile_coverage(self):
        content = self._content()
        assert "slow-profile only" in content
        assert "`hk check --slow` / `mise run cov`" in content

    def test_stale_gitleaks_pre_commit_description_removed(self):
        """The old text describing gitleaks as the pre-commit tool must be gone."""
        content = self._content()
        assert "Automatically runs `gitleaks` and other pre-commit checks." not in content


class TestDevelopmentMdContributionWorkflowUpdated:
    """The contribution workflow must reference the new canonical mise tasks."""

    def _content(self) -> str:
        """Read and return the contents of the development documentation file."""
        return DEVELOPMENT_MD.read_text(encoding="utf-8")

    def test_contribution_step_references_mise_run_lint_and_test(self):
        """Verify that the contribution workflow documents the canonical lint and test commands."""
        content = self._content()
        assert "Ensure `mise run lint` and `mise run test` pass locally" in content

    def test_contribution_step_still_mentions_just_as_secondary(self):
        content = self._content()
        assert "keep `just lint` / `just test` green if you touch those surfaces" in content

    # ===========================================================================
    # docs/ADRs/0002-adopt-gitleaks-and-trufflehog.md
    # ===========================================================================

    def test_codecov_cli_pin_exception_and_patch_burn_in_note(self):
        """Issue #170 nice-to-have: document Codecov CLI pin exception and main.py patch burn-in."""
        content = self._content()
        assert "Codecov CLI" in content
        assert "pin exception" in content
        assert "80%" in content
        assert "main.py" in content or "cli-main" in content


class TestAdr0002Update4Section:
    """Tests for 'Update 4: betterleaks-local / TruffleHog-CI pin posture (v1.4.0)'."""

    def _content(self) -> str:
        """Read and return the ADR content as UTF-8 text.

        Returns:
            str: The contents of the ADR document.
        """
        return ADR_0002.read_text(encoding="utf-8")

    def test_file_exists(self):
        assert ADR_0002.is_file()

    def test_update_4_heading_present(self):
        content = self._content()
        assert "## V. Update 4: betterleaks-local / TruffleHog-CI pin posture (v1.4.0)" in content

    def test_update_4_is_marked_append_only(self):
        content = self._content()
        assert "Append-only clarification for Issue #170." in content
        assert "Historical gitleaks text above is preserved." in content

    def test_current_posture_table_lists_all_layers(self):
        content = self._content()
        assert "### Current posture" in content
        assert "Local pre-commit (fast)" in content
        assert "**betterleaks** via `hk.pkl`" in content
        assert "CI secrets (deep)" in content
        assert "**TruffleHog** GitHub Action" in content
        assert "SBOM / vuln / license" in content
        assert "**Syft / Grype / Grant** via mise" in content
        assert "Coverage upload" in content
        assert "**Codecov** OIDC" in content

    def test_pin_bar_subsection_present(self):
        content = self._content()
        assert "### Pin bar" in content
        assert "use **full commit SHAs**" in content
        assert "TruffleHog `version:` input" in content
        assert "Floating `@main` / tool `latest` is rejected" in content

    def test_update_4_references_issue_170_and_hk_docs(self):
        """Verify that the ADR Update 4 section references Issue #170 and the relevant hk and TruffleHog documentation."""
        content = self._content()
        section = content.split("## V. Update 4")[1]
        assert "Issue #170" in section
        assert "https://hk.jdx.dev/configuration.html" in section
        assert "https://github.com/trufflesecurity/trufflehog" in section

    def test_changelog_has_v1_4_0_entry(self):
        content = self._content()
        changelog = content.split("## CHANGELOG")[1]
        assert "v1.4.0 (2026-07-21)" in changelog
        assert "betterleaks-local / TruffleHog-CI dual posture" in changelog
        assert "Codecov same-repo OIDC (Issue #170)" in changelog

    def test_changelog_entries_remain_in_reverse_or_documented_order(self):
        """The new v1.4.0 entry must appear before the older v1.0.0-v1.3.0 entries."""
        content = self._content()
        changelog = content.split("## CHANGELOG")[1]
        assert changelog.index("v1.4.0") < changelog.index("v1.0.0")
        assert (
            changelog.index("v1.0.0")
            < changelog.index("v1.1.0")
            < changelog.index("v1.2.0")
            < changelog.index("v1.3.0")
        )

    def test_update_4_section_appears_after_update_3(self):
        """Verify that the ADR's Update 4 section appears after Update 3."""
        content = self._content()
        assert content.index("## IV. Update 3") < content.index("## V. Update 4")

    def test_frontmatter_version_is_v1_4_0(self):
        """Verify that ADR-0002 frontmatter declares version v1.4.0 instead of v1.3.0."""
        content = self._content()
        frontmatter = content.split("```yaml")[1].split("```")[0]
        assert 'version: "v1.4.0"' in frontmatter
        assert 'version: "v1.3.0"' not in frontmatter
