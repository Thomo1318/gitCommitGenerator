from git_cg.release import group_commits_for_changelog, parse_commit_impact

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
