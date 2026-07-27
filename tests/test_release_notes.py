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
    {"emoji": "🔧", "code": "wrench", "cc_type": "chore", "semver_impact": "NONE", "changelog_group": "Chores"},
    {"emoji": "🎨", "code": "art", "cc_type": "style", "semver_impact": "NONE", "changelog_group": "Changed"},
    {"emoji": "⚡️", "code": "zap", "cc_type": "perf", "semver_impact": "PATCH", "changelog_group": "Changed"},
    {"emoji": "♻️", "code": "recycle", "cc_type": "refactor", "semver_impact": "PATCH", "changelog_group": "Changed"},
    {
        "emoji": "👷",
        "code": "construction_worker",
        "cc_type": "ci",
        "semver_impact": "NONE",
        "changelog_group": "Chores",
    },
    {"emoji": "📦", "code": "package", "cc_type": "build", "semver_impact": "NONE", "changelog_group": "Changed"},
    {"emoji": "⏪", "code": "rewind", "cc_type": "revert", "semver_impact": "PATCH", "changelog_group": "Changed"},
    {"emoji": "🎉", "code": "tada", "cc_type": "init", "semver_impact": "MINOR", "changelog_group": "Miscellaneous"},
    {
        "emoji": "🔖",
        "code": "bookmark",
        "cc_type": "release",
        "semver_impact": "NONE",
        "changelog_group": "Miscellaneous",
    },
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
    assert any("guard bools" in s for s in groups["🐛 Bug Fixes"])
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
    assert "### 🐛 Bug Fixes" in body
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


def test_prepend_changelog_does_not_treat_prerelease_heading_as_final():
    """## v0.6.0-rc.1 must not suppress insertion of ## v0.6.0."""
    from git_cg.release import _prepend_changelog_version

    old = "# Changelog\n\n## Unreleased\n\n## v0.6.0-rc.1\n\n### Added\n\n- rc only\n"
    block = "## v0.6.0\n\n### Added\n\n- final\n"
    out = _prepend_changelog_version(old, block, "v0.6.0")
    assert "## v0.6.0\n" in out
    assert out.index("## v0.6.0\n") < out.index("## v0.6.0-rc.1")
    # exact final heading present as its own line
    assert any(line.strip() == "## v0.6.0" for line in out.splitlines())


def test_format_release_title_default_theme_when_empty():
    title = format_release_title(new_tag="v1.0.0", theme="")
    assert title == "🚀 git-cg v1.0.0: Release"


def test_group_commits_for_github_sections_empty_commits_returns_empty_dict():
    assert group_commits_for_github_sections([], MOCK_GITMOJI_MATRIX) == {}


def test_group_commits_for_github_sections_unknown_group_buckets_to_miscellaneous():
    """Unmapped Changelog-Groups values must land under Miscellaneous, not ad-hoc headings."""
    commits = [_c("🔧 chore: custom thing", "Changelog-Groups: TotallyCustomGroup\n")]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert "TotallyCustomGroup" not in groups
    assert "Miscellaneous" in groups
    assert any("custom thing" in s for s in groups["Miscellaneous"])


def test_group_commits_for_github_sections_deduplicates_subjects_within_a_section():
    """The same subject mapped into the same section twice must not be duplicated."""
    commits = [
        _c("✨ feat: add x", "Changelog-Groups: Added\n"),
        _c("✨ feat: add x", "Changelog-Groups: Features\n"),
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    feature_subjects = [s.strip() for s in groups["✨ Features"]]
    assert feature_subjects.count("✨ feat: add x") == 1


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
            require_existing_tag=False,
        )
    mock_check_output.assert_not_called()
    assert summary.startswith("[dry-run] gh release create v1.2.3 --repo acme/repo")
    assert "--prerelease" in summary
    assert "6 bytes notes" in summary


def test_create_github_release_dry_run_without_prerelease_omits_flag():
    summary = release_module.create_github_release(
        tag="v1.2.3",
        title="T",
        body="B",
        prerelease=False,
        dry_run=True,
        require_existing_tag=False,
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
        require_existing_tag=False,
    )

    assert url == "https://github.com/acme/repo/releases/tag/v1.0.0"
    args, kwargs = mock_check_output.call_args
    cmd = args[0]
    assert cmd[:4] == ["gh", "release", "create", "v1.0.0"]
    assert "--repo" in cmd and "acme/repo" in cmd
    assert "--title" in cmd and "Title" in cmd
    assert "--prerelease" in cmd
    assert "--target" not in cmd
    assert kwargs.get("timeout") == release_module.GH_RELEASE_TIMEOUT_SECONDS


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_without_prerelease_omits_flag(mock_check_output):
    mock_check_output.return_value = b"ok"

    release_module.create_github_release(
        tag="v1.0.0", title="T", body="B", prerelease=False, dry_run=False, require_existing_tag=False
    )

    args, _kwargs = mock_check_output.call_args
    assert "--prerelease" not in args[0]


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_falls_back_to_constructed_url_when_output_empty(mock_check_output):
    mock_check_output.return_value = b"   "

    url = release_module.create_github_release(
        tag="v2.0.0",
        title="T",
        body="B",
        repo_slug="acme/repo",
        dry_run=False,
        require_existing_tag=False,
    )

    assert url == "https://github.com/acme/repo/releases/tag/v2.0.0"


@patch("git_cg.release.subprocess.check_output")
def test_create_github_release_cleans_up_temp_notes_file_on_success(mock_check_output):
    mock_check_output.return_value = b"ok"

    release_module.create_github_release(tag="v1.0.0", title="T", body="B", dry_run=False, require_existing_tag=False)

    args, _kwargs = mock_check_output.call_args
    cmd = args[0]
    notes_path = cmd[cmd.index("--notes-file") + 1]
    assert not Path(notes_path).exists()


@patch("git_cg.release.subprocess.check_output", side_effect=FileNotFoundError())
def test_create_github_release_missing_gh_cli_raises_runtime_error(_mock_check_output):
    with pytest.raises(RuntimeError, match="`gh` CLI not found"):
        release_module.create_github_release(
            tag="v1.0.0", title="T", body="B", dry_run=False, require_existing_tag=False
        )


def test_create_github_release_gh_failure_raises_runtime_error_with_detail_and_cleans_up_temp_file():
    captured: dict[str, str] = {}

    def fake_check_output(cmd, **_kwargs):
        captured["notes_path"] = cmd[cmd.index("--notes-file") + 1]
        raise subprocess.CalledProcessError(1, cmd, output=b"not authenticated")

    with (
        patch("git_cg.release.subprocess.check_output", side_effect=fake_check_output),
        pytest.raises(RuntimeError, match="not authenticated"),
    ):
        release_module.create_github_release(
            tag="v1.0.0", title="T", body="B", dry_run=False, require_existing_tag=False
        )

    assert not Path(captured["notes_path"]).exists()


# ---------------------------------------------------------------------------
# execute_release orchestration (Issue #181 GitHub notes wiring)
# ---------------------------------------------------------------------------

_FEAT_COMMIT = _c("✨ feat: add semantic context", "Changelog-Groups: Added\nSemVer-Impact: MINOR\n")


def _patch_release_collaborators(monkeypatch, *, commits, last_tag="v0.5.0", repo_slug="acme/repo"):
    """Stub out git/SOP collaborators of execute_release so tests run without a real git repo."""
    monkeypatch.setattr(release_module, "get_sop_data", lambda: {"gitmoji_reference_matrix": MOCK_GITMOJI_MATRIX})
    monkeypatch.setattr(release_module, "get_last_tag", lambda: last_tag)
    monkeypatch.setattr(release_module, "get_commits_since", lambda _tag: commits)
    monkeypatch.setattr(release_module, "get_modified_files_since", lambda _tag: [])
    monkeypatch.setattr(release_module, "validate_release", lambda _tag: True)
    monkeypatch.setattr(
        release_module,
        "detect_repo_slug",
        lambda explicit=None, allow_default=True: explicit or repo_slug,
    )


def _printed_text(mock_print: MagicMock) -> str:
    return "\n".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)


def test_execute_release_skip_github_notes_only_updates_changelog(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_detect = MagicMock(side_effect=AssertionError("detect_repo_slug must not run on skip_github_notes"))
    monkeypatch.setattr(release_module, "detect_repo_slug", mock_detect)

    release_module.execute_release(dry_run=False, verbose=False, skip_github_notes=True)

    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v0.6.0" in changelog
    assert not (tmp_path / ".git").exists()
    mock_detect.assert_not_called()


def test_execute_release_repo_slug_failure_before_mutations_writes_nothing(monkeypatch, tmp_path):
    """Failed repo detection must abort before version/changelog mutations when notes are enabled."""
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    mock_detect = MagicMock(side_effect=RuntimeError("no remote"))
    mock_inject = MagicMock()
    monkeypatch.setattr(release_module, "detect_repo_slug", mock_detect)
    monkeypatch.setattr(release_module, "inject_file_versions", mock_inject)

    release_module.execute_release(dry_run=False, verbose=False, publish_github=True, repo_slug=None)

    mock_detect.assert_called_once()
    mock_inject.assert_not_called()
    assert not (tmp_path / "CHANGELOG.md").exists()
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

    release_module.execute_release(dry_run=True, verbose=False, publish_github=True, repo_slug="acme/repo")

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
    assert "compare/v0.5.0...v0.6.0" in body
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

    release_module.execute_release(dry_run=False, verbose=False, publish_github=True, repo_slug="acme/repo")

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
    release_module.execute_release(dry_run=False, verbose=False, publish_github=True, repo_slug="acme/repo")

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


# ---------------------------------------------------------------------------
# Review-finding regressions (PR #183)
# ---------------------------------------------------------------------------


def test_parse_github_slug_from_remote_ssh_and_https():
    assert release_module._parse_github_slug_from_remote("git@github.com:Acme/Repo.git") == "Acme/Repo"
    assert release_module._parse_github_slug_from_remote("https://github.com/Acme/Repo.git") == "Acme/Repo"
    assert release_module._parse_github_slug_from_remote("not-a-remote") == ""


def test_detect_repo_slug_prefers_explicit_then_remote(monkeypatch):
    assert release_module.detect_repo_slug(" explicit/repo.git ") == "explicit/repo"

    monkeypatch.setattr(
        release_module.subprocess,
        "check_output",
        lambda *a, **k: "git@github.com:from/remote.git\n",
    )
    assert release_module.detect_repo_slug(None) == "from/remote"


def test_detect_repo_slug_disallow_default_raises(monkeypatch):
    def boom(*_a, **_k):
        raise FileNotFoundError("no git")

    monkeypatch.setattr(release_module.subprocess, "check_output", boom)
    with pytest.raises(RuntimeError, match="Could not detect GitHub owner/repo"):
        release_module.detect_repo_slug(None, allow_default=False)


def test_effective_semver_bump_type_downgrades_major_on_0x():
    assert release_module.effective_semver_bump_type("v0.5.0", "MAJOR") == "MINOR"
    assert release_module.effective_semver_bump_type("v1.2.0", "MAJOR") == "MAJOR"
    assert release_module.effective_semver_bump_type("v0.5.0", "PATCH") == "PATCH"


def test_prepend_changelog_inserts_after_h1_when_unreleased_missing():
    from git_cg.release import _prepend_changelog_version

    old = "# Changelog\n\n## v0.5.0\n\n### Added\n\n- old\n"
    block = "## v0.6.0\n\n### Added\n\n- new\n"
    out = _prepend_changelog_version(old, block, "v0.6.0")
    assert out.startswith("# Changelog\n")
    assert out.index("# Changelog") < out.index("## v0.6.0") < out.index("## v0.5.0")


def test_prepend_changelog_blank_line_when_unreleased_has_body_without_next_heading():
    from git_cg.release import _prepend_changelog_version

    old = "# Changelog\n\n## Unreleased\n\n- pending\n"
    block = "## v0.6.0\n\n### Added\n\n- new\n"
    out = _prepend_changelog_version(old, block, "v0.6.0")
    assert "## Unreleased\n\n- pending\n\n## v0.6.0" in out


def test_create_github_release_requires_existing_tag_by_default(monkeypatch):
    def fake_check_output(cmd, **_kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    with pytest.raises(RuntimeError, match="does not exist locally"):
        release_module.create_github_release(
            tag="v9.9.9", title="T", body="B", dry_run=False, require_existing_tag=True
        )


def test_create_github_release_timeout_raises_runtime_error(monkeypatch):
    def fake_check_output(cmd, **_kwargs):
        # First call is only for gh itself when require_existing_tag=False
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    with pytest.raises(RuntimeError, match="timed out"):
        release_module.create_github_release(
            tag="v1.0.0", title="T", body="B", dry_run=False, require_existing_tag=False
        )


def test_create_github_release_rejects_mismatched_target(monkeypatch):
    def fake_check_output(cmd, **_kwargs):
        joined = " ".join(cmd)
        if "rev-parse" in joined and "v1.0.0" in joined:
            return "aaa111\n"
        if "rev-parse" in joined and "main" in joined:
            return "bbb222\n"
        return b"ok"

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    with pytest.raises(RuntimeError, match="Refusing to publish mismatched refs"):
        release_module.create_github_release(
            tag="v1.0.0",
            title="T",
            body="B",
            target="main",
            dry_run=False,
            require_existing_tag=True,
        )


def test_execute_release_rejects_publish_with_skip_notes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    with pytest.raises(ValueError, match="--publish-github cannot be combined"):
        release_module.execute_release(dry_run=True, verbose=False, publish_github=True, skip_github_notes=True)


def test_execute_release_notes_use_effective_0x_bump(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    breaking = _c("💥 feat!: break api", "Changelog-Groups: Added\nSemVer-Impact: MAJOR\n")
    _patch_release_collaborators(monkeypatch, commits=[breaking], last_tag="v0.5.0")
    monkeypatch.setattr(release_module, "calculate_global_bump", lambda *_a, **_k: "MAJOR")
    notes_path = tmp_path / "notes.md"

    release_module.execute_release(dry_run=False, verbose=False, notes_path=str(notes_path))

    body = notes_path.read_text(encoding="utf-8")
    # Tag is MINOR under 0.x rule 4, and notes must not claim MAJOR.
    assert "v0.6.0" in body
    assert "**MAJOR**" not in body
    assert "**MINOR**" in body


def test_prepend_changelog_idempotent_exact_heading():
    from git_cg.release import _prepend_changelog_version

    old = "# Changelog\n\n## v0.6.0\n\n### Added\n\n- already\n"
    block = "## v0.6.0\n\n### Added\n\n- again\n"
    assert _prepend_changelog_version(old, block, "v0.6.0") == old


def test_prepend_changelog_empty_and_non_changelog_prefix():
    from git_cg.release import _prepend_changelog_version

    block = "## v0.6.0\n\n### Added\n\n- x\n"
    assert _prepend_changelog_version("", block, "0.6.0").startswith("## v0.6.0")
    out = _prepend_changelog_version("notes\n", block, "v0.6.0")
    assert out.startswith("## v0.6.0")
    assert "notes" in out


def test_require_existing_release_tag_success_and_empty_sha(monkeypatch):
    monkeypatch.setattr(
        release_module.subprocess,
        "check_output",
        lambda *a, **k: "abc123\n",
    )
    assert release_module.require_existing_release_tag("v1.0.0") == "abc123"

    monkeypatch.setattr(release_module.subprocess, "check_output", lambda *a, **k: "\n")
    with pytest.raises(RuntimeError, match="Could not resolve commit"):
        release_module.require_existing_release_tag("v1.0.0")


def test_create_github_release_with_matching_target_passes_target(monkeypatch):
    calls = []

    def fake_check_output(cmd, **k):
        calls.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return "deadbeef\n"
        return b"https://github.com/acme/repo/releases/tag/v1.0.0\n"

    monkeypatch.setattr(release_module, "require_existing_release_tag", lambda tag: "deadbeef")
    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    url = release_module.create_github_release(
        tag="v1.0.0",
        title="T",
        body="B",
        repo_slug="acme/repo",
        target="deadbeef",
        dry_run=False,
        require_existing_tag=True,
        prerelease=False,
    )
    assert "releases/tag/v1.0.0" in url
    gh_cmds = [c for c in calls if c and c[0] == "gh"]
    assert gh_cmds
    assert "--target" in gh_cmds[0]
    assert "--prerelease" not in gh_cmds[0]


def test_execute_release_aborts_when_no_bump(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_c("📝 docs: x", "SemVer-Impact: NONE\n")])
    monkeypatch.setattr(release_module, "calculate_global_bump", lambda *_a, **_k: "NONE")
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(str(a[0]) if a else ""))
    release_module.execute_release(dry_run=False, verbose=False, skip_github_notes=True)
    assert any("No changes warrant" in p for p in printed)
    assert not (tmp_path / "CHANGELOG.md").exists()


def test_execute_release_aborts_when_validate_release_false(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    monkeypatch.setattr(release_module, "validate_release", lambda _t: False)
    release_module.execute_release(dry_run=False, verbose=False, skip_github_notes=True)
    assert not (tmp_path / "CHANGELOG.md").exists()


def test_execute_release_invalid_prerelease_on_first_tag(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT], last_tag="")
    monkeypatch.setattr(release_module, "calculate_global_bump", lambda *_a, **_k: "MINOR")
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(str(a[0]) if a else ""))
    release_module.execute_release(dry_run=True, verbose=False, pre_release="bad id!", skip_github_notes=True)
    assert any("Invalid pre-release" in p for p in printed)


def test_execute_release_changelog_write_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(str(a[0]) if a else ""))

    import builtins

    real_open = open

    def open_proxy(file, mode="r", *a, **k):
        if str(file) == "CHANGELOG.md" and "w" in mode:
            raise OSError("disk full")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", open_proxy)
    release_module.execute_release(dry_run=False, verbose=False, skip_github_notes=True)
    assert any("Failed to update CHANGELOG.md" in p for p in printed)


def test_execute_release_verbose_logs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _patch_release_collaborators(monkeypatch, commits=[_FEAT_COMMIT])
    logs = []
    monkeypatch.setattr(release_module.console, "log", lambda *a, **k: logs.append(str(a[0]) if a else ""))
    release_module.execute_release(dry_run=True, verbose=True, skip_github_notes=True)
    assert any("commits since tag" in x for x in logs)


def test_all_commit_types_map_to_gold_headings():
    """Every CommitType / SOP changelog token must resolve to a gold heading."""
    from git_cg.models import CommitType
    from git_cg.release import _CHANGELOG_GROUP_LOOKUP, GITHUB_CHANGELOG_SECTION_ORDER

    gold = set(GITHUB_CHANGELOG_SECTION_ORDER)
    for token in (
        "Added",
        "Changed",
        "Deprecated",
        "Removed",
        "Fixed",
        "Security",
        "Miscellaneous",
        "Tests",
        "Documentation",
        "Chores",
        "Style",
        "Perf",
        "Performance",
        "Refactor",
        "Refactors",
        "Revert",
        "Reverts",
        "Build",
        "CI",
        "Breaking",
        "BreakingChanges",
    ):
        section = _CHANGELOG_GROUP_LOOKUP[token.casefold()]
        assert section in gold, f"{token} -> {section}"

    expected = {
        "feat": "✨ Features",
        "fix": "🐛 Bug Fixes",
        "docs": "📝 Documentation",
        "style": "🎨 Style",
        "refactor": "♻️ Refactors",
        "perf": "⚡️ Performance",
        "test": "✅ Tests",
        "build": "🏗️ Build & CI",
        "ci": "🏗️ Build & CI",
        "chore": "🔧 Chores & Internal",
        "revert": "⏪ Reverts",
        "init": "Miscellaneous",
        "release": "Miscellaneous",
    }
    for ct in CommitType:
        section = _CHANGELOG_GROUP_LOOKUP[ct.value.casefold()]
        assert section == expected[ct.value], f"cc_type {ct.value} -> {section}"
        assert section in gold


def test_github_section_order_is_fixed_gold_not_priority_dynamic():
    """Headings must follow GITHUB_CHANGELOG_SECTION_ORDER; empty heads omitted."""
    commits = [
        _c("🔧 chore: high priority chore", "Changelog-Groups: Chores\n"),
        _c("✨ feat: feature", "Changelog-Groups: Added\n"),
        _c("✅ test: coverage", "Changelog-Groups: Tests\n"),
        _c("📝 docs: usage", "Changelog-Groups: Documentation\n"),
        _c("🐛 fix: bug", "Changelog-Groups: Fixed\n"),
        _c("🔒️ fix(deps): floor", "Changelog-Groups: Security\n"),
        _c("♻️ refactor: tidy", "Changelog-Groups: Refactor\n"),
        _c("⚡️ perf: faster", "Changelog-Groups: Perf\n"),
        _c("🎨 style: format", "Changelog-Groups: Style\n"),
        _c("👷 ci: pipeline", "Changelog-Groups: CI\n"),
        _c("⏪ revert: undo", "Changelog-Groups: Revert\n"),
        _c("💥 feat!: break api", "Changelog-Groups: Added\nSemVer-Impact: MAJOR\n\nBREAKING CHANGE: api\n"),
    ]
    matrix = [
        {"emoji": "🔧", "code": "wrench", "cc_type": "chore", "priority": 99, "changelog_group": "Chores"},
        {"emoji": "✨", "code": "sparkles", "cc_type": "feat", "priority": 10, "changelog_group": "Added"},
        {"emoji": "✅", "code": "white_check_mark", "cc_type": "test", "priority": 50, "changelog_group": "Tests"},
        {"emoji": "📝", "code": "memo", "cc_type": "docs", "priority": 40, "changelog_group": "Documentation"},
        {"emoji": "🐛", "code": "bug", "cc_type": "fix", "priority": 80, "changelog_group": "Fixed"},
        {"emoji": "🔒️", "code": "lock", "cc_type": "fix", "priority": 95, "changelog_group": "Security"},
        {"emoji": "♻️", "code": "recycle", "cc_type": "refactor", "priority": 70, "changelog_group": "Changed"},
        {"emoji": "⚡️", "code": "zap", "cc_type": "perf", "priority": 75, "changelog_group": "Changed"},
        {"emoji": "🎨", "code": "art", "cc_type": "style", "priority": 40, "changelog_group": "Changed"},
        {"emoji": "👷", "code": "construction_worker", "cc_type": "ci", "priority": 65, "changelog_group": "Chores"},
        {"emoji": "⏪", "code": "rewind", "cc_type": "revert", "priority": 75, "changelog_group": "Changed"},
        {"emoji": "💥", "code": "boom", "cc_type": "feat", "priority": 100, "changelog_group": "Added"},
    ]
    md = format_changelog_markdown(
        new_tag="v0.7.0",
        commits=commits,
        gitmoji_matrix=matrix,
        use_github_sections=True,
    )
    heads = [line for line in md.splitlines() if line.startswith("### ")]
    assert heads == [
        "### ✨ Features",
        "### 💥 Breaking Changes",
        "### 🐛 Bug Fixes",
        "### ♻️ Refactors",
        "### ⚡️ Performance",
        "### 📝 Documentation",
        "### ✅ Tests",
        "### 🎨 Style",
        "### 🏗️ Build & CI",
        "### 🔧 Chores & Internal",
        "### 🔒️ Security / Dependencies",
        "### ⏪ Reverts",
    ]

    body = build_github_release_notes(
        ReleaseNotesInput(
            new_tag="v0.7.0",
            previous_tag="v0.6.0",
            theme="Gold Standard Release Notes",
            bump_type="MAJOR",
            commits=commits,
            gitmoji_matrix=matrix,
        )
    )
    changed = body.split("## 📦 What's Changed", 1)[1]
    gh_heads = [line for line in changed.splitlines() if line.startswith("### ")]
    assert gh_heads == heads


def test_empty_optional_headings_are_omitted():
    """Optional heads must not appear when no commits map to them."""
    commits = [_c("✨ feat: only feature", "Changelog-Groups: Added\n")]
    md = format_changelog_markdown(
        new_tag="v0.7.0",
        commits=commits,
        gitmoji_matrix=MOCK_GITMOJI_MATRIX,
        use_github_sections=True,
    )
    heads = [line for line in md.splitlines() if line.startswith("### ")]
    assert heads == ["### ✨ Features"]
    for absent in (
        "💥 Breaking Changes",
        "♻️ Refactors",
        "⚡️ Performance",
        "🎨 Style",
        "🏗️ Build & CI",
        "⏪ Reverts",
        "Miscellaneous",
    ):
        assert f"### {absent}" not in md


def test_cc_type_trailer_aliases_map_to_gold_sections():
    commits = [
        _c("✨ feat: x", "Changelog-Groups: feat\n"),
        _c("🎨 style: y", "Changelog-Groups: style\n"),
        _c("⚡️ perf: z", "Changelog-Groups: perf\n"),
        _c("♻️ refactor: r", "Changelog-Groups: refactor\n"),
        _c("👷 ci: pipeline", "Changelog-Groups: ci\n"),
        _c("📦 build: deps", "Changelog-Groups: build\n"),
        _c("✅ test: t", "Changelog-Groups: test\n"),
        _c("📝 docs: d", "Changelog-Groups: docs\n"),
        _c("🔧 chore: c", "Changelog-Groups: chore\n"),
        _c("⏪ revert: back", "Changelog-Groups: revert\n"),
        _c("🎉 init: start", "Changelog-Groups: init\n"),
        _c("🔖 release: cut", "Changelog-Groups: release\n"),
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("feat: x" in s for s in groups["✨ Features"])
    assert any("style: y" in s for s in groups["🎨 Style"])
    assert any("perf: z" in s for s in groups["⚡️ Performance"])
    assert any("refactor: r" in s for s in groups["♻️ Refactors"])
    assert any("revert: back" in s for s in groups["⏪ Reverts"])
    assert any("test: t" in s for s in groups["✅ Tests"])
    assert any("docs: d" in s for s in groups["📝 Documentation"])
    assert any("ci: pipeline" in s for s in groups["🏗️ Build & CI"])
    assert any("build: deps" in s for s in groups["🏗️ Build & CI"])
    assert any("chore: c" in s for s in groups["🔧 Chores & Internal"])
    assert any("init: start" in s for s in groups["Miscellaneous"])
    assert any("release: cut" in s for s in groups["Miscellaneous"])


def test_legacy_miscellaneous_trailer_rebuckets_via_matrix():
    commits = [
        _c("✅ test: coverage", "Changelog-Groups: Miscellaneous\n"),
        _c("📝 docs: usage", "Changelog-Groups: Miscellaneous\n"),
        _c("🔧 chore: lock", "Changelog-Groups: Miscellaneous\n"),
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("coverage" in s for s in groups["✅ Tests"])
    assert any("usage" in s for s in groups["📝 Documentation"])
    assert any("lock" in s for s in groups["🔧 Chores & Internal"])
    assert "Miscellaneous" not in groups


def test_changed_group_refined_by_cc_type():
    """SOP Changed + subject CC type should split into fine-grained gold heads."""
    commits = [
        _c("♻️ refactor(core): tidy", "Changelog-Groups: Changed\n"),
        _c("⚡️ perf(cli): faster path", "Changelog-Groups: Changed\n"),
        _c("🎨 style: format", "Changelog-Groups: Changed\n"),
        _c("🐛 fix: real bug", "Changelog-Groups: Fixed\n"),
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("tidy" in s for s in groups["♻️ Refactors"])
    assert any("faster path" in s for s in groups["⚡️ Performance"])
    assert any("format" in s for s in groups["🎨 Style"])
    assert any("real bug" in s for s in groups["🐛 Bug Fixes"])


def test_breaking_change_dual_lists_under_breaking_heading():
    commits = [
        _c(
            "✨ feat(api)!: rename endpoint",
            "Changelog-Groups: Added\nSemVer-Impact: MAJOR\n\nBREAKING CHANGE: rename\n",
        )
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("rename endpoint" in s for s in groups["✨ Features"])
    assert any("rename endpoint" in s for s in groups["💥 Breaking Changes"])


def test_non_breaking_refactor_does_not_enter_breaking_heading():
    """Plain refactors with NONE impact must not dual-list under Breaking Changes."""
    commits = [
        _c(
            "🏗️ refactor(adr): document observability hierarchy and resources",
            "Changelog-Groups: Changed\nSemVer-Impact: NONE\n",
        )
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("document observability" in s for s in groups["♻️ Refactors"])
    assert "💥 Breaking Changes" not in groups


def test_major_semver_trailer_alone_dual_lists_under_breaking_heading():
    """SemVer-Impact: MAJOR is sufficient breaking signal without bang subject."""
    commits = [
        _c(
            "♻️ refactor(api): reshape public surface",
            "Changelog-Groups: Changed\nSemVer-Impact: MAJOR\n",
        )
    ]
    groups = group_commits_for_github_sections(commits, MOCK_GITMOJI_MATRIX)
    assert any("reshape public surface" in s for s in groups["♻️ Refactors"])
    assert any("reshape public surface" in s for s in groups["💥 Breaking Changes"])
