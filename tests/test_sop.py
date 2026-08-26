import json
import re
from pathlib import Path

from git_cg.sop import load_sop

_COMMIT_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


def test_load_sop_success():
    # The default behavior should successfully load the bundled SOP matrix
    sop_data = load_sop()

    assert isinstance(sop_data, dict)
    assert "gitmoji_reference_matrix" in sop_data

    matrix = sop_data["gitmoji_reference_matrix"]
    assert isinstance(matrix, list)
    assert len(matrix) > 0

    # Check that rows have standard keys
    first_row = matrix[0]
    assert "intent_id" in first_row or "code" in first_row
    assert "emoji" in first_row
    assert "description" in first_row


def test_load_sop_invalid_path(monkeypatch):
    # Simulate user setting an invalid SOP path in the environment
    monkeypatch.setenv("GIT_CG_SOP_PATH", "/path/to/nonexistent/sop.json")

    # Should fall back to repo config or packaged data without crashing
    sop_data = load_sop()
    assert isinstance(sop_data, dict)
    # It should still load the standard matrix
    assert "gitmoji_reference_matrix" in sop_data


# ---------------------------------------------------------------------------
# Tests for the commit_language field added in the localisation PR
# ---------------------------------------------------------------------------


def test_load_sop_contains_commit_language():
    """``load_sop()`` must include the ``commit_language`` key from the config."""
    sop_data = load_sop()
    assert "commit_language" in sop_data, "commit_language must be present in the loaded SOP document"


def test_load_sop_commit_language_is_string():
    """The ``commit_language`` value returned by ``load_sop()`` must be a string."""
    sop_data = load_sop()
    assert isinstance(sop_data["commit_language"], str)


def test_load_sop_commit_language_matches_pattern():
    """``commit_language`` from ``load_sop()`` must match ``^[a-z]{2}-[A-Z]{2}$``."""
    value = load_sop()["commit_language"]
    assert _COMMIT_LANGUAGE_PATTERN.match(value), (
        f"commit_language {value!r} does not match the expected BCP-47-style pattern"
    )


def test_load_sop_per_repo_override_wins(monkeypatch, tmp_path):
    """The per-repo ``.git-cg/sop.json`` override must take precedence over the default SOP.

    We simulate an isolated repository root with a ``.git-cg/sop.json`` that sets a
    distinct ``commit_language``, verifying that ``_deep_merge`` applies it correctly.
    """
    import git_cg.sop as sop_module

    # Create a fake repo root with a config/ dir and .git-cg/ override
    fake_root = tmp_path / "fake_repo"
    fake_root.mkdir()

    # Write a minimal base SOP to config/
    base_sop = {
        "commit_language": "en-US",
        "gitmoji_reference_matrix": [],
    }
    config_dir = fake_root / "config"
    config_dir.mkdir()
    (config_dir / "gitops_agent_sop.json").write_text(json.dumps(base_sop), encoding="utf-8")

    # Write an override to .git-cg/sop.json with a different language
    git_cg_dir = fake_root / ".git-cg"
    git_cg_dir.mkdir()
    (git_cg_dir / "sop.json").write_text(json.dumps({"commit_language": "en-AU"}), encoding="utf-8")

    # Patch the repo-root resolution to point at our fake root
    monkeypatch.setattr(sop_module, "_git_repo_root", lambda: fake_root)

    # Clear the LRU cache so the patched function is invoked
    sop_module.load_sop.cache_clear()
    try:
        result = sop_module.load_sop()
        assert result["commit_language"] == "en-AU", (
            "Per-repo .git-cg/sop.json override should override the base commit_language"
        )
    finally:
        sop_module.load_sop.cache_clear()


def test_load_sop_env_var_override_wins(monkeypatch, tmp_path):
    """An explicit ``GIT_CG_SOP_PATH`` override must take highest precedence for commit_language."""
    import git_cg.sop as sop_module

    # Write a custom SOP file with a distinct commit_language
    custom_sop = {"commit_language": "fr-FR"}
    custom_file = tmp_path / "custom_sop.json"
    custom_file.write_text(json.dumps(custom_sop), encoding="utf-8")

    monkeypatch.setenv("GIT_CG_SOP_PATH", str(custom_file))
    sop_module.load_sop.cache_clear()
    try:
        result = sop_module.load_sop()
        assert result["commit_language"] == "fr-FR", "GIT_CG_SOP_PATH override should set commit_language to fr-FR"
    finally:
        sop_module.load_sop.cache_clear()


def test_deep_merge_commit_language_override():
    """``_deep_merge`` must correctly override a scalar value like ``commit_language``."""
    from git_cg.sop import _deep_merge

    target = {"commit_language": "en-US", "other_key": "value"}
    source = {"commit_language": "en-AU"}
    _deep_merge(target, source)

    assert target["commit_language"] == "en-AU"
    assert target["other_key"] == "value"  # other keys are preserved


def test_deep_merge_does_not_alter_source():
    """``_deep_merge`` must not mutate the source dictionary."""
    from git_cg.sop import _deep_merge

    target = {"commit_language": "en-US"}
    source = {"commit_language": "en-AU"}
    original_source = dict(source)
    _deep_merge(target, source)

    assert source == original_source


# ---------------------------------------------------------------------------
# Changelog-group vocabulary contract (SOP matrix ↔ schema ↔ hook ↔ release)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _REPO_ROOT / "config" / "gitops_sop.schema.json"
_HOOK_PATH = _REPO_ROOT / "scripts" / "validateCommitHook.mjs"


def _schema_changelog_group_enum() -> set[str]:
    """
    Extract the allowed changelog group values from the SOP JSON schema.

    Returns:
        set[str]: The schema-defined changelog group values.
    """
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["properties"]["gitmoji_reference_matrix"]["items"]["properties"]["changelog_group"]["enum"]
    return set(enum)


def _hook_valid_groups() -> set[str]:
    """
    Extract the changelog groups allowed by the commit validation hook.

    Returns:
        set[str]: The set of valid changelog group names.
    """
    text = _HOOK_PATH.read_text(encoding="utf-8")
    match = re.search(r"const validGroups = \[(.*?)\];", text, flags=re.DOTALL)
    assert match, "validGroups array not found in validateCommitHook.mjs"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _matrix_changelog_groups() -> set[str]:
    """Collect the non-empty changelog group values from the loaded SOP matrix.

    Returns:
        set[str]: The set of non-empty changelog group names from matrix rows.
    """
    matrix = load_sop()["gitmoji_reference_matrix"]
    groups: set[str] = set()
    for row in matrix:
        raw = row.get("changelog_group")
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            groups.add(value)
    return groups


def test_sop_validates_against_schema():
    """Bundled SOP must validate against gitops_sop.schema.json (incl. changelog_group enum)."""
    from jsonschema import Draft202012Validator

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    sop = load_sop()
    errors = sorted(Draft202012Validator(schema).iter_errors(sop), key=lambda e: list(e.absolute_path))
    assert not errors, "SOP schema validation failed:\n" + "\n".join(
        f"- {list(e.absolute_path)}: {e.message}" for e in errors[:20]
    )


def test_schema_changelog_group_enum_is_collapsed_taxonomy():
    """Schema enum is the collapsed Keep-a-Changelog taxonomy only (Issue #182).

    Chores/docs/tests/build intents map to Miscellaneous in the matrix; the finer
    names (Documentation, Tests, Chores) are hook/release render-only aliases and
    must not re-enter the matrix enum.
    """
    enum = _schema_changelog_group_enum()
    assert enum == {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security", "Miscellaneous"}
    assert not ({"Documentation", "Tests", "Chores"} & enum)


def test_matrix_changelog_groups_are_schema_enum_members():
    """Every matrix changelog_group must be in the schema enum (no silent authority drift)."""
    enum = _schema_changelog_group_enum()
    matrix_groups = _matrix_changelog_groups()
    unknown = sorted(g for g in matrix_groups if g not in enum)
    assert not unknown, f"Matrix changelog_group values missing from schema enum: {unknown}"


def test_hook_allowlist_covers_schema_and_matrix_groups():
    """Ensure the commit hook allowlist includes every changelog group defined by the schema and SOP matrix."""
    enum = _schema_changelog_group_enum()
    matrix_groups = _matrix_changelog_groups()
    hook = _hook_valid_groups()
    required = enum | matrix_groups
    missing = sorted(required - hook)
    assert not missing, f"validateCommitHook.mjs validGroups missing: {missing}"


def test_release_mapping_covers_schema_and_matrix_groups():
    """Release mapper must resolve every schema/matrix changelog_group to a gold heading."""
    from git_cg.release import CHANGELOG_GROUP_TO_GITHUB_SECTION, GITHUB_CHANGELOG_SECTION_ORDER

    enum = _schema_changelog_group_enum()
    matrix_groups = _matrix_changelog_groups()
    required = enum | matrix_groups
    missing = sorted(g for g in required if g not in CHANGELOG_GROUP_TO_GITHUB_SECTION)
    assert not missing, f"CHANGELOG_GROUP_TO_GITHUB_SECTION missing keys: {missing}"

    gold = set(GITHUB_CHANGELOG_SECTION_ORDER)
    bad_targets = sorted(
        {
            f"{g} -> {CHANGELOG_GROUP_TO_GITHUB_SECTION[g]}"
            for g in required
            if CHANGELOG_GROUP_TO_GITHUB_SECTION[g] not in gold
        }
    )
    assert not bad_targets, f"Mapped headings outside gold order: {bad_targets}"


def test_changelog_generation_rules_taxonomy_covers_matrix_groups():
    """taxonomy prose must name every matrix changelog_group token in use."""
    sop = load_sop()
    taxonomy = sop.get("changelog_generation_rules", {}).get("taxonomy") or []
    assert isinstance(taxonomy, list) and taxonomy, "changelog_generation_rules.taxonomy must be a non-empty list"
    # Each taxonomy entry starts with "Token: ..."
    named = set()
    for line in taxonomy:
        token = str(line).split(":", 1)[0].strip()
        if token:
            named.add(token)
    matrix_groups = _matrix_changelog_groups()
    missing = sorted(matrix_groups - named)
    assert not missing, f"taxonomy missing matrix groups: {missing}"


# ---------------------------------------------------------------------------
# Dark Launch matrix row (🌑 / :new_moon: / dark_launch)
# ---------------------------------------------------------------------------


def _matrix_rows() -> list[dict]:
    """Return the live SOP gitmoji reference matrix rows."""
    return list(load_sop().get("gitmoji_reference_matrix") or [])


def test_dark_launch_matrix_row_present_and_unique() -> None:
    """🌑 dark_launch must exist exactly once with unique emoji/code/intent_id."""
    import git_cg.sop as sop_module

    sop_module.load_sop.cache_clear()
    matrix = _matrix_rows()
    rows = [r for r in matrix if r.get("intent_id") == "dark_launch"]
    assert len(rows) == 1, f"expected exactly one dark_launch row, found {len(rows)}"
    row = rows[0]

    assert row.get("emoji") == "🌑"
    assert row.get("code") == ":new_moon:"
    assert row.get("cc_type") == "chore"
    assert row.get("semver_impact") == "PATCH"
    assert row.get("changelog_group") == "Changed"
    assert row.get("intent_group") == "config_chore"
    assert int(row.get("priority", 100)) <= 40
    assert int(row.get("specificity", 0)) >= 90

    # Uniqueness across the whole matrix (not only this row)
    assert sum(1 for r in matrix if r.get("emoji") == "🌑") == 1
    assert sum(1 for r in matrix if r.get("code") == ":new_moon:") == 1
    assert sum(1 for r in matrix if r.get("intent_id") == "dark_launch") == 1


def test_dark_launch_matrix_row_does_not_reuse_flag_feature_signals() -> None:
    """Dark-launch positives must not collide with 🚩 feature_flags_update signal tokens."""
    matrix = _matrix_rows()
    dark = next(r for r in matrix if r.get("intent_id") == "dark_launch")
    flags = next(r for r in matrix if r.get("intent_id") == "feature_flags_update")
    dark_pos = set(dark.get("positive_signals") or [])
    flag_pos = set(flags.get("positive_signals") or [])
    overlap = sorted(dark_pos & flag_pos)
    assert not overlap, f"dark_launch shares feature_flags positives: {overlap}"


def test_validate_commit_accepts_dark_launch_hybrid_subject(tmp_path) -> None:
    """scripts/validate_commit.mjs must accept 🌑 chore(...) Hybrid subjects."""
    import os
    import shutil
    import subprocess

    import git_cg.sop as sop_module

    node = shutil.which("node")
    assert node, "node is required to exercise validate_commit.mjs"

    script = _REPO_ROOT / "scripts" / "validate_commit.mjs"
    assert script.is_file(), f"missing {script}"

    # validate_commit.mjs rejects absolute/outside-repo paths; use cwd-relative msg.
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        "🌑 chore(semantic): ship graph refresh behind enable_semantic\n",
        encoding="utf-8",
    )

    sop_module.load_sop.cache_clear()
    proc = subprocess.run(
        [node, str(script), "COMMIT_EDITMSG"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert proc.returncode == 0, (
        f"validate_commit.mjs rejected dark_launch subject\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "PATCH" in proc.stdout or "Commit Validated" in proc.stdout


def test_validate_commit_rejects_dark_launch_emoji_type_mismatch(tmp_path) -> None:
    """🌑 must stay paired with matrix cc_type=chore (not feat)."""
    import os
    import shutil
    import subprocess

    node = shutil.which("node")
    assert node, "node is required to exercise validate_commit.mjs"

    script = _REPO_ROOT / "scripts" / "validate_commit.mjs"
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        "🌑 feat(semantic): ship graph refresh behind enable_semantic\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [node, str(script), "COMMIT_EDITMSG"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "mismatch" in combined.lower() or "MUST be paired" in combined
