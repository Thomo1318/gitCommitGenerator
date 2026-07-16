import json
import re

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
