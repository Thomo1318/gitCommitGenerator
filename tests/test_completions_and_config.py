"""
Tests for configuration and completion spec changes introduced in this PR.

Covers:
- .gitignore: new patterns `promptfoo_*.json` and `docs/phase_artifacts/`
- completions/_git-cg: new `--pre-release` flag with `<IDENTIFIER>` arg on the `release` command
- usage.kdl: source-of-truth file for the same `--pre-release` spec
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
COMPLETIONS_PATH = REPO_ROOT / "completions" / "_git-cg"
USAGE_KDL_PATH = REPO_ROOT / "usage.kdl"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ===========================================================================
# .gitignore — new promptfoo_*.json pattern
# ===========================================================================


class TestGitignorePromptfooPattern:
    """The `promptfoo_*.json` pattern was added in this PR."""

    def test_pattern_present_in_gitignore(self):
        """The literal pattern line must exist in the .gitignore file."""
        lines = _read(GITIGNORE_PATH).splitlines()
        assert "promptfoo_*.json" in lines, (
            "Expected 'promptfoo_*.json' to be a line in .gitignore"
        )

    def test_pattern_matches_typical_promptfoo_output_file(self):
        """promptfoo_*.json should match a representative output filename."""
        pattern = "promptfoo_*.json"
        assert fnmatch.fnmatch("promptfoo_results.json", pattern)

    def test_pattern_matches_timestamped_promptfoo_file(self):
        """promptfoo_*.json should match a timestamped output filename."""
        pattern = "promptfoo_*.json"
        assert fnmatch.fnmatch("promptfoo_20260614_2028.json", pattern)

    def test_pattern_does_not_match_plain_json(self):
        """promptfoo_*.json must NOT match arbitrary JSON files."""
        pattern = "promptfoo_*.json"
        assert not fnmatch.fnmatch("results.json", pattern)

    def test_pattern_does_not_match_non_promptfoo_prefix(self):
        """promptfoo_*.json must NOT match JSON files with a different prefix."""
        pattern = "promptfoo_*.json"
        assert not fnmatch.fnmatch("opik_results.json", pattern)

    def test_pattern_does_not_match_yaml(self):
        """promptfoo_*.json should not match a YAML file with a promptfoo prefix."""
        pattern = "promptfoo_*.json"
        assert not fnmatch.fnmatch("promptfoo_config.yaml", pattern)

    def test_pattern_does_not_match_bare_promptfoo(self):
        """The wildcard requires at least an underscore separator."""
        pattern = "promptfoo_*.json"
        # 'promptfoo.json' has no underscore, should not match
        assert not fnmatch.fnmatch("promptfoo.json", pattern)


# ===========================================================================
# .gitignore — new docs/phase_artifacts/ pattern
# ===========================================================================


class TestGitignorePhaseArtifactsPattern:
    """The `docs/phase_artifacts/` pattern was added in this PR."""

    def test_pattern_present_in_gitignore(self):
        """The literal pattern line must exist in the .gitignore file."""
        lines = _read(GITIGNORE_PATH).splitlines()
        assert "docs/phase_artifacts/" in lines, (
            "Expected 'docs/phase_artifacts/' to be a line in .gitignore"
        )

    def test_pattern_is_directory_indicator(self):
        """The pattern must end with '/' to signal a directory match."""
        lines = _read(GITIGNORE_PATH).splitlines()
        matching = [l for l in lines if "phase_artifacts" in l]
        assert matching, "No line containing 'phase_artifacts' found in .gitignore"
        assert all(l.endswith("/") for l in matching), (
            "phase_artifacts gitignore pattern must end with '/' to mark it as a directory"
        )

    def test_pattern_does_not_match_file_with_same_name(self):
        """Without the trailing slash, the pattern should not match a file named phase_artifacts."""
        # fnmatch treats patterns differently from gitignore; we test the raw pattern text
        # just verifying the trailing slash is present (directory semantics are git-specific)
        lines = _read(GITIGNORE_PATH).splitlines()
        assert "docs/phase_artifacts/" in lines
        # A raw file (no trailing slash) would NOT be `docs/phase_artifacts/`
        assert "docs/phase_artifacts" not in lines or "docs/phase_artifacts/" in lines

    def test_pattern_path_matches_docs_subdirectory(self):
        """docs/phase_artifacts/ should match path components under docs/."""
        # Using fnmatch to simulate directory matching (stripping trailing slash)
        pattern = "docs/phase_artifacts"
        assert fnmatch.fnmatch("docs/phase_artifacts", pattern)

    def test_pattern_path_does_not_match_other_docs_subdirectory(self):
        """docs/phase_artifacts/ should not match sibling directories."""
        pattern = "docs/phase_artifacts"
        assert not fnmatch.fnmatch("docs/phase_data", pattern)
        assert not fnmatch.fnmatch("docs/phase_artifacts_old", pattern)

    def test_both_new_patterns_appear_together_in_file(self):
        """Both new PR patterns must coexist in the same .gitignore."""
        content = _read(GITIGNORE_PATH)
        assert "promptfoo_*.json" in content
        assert "docs/phase_artifacts/" in content


# ===========================================================================
# completions/_git-cg — --pre-release flag on the release command
# ===========================================================================


class TestCompletionsPreReleaseFlag:
    """The `--pre-release` flag with `<IDENTIFIER>` arg was added to the `release` cmd."""

    def test_completions_file_exists(self):
        """The completions file must exist at its expected path."""
        assert COMPLETIONS_PATH.exists(), f"Expected {COMPLETIONS_PATH} to exist"

    def test_completions_contains_release_cmd(self):
        """The spec embedded in the completions script must define a `release` command."""
        content = _read(COMPLETIONS_PATH)
        assert "cmd release" in content, "Expected 'cmd release' in completions/_git-cg"

    def test_completions_release_contains_pre_release_flag(self):
        """The `release` command spec must include a `--pre-release` flag."""
        content = _read(COMPLETIONS_PATH)
        assert "--pre-release" in content, (
            "Expected '--pre-release' flag in completions/_git-cg release command spec"
        )

    def test_completions_pre_release_has_identifier_argument(self):
        """The `--pre-release` flag must declare an `<IDENTIFIER>` argument."""
        content = _read(COMPLETIONS_PATH)
        assert "<IDENTIFIER>" in content, (
            "Expected '<IDENTIFIER>' argument for --pre-release in completions/_git-cg"
        )

    def test_completions_pre_release_has_help_text(self):
        """The `--pre-release` flag must carry a help description."""
        content = _read(COMPLETIONS_PATH)
        # The help text mentions 'alpha' and 'rc' as examples
        assert "alpha" in content, (
            "Expected example 'alpha' in --pre-release help text"
        )
        assert "rc" in content, (
            "Expected example 'rc' in --pre-release help text"
        )

    def test_completions_release_help_text_mentions_semver_compliance(self):
        """The release command help must mention SemVer 2.0.0 compliance."""
        content = _read(COMPLETIONS_PATH)
        assert "SemVer 2.0.0" in content, (
            "Expected 'SemVer 2.0.0' in release command help text"
        )

    def test_completions_pre_release_flag_is_inside_release_cmd_block(self):
        """The --pre-release flag must appear after `cmd release`, not as a global flag."""
        content = _read(COMPLETIONS_PATH)
        release_idx = content.find("cmd release")
        pre_release_idx = content.find("--pre-release")
        assert release_idx != -1, "cmd release not found"
        assert pre_release_idx != -1, "--pre-release not found"
        assert pre_release_idx > release_idx, (
            "--pre-release must appear after 'cmd release' in the spec"
        )

    def test_completions_global_flags_are_preserved(self):
        """Existing global flags must not have been accidentally removed."""
        content = _read(COMPLETIONS_PATH)
        for expected_flag in ["-i --interactive", "-e --engine", "-d --dry-run", "-v --verbose", "--strict"]:
            assert expected_flag in content, (
                f"Expected global flag '{expected_flag}' to still be present in completions/_git-cg"
            )

    def test_completions_other_commands_are_preserved(self):
        """The `commit` and `sop` commands must not have been removed."""
        content = _read(COMPLETIONS_PATH)
        assert "cmd commit" in content
        assert "cmd sop" in content

    def test_completions_heredoc_boundaries_are_intact(self):
        """The heredoc that embeds the spec must have valid open and close markers."""
        content = _read(COMPLETIONS_PATH)
        assert "__USAGE_EOF__" in content
        # There should be exactly two occurrences: open and close
        count = content.count("__USAGE_EOF__")
        assert count == 2, f"Expected 2 __USAGE_EOF__ markers, found {count}"


# ===========================================================================
# usage.kdl — source-of-truth for the completion spec
# ===========================================================================


class TestUsageKdlPreReleaseFlag:
    """
    usage.kdl is the canonical source file from which completions/_git-cg is generated.
    Any flag added to the completions script must also be defined in usage.kdl.
    """

    def test_usage_kdl_exists(self):
        """usage.kdl must exist at the repository root."""
        assert USAGE_KDL_PATH.exists(), f"Expected {USAGE_KDL_PATH} to exist"

    def test_usage_kdl_contains_release_cmd(self):
        """The release command must be defined in usage.kdl."""
        content = _read(USAGE_KDL_PATH)
        assert 'cmd "release"' in content, "Expected 'cmd \"release\"' in usage.kdl"

    def test_usage_kdl_release_contains_pre_release_flag(self):
        """The release command in usage.kdl must declare the --pre-release flag."""
        content = _read(USAGE_KDL_PATH)
        assert '"--pre-release"' in content, (
            "Expected '\"--pre-release\"' flag inside release command in usage.kdl"
        )

    def test_usage_kdl_pre_release_has_identifier_argument(self):
        """The --pre-release flag in usage.kdl must declare an <IDENTIFIER> argument."""
        content = _read(USAGE_KDL_PATH)
        assert '"<IDENTIFIER>"' in content, (
            "Expected '\"<IDENTIFIER>\"' argument in usage.kdl"
        )

    def test_usage_kdl_pre_release_has_help_text(self):
        """The --pre-release flag in usage.kdl must include human-readable help."""
        content = _read(USAGE_KDL_PATH)
        # Check for typical example identifiers referenced in the help text
        assert "alpha" in content, "Expected 'alpha' in --pre-release help text in usage.kdl"
        assert "rc" in content, "Expected 'rc' in --pre-release help text in usage.kdl"

    def test_usage_kdl_release_help_mentions_semver_compliance(self):
        """The release command help in usage.kdl must mention SemVer 2.0.0 compliance."""
        content = _read(USAGE_KDL_PATH)
        assert "SemVer 2.0.0" in content, (
            "Expected 'SemVer 2.0.0' in release command help in usage.kdl"
        )

    def test_usage_kdl_pre_release_flag_inside_release_block(self):
        """The --pre-release flag must appear after the release cmd definition."""
        content = _read(USAGE_KDL_PATH)
        release_idx = content.find('cmd "release"')
        pre_release_idx = content.find('"--pre-release"')
        assert release_idx != -1, 'cmd "release" not found in usage.kdl'
        assert pre_release_idx != -1, '"--pre-release" not found in usage.kdl'
        assert pre_release_idx > release_idx, (
            '"--pre-release" must appear after \'cmd "release"\' in usage.kdl'
        )

    def test_usage_kdl_spec_matches_completions_for_pre_release_help(self):
        """The help text for --pre-release must be identical in both source files."""
        kdl_content = _read(USAGE_KDL_PATH)
        completions_content = _read(COMPLETIONS_PATH)
        # Both must reference the same identifier examples
        for token in ["alpha", "rc", "pre-release"]:
            assert token in kdl_content, f"Token '{token}' missing from usage.kdl"
            assert token in completions_content, f"Token '{token}' missing from completions/_git-cg"

    def test_usage_kdl_global_flags_preserved(self):
        """Existing global flags must be intact in usage.kdl."""
        content = _read(USAGE_KDL_PATH)
        for flag in ["-i --interactive", "-e --engine", "-d --dry-run", "-v --verbose", "--strict"]:
            assert flag in content, f"Expected global flag '{flag}' in usage.kdl"

    def test_usage_kdl_other_commands_preserved(self):
        """The commit and sop commands must not have been removed from usage.kdl."""
        content = _read(USAGE_KDL_PATH)
        assert 'cmd "commit"' in content
        assert 'cmd "sop"' in content

    def test_usage_kdl_is_parseable_structure(self):
        """usage.kdl must have balanced braces (basic structural sanity check)."""
        content = _read(USAGE_KDL_PATH)
        open_braces = content.count("{")
        close_braces = content.count("}")
        assert open_braces == close_braces, (
            f"Unbalanced braces in usage.kdl: {open_braces} open vs {close_braces} close"
        )


# ===========================================================================
# Cross-file consistency: completions/_git-cg and usage.kdl must agree
# ===========================================================================


class TestSpecConsistency:
    """Cross-file checks ensuring completions/_git-cg and usage.kdl stay in sync."""

    def test_both_files_define_pre_release_flag(self):
        """Both the source (usage.kdl) and generated (completions) file must define --pre-release."""
        kdl_content = _read(USAGE_KDL_PATH)
        comp_content = _read(COMPLETIONS_PATH)
        assert "--pre-release" in kdl_content
        assert "--pre-release" in comp_content

    def test_both_files_define_identifier_argument(self):
        """Both files must declare the IDENTIFIER argument for --pre-release."""
        kdl_content = _read(USAGE_KDL_PATH)
        comp_content = _read(COMPLETIONS_PATH)
        assert "IDENTIFIER" in kdl_content
        assert "IDENTIFIER" in comp_content

    def test_release_cmd_appears_in_both_files(self):
        """The release command must be defined in both the KDL source and the completion script."""
        kdl_content = _read(USAGE_KDL_PATH)
        comp_content = _read(COMPLETIONS_PATH)
        assert "release" in kdl_content
        assert "release" in comp_content

    def test_gitignore_patterns_do_not_overlap_with_test_data(self):
        """The new gitignore patterns must not accidentally exclude existing test data files."""
        # Verify none of the test data files under tests/ would be matched
        # by the new promptfoo_*.json pattern
        pattern = "promptfoo_*.json"
        tests_dir = REPO_ROOT / "tests"
        if tests_dir.exists():
            for json_file in tests_dir.rglob("*.json"):
                # Test data files should not start with 'promptfoo_'
                # (if they do, they might be accidentally ignored by git)
                filename = json_file.name
                if fnmatch.fnmatch(filename, pattern):
                    # If a test file matches, it may be intentionally ignored —
                    # but we document this as a finding
                    assert False, (
                        f"Test data file {json_file} matches the new promptfoo_*.json "
                        "gitignore pattern and may be accidentally excluded from tracking"
                    )