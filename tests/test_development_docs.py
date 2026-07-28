"""
Tests for documentation changes introduced by Issue #170 pipeline hardening
and Issue #161 (Phase 3 SOP-marker intent engine hardening):
  - DEVELOPMENT.md                                  (canonical `mise` quality task docs;
                                                      ADR-0005 phase ownership; branch-naming
                                                      auto-detection convention)
  - docs/ADRs/0002-adopt-gitleaks-and-trufflehog.md  (Update 4 / v1.4.0 pin posture)
  - README.md                                        (Issue Auto-Detection tip)
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEVELOPMENT_MD = REPO_ROOT / "DEVELOPMENT.md"
ADR_0002 = REPO_ROOT / "docs/ADRs/0002-adopt-gitleaks-and-trufflehog.md"
README_MD = REPO_ROOT / "README.md"
CHANGELOG_MD = REPO_ROOT / "CHANGELOG.md"
USAGE_MD = REPO_ROOT / "docs/usage.md"


def _read_development_md() -> str:
    """Return UTF-8 contents of DEVELOPMENT.md (module-level shared reader)."""
    return DEVELOPMENT_MD.read_text(encoding="utf-8")


def _read_changelog_md() -> str:
    """Return UTF-8 contents of CHANGELOG.md (module-level shared reader)."""
    return CHANGELOG_MD.read_text(encoding="utf-8")


def _read_readme_md() -> str:
    """Return UTF-8 contents of README.md (module-level shared reader)."""
    return README_MD.read_text(encoding="utf-8")


def _section_after_heading(content: str, heading: str) -> str:
    """Return content after ``heading`` until the next markdown H2 (or EOF)."""
    if heading not in content:
        raise AssertionError(f"missing heading: {heading}")
    rest = content.split(heading, 1)[1]
    # Stop at the next top-level ## heading so later sections cannot pollute assertions.
    lines = rest.splitlines(keepends=True)
    out: list[str] = []
    for i, line in enumerate(lines):
        if i == 0:
            out.append(line)
            continue
        if line.startswith("## ") and not line.startswith("### "):
            break
        out.append(line)
    return "".join(out)


def _section_after_h3(content: str, heading: str) -> str:
    """Return content after an H3 ``heading`` until the next H2/H3 (or EOF)."""
    if heading not in content:
        raise AssertionError(f"missing heading: {heading}")
    rest = content.split(heading, 1)[1]
    lines = rest.splitlines(keepends=True)
    out: list[str] = []
    for i, line in enumerate(lines):
        if i == 0:
            out.append(line)
            continue
        if line.startswith("## "):
            break
        out.append(line)
    return "".join(out)


# ===========================================================================
# DEVELOPMENT.md
# ===========================================================================


class TestDevelopmentMdCanonicalQualitySection:
    """Tests for the new '📏 Canonical quality commands' section."""

    def _content(self) -> str:
        """Read and return the contents of the development documentation file."""
        return _read_development_md()

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
        return _read_development_md()

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
        return _read_development_md()

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


class TestDevelopmentMdCodecovCliPinExceptionDetailed:
    """Detailed tests for the Codecov CLI pin exception bullet (Issue #170 nice-to-have)."""

    def _content(self) -> str:
        """Read and return the contents of the development documentation file."""
        return _read_development_md()

    def test_accepted_pin_exception_exact_text(self):
        content = self._content()
        assert (
            "Downloaded Codecov CLI from `codecov-action` is an **accepted pin exception** "
            "(action SHA is pinned; CLI binary tracks the action release channel)."
        ) in content

    def test_hermetic_pin_described_as_optional_future_work(self):
        content = self._content()
        assert (
            "A hermetic CLI version pin is optional future work only if supply-chain policy tightens further."
            in content
        )

    def test_old_unconditional_hermetic_wording_removed(self):
        """The old text framing a future hermetic pin as an unconditional addition must be gone."""
        content = self._content()
        assert "unless a future hermetic CLI pin is added" not in content


class TestDevelopmentMdPatchBurnInNote:
    """Detailed tests for the new 'Patch 80% burn-in note' bullet (Issue #170 nice-to-have)."""

    def _content(self) -> str:
        """Read and return the contents of the development documentation file."""
        return _read_development_md()

    def test_patch_burn_in_note_label_and_target_exact_text(self):
        content = self._content()
        assert "**Patch 80% burn-in note:** root patch target stays `80%` with no `paths`/`flags`." in content

    def test_patch_burn_in_note_mentions_main_py_and_component(self):
        content = self._content()
        assert "Huge diffs concentrated in `src/git_cg/main.py` (`cli-main` component)" in content

    def test_patch_burn_in_note_mentions_mitigation_guidance(self):
        content = self._content()
        assert "prefer splitting product changes or accepting a deliberate patch miss" in content
        assert "weakening the global target / component map" in content

    def test_pin_exception_bullet_precedes_patch_burn_in_bullet(self):
        content = self._content()
        assert content.index("accepted pin exception") < content.index("Patch 80% burn-in note")

    def test_both_bullets_within_codecov_upload_policy_section(self):
        """Both new bullets must live inside '### Codecov upload policy', before '### Security / SBOM'."""
        content = self._content()
        section = content.split("### Codecov upload policy", 1)[1].split("### Security / SBOM", 1)[0]
        assert "accepted pin exception" in section
        assert "Patch 80% burn-in note" in section

    def test_security_sbom_section_still_follows_codecov_policy_section(self):
        content = self._content()
        assert content.index("### Codecov upload policy") < content.index("### Security / SBOM")


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


# ===========================================================================
# DEVELOPMENT.md — Issue #161 (Phase 3 intent engine hardening) additions
# ===========================================================================


class TestDevelopmentMdContributionWorkflowBranchNaming:
    """Tests for the updated Contribution Workflow branch-naming guidance."""

    def _content(self) -> str:
        return _read_development_md()

    def test_branch_naming_step_mentions_issue_number_auto_detection(self):
        content = self._content()
        assert "including the issue number in the branch name to enable `git-cg` auto-detection" in content

    def test_branch_naming_step_gives_concrete_example(self):
        content = self._content()
        assert "`feat/123-my-new-feature`" in content

    def test_branch_naming_step_is_first_step_of_contribution_workflow(self):
        """The auto-detection guidance must live in step 1, directly under the workflow heading."""
        content = self._content()
        workflow_section = content.split("## 🤝 Contribution Workflow")[1]
        first_step = workflow_section.strip().splitlines()[0]
        assert first_step.startswith("1. Branch off `main`")
        assert "auto-detection" in first_step


class TestDevelopmentMdAdr0005PhaseOwnership:
    """Tests for the new '## ADR-0005 phase ownership (intent engine)' section."""

    def _content(self) -> str:
        return _read_development_md()

    def test_section_heading_present(self):
        content = self._content()
        assert "## ADR-0005 phase ownership (intent engine)" in content

    def test_section_references_issue_161_as_phase_3(self):
        content = self._content()
        section = _section_after_heading(content, "## ADR-0005 phase ownership (intent engine)")
        assert "Phase 3" in section
        assert "Issue #161" in section

    def test_phase_ownership_table_covers_all_documented_phases(self):
        content = self._content()
        section = _section_after_heading(content, "## ADR-0005 phase ownership (intent engine)")
        assert "**Phase 3** (#161)" in section
        assert "**Phase 0.5**" in section
        assert "**Phase 7**" in section
        assert "**Phase 11**" in section
        assert "**Out of scope**" in section

    def test_phase_ownership_table_lists_expected_concerns(self):
        content = self._content()
        section = _section_after_heading(content, "## ADR-0005 phase ownership (intent engine)")
        assert "preflight_" in section
        assert "Preflight multi-group product" in section
        assert "Semantic summary object / graph product metrics" in section
        assert "Token-budget prompt assembly (`prompt_budget.py`)" in section
        assert "CRG embeddings" in section

    def test_analysis_vs_prompt_diff_subsection_present(self):
        content = self._content()
        assert "### Analysis vs prompt diff (interim until Phase 11)" in content

    def test_analysis_vs_prompt_diff_documents_extract_git_diff_contract(self):
        content = self._content()
        section = content.split("### Analysis vs prompt diff (interim until Phase 11)")[1]
        assert "`extract_git_diff()` returns the **full** staged analysis diff" in section

    def test_analysis_vs_prompt_diff_documents_pack_prompt_diff_contract(self):
        content = self._content()
        section = content.split("### Analysis vs prompt diff (interim until Phase 11)")[1]
        assert "`pack_prompt_diff()`" in section
        assert "not** the Phase 11 packer product" in section

    def test_analysis_vs_prompt_diff_subsection_appears_after_ownership_table(self):
        content = self._content()
        section = _section_after_heading(content, "## ADR-0005 phase ownership (intent engine)")
        # Ownership table ends at the Out of scope row; subsection must follow that row.
        table_end_marker = "**Out of scope**"
        assert table_end_marker in section
        assert section.index(table_end_marker) < section.index("### Analysis vs prompt diff (interim until Phase 11)")


# ===========================================================================
# README.md — Issue #161 Issue Auto-Detection tip
# ===========================================================================


class TestReadmeIssueAutoDetectionTip:
    """Tests for the new '> [!TIP] Issue Auto-Detection' callout in README.md."""

    def _content(self) -> str:
        return _read_readme_md()

    def test_file_exists(self):
        assert README_MD.is_file()

    def test_tip_callout_present(self):
        content = self._content()
        assert "> [!TIP]" in content
        assert "Issue Auto-Detection" in content

    def test_tip_explains_branch_name_hyphen_convention(self):
        content = self._content()
        assert "branch name contains an issue number separated by a hyphen" in content

    def test_tip_gives_concrete_branch_example(self):
        content = self._content()
        assert "`feat/123-new-badge`" in content

    def test_tip_documents_resolves_trailer_behavior(self):
        content = self._content()
        assert "`git-cg` will automatically detect it and append `Resolves: #123`" in content


class TestDevelopmentMdIssue177BaselineAndFloors:
    """Issue #177 WP0 baseline evidence and WP1 dependency floor docs."""

    def _content(self) -> str:
        return _read_development_md()

    def test_wp0_baseline_section_present(self):
        content = self._content()
        heading = "### Evidence expectations (Issue #177 WP0 baseline)"
        assert heading in content
        section = _section_after_h3(content, heading)
        assert "44c9d3e31220b953541ebb724e4f5bc8802897d8" in section
        assert "29995846892" in section  # ci.yml run id
        assert "Deferred Phase 3 leftovers" in section

    def test_dependency_floors_section_present(self):
        content = self._content()
        heading = "### Dependency floors (Issue #177 WP1)"
        assert heading in content
        section = _section_after_h3(content, heading)
        assert "tree-sitter-language-pack" in section
        assert ">=0.13,<1" in section
        assert "| `pytest` | `>=9`" in section or "pytest` | `>=9`" in section
        assert ">=0.26,<0.27" in section
        assert "rich" in section

    def test_wp6_deferred_pin_bumps_section(self):
        content = self._content()
        assert "### Deferred pin bumps (Issue #177 WP6)" in content
        assert "ruff" in content
        assert "hk" in content
        assert "instructor" in content
        assert "tree-sitter-language-pack" in content

    def test_wp0_baseline_table_lists_all_ci_workflow_runs(self):
        """Every workflow run link recorded at the #177 baseline must be present."""
        content = self._content()
        section = _section_after_h3(content, "### Evidence expectations (Issue #177 WP0 baseline)")
        for run_id in ("29995846892", "29995847178", "29995846842", "29995846813"):
            assert run_id in section, run_id
        for workflow in ("ci.yml", "security.yml", "docs.yml", "codeql.yml"):
            assert f"CI `{workflow}`" in section, workflow

    def test_wp0_baseline_table_records_branch_and_local_evidence(self):
        content = self._content()
        section = _section_after_h3(content, "### Evidence expectations (Issue #177 WP0 baseline)")
        assert "`main` and `CI/177-deps-actions-and-python-upgrades`" in section
        assert "**1006 passed**" in section
        assert "Python 3.14.5" in section

    def test_wp0_baseline_table_records_deferred_leftovers_and_epic_link(self):
        content = self._content()
        section = _section_after_h3(content, "### Evidence expectations (Issue #177 WP0 baseline)")
        assert "Deferred Phase 3 leftovers" in section
        assert "**none** for this baseline" in section
        assert "Parent epic link" in section
        assert "[#158]" in section

    def test_wp1_dependency_floor_table_rows_have_rationale(self):
        """Each WP1 floor row must document its floor/bound and rationale, not just the name."""
        content = self._content()
        section = _section_after_h3(content, "### Dependency floors (Issue #177 WP1)")
        assert "| `pytest` | `>=9` |" in section
        assert "| `pytest-cov` | `>=7` |" in section
        assert "| `tree-sitter-language-pack` | `>=0.13,<1` |" in section
        assert "| `tree-sitter` | `>=0.26,<0.27` |" in section
        assert "| `rich` | `>=14.3.4,<16` |" in section
        assert "| `code-review-graph` | `>=2.3.7` |" in section
        assert "tests/test_project_config.py" in section

    def test_wp1_dependency_floor_table_explains_ceilings(self):
        content = self._content()
        section = _section_after_h3(content, "### Dependency floors (Issue #177 WP1)")
        assert "CRG `<1` cap" in section
        assert "instructor` 1.15.x requires `rich<15`" in section
        assert "no silent rich 15 / tslp 1.x beyond the CRG `<1` cap" in section

    def test_wp6_deferred_pin_bumps_lists_each_bullet(self):
        content = self._content()
        section = _section_after_h3(content, "### Deferred pin bumps (Issue #177 WP6)")
        assert "**`ruff`** and **`hk`**" in section
        assert "`mise.toml` exact `hk` pin" in section
        assert "`hk.pkl` / `min_hk_version`" in section
        assert "tests/test_hk_config.py` unchanged" in section
        assert "**`rich` 15.x**" in section
        assert "**`tree-sitter-language-pack` 1.x**" in section
        assert "**Dependabot `github-actions` grouping**" in section
        assert '`patterns: ["*"]`' in section

    def test_issue_177_sections_appear_in_documented_order(self):
        """WP0 baseline, WP1 floors, and WP6 deferrals must appear in ascending WP order."""
        content = self._content()
        assert (
            content.index("### Evidence expectations (Issue #177 WP0 baseline)")
            < content.index("### Dependency floors (Issue #177 WP1)")
            < content.index("### Deferred pin bumps (Issue #177 WP6)")
        )

    def test_issue_177_sections_precede_contribution_workflow(self):
        content = self._content()
        assert content.index("### Deferred pin bumps (Issue #177 WP6)") < content.index("## 🤝 Contribution Workflow")


# ===========================================================================
# CHANGELOG.md — Issue #177 Unreleased entries
# ===========================================================================


class TestChangelogUnreleasedIssue177Entries:
    """Tests for CHANGELOG structure after #177 work landed under v0.6.0.

    Historically these assertions targeted a populated ``## Unreleased`` block.
    That content was cut into ``## v0.6.0``; keep Unreleased as the leading
    placeholder and assert #177 evidence on the v0.6.0 section instead.
    """

    def _content(self) -> str:
        return _read_changelog_md()

    def _v0_6_0_section(self) -> str:
        content = self._content()
        return content.split("## v0.6.0", 1)[1].split("## v0.5.0", 1)[0]

    def test_file_exists(self):
        assert CHANGELOG_MD.is_file()

    def test_changelog_document_title_and_unreleased_section(self):
        content = self._content()
        assert content.lstrip().startswith("# Changelog")
        assert "## Unreleased" in content
        # Unreleased remains the first release section after the document H1.
        assert content.index("# Changelog") < content.index("## Unreleased")

    def test_unreleased_precedes_version_sections(self):
        content = self._content()
        assert content.index("## Unreleased") < content.index("## v0.6.0") < content.index("## v0.5.0")

    def test_unreleased_section_has_no_bullets(self):
        """Unreleased is a placeholder once v0.6.0 absorbed the staged entries."""
        content = self._content()
        section = content.split("## Unreleased", 1)[1].split("## v0.6.0", 1)[0]
        bullet_lines = [line for line in section.splitlines() if line.strip().startswith("- ")]
        assert bullet_lines == []

    def test_v0_6_0_security_dependencies_subheading_present(self):
        section = self._v0_6_0_section()
        assert "### 🔒️ Security / Dependencies" in section

    def test_v0_6_0_retains_issue_177_dependency_work(self):
        section = self._v0_6_0_section()
        expected_fragments = [
            "(#177)",
            "python-dotenv",
            "GitHub Actions",
            "pytest",
            "code-review-graph",
        ]
        for fragment in expected_fragments:
            assert fragment in section, fragment

    def test_v0_5_0_section_still_follows_with_features_heading(self):
        """The pre-existing v0.5.0 release section must be preserved below newer cuts."""
        content = self._content()
        assert "## v0.5.0" in content
        v0_5_0_section = content.split("## v0.5.0", 1)[1]
        assert "### ✨ Features" in v0_5_0_section


# ===========================================================================
# docs/usage.md — `git-cg release` gold-standard GitHub notes flags (#181)
# ===========================================================================


class TestUsageMdReleaseFlags:
    """Tests for the expanded 'git-cg release' flags section (Issue #181)."""

    def _content(self) -> str:
        """Return UTF-8 contents of docs/usage.md."""
        return USAGE_MD.read_text(encoding="utf-8")

    def _release_section(self) -> str:
        """Return the `git-cg release` section body, up to the next top-level heading."""
        content = self._content()
        return content.split("## `git-cg release`", 1)[1].split("## Semantic context", 1)[0]

    def test_file_exists(self):
        assert USAGE_MD.is_file()

    def test_usage_line_uses_generic_flags_placeholder(self):
        """The old literal `[--pre-release <IDENTIFIER>]` usage line is replaced by `[FLAGS]`."""
        content = self._content()
        assert "- **Usage**: `git-cg release [FLAGS]`" in content
        assert "- **Usage**: `git-cg release [--pre-release <IDENTIFIER>]`" not in content

    def test_description_mentions_gold_standard_release_notes(self):
        content = self._content()
        assert "**gold-standard GitHub Release notes**" in content
        assert "boundary table, highlights, grouped What\u2019s Changed, compare links" in content

    def test_flags_heading_present(self):
        section = self._release_section()
        assert "### Flags" in section

    def test_dry_run_flag_documented(self):
        section = self._release_section()
        assert "#### `-d --dry-run`" in section
        assert "Print planned changelog and GitHub notes without writing files or publishing." in section

    def test_verbose_flag_documented(self):
        section = self._release_section()
        assert "#### `-v --verbose`" in section
        assert "Enable verbose output." in section

    def test_pre_release_flag_still_documented(self):
        section = self._release_section()
        assert "#### `--pre-release <IDENTIFIER>`" in section
        assert "Add or bump a pre-release identifier (e.g., 'alpha', 'rc')" in section

    def test_theme_flag_documented_with_example(self):
        section = self._release_section()
        assert "#### `--theme <THEME>`" in section
        assert "Semantic Context integration" in section
        assert "🚀 git-cg vX.Y.Z: Semantic Context integration" in section

    def test_notes_file_flag_documents_default_path(self):
        section = self._release_section()
        assert "#### `--notes-file <PATH>`" in section
        assert ".git/GIT_CG_RELEASE_NOTES_<tag>.md" in section

    def test_publish_github_flag_documents_prerelease_default(self):
        section = self._release_section()
        assert "#### `--publish-github`" in section
        assert "Create the GitHub Release via `gh` after preparing files (requires auth)." in section
        assert "Default marks the release as **pre-release**." in section

    def test_github_latest_flag_documented(self):
        section = self._release_section()
        assert "#### `--github-latest`" in section
        assert "mark the GitHub release as latest (not pre-release)" in section

    def test_skip_github_notes_flag_documented(self):
        section = self._release_section()
        assert "#### `--skip-github-notes`" in section
        assert "Only bump versions / CHANGELOG; skip gold-standard GitHub notes assembly." in section

    def test_flags_appear_in_declared_order(self):
        """Flags must be documented in the same order they are declared in main.py's release() signature."""
        section = self._release_section()
        assert (
            section.index("-d --dry-run")
            < section.index("-v --verbose")
            < section.index("--pre-release")
            < section.index("--theme")
            < section.index("--notes-file")
            < section.index("--publish-github")
            < section.index("--github-latest")
            < section.index("--skip-github-notes")
        )


# ===========================================================================
# README.md — Changelog-Groups vocabulary alignment (Documentation/Tests/Chores)
# ===========================================================================


class TestReadmeChangelogGroupsVocabularyAlignment:
    """Tests for the Hybrid changelog vocabulary alignment (adds Documentation/Tests/Chores)."""

    def _content(self) -> str:
        return _read_readme_md()

    def _matrix_section(self) -> str:
        content = self._content()
        return _section_after_heading(content, "#### Gitmoji Reference Matrix")

    def test_file_exists(self):
        assert README_MD.is_file()

    def test_issue_reference_trailer_example_uses_documentation_not_miscellaneous(self):
        """The structured-issue-reference example must no longer bucket docs under Miscellaneous."""
        content = self._content()
        assert "Changelog-Groups: Fixed, Documentation" in content
        assert "Changelog-Groups: Fixed, Miscellaneous" not in content

    def test_hybrid_commit_example_trailer_drops_trailing_miscellaneous(self):
        """The Hybrid Commits example must resolve refactor/fix/build to Changed, Fixed only."""
        content = self._content()
        assert "Changelog-Groups: Changed, Fixed" in content
        assert "Changelog-Groups: Changed, Fixed, Miscellaneous" not in content

    def test_matrix_section_present_and_non_trivial(self):
        section = self._matrix_section()
        assert "| Emoji | Code" in section
        assert section.count("\n|") > 50

    def test_matrix_contains_chores_documentation_and_tests_columns(self):
        """New hybrid tokens must actually appear as Changelog Group column values."""
        section = self._matrix_section()
        assert "| Chores" in section
        assert "| Documentation" in section
        assert "| Tests" in section

    @staticmethod
    def _changelog_group_cell(line: str) -> str:
        """Return the Changelog Group cell value without depending on column padding."""
        cells = [c.strip() for c in line.split("|")]
        # Markdown tables: ['', col1, col2, ..., colN, '']
        meaningful = [c for c in cells if c != ""]
        assert meaningful, f"empty table row: {line!r}"
        return meaningful[-1]

    def test_matrix_chore_and_ci_rows_use_chores_not_miscellaneous(self):
        """Representative chore/ci rows must resolve to the new Chores token."""
        section = self._matrix_section()
        assert "`:rocket:`" in section
        rocket_line = next(line for line in section.splitlines() if ":rocket:" in line)
        assert self._changelog_group_cell(rocket_line) == "Chores"
        ci_line = next(line for line in section.splitlines() if ":construction_worker:" in line)
        assert self._changelog_group_cell(ci_line) == "Chores"

    def test_matrix_docs_rows_use_documentation_not_miscellaneous(self):
        section = self._matrix_section()
        memo_line = next(line for line in section.splitlines() if ":memo:" in line)
        assert self._changelog_group_cell(memo_line) == "Documentation"

    def test_matrix_test_rows_use_tests_not_miscellaneous(self):
        section = self._matrix_section()
        check_line = next(line for line in section.splitlines() if ":white_check_mark:" in line)
        assert self._changelog_group_cell(check_line) == "Tests"

    def test_matrix_miscellaneous_is_narrowed_to_exactly_four_rows(self):
        """Only init/tada, refactor/poop, refactor/beers, and release/bookmark remain Miscellaneous."""
        section = self._matrix_section()
        misc_lines = [line for line in section.splitlines() if "Miscellaneous" in line]
        assert len(misc_lines) == 4
        for code in (":tada:", ":poop:", ":beers:", ":bookmark:"):
            assert any(code in line for line in misc_lines), f"expected {code} row to remain Miscellaneous"


# ===========================================================================
# docs/ADRs/0007-Integrate-gum-for-terminalnative-git-hook-tui.md
# ===========================================================================

ADR_0007 = REPO_ROOT / "docs/ADRs/0007-Integrate-gum-for-terminalnative-git-hook-tui.md"


class TestAdr0007Refinement7Section:
    """Tests for the appended 'Refinement 7: Changelog-Groups vocabulary alignment' section."""

    def _content(self) -> str:
        return ADR_0007.read_text(encoding="utf-8")

    def _refinement_7_section(self) -> str:
        content = self._content()
        heading = "## VI. Refinement 7: Changelog-Groups vocabulary alignment (v1.7.0)"
        return _section_after_heading(content, heading)

    def test_file_exists(self):
        assert ADR_0007.is_file()

    def test_refinement_7_heading_present(self):
        content = self._content()
        assert "## VI. Refinement 7: Changelog-Groups vocabulary alignment (v1.7.0)" in content

    def test_refinement_7_explains_sop_matrix_rebucket_catalyst(self):
        section = self._refinement_7_section()
        assert "### 1. Architectural Catalyst" in section
        assert "Changelog-Groups: Miscellaneous" in section
        assert "first-class `Chores` token" in section
        assert "`Documentation`, `Tests`, and `Chores` as closed vocabulary" in section

    def test_refinement_7_updated_decision_forbids_rewriting_history(self):
        section = self._refinement_7_section()
        assert "### 2. Updated Decision" in section
        assert "Do **not** rewrite historical Refinement 2 examples." in section
        assert "validateCommitHook.mjs" in section

    def test_refinement_7_corrected_example_uses_chores_token(self):
        section = self._refinement_7_section()
        assert "#### Corrected present-day example (non-historical)" in section
        assert "Changelog-Groups: Chores" in section
        assert "Change-Types: ci, chore" in section

    def test_refinement_7_implementation_guidance_present(self):
        section = self._refinement_7_section()
        assert "### 3. Implementation Guidance" in section
        assert "Prefer matrix-authored `changelog_group` values over free-text groups." in section

    def test_historical_refinement_2_example_is_not_rewritten(self):
        """Append-only guarantee: Refinement 2's original example must keep 'Miscellaneous'."""
        content = self._content()
        refinement_2_heading = "## III. Refinement 2: Structured Issue Reference Review Metadata (v1.2.0)"
        refinement_2_section = _section_after_heading(content, refinement_2_heading)
        assert "Changelog-Groups: Miscellaneous" in refinement_2_section
        assert "Changelog-Groups: Chores" not in refinement_2_section

    def test_changelog_has_v1_7_0_entry_documenting_refinement_7(self):
        content = self._content()
        changelog_section = _section_after_heading(content, "## CHANGELOG")
        assert (
            "v1.7.0 (2026-07-27): Added Refinement 7 documenting append-only Changelog-Groups vocabulary "
            "alignment (`Chores` / `Documentation` / `Tests`) without rewriting historical Refinement 2 examples."
        ) in changelog_section

    def test_changelog_entries_remain_in_ascending_version_order(self):
        """v1.7.0 must be the last (most recent) CHANGELOG bullet, after v1.6.0."""
        content = self._content()
        changelog_section = _section_after_heading(content, "## CHANGELOG")
        assert changelog_section.index("v1.6.0") < changelog_section.index("v1.7.0")
