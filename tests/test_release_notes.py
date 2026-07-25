"""Tests for gold-standard GitHub release notes assembly (Issue #181)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import git_cg.release as release_module
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


# ---------------------------------------------------------------------------
# Additional edge cases for existing gold-standard helpers
# ---------------------------------------------------------------------------


def test_format_release_title_default_theme_when_empty():
    title = format_release_title(new_tag="v1.0.0", theme="")
    assert title == "🚀 git-cg v1.0.0: Release"


def test_group_commits_for_github_sections_empty_commits_returns_empty_dict():
    assert group_commits_for_github_sections([], MOCK_GITMOJI_MATRIX) == {}


def test_group_commits_for_github_sections_custom_group_kept_as_is():
    """A Changelog-Groups value with no known mapping must be preserved verbatim as its own section."""
    commits = [_c("🔧 chore: custom thing", "Changelog-Groups: TotallyCustomGroup\n")]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert "TotallyCustomGroup" in groups
    assert any("custom thing" in s for s in groups["TotallyCustomGroup"])


def test_group_commits_for_github_sections_deduplicates_subjects_within_a_section():
    """The same subject mapped into the same section twice must not be duplicated."""
    commits = [
        _c("✨ feat: add x", "Changelog-Groups: Added\n"),
        _c("✨ feat: add x", "Changelog-Groups: Features\n"),
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert groups["✨ Features"].count("✨ feat: add x") == 1


def test_format_changelog_markdown_empty_commits_still_has_heading():
    md = format_changelog_markdown(new_tag="v0.1.0", commits=[], gitmoji_matrix=MOCK_GITMOJI_MATRIX)
    assert md == "## v0.1.0\n"


def test_build_github_release_notes_no_previous_tag_uses_releases_tag_link():
    body = build_github_release_notes(
        ReleaseNotesInput(
            new_tag="v0.1.0",
            previous_tag="",
            theme="Initial release",
            bump_type="MINOR",
            commits=[],
            gitmoji_matrix=MOCK_GITMOJI_MATRIX,
        )
    )
    assert "releases/tag/v0.1.0" in body
    assert "compare/" not in body


def test_build_github_release_notes_pads_uneven_scope_rows():
    body = build_github_release_notes(
        ReleaseNotesInput(
            new_tag="v0.2.0",
            previous_tag="v0.1.0",
            theme="Pad check",
            bump_type="PATCH",
            commits=[],
            gitmoji_matrix=MOCK_GITMOJI_MATRIX,
            in_scope=["only in scope"],
            out_of_scope=["out A", "out B"],
        )
    )
    assert "| only in scope | out A |" in body
    assert "|  | out B |" in body


def test_write_github_release_notes_file_no_double_newline_when_body_already_ends_with_newline(tmp_path: Path):
    out = write_github_release_notes_file(tmp_path / "n.md", "line one\n")
    assert out.read_text(encoding="utf-8") == "line one\n"


def test_write_github_release_notes_file_overwrites_existing_content(tmp_path: Path):
    path = tmp_path / "n.md"
    write_github_release_notes_file(path, "first")
    out = write_github_release_notes_file(path, "second")
    assert out.read_text(encoding="utf-8") == "second\n"


def test_resolve_release_theme_ignores_non_feat_commits_uses_bump_fallback():
    commits = [_c("🐛 fix: squash a bug", "SemVer-Impact: PATCH\n")]
    theme = resolve_release_theme(None, bump_type="PATCH", commits=commits)
    assert theme == "Patch release"


def test_resolve_release_theme_truncates_long_feat_subject_to_72_chars():
    long_desc = "x" * 100
    commits = [_c(f"✨ feat(core): {long_desc}", "SemVer-Impact: MINOR\n")]
    theme = resolve_release_theme(None, bump_type="MINOR", commits=commits)
    assert len(theme) == 72
    assert theme == long_desc[:72]


def test_resolve_release_theme_unknown_bump_type_returns_release():
    assert resolve_release_theme(None, bump_type="WEIRD", commits=[]) == "Release"


# ---------------------------------------------------------------------------
# create_github_release (Issue #181) — `gh` CLI wrapper
# ---------------------------------------------------------------------------


def test_create_github_release_dry_run_does_not_invoke_gh():
    with patch("git_cg.release.subprocess.check_output") as mock_check_output:
        summary = release_module.create_github_release(
            tag="1.2.3",
            title="My Title",
            body="abcdef",
            repo_slug="acme/repo",
            prerelease=True,
            dry_run=True,
        )
    mock_check_output.assert_not_called()
    assert summary.startswith("[dry-run] gh release create v1.2.3 --repo acme/repo")
    assert "--prerelease" in summary
    assert "(6 bytes notes)" in summary


def test_create_github_release_dry_run_without_prerelease_omits_flag():
    summary = release_module.create_github_release(
        tag="v1.2.3", title="T", body="B", prerelease=False, dry_run=True
    )
    assert "--prerelease" not in summary


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_success_invokes_gh_with_expected_args(mock_check_output):
    mock_check_output.return_value = b"https://github.com/acme/repo/releases/tag/v1.0.0\n"

    url = release_module.create_github_release(
        tag="1.0.0",
        title="Title",
        body="Body text",
        repo_slug="acme/repo",
        prerelease=True,
        dry_run=False,
    )

    assert url == "https://github.com/acme/repo/releases/tag/v1.0.0"
    args, _kwargs = mock_check_output.call_args
    cmd = args[0]
    assert cmd[:4] == ["gh", "release", "create", "v1.0.0"]
    assert "--repo" in cmd and "acme/repo" in cmd
    assert "--title" in cmd and "Title" in cmd
    assert "--prerelease" in cmd


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_without_prerelease_omits_flag(mock_check_output):
    mock_check_output.return_value = b"ok"

    release_module.create_github_release(tag="v1.0.0", title="T", body="B", prerelease=False, dry_run=False)

    args, _kwargs = mock_check_output.call_args
    assert "--prerelease" not in args[0]


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_falls_back_to_constructed_url_when_output_empty(mock_check_output):
    mock_check_output.return_value = b"   "

    url = release_module.create_github_release(
        tag="v2.0.0", title="T", body="B", repo_slug="acme/repo", dry_run=False
    )

    assert url == "https://github.com/acme/repo/releases/tag/v2.0.0"


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_cleans_up_temp_notes_file_on_success(mock_check_output):
    mock_check_output.return_value = b"ok"

    release_module.create_github_release(tag="v1.0.0", title="T", body="B", dry_run=False)

    args, _kwargs = mock_check_output.call_args
    cmd = args[0]
    notes_path = cmd[cmd.index("--notes-file") + 1]
    assert not Path(notes_path).exists()


@patch("git_cg.release.subprocess.check_output", side_effect=FileNotFoundError())
def test_create_github_release_missing_gh_cli_raises_runtime_error(_mock_check_output):
    with pytest.raises(RuntimeError, match="`gh` CLI not found"):
        release_module.create_github_release(tag="v1.0.0", title="T", body="B", dry_run=False)


def test_create_github_release_gh_failure_raises_runtime_error_with_detail_and_cleans_up_temp_file():
    captured: dict[str, str] = {}

    def fake_check_output(cmd, **_kwargs):
        captured["notes_path"] = cmd[cmd.index("--notes-file") + 1]
        raise subprocess.CalledProcessError(1, cmd, output=b"not authenticated")

    with patch("git_cg.release.subprocess.check_output", side_effect=fake_check_output):
        with pytest.raises(RuntimeError, match="not authenticated"):
            release_module.create_github_release(tag="v1.0.0", title="T", body="B", dry_run=False)

    assert not Path(captured["notes_path"]).exists()


# ---------------------------------------------------------------------------
# execute_release orchestration (Issue #181 GitHub notes wiring)
# ---------------------------------------------------------------------------

_FEAT_COMMIT = _c("✨ feat: add semantic context", "Changelog-Groups: Added\nSemVer-Impact: MINOR\n")


def _patch_release_collaborators(monkeypatch, *, commits, last_tag="v0.5.0"):
    """Stub out git/SOP collaborators of execute_release so tests run without a real git repo."""
    monkeypatch.setattr(release_module, "get_sop_data", lambda: {"gitmoji_reference_matrix": MOCK_GITMOJI_MATRIX})
    monkeypatch.setattr(release_module, "get_last_tag", lambda: last_tag)
    monkeypatch.setattr(release_module, "get_commits_since", lambda _tag: commits)
    monkeypatch.setattr(release_module, "get_modified_files_since", lambda _tag: [])
    monkeypatch.setattr(release_module, "validate_release", lambda _tag: True)


def _printed_text(mock_print: MagicMock) -> str:
    return "\n".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)


def test_execute_release_skip_github_notes_only_updates_changelog(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])

    release_module.execute_release(dry_run=False, verbose=False, skip_github_notes=True)

    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v0.6.0" in changelog
    assert not (tmp_path / ".git").exists()


def test_execute_release_dry_run_writes_no_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])

    release_module.execute_release(dry_run=True, verbose=False)

    assert not (tmp_path / "CHANGELOG.md").exists()
    assert not (tmp_path / ".git").exists()


def test_execute_release_dry_run_with_publish_calls_create_github_release_in_dry_run_mode(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_create = MagicMock(return_value="[dry-run] gh release create v0.6.0 ...")
    monkeypatch.setattr(release_module, "create_github_release", mock_create)

    release_module.execute_release(dry_run=True, verbose=False, publish_github=True)

    mock_create.assert_called_once()
    _args, kwargs = mock_create.call_args
    assert kwargs["dry_run"] is True
    assert kwargs["tag"] == "v0.6.0"
    assert not (tmp_path / "CHANGELOG.md").exists()


def test_execute_release_writes_notes_file_at_custom_path_when_not_skipped(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    notes_path = tmp_path / "notes" / "out.md"

    release_module.execute_release(dry_run=False, verbose=False, notes_path=str(notes_path))

    assert notes_path.exists()
    body = notes_path.read_text(encoding="utf-8")
    assert "## 📝 Release Notes" in body
    assert "🚀 git-cg v0.6.0:" in body
    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v0.6.0" in changelog


def test_execute_release_default_notes_path_is_under_dot_git(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])

    release_module.execute_release(dry_run=False, verbose=False)

    default_notes = tmp_path / ".git" / "GIT_CG_RELEASE_NOTES_v0.6.0.md"
    assert default_notes.exists()


def test_execute_release_publish_github_success_prints_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_print = MagicMock()
    monkeypatch.setattr(release_module.console, "print", mock_print)
    mock_create = MagicMock(return_value="https://github.com/acme/repo/releases/tag/v0.6.0")
    monkeypatch.setattr(release_module, "create_github_release", mock_create)

    release_module.execute_release(dry_run=False, verbose=False, publish_github=True)

    mock_create.assert_called_once()
    _args, kwargs = mock_create.call_args
    assert kwargs["tag"] == "v0.6.0"
    assert kwargs["prerelease"] is True
    assert kwargs["dry_run"] is False
    assert "GitHub release created" in _printed_text(mock_print)


def test_execute_release_publish_github_failure_is_handled_gracefully(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_print = MagicMock()
    monkeypatch.setattr(release_module.console, "print", mock_print)
    monkeypatch.setattr(
        release_module,
        "create_github_release",
        MagicMock(side_effect=RuntimeError("gh not authenticated")),
    )

    # Must not raise, and must not lose the already-prepared files.
    release_module.execute_release(dry_run=False, verbose=False, publish_github=True)

    printed = _printed_text(mock_print)
    assert "GitHub publish failed" in printed
    assert (tmp_path / "CHANGELOG.md").exists()
    assert (tmp_path / ".git" / "GIT_CG_RELEASE_NOTES_v0.6.0.md").exists()


def test_execute_release_hint_includes_prerelease_flag_by_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_print = MagicMock()
    monkeypatch.setattr(release_module.console, "print", mock_print)

    release_module.execute_release(dry_run=False, verbose=False, publish_github=False)

    assert "--prerelease" in _printed_text(mock_print)


def test_execute_release_hint_omits_prerelease_flag_when_github_latest_requested(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_print = MagicMock()
    monkeypatch.setattr(release_module.console, "print", mock_print)

    release_module.execute_release(dry_run=False, verbose=False, publish_github=False, github_prerelease=False)

    assert "--prerelease" not in _printed_text(mock_print)


def test_execute_release_merges_new_version_after_existing_unreleased_section(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(
        "# Changelog\n\n## Unreleased\n\n## v0.5.0\n\n### Added\n\n- old entry\n",
        encoding="utf-8",
    )

    release_module.execute_release(dry_run=False, verbose=False, skip_github_notes=True)

    content = changelog_path.read_text(encoding="utf-8")
    assert content.index("## Unreleased") < content.index("## v0.6.0") < content.index("## v0.5.0")
    assert "- old entry" in content
