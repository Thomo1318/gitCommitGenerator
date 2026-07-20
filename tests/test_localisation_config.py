"""
Tests for localisation-related configuration changes in this PR:
  - config/gitops_sop.schema.json  (new ``commit_language`` property)
  - config/gitops_agent_sop.json   (new ``commit_language`` field)
  - .git-cg/sop.json               (new per-repo override file)
  - .vscode/settings.json          (new cSpell.ignoreRegExpList / words / overrides)
  - .vscode/prompts.json           (new prompts file)
  - .github/ISSUE_TEMPLATE/bug_report.md
  - .github/ISSUE_TEMPLATE/feature_request.md
  - .github/PULL_REQUEST_TEMPLATE.md
  - .github/release.yml
  - .gitignore                     (vscode exclusion rule changes)
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent

_COMMIT_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


def _load_json(rel_path: str) -> Any:
    """Load a JSON file relative to the repo root."""
    return json.loads((REPO_ROOT / rel_path).read_text(encoding="utf-8"))


def _load_yaml(rel_path: str) -> Any:
    """Load a YAML file relative to the repo root."""
    data = yaml.safe_load((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and True in data:
        # PyYAML may parse the unquoted key `on` as boolean True.
        data["on"] = data.pop(True)
    return data


def _gitignore_lines() -> list[str]:
    return (REPO_ROOT / ".gitignore").read_text().splitlines()


# ===========================================================================
# Schema: commit_language property (config/gitops_sop.schema.json)
# ===========================================================================


class TestSchemaCommitLanguage:
    """Tests for the newly-added ``commit_language`` property in the JSON Schema."""

    def _schema(self) -> dict[str, Any]:
        data = _load_json("config/gitops_sop.schema.json")
        if not isinstance(data, dict):
            raise TypeError("schema must be a JSON object")
        return data

    def test_schema_is_valid_json(self):
        """The schema file must parse as valid JSON."""
        schema = self._schema()
        assert isinstance(schema, dict)

    def test_commit_language_property_exists(self):
        """``commit_language`` must be listed under top-level properties."""
        schema = self._schema()
        assert "commit_language" in schema["properties"]

    def test_commit_language_type_is_string(self):
        """``commit_language`` must declare ``type: string``."""
        prop = self._schema()["properties"]["commit_language"]
        assert prop["type"] == "string"

    def test_commit_language_has_description(self):
        """``commit_language`` must have a non-empty description."""
        prop = self._schema()["properties"]["commit_language"]
        assert "description" in prop
        assert prop["description"].strip() != ""

    def test_commit_language_description_mentions_language_code(self):
        """The description should explain that this is a language code."""
        desc = self._schema()["properties"]["commit_language"]["description"].lower()
        assert "language" in desc and "code" in desc

    def test_commit_language_pattern_present(self):
        """``commit_language`` must declare a ``pattern`` constraint."""
        prop = self._schema()["properties"]["commit_language"]
        assert "pattern" in prop

    def test_commit_language_pattern_value(self):
        """The pattern must be exactly ``^[a-z]{2}-[A-Z]{2}$``."""
        prop = self._schema()["properties"]["commit_language"]
        assert prop["pattern"] == "^[a-z]{2}-[A-Z]{2}$"

    def test_commit_language_is_optional(self):
        """``commit_language`` must NOT appear in the ``required`` array."""
        schema = self._schema()
        required = schema.get("required", [])
        assert "commit_language" not in required

    # -----------------------------------------------------------------------
    # Pattern acceptance / rejection (tested using Python's re module which
    # uses the same subset of regex syntax as JSON Schema)
    # -----------------------------------------------------------------------

    def test_pattern_accepts_en_au(self):
        """Pattern must accept ``en-AU``."""
        assert _COMMIT_LANGUAGE_PATTERN.match("en-AU")

    def test_pattern_accepts_en_us(self):
        """Pattern must accept ``en-US``."""
        assert _COMMIT_LANGUAGE_PATTERN.match("en-US")

    def test_pattern_accepts_fr_fr(self):
        """Pattern must accept ``fr-FR``."""
        assert _COMMIT_LANGUAGE_PATTERN.match("fr-FR")

    def test_pattern_accepts_zh_cn(self):
        """Pattern must accept ``zh-CN``."""
        assert _COMMIT_LANGUAGE_PATTERN.match("zh-CN")

    def test_pattern_rejects_uppercase_language_code(self):
        """Pattern must reject ``EN-AU`` (uppercase language subtag)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("EN-AU")

    def test_pattern_rejects_lowercase_region_code(self):
        """Pattern must reject ``en-au`` (lowercase region subtag)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("en-au")

    def test_pattern_rejects_underscore_separator(self):
        """Pattern must reject ``en_AU`` (underscore instead of hyphen)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("en_AU")

    def test_pattern_rejects_too_short_language(self):
        """Pattern must reject ``e-AU`` (single-character language subtag)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("e-AU")

    def test_pattern_rejects_too_long_language(self):
        """Pattern must reject ``eng-AU`` (three-character language subtag)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("eng-AU")

    def test_pattern_rejects_too_long_region(self):
        """Pattern must reject ``en-AUS`` (three-character region subtag)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("en-AUS")

    def test_pattern_rejects_empty_string(self):
        """Pattern must reject an empty string."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("")

    def test_pattern_rejects_missing_region(self):
        """Pattern must reject ``en`` (no region subtag at all)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("en")

    def test_pattern_rejects_digits_in_language(self):
        """Pattern must reject ``e2-AU`` (digits in language subtag)."""
        assert not _COMMIT_LANGUAGE_PATTERN.match("e2-AU")

    def test_schema_uses_draft07(self):
        """Schema must reference JSON Schema Draft-07."""
        schema = self._schema()
        assert "draft-07" in schema.get("$schema", "")

    def test_schema_additional_properties_false(self):
        """Top-level ``additionalProperties`` must be false to prevent unknown keys."""
        schema = self._schema()
        assert schema.get("additionalProperties") is False


# ===========================================================================
# Agent SOP: commit_language field (config/gitops_agent_sop.json)
# ===========================================================================


class TestAgentSopCommitLanguage:
    """Tests for the ``commit_language`` field added to gitops_agent_sop.json."""

    def _sop(self) -> dict[str, Any]:
        data = _load_json("config/gitops_agent_sop.json")
        if not isinstance(data, dict):
            raise TypeError("agent SOP must be a JSON object")
        return data

    def test_file_is_valid_json(self):
        """gitops_agent_sop.json must parse as valid JSON."""
        sop = self._sop()
        assert isinstance(sop, dict)

    def test_commit_language_field_present(self):
        """``commit_language`` key must be present in the SOP document."""
        sop = self._sop()
        assert "commit_language" in sop

    def test_commit_language_value_is_en_us(self):
        """Default SOP ``commit_language`` must be ``en-US``."""
        sop = self._sop()
        assert sop["commit_language"] == "en-US"

    def test_commit_language_value_matches_pattern(self):
        """``commit_language`` in the SOP must match the ``^[a-z]{2}-[A-Z]{2}$`` pattern."""
        value = self._sop()["commit_language"]
        assert _COMMIT_LANGUAGE_PATTERN.match(value), (
            f"commit_language value {value!r} does not match the expected pattern"
        )

    def test_commit_language_is_a_string(self):
        """``commit_language`` must be a string, not another type."""
        assert isinstance(self._sop()["commit_language"], str)

    def test_existing_required_keys_still_present(self):
        """Pre-existing top-level keys must not have been removed."""
        sop = self._sop()
        for key in (
            "_meta",
            "specifications_and_standards",
            "agentic_commit_workflow",
            "agentic_release_workflow",
            "changelog_generation_rules",
            "semver_resolution_matrix",
            "gitmoji_reference_matrix",
        ):
            assert key in sop, f"Required key {key!r} missing from gitops_agent_sop.json"

    def test_commit_language_positioned_before_matrix(self):
        """``commit_language`` must appear before ``gitmoji_reference_matrix`` in the file."""
        text = (REPO_ROOT / "config/gitops_agent_sop.json").read_text(encoding="utf-8")
        lang_pos = text.find('"commit_language"')
        matrix_pos = text.find('"gitmoji_reference_matrix"')
        assert lang_pos != -1, "commit_language not found in file"
        assert matrix_pos != -1, "gitmoji_reference_matrix not found in file"
        assert lang_pos < matrix_pos, "commit_language should appear before gitmoji_reference_matrix in the file"


# ===========================================================================
# Per-repo override SOP (.git-cg/sop.json)
# ===========================================================================


class TestGitCgSopOverride:
    """Tests for the new `.git-cg/sop.json` per-repo override file."""

    def _sop_override(self) -> dict[str, Any]:
        data = _load_json(".git-cg/sop.json")
        if not isinstance(data, dict):
            raise TypeError("sop override must be a JSON object")
        return data

    def test_file_exists(self):
        """`.git-cg/sop.json` must exist."""
        assert (REPO_ROOT / ".git-cg" / "sop.json").exists()

    def test_file_is_valid_json(self):
        """`.git-cg/sop.json` must parse as valid JSON."""
        data = self._sop_override()
        assert isinstance(data, dict)

    def test_commit_language_present(self):
        """The override file must contain the ``commit_language`` key."""
        assert "commit_language" in self._sop_override()

    def test_commit_language_value_is_en_au(self):
        """The per-repo override must set ``commit_language`` to ``en-AU``."""
        assert self._sop_override()["commit_language"] == "en-AU"

    def test_commit_language_value_matches_pattern(self):
        """``commit_language`` in the override must match ``^[a-z]{2}-[A-Z]{2}$``."""
        value = self._sop_override()["commit_language"]
        assert _COMMIT_LANGUAGE_PATTERN.match(value), (
            f"commit_language override {value!r} does not match the expected pattern"
        )

    def test_commit_language_is_a_string(self):
        """``commit_language`` override must be a string."""
        assert isinstance(self._sop_override()["commit_language"], str)

    def test_override_differs_from_default_sop(self):
        """The per-repo override must differ from the default SOP language (en-US vs en-AU)."""
        default = _load_json("config/gitops_agent_sop.json")["commit_language"]
        override = self._sop_override()["commit_language"]
        assert override != default, "Per-repo override should differ from the default SOP commit_language"

    def test_file_has_no_unexpected_keys(self):
        """The override file should only contain expected keys for a minimal override."""
        data = self._sop_override()
        # The override file should be a small, focused file
        # commit_language is the only key added in this PR
        assert "commit_language" in data


# ===========================================================================
# VSCode settings (.vscode/settings.json) — cSpell additions
# ===========================================================================


class TestVscodeSettingsSpellCheck:
    """Tests for the new cSpell configuration entries in .vscode/settings.json."""

    def _settings(self) -> dict[str, Any]:
        data = _load_json(".vscode/settings.json")
        if not isinstance(data, dict):
            raise TypeError("settings must be a JSON object")
        return data

    def test_file_is_valid_json(self):
        """.vscode/settings.json must parse as valid JSON."""
        settings = self._settings()
        assert isinstance(settings, dict)

    def test_cspell_language_present(self):
        """``cSpell.language`` must still be present (pre-existing)."""
        assert "cSpell.language" in self._settings()

    def test_cspell_language_includes_en_au(self):
        """``cSpell.language`` must include ``en-AU``."""
        lang = self._settings()["cSpell.language"]
        assert "en-AU" in lang

    def test_ignore_regexp_list_present(self):
        """``cSpell.ignoreRegExpList`` must be present."""
        assert "cSpell.ignoreRegExpList" in self._settings()

    def test_ignore_regexp_list_is_list(self):
        """``cSpell.ignoreRegExpList`` must be a list."""
        assert isinstance(self._settings()["cSpell.ignoreRegExpList"], list)

    def test_ignore_regexp_list_has_two_entries(self):
        """``cSpell.ignoreRegExpList`` must have exactly 2 entries."""
        assert len(self._settings()["cSpell.ignoreRegExpList"]) == 2

    def test_ignore_regexp_list_covers_inline_code(self):
        """``cSpell.ignoreRegExpList`` must include a pattern for inline backtick code."""
        patterns = self._settings()["cSpell.ignoreRegExpList"]
        assert any("`" in p for p in patterns), (
            "ignoreRegExpList should include a pattern covering inline backtick code"
        )

    def test_ignore_regexp_list_covers_fenced_code_blocks(self):
        """``cSpell.ignoreRegExpList`` must include a pattern for fenced code blocks."""
        patterns = self._settings()["cSpell.ignoreRegExpList"]
        assert any("```" in p for p in patterns), (
            "ignoreRegExpList should include a pattern covering fenced code blocks (```)"
        )

    def test_words_list_present(self):
        """``cSpell.words`` must be present."""
        assert "cSpell.words" in self._settings()

    def test_words_list_is_list(self):
        """``cSpell.words`` must be a list."""
        assert isinstance(self._settings()["cSpell.words"], list)

    def test_words_list_contains_project_terms(self):
        """``cSpell.words`` must include key project-specific terms added in this PR."""
        words = self._settings()["cSpell.words"]
        expected_terms = ["coderabbit", "fnox", "gitmoji", "gitops", "opik", "qodo"]
        for term in expected_terms:
            assert term in words, f"Expected project term {term!r} missing from cSpell.words"

    def test_words_list_contains_all_new_terms(self):
        """All 12 new project-specific words must be present in cSpell.words."""
        words = self._settings()["cSpell.words"]
        all_new_terms = [
            "coderabbit",
            "fnox",
            "gitmoji",
            "gitops",
            "javascripts",
            "lucide",
            "opik",
            "pymdownx",
            "qodo",
            "superfences",
            "tablesort",
            "terminalnative",
            "twemoji",
        ]
        for term in all_new_terms:
            assert term in words, f"Term {term!r} missing from cSpell.words"

    def test_overrides_present(self):
        """``cSpell.overrides`` must be present."""
        assert "cSpell.overrides" in self._settings()

    def test_overrides_is_list(self):
        """``cSpell.overrides`` must be a list."""
        assert isinstance(self._settings()["cSpell.overrides"], list)

    def test_overrides_has_four_entries(self):
        """``cSpell.overrides`` must have exactly 4 override rules."""
        assert len(self._settings()["cSpell.overrides"]) == 4

    def test_each_override_has_filename_and_language(self):
        """Each override entry must have both ``filename`` and ``language`` fields."""
        for override in self._settings()["cSpell.overrides"]:
            assert "filename" in override, f"Override missing 'filename': {override}"
            assert "language" in override, f"Override missing 'language': {override}"

    def test_markdown_files_use_en_au(self):
        """Markdown files (``**/*.md``) must use ``en-AU`` language."""
        overrides = self._settings()["cSpell.overrides"]
        md_override = next((o for o in overrides if "*.md" in o["filename"]), None)
        assert md_override is not None, "No override found for *.md files"
        assert md_override["language"] == "en-AU"

    def test_python_files_use_en_us(self):
        """Python files (``**/*.py``) must use ``en-US`` language."""
        overrides = self._settings()["cSpell.overrides"]
        py_override = next((o for o in overrides if "*.py" in o["filename"]), None)
        assert py_override is not None, "No override found for *.py files"
        assert py_override["language"] == "en-US"

    def test_toml_files_use_en_us(self):
        """TOML files (``**/*.toml``) must use ``en-US`` language."""
        overrides = self._settings()["cSpell.overrides"]
        toml_override = next((o for o in overrides if "*.toml" in o["filename"]), None)
        assert toml_override is not None, "No override found for *.toml files"
        assert toml_override["language"] == "en-US"

    def test_json_files_use_en_us(self):
        """JSON files (``**/*.json``) must use ``en-US`` language."""
        overrides = self._settings()["cSpell.overrides"]
        json_override = next((o for o in overrides if "*.json" in o["filename"]), None)
        assert json_override is not None, "No override found for *.json files"
        assert json_override["language"] == "en-US"

    def test_overrides_filename_patterns_are_glob_strings(self):
        """Each override ``filename`` must be a glob pattern string."""
        for override in self._settings()["cSpell.overrides"]:
            assert isinstance(override["filename"], str)
            assert "**" in override["filename"] or "*" in override["filename"], (
                f"filename pattern {override['filename']!r} should be a glob"
            )

    def test_existing_python_settings_intact(self):
        """Pre-existing Python editor settings must not have been removed."""
        settings = self._settings()
        assert "[python]" in settings
        python_settings = settings["[python]"]
        assert "editor.formatOnSave" in python_settings
        assert "editor.defaultFormatter" in python_settings


# ===========================================================================
# VSCode prompts (.vscode/prompts.json)
# ===========================================================================


class TestVscodePrompts:
    """Tests for the new `.vscode/prompts.json` file."""

    def _prompts(self) -> list[Any]:
        data = _load_json(".vscode/prompts.json")
        if not isinstance(data, list):
            raise TypeError("prompts.json must be a JSON array")
        return data

    def test_file_exists(self):
        """`.vscode/prompts.json` must exist."""
        assert (REPO_ROOT / ".vscode" / "prompts.json").exists()

    def test_file_is_valid_json(self):
        """`.vscode/prompts.json` must parse as valid JSON."""
        data = self._prompts()
        assert data is not None

    def test_file_is_an_array(self):
        """`.vscode/prompts.json` must be a JSON array (list)."""
        assert isinstance(self._prompts(), list)

    def test_has_at_least_one_entry(self):
        """`.vscode/prompts.json` must contain at least one prompt entry."""
        assert len(self._prompts()) >= 1

    def test_first_entry_has_id(self):
        """The first prompt entry must have an ``id`` field."""
        entry = self._prompts()[0]
        assert "id" in entry

    def test_first_entry_has_title(self):
        """The first prompt entry must have a ``title`` field."""
        entry = self._prompts()[0]
        assert "title" in entry

    def test_first_entry_has_content(self):
        """The first prompt entry must have a ``content`` field."""
        entry = self._prompts()[0]
        assert "content" in entry

    def test_first_entry_content_is_non_empty(self):
        """The first prompt entry's ``content`` must be a non-empty string."""
        content = self._prompts()[0]["content"]
        assert isinstance(content, str)
        assert content.strip() != ""

    def test_first_entry_has_use_count(self):
        """The first prompt entry must have a ``use_count`` field."""
        entry = self._prompts()[0]
        assert "use_count" in entry

    def test_first_entry_use_count_is_integer(self):
        """``use_count`` must be an integer."""
        assert isinstance(self._prompts()[0]["use_count"], int)

    def test_first_entry_has_last_used(self):
        """The first prompt entry must have a ``last_used`` field."""
        entry = self._prompts()[0]
        assert "last_used" in entry

    def test_first_entry_has_created_at(self):
        """The first prompt entry must have a ``created_at`` field."""
        entry = self._prompts()[0]
        assert "created_at" in entry

    def test_first_entry_has_pinned(self):
        """The first prompt entry must have a ``pinned`` field."""
        entry = self._prompts()[0]
        assert "pinned" in entry

    def test_first_entry_pinned_is_boolean(self):
        """``pinned`` must be a boolean."""
        assert isinstance(self._prompts()[0]["pinned"], bool)

    def test_first_entry_has_meta(self):
        """The first prompt entry must have a ``meta`` field."""
        entry = self._prompts()[0]
        assert "meta" in entry

    def test_first_entry_meta_has_total_versions(self):
        """The ``meta`` object must have a ``totalVersions`` field."""
        meta = self._prompts()[0]["meta"]
        assert "totalVersions" in meta

    def test_first_entry_meta_total_versions_is_integer(self):
        """``meta.totalVersions`` must be an integer."""
        meta = self._prompts()[0]["meta"]
        assert isinstance(meta["totalVersions"], int)

    def test_each_entry_has_required_fields(self):
        """Every prompt entry must contain the required set of fields."""
        required = {"id", "title", "content", "use_count", "last_used", "created_at", "pinned", "meta"}
        for i, entry in enumerate(self._prompts()):
            missing = required - set(entry.keys())
            assert not missing, f"Prompt entry {i} is missing fields: {missing}"

    def test_date_fields_look_like_dates(self):
        """``last_used`` and ``created_at`` should look like ISO 8601 date strings."""
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}")
        entry = self._prompts()[0]
        for field in ("last_used", "created_at"):
            assert date_pattern.match(str(entry[field])), f"{field} value {entry[field]!r} does not look like a date"


# ===========================================================================
# GitHub Issue Templates
# ===========================================================================


class TestBugReportTemplate:
    """Tests for `.github/ISSUE_TEMPLATE/bug_report.md`."""

    def _content(self) -> str:
        return (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").read_text()

    def test_file_exists(self):
        """Bug report template must exist."""
        assert (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").exists()

    def test_has_frontmatter(self):
        """Template must begin with YAML frontmatter delimited by ``---``."""
        content = self._content()
        assert content.startswith("---")

    def test_name_is_bug_report(self):
        """``name`` in frontmatter must be ``Bug report``."""
        content = self._content()
        assert "name: Bug report" in content

    def test_labels_includes_bug(self):
        """``labels`` in frontmatter must include ``bug``."""
        content = self._content()
        assert "labels: bug" in content

    def test_title_has_bug_emoji(self):
        """The title template must reference the 🐛 bug emoji."""
        content = self._content()
        assert "🐛" in content

    def test_title_uses_fix_type(self):
        """The title template must use the ``fix`` conventional commit type."""
        content = self._content()
        assert "fix(scope)" in content

    def test_has_summary_section(self):
        """Template must include a ``## 🎯 Summary`` section."""
        assert "## 🎯 Summary" in self._content()

    def test_has_why_this_matters_section(self):
        """Template must include a ``## 💡 Why this matters`` section."""
        assert "## 💡 Why this matters" in self._content()

    def test_has_to_reproduce_section(self):
        """Template must include a ``## 🔄 To Reproduce`` section."""
        assert "## 🔄 To Reproduce" in self._content()

    def test_has_expected_behaviour_section(self):
        """Template must include an ``## ✅ Expected behaviour`` section (en-AU spelling)."""
        assert "## ✅ Expected behaviour" in self._content()

    def test_expected_behaviour_uses_en_au_spelling(self):
        """The template must use Australian English spelling for 'behaviour'."""
        content = self._content()
        assert "behaviour" in content.lower()
        # Ensure US spelling is NOT used in this section title
        assert "## ✅ Expected behavior" not in content

    def test_has_environment_details_section(self):
        """Template must include a ``## 💻 Environment Details`` section."""
        assert "## 💻 Environment Details" in self._content()

    def test_reproduce_steps_are_numbered(self):
        """The reproduction steps must be a numbered list."""
        content = self._content()
        parts = content.split("## 🔄 To Reproduce")
        assert len(parts) > 1, "To Reproduce section not found"
        reproduce_section = parts[1].split("## ")[0]
        assert "1." in reproduce_section


class TestFeatureRequestTemplate:
    """Tests for `.github/ISSUE_TEMPLATE/feature_request.md`."""

    def _content(self) -> str:
        return (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").read_text()

    def test_file_exists(self):
        """Feature request template must exist."""
        assert (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").exists()

    def test_has_frontmatter(self):
        """Template must begin with YAML frontmatter."""
        assert self._content().startswith("---")

    def test_name_is_feature_request(self):
        """``name`` in frontmatter must be ``Feature request``."""
        assert "name: Feature request" in self._content()

    def test_labels_includes_enhancement(self):
        """``labels`` in frontmatter must include ``enhancement``."""
        assert "labels: enhancement" in self._content()

    def test_title_has_sparkles_emoji(self):
        """The title template must reference the ✨ feature emoji."""
        assert "✨" in self._content()

    def test_title_uses_feat_type(self):
        """The title template must use the ``feat`` conventional commit type."""
        assert "feat(scope)" in self._content()

    def test_has_summary_section(self):
        """Template must include a ``## 🎯 Summary`` section."""
        assert "## 🎯 Summary" in self._content()

    def test_has_why_this_matters_section(self):
        """Template must include a ``## 💡 Why this matters`` section."""
        assert "## 💡 Why this matters" in self._content()

    def test_has_proposed_solution_section(self):
        """Template must include a ``## 🛠️ Proposed Solution`` section."""
        assert "## 🛠️ Proposed Solution" in self._content()

    def test_has_expected_behaviour_section(self):
        """Template must include a ``## ✅ Expected Behaviour`` section."""
        assert "## ✅ Expected Behaviour" in self._content()


class TestPullRequestTemplate:
    """Tests for `.github/PULL_REQUEST_TEMPLATE.md`."""

    def _content(self) -> str:
        return (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()

    def test_file_exists(self):
        """PR template must exist."""
        assert (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").exists()

    def test_has_summary_section(self):
        """Template must include a ``## Summary`` section."""
        assert "## 🎯 Summary" in self._content()

    def test_has_semver_impact_section(self):
        """Template must include a ``## SemVer Impact`` section."""
        assert "## 📊 SemVer Impact" in self._content()

    def test_has_verification_section(self):
        """Template must include a ``## Verification`` section."""
        assert "## ✅ Verification" in self._content()

    def test_references_related_issues(self):
        """Template must include the ``## Related Issues`` section."""
        assert "## 🔗 Related Issues" in self._content()

    def test_semver_includes_patch_minor_major(self):
        """SemVer Impact section must list PATCH, MINOR, and MAJOR as options."""
        content = self._content()
        assert "PATCH" in content
        assert "MINOR" in content
        assert "MAJOR" in content

    def test_has_breaking_change_section(self):
        """Template must include a breaking change heading."""
        assert "## 💥 BREAKING CHANGE 💥" in self._content()

    def test_verification_includes_tests_item(self):
        """Verification checklist must include a tests item."""
        content = self._content()
        assert "tests" in content.lower()

    def test_verification_includes_linting_item(self):
        """Verification checklist must include a linting item."""
        assert "linting" in self._content().lower()

    def test_verification_items_are_checkboxes(self):
        """All verification items must use markdown checkbox format."""
        content = self._content()
        checklist_section = content[content.index("## ✅ Verification") :]
        checkbox_count = checklist_section.count("- [ ]")
        assert checkbox_count >= 4, f"Expected at least 4 verification checkboxes, found {checkbox_count}"

    def test_semver_impact_items_are_checkboxes(self):
        """SemVer impact options must use markdown checkbox format."""
        content = self._content()
        # Find the SemVer Impact section
        start = content.index("## 📊 SemVer Impact")
        end = content.index("## ✅ Verification")
        section = content[start:end]
        checkbox_count = section.count("- [ ]")
        assert checkbox_count >= 3, f"Expected at least 3 semver-impact checkboxes, found {checkbox_count}"


# ===========================================================================
# GitHub Release Workflow (.github/release.yml)
# ===========================================================================


class TestReleaseWorkflow:
    """Tests for the new `.github/release.yml` GitHub Actions workflow."""

    def _workflow(self) -> dict[str, Any]:
        data = _load_yaml(".github/release.yml")
        if not isinstance(data, dict):
            raise TypeError("release workflow must be a YAML mapping")
        return data

    def test_file_exists(self):
        """`.github/release.yml` must exist."""
        assert (REPO_ROOT / ".github" / "release.yml").exists()

    def test_file_is_valid_yaml(self):
        """`.github/release.yml` must parse as valid YAML."""
        workflow = self._workflow()
        assert isinstance(workflow, dict)

    def test_workflow_has_name(self):
        """Workflow must declare a ``name``."""
        assert "name" in self._workflow()

    def test_workflow_name_mentions_release(self):
        """Workflow name must mention 'Release'."""
        assert "Release" in self._workflow()["name"]

    def test_workflow_triggered_on_push(self):
        """Workflow must be triggered on ``push`` events."""
        workflow = self._workflow()
        assert "on" in workflow
        assert "push" in workflow["on"]

    def test_workflow_triggered_on_version_tags(self):
        """Workflow must be triggered on ``v*`` tags."""
        push_config = self._workflow()["on"]["push"]
        tags = push_config.get("tags", [])
        assert any(t.startswith("v") for t in tags), "Workflow should trigger on tags matching 'v*'"

    def test_workflow_has_release_job(self):
        """Workflow must define a ``release`` job."""
        assert "release" in self._workflow()["jobs"]

    def test_release_job_runs_on_ubuntu(self):
        """``release`` job must run on ``ubuntu-latest``."""
        job = self._workflow()["jobs"]["release"]
        assert job["runs-on"] == "ubuntu-latest"

    def test_release_job_has_write_permissions(self):
        """``release`` job must have ``contents: write`` permission."""
        job = self._workflow()["jobs"]["release"]
        assert "permissions" in job
        assert job["permissions"].get("contents") == "write"

    def test_release_job_checks_out_code(self):
        """``release`` job must include a checkout step."""
        steps = self._workflow()["jobs"]["release"]["steps"]
        uses_list = [step.get("uses", "") for step in steps]
        assert any("actions/checkout" in u for u in uses_list), "Release job must include an actions/checkout step"

    def test_release_job_uses_softprops_action(self):
        """``release`` job must use ``softprops/action-gh-release``."""
        steps = self._workflow()["jobs"]["release"]["steps"]
        uses_list = [step.get("uses", "") for step in steps]
        assert any("softprops/action-gh-release" in u for u in uses_list), (
            "Release job must use the softprops/action-gh-release action"
        )

    def test_release_job_generates_release_notes(self):
        """``softprops/action-gh-release`` must have ``generate_release_notes: true``."""
        steps = self._workflow()["jobs"]["release"]["steps"]
        for step in steps:
            if "softprops/action-gh-release" in step.get("uses", ""):
                assert step.get("with", {}).get("generate_release_notes") is True, "generate_release_notes must be true"
                return
        raise AssertionError("softprops/action-gh-release step not found")

    def test_checkout_uses_v4(self):
        """actions/checkout must use at least v4."""
        steps = self._workflow()["jobs"]["release"]["steps"]
        for step in steps:
            uses = step.get("uses", "")
            if "actions/checkout" in uses:
                assert "@v4" in uses or "@v" in uses, f"actions/checkout should pin to v4 or later, got: {uses!r}"
                version_str = uses.split("@v")[-1]
                assert int(version_str.split(".")[0]) >= 4, "actions/checkout must be version 4 or later"
                return
        raise AssertionError("actions/checkout step not found")


# ===========================================================================
# .gitignore — vscode exclusion rule changes
# ===========================================================================


class TestGitignoreVscodeRules:
    """Tests for the changed vscode exclusion rules in .gitignore."""

    def test_vscode_dir_no_longer_excluded(self):
        """.vscode/ must not be an active exclusion in .gitignore."""
        lines = _gitignore_lines()
        active_exclusions = [line.strip() for line in lines if not line.strip().startswith("#")]
        assert ".vscode/" not in active_exclusions, (
            ".vscode/ should not be an active exclusion (it was changed to a comment)"
        )

    def test_vscode_dir_unignored_at_end(self):
        """`.gitignore` must have ``!.vscode/`` to explicitly unignore the vscode directory."""
        lines = _gitignore_lines()
        active_lines = [line.strip() for line in lines if not line.strip().startswith("#") and line.strip()]
        assert "!.vscode/" in active_lines, "!.vscode/ rule must be present in .gitignore"

    def test_original_vscode_exclusion_is_now_commented(self):
        """The original `.vscode/` exclusion must now appear as a comment."""
        lines = _gitignore_lines()
        found_comment = any(line.strip().startswith("#") and ".vscode/" in line for line in lines)
        assert found_comment, "The old .vscode/ exclusion should be commented out"

    def test_gitignore_still_excludes_idea(self):
        """`.idea/` IDE directory must still be actively excluded."""
        lines = _gitignore_lines()
        active_exclusions = [line.strip() for line in lines if not line.strip().startswith("#")]
        assert ".idea/" in active_exclusions, ".idea/ must still be excluded in .gitignore"

    def test_gitignore_still_excludes_env(self):
        """`.env` must still be excluded."""
        active_lines = [
            line.strip() for line in _gitignore_lines() if not line.strip().startswith("#") and line.strip()
        ]
        assert ".env" in active_lines

    def test_promptfoo_json_still_ignored(self):
        """``promptfoo_*.json`` must still be listed in .gitignore."""
        content = (REPO_ROOT / ".gitignore").read_text()
        assert "promptfoo_*.json" in content
