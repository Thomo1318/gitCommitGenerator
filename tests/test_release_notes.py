"""Tests for gold-standard GitHub release notes assembly (Issue #181)."""

from __future__ import annotations

from pathlib import Path

from git_cg.release import (
    ReleaseNotesInput,
    build_github_release_notes,
    format_changelog_markdown,
    format_release_title,
    group_commits_for_github_sections,
    resolve_release_theme,
    write_github_release_notes_file,
)

MOCK_GITMOJI_MATRIX = [
    {"emoji": "✨", "code": "sparkles", "cc_type": "feat", "semver_impact": "MINOR", "changelog_group": "Added"},
    {"emoji": "🐛", "code": "bug", "cc_type": "fix", "semver_impact": "PATCH", "changelog_group": "Fixed"},
    {"emoji": "📝", "code": "memo", "cc_type": "docs", "semver_impact": "NONE", "changelog_group": "Documentation"},
    {"emoji": "✅", "code": "white_check_mark", "cc_type": "test", "semver_impact": "NONE", "changelog_group": "Tests"},
    {"emoji": "🔧", "code": "wrench", "cc_type": "chore", "semver_impact": "NONE", "changelog_group": "Miscellaneous"},
    {"emoji": "🔒️", "code": "lock", "cc_type": "fix", "semver_impact": "PATCH", "changelog_group": "Security"},
]


def _c(subject: str, body: str = "") -> str:
    return f"{subject}\n---COMMIT_BODY---\n{body}\n"


def test_format_release_title_pattern():
    title = format_release_title(new_tag="0.6.0", theme="Semantic Context integration")
    assert title == "🚀 git-cg v0.6.0: Semantic Context integration"


def test_format_release_title_strips_noise():
    title = format_release_title(new_tag="v1.2.3", theme="  Theme : ")
    assert title == "🚀 git-cg v1.2.3: Theme"


def test_group_commits_maps_trailer_groups_to_github_sections():
    commits = [
        _c("✨ feat: add context", "Changelog-Groups: Added\nSemVer-Impact: MINOR\n"),
        _c("🐛 fix: guard bools", "Changelog-Groups: Fixed\nSemVer-Impact: PATCH\n"),
        _c("📝 docs: usage", "Changelog-Groups: Documentation\n"),
        _c("🔒️ fix(deps): floor", "Changelog-Groups: Security\n"),
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("add context" in s for s in groups["✨ Features"])
    assert any("guard bools" in s for s in groups["🐛 Bug Fixes & Refactors"])
    assert any("usage" in s for s in groups["📝 Documentation"])
    assert any("floor" in s for s in groups["🔒️ Security / Dependencies"])


def test_build_github_release_notes_contains_house_sections():
    commits = [
        _c("✨ feat(semantic): integrate phase 7", "Changelog-Groups: Added\nSemVer-Impact: MINOR\n"),
        _c("🥅 fix(git_cg): guard ints", "Changelog-Groups: Fixed\nSemVer-Impact: PATCH\n"),
        _c("✅ test(semantic): fixtures", "Changelog-Groups: Tests\n"),
    ]
    body = build_github_release_notes(
        ReleaseNotesInput(
            new_tag="v0.6.0",
            previous_tag="v0.5.0",
            theme="Semantic Context integration",
            bump_type="MINOR",
            commits=commits,
            gitmoji_matrix=MOCK_GITMOJI_MATRIX,
            in_scope=["Phase 7 semantic context (#162)"],
            out_of_scope=["Phase 11 packer (#165)"],
            highlights=["**Semantic context** landed behind dark-launch."],
            dx_improvements=["Fail-open graph product path."],
            welcome_blurb="Welcome to **`0.6.0`** of `git-cg`.\n\nPhase 7 ships.",
        )
    )
    assert "## 📝 Release Notes" in body
    assert "### Boundary (read this first)" in body
    assert "| In this release | **Not** in this release |" in body
    assert "Phase 7 semantic context (#162)" in body
    assert "Phase 11 packer (#165)" in body
    assert "**Invariant:**" in body
    assert "### 🌟 Highlights" in body
    assert "### 🛡️ DX & Stability Improvements" in body
    assert "## 📦 What's Changed" in body
    assert "### ✨ Features" in body
    assert "### 🐛 Bug Fixes & Refactors" in body
    assert "### ✅ Tests" in body
    assert "compare/v0.5.0...v0.6.0" in body
    assert "thomo1318.github.io/gitCommitGenerator/CHANGELOG.html" in body


def test_format_changelog_markdown_legacy_groups():
    commits = [_c("✨ feat: x", "Changelog-Groups: Added\n")]
    md = format_changelog_markdown(
        new_tag="v0.6.0",
        commits=commits,
        gitmoji_matrix=MOCK_GITMOJI_MATRIX,
        use_github_sections=False,
    )
    assert md.startswith("## v0.6.0\n")
    assert "### Added" in md


def test_format_changelog_markdown_github_sections():
    commits = [_c("✨ feat: x", "Changelog-Groups: Added\n")]
    md = format_changelog_markdown(
        new_tag="v0.6.0",
        commits=commits,
        gitmoji_matrix=MOCK_GITMOJI_MATRIX,
        use_github_sections=True,
    )
    assert "### ✨ Features" in md


def test_write_github_release_notes_file(tmp_path: Path):
    path = tmp_path / "notes" / "v0.6.0.md"
    out = write_github_release_notes_file(path, "# hi")
    assert out.read_text(encoding="utf-8") == "# hi\n"


def test_resolve_release_theme_explicit():
    assert resolve_release_theme("  My Theme  ", bump_type="MINOR", commits=[]) == "My Theme"


def test_resolve_release_theme_from_feat_commit():
    commits = [_c("✨ feat(core): Semantic Context integration", "SemVer-Impact: MINOR\n")]
    theme = resolve_release_theme(None, bump_type="MINOR", commits=commits)
    assert "Semantic Context integration" in theme


def test_resolve_release_theme_fallback_bump():
    assert resolve_release_theme(None, bump_type="PATCH", commits=[]) == "Patch release"


def test_prepend_changelog_inserts_after_unreleased():
    from git_cg.release import _prepend_changelog_version

    old = "# Changelog\n\n## Unreleased\n\n## v0.5.0\n\n### Added\n\n- old\n"
    block = "## v0.6.0\n\n### Added\n\n- new\n"
    out = _prepend_changelog_version(old, block, "v0.6.0")
    assert out.index("## Unreleased") < out.index("## v0.6.0") < out.index("## v0.5.0")
    assert "- new" in out
