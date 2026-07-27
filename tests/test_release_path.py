import git_cg.release as release_module
from git_cg.release import (
    bump_version_string,
    calculate_global_bump,
    get_commits_since,
    get_last_tag,
    get_modified_files_since,
    group_commits_for_changelog,
    inject_file_versions,
    parse_commit_impact,
    validate_release,
)

# Mock gitmoji matrix for testing fallback parsing
MOCK_GITMOJI_MATRIX = [
    {"emoji": "✨", "code": "sparkles", "cc_type": "feat", "semver_impact": "MINOR", "changelog_group": "Added"},
    {"emoji": "🐛", "code": "bug", "cc_type": "fix", "semver_impact": "PATCH", "changelog_group": "Fixed"},
    {"emoji": "📝", "code": "memo", "cc_type": "docs", "semver_impact": "NONE", "changelog_group": "Changed"},
]


def test_parse_commit_impact_with_trailer():
    """Verify that the machine-readable trailer overrides legacy heuristics."""
    # Note: Using "feat" in subject which usually means MINOR, but trailer says PATCH
    commit_string = (
        "✨ feat: some new feature\n"
        "---COMMIT_BODY---\n"
        "Some details about the feature.\n"
        "\n"
        "SemVer-Impact: PATCH\n"
        "Changelog-Groups: Added\n"
    )
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "PATCH"


def test_parse_commit_impact_with_trailer_major():
    """Verify MAJOR trailer is respected."""
    commit_string = "🐛 fix: fix something small\n---COMMIT_BODY---\nSemVer-Impact: MAJOR\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "MAJOR"


def test_parse_commit_impact_legacy_breaking_body():
    """Verify fallback to BREAKING CHANGE in body when trailer is missing."""
    commit_string = (
        "🐛 fix: fix something small\n---COMMIT_BODY---\nSome details.\n\nBREAKING CHANGE: this changes the API.\n"
    )
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "MAJOR"


def test_parse_commit_impact_legacy_breaking_subject():
    """Verify fallback to BREAKING CHANGE in subject when trailer is missing."""
    commit_string = "BREAKING CHANGE: redesign core engine\n---COMMIT_BODY---\nDetails here.\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "MAJOR"


def test_parse_commit_impact_legacy_bang():
    """Verify fallback to cc_type with ! (e.g. feat!) when trailer is missing."""
    commit_string = "✨ feat!: breaking new feature\n---COMMIT_BODY---\nDetails here.\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "MAJOR"


def test_parse_commit_impact_legacy_cc_type():
    """Verify fallback to cc_type match when trailer is missing."""
    commit_string = "✨ feat(core): a new feature\n---COMMIT_BODY---\nDetails here.\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "MINOR"


def test_parse_commit_impact_legacy_emoji_fallback():
    """Verify fallback to emoji match when cc_type is missing/unrecognized and trailer is missing."""
    commit_string = "🐛 a fix without cc_type\n---COMMIT_BODY---\nDetails here.\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "PATCH"


def test_parse_commit_impact_no_match():
    """Verify NONE is returned when no heuristics match."""
    commit_string = "Initial commit\n---COMMIT_BODY---\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    assert impact == "NONE"


def test_parse_commit_impact_malformed_trailer():
    """Verify malformed trailers are ignored and it falls back."""
    commit_string = "✨ feat: new stuff\n---COMMIT_BODY---\nSemVer-Impact: INVALID_VALUE\n"
    impact = parse_commit_impact(commit_string, MOCK_GITMOJI_MATRIX)
    # The regex r"^SemVer-Impact:\s*(MAJOR|MINOR|PATCH|NONE)" won't match INVALID_VALUE.
    # So it falls back to the cc_type 'feat' which maps to MINOR.
    assert impact == "MINOR"


def test_group_commits_with_trailer():
    """Verify Changelog-Groups trailer splits commit into multiple groups."""
    commits = ["✨ feat: some new feature\n---COMMIT_BODY---\nChangelog-Groups: Added, Changed\n"]
    groups = group_commits_for_changelog(commits, MOCK_GITMOJI_MATRIX)
    assert len(groups["Added"]) == 1
    assert len(groups["Changed"]) == 1
    assert "feat: some new feature" in groups["Added"][0]


def test_group_commits_legacy_fallback():
    """Verify legacy fallback grouping if trailer is missing."""
    commits = ["🐛 fix: squash a bug\n---COMMIT_BODY---\n"]
    groups = group_commits_for_changelog(commits, MOCK_GITMOJI_MATRIX)
    assert len(groups["Fixed"]) == 1
    assert "fix: squash a bug" in groups["Fixed"][0]


def test_bump_version_string_major_on_0x_becomes_minor():
    assert bump_version_string("v0.5.0", "MAJOR") == "v0.6.0"


def test_bump_version_string_minor_patch_and_prefixless():
    assert bump_version_string("1.2.3", "MINOR") == "1.3.0"
    assert bump_version_string("v1.2.3", "PATCH") == "v1.2.4"


def test_bump_version_string_prerelease_from_stable_bumps_patch():
    assert bump_version_string("v1.2.3", "NONE", pre_release="rc") == "v1.2.4-rc.1"


def test_bump_version_string_prerelease_same_token_bumps_counter():
    assert bump_version_string("v1.2.3-rc.1", "NONE", pre_release="rc") == "v1.2.3-rc.2"


def test_bump_version_string_prerelease_switch_token():
    assert bump_version_string("v1.2.3-rc.1", "NONE", pre_release="beta") == "v1.2.3-beta.1"


def test_bump_version_string_finalize_prerelease_on_patch_none():
    assert bump_version_string("v1.2.3-rc.1", "PATCH") == "v1.2.3"
    assert bump_version_string("v1.2.3-rc.1", "NONE") == "v1.2.3"


def test_bump_version_string_prerelease_with_minor_major_patch_bumps():
    assert bump_version_string("v1.2.3", "MINOR", pre_release="rc") == "v1.3.0-rc.1"
    assert bump_version_string("v1.2.3", "MAJOR", pre_release="rc") == "v2.0.0-rc.1"
    assert bump_version_string("v1.2.3", "PATCH", pre_release="rc") == "v1.2.4-rc.1"


def test_bump_version_string_invalid_returns_original(monkeypatch):
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(a))
    assert bump_version_string("not-a-version", "MINOR") == "not-a-version"
    assert printed


def test_calculate_global_bump_precedence():
    commits = [
        "📝 docs: x\n---COMMIT_BODY---\nSemVer-Impact: NONE\n",
        "🐛 fix: y\n---COMMIT_BODY---\nSemVer-Impact: PATCH\n",
        "✨ feat: z\n---COMMIT_BODY---\nSemVer-Impact: MINOR\n",
    ]
    assert calculate_global_bump(commits, MOCK_GITMOJI_MATRIX) == "MINOR"
    commits.append("💥 feat!: break\n---COMMIT_BODY---\nSemVer-Impact: MAJOR\n")
    assert calculate_global_bump(commits, MOCK_GITMOJI_MATRIX) == "MAJOR"


def test_get_last_tag_success_and_failure(monkeypatch):
    monkeypatch.setattr(
        release_module.subprocess,
        "check_output",
        lambda *a, **k: b"v1.2.3\n",
    )
    assert get_last_tag() == "v1.2.3"

    def boom(*a, **k):
        raise release_module.subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(release_module.subprocess, "check_output", boom)
    assert get_last_tag() == ""


def test_get_commits_since_with_and_without_tag(monkeypatch):
    def fake_check_output(cmd, **k):
        if any("v1.0.0..HEAD" in str(c) for c in cmd):
            return b"s1---COMMIT_BODY---b1---COMMIT_DELIM---\ns2---COMMIT_BODY---b2---COMMIT_DELIM---\n"
        return b"only---COMMIT_BODY---x---COMMIT_DELIM---\n"

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    assert len(get_commits_since("v1.0.0")) == 2
    assert len(get_commits_since("")) == 1

    def boom(*a, **k):
        raise release_module.subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(release_module.subprocess, "check_output", boom)
    assert get_commits_since("v1.0.0") == []


def test_get_commits_since_strips_whitespace_around_entries(monkeypatch):
    """Each returned commit entry must have leading/trailing whitespace stripped."""

    def fake_check_output(cmd, **k):
        return (
            b"  \n s1---COMMIT_BODY---b1---COMMIT_DELIM---\n\n   s2---COMMIT_BODY---b2  ---COMMIT_DELIM---  \n"
        )

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    commits = get_commits_since("v1.0.0")
    assert commits == ["s1---COMMIT_BODY---b1", "s2---COMMIT_BODY---b2"]


def test_get_commits_since_filters_out_whitespace_only_entries(monkeypatch):
    """Entries that are empty/whitespace-only after stripping must be dropped, not kept as blanks."""

    def fake_check_output(cmd, **k):
        return b"only---COMMIT_BODY---x---COMMIT_DELIM---\n   \n---COMMIT_DELIM---\n"

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    commits = get_commits_since("")
    assert commits == ["only---COMMIT_BODY---x"]


def test_get_modified_files_since(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    # missing.py is intentionally absent on disk but present in mocked git output

    def fake_check_output(cmd, **k):
        return b"a.py\nmissing.py\n\n"

    monkeypatch.setattr(release_module.subprocess, "check_output", fake_check_output)
    assert get_modified_files_since("v1.0.0") == ["a.py"]

    def boom(*a, **k):
        raise release_module.subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(release_module.subprocess, "check_output", boom)
    assert get_modified_files_since("") == []


def test_validate_release_tag_exists_and_fetch_failure(monkeypatch):
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(str(a[0]) if a else ""))

    def check_call(cmd, **k):
        raise release_module.subprocess.CalledProcessError(1, cmd)

    def check_output(cmd, **k):
        return b"v1.0.0\nv1.1.0\n"

    monkeypatch.setattr(release_module.subprocess, "check_call", check_call)
    monkeypatch.setattr(release_module.subprocess, "check_output", check_output)
    assert validate_release("v1.0.0") is False
    assert any("already exists" in p for p in printed)
    assert validate_release("v9.9.9") is True


def test_validate_release_tag_list_failure_returns_true(monkeypatch):
    monkeypatch.setattr(release_module.subprocess, "check_call", lambda *a, **k: 0)

    def boom(*a, **k):
        raise release_module.subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(release_module.subprocess, "check_output", boom)
    assert validate_release("v1.2.3") is True


def _sop_with_strategies():
    return {
        "specifications_and_standards": {
            "version_injection_matrix": {
                "strategies": {
                    "json": {"extensions": [".json"], "method": "json"},
                    "hash": {"extensions": [".toml", ".yml"], "method": "hash_comment"},
                    "slash": {"extensions": [".js"], "method": "slash_comment"},
                    "block": {"extensions": [".html"], "method": "block_comment"},
                    "py": {"extensions": [".py"], "method": "python_variable"},
                }
            }
        }
    }


def test_inject_file_versions_none_without_prerelease_is_noop(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"version": "1.0.0"}\n', encoding="utf-8")
    inject_file_versions([str(f)], "NONE", _sop_with_strategies(), dry_run=False, verbose=False)
    assert f.read_text(encoding="utf-8") == '{"version": "1.0.0"}\n'


def test_inject_file_versions_no_strategies_returns(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"version": "1.0.0"}\n', encoding="utf-8")
    inject_file_versions([str(f)], "MINOR", {}, dry_run=False, verbose=False)
    assert f.read_text(encoding="utf-8") == '{"version": "1.0.0"}\n'


def test_inject_file_versions_all_methods(tmp_path, monkeypatch):
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(str(a[0]) if a else ""))
    files = {
        "pkg.json": '{"version": "1.0.0"}',
        "cfg.toml": "# version: v2.0.0\n",
        "app.js": "// version: v1.0.0\n",
        "page.html": "<!-- version: v1.0.0 -->\n",
        "mod.py": '__version__ = "1.0.0"\n',
        "skip.txt": "nope\n",
    }
    paths = []
    for name, content in files.items():
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        paths.append(str(p))

    inject_file_versions(paths, "MINOR", _sop_with_strategies(), dry_run=False, verbose=True)
    assert '"1.1.0"' in (tmp_path / "pkg.json").read_text(encoding="utf-8")
    assert "v2.1.0" in (tmp_path / "cfg.toml").read_text(encoding="utf-8")
    assert "v1.1.0" in (tmp_path / "app.js").read_text(encoding="utf-8")
    assert "v1.1.0" in (tmp_path / "page.html").read_text(encoding="utf-8")
    assert "1.1.0" in (tmp_path / "mod.py").read_text(encoding="utf-8")
    assert (tmp_path / "skip.txt").read_text(encoding="utf-8") == "nope\n"
    assert printed


def test_inject_file_versions_dry_run_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: None)
    f = tmp_path / "pkg.json"
    f.write_text('{"version": "1.0.0"}', encoding="utf-8")
    inject_file_versions([str(f)], "PATCH", _sop_with_strategies(), dry_run=True, verbose=True)
    assert f.read_text(encoding="utf-8") == '{"version": "1.0.0"}'


def test_inject_file_versions_verbose_error_on_unreadable(tmp_path, monkeypatch):
    printed = []
    monkeypatch.setattr(release_module.console, "print", lambda *a, **k: printed.append(str(a[0]) if a else ""))
    missing = str(tmp_path / "nope.json")
    inject_file_versions([missing], "MINOR", _sop_with_strategies(), dry_run=False, verbose=True)
    assert any("Could not inject" in p for p in printed)


def test_group_commits_rebuckets_miscellaneous_trailer():
    matrix = [
        {"emoji": "✅", "code": "white_check_mark", "cc_type": "test", "priority": 50, "changelog_group": "Tests"},
        {"emoji": "📝", "code": "memo", "cc_type": "docs", "priority": 40, "changelog_group": "Documentation"},
    ]
    commits = [
        "✅ test: a\n---COMMIT_BODY---\nChangelog-Groups: Miscellaneous\n",
        "📝 docs: b\n---COMMIT_BODY---\nChangelog-Groups: Miscellaneous\n",
    ]
    groups = group_commits_for_changelog(commits, matrix)
    assert "Tests" in groups and "Documentation" in groups
    assert "Miscellaneous" not in groups


def test_group_commits_sorts_within_section_by_priority():
    matrix = [
        {"emoji": "🐛", "code": "bug", "cc_type": "fix", "priority": 50, "changelog_group": "Fixed"},
        {"emoji": "🚑", "code": "ambulance", "cc_type": "fix", "priority": 90, "changelog_group": "Fixed"},
    ]
    commits = [
        "🐛 fix: low\n---COMMIT_BODY---\nChangelog-Groups: Fixed\n",
        "🚑 fix: high\n---COMMIT_BODY---\nChangelog-Groups: Fixed\n",
    ]
    groups = group_commits_for_changelog(commits, matrix)
    subjects = groups["Fixed"]
    assert subjects[0].startswith("🚑")
    assert subjects[1].startswith("🐛")


def test_group_commits_for_changelog_unmatched_subject_sorts_last_with_zero_priority():
    """A subject with no matching gitmoji entry defaults to priority 0 and sorts last."""
    matrix = [
        {"emoji": "🐛", "code": "bug", "cc_type": "fix", "priority": 50, "changelog_group": "Fixed"},
    ]
    commits = [
        "Unrecognised commit with no emoji\n---COMMIT_BODY---\nChangelog-Groups: Fixed\n",
        "🐛 fix: known\n---COMMIT_BODY---\nChangelog-Groups: Fixed\n",
    ]
    groups = group_commits_for_changelog(commits, matrix)
    subjects = groups["Fixed"]
    assert subjects[0].startswith("🐛 fix: known")
    assert subjects[1].startswith("Unrecognised commit")


def test_group_commits_for_changelog_deduplicates_subject_within_same_group():
    """The same subject repeated for the same resolved group must not be duplicated."""
    matrix = [
        {"emoji": "🐛", "code": "bug", "cc_type": "fix", "priority": 50, "changelog_group": "Fixed"},
    ]
    commits = ["🐛 fix: dup\n---COMMIT_BODY---\nChangelog-Groups: Fixed, Fixed\n"]
    groups = group_commits_for_changelog(commits, matrix)
    assert groups["Fixed"] == ["🐛 fix: dup"]
