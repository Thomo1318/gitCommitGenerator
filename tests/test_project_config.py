"""
Tests for project configuration files added/modified in this PR:
  - Brewfile       (added `brew "promptfoo"`)
  - mise.toml      (added commented npm:promptfoo, added [tasks."setup:brew"])
  - promptfooconfig.yaml  (new file)
"""

import tomllib
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _load_mise() -> dict:
    with open(REPO_ROOT / "mise.toml", "rb") as f:
        return tomllib.load(f)


def _load_promptfoo_yaml() -> dict:
    with open(REPO_ROOT / "promptfooconfig.yaml") as f:
        return yaml.safe_load(f)


def _brewfile_lines() -> list[str]:
    return (REPO_ROOT / "Brewfile").read_text().splitlines()


# ===========================================================================
# Brewfile tests
# ===========================================================================


class TestBrewfile:
    def test_promptfoo_brew_entry_present(self):
        """The `promptfoo` brew formula must be listed."""
        lines = _brewfile_lines()
        assert any(line.strip() == 'brew "promptfoo"' for line in lines)

    def test_promptfoo_brew_entry_not_commented_out(self):
        """The promptfoo entry must be active (not commented)."""
        lines = _brewfile_lines()
        found = False
        for line in lines:
            stripped = line.strip()
            if 'brew "promptfoo"' in stripped:
                found = True
                assert not stripped.startswith("#"), "promptfoo entry must not be commented out in Brewfile"
        assert found, "promptfoo entry not found in Brewfile"

    def test_promptfoo_comment_describes_purpose(self):
        """A descriptive comment precedes the promptfoo entry."""
        lines = _brewfile_lines()
        for i, line in enumerate(lines):
            if line.strip() == 'brew "promptfoo"':
                # Look for a comment within the two lines before this entry
                preceding = lines[max(0, i - 2) : i]
                assert any(ln.strip().startswith("#") for ln in preceding), (
                    "A comment describing promptfoo should appear before its brew entry"
                )
                break

    def test_brewfile_existing_taps_intact(self):
        """Pre-existing taps are not disturbed."""
        content = (REPO_ROOT / "Brewfile").read_text()
        assert "youssofal/mtplx" in content
        assert "jundot/omlx" in content
        assert "vjeantet/tap" in content

    def test_brewfile_is_valid_bundle_format(self):
        """Every non-empty, non-comment line starts with a known directive."""
        valid_directives = ("brew ", "tap ", "cask ", "mas ", "whalebrew ", "vscode ")
        lines = _brewfile_lines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert any(stripped.startswith(d) for d in valid_directives), f"Unexpected Brewfile directive: {stripped!r}"


# ===========================================================================
# mise.toml tests
# ===========================================================================


class TestMiseToml:
    def test_setup_brew_task_exists(self):
        """[tasks.'setup:brew'] section must be present."""
        data = _load_mise()
        assert "tasks" in data
        assert "setup:brew" in data["tasks"]

    def test_setup_brew_task_has_description(self):
        """The setup:brew task must carry a description."""
        task = _load_mise()["tasks"]["setup:brew"]
        assert "description" in task
        assert task["description"].strip() != ""

    def test_setup_brew_task_run_command(self):
        """The run command must invoke `brew bundle` pointing at Brewfile."""
        task = _load_mise()["tasks"]["setup:brew"]
        run = task["run"]
        assert "brew bundle" in run
        assert "Brewfile" in run

    def test_setup_brew_task_run_references_correct_file(self):
        """The --file flag must point to the repo-level Brewfile."""
        task = _load_mise()["tasks"]["setup:brew"]
        run = task["run"]
        assert "--file=Brewfile" in run or "--file Brewfile" in run

    def test_npm_promptfoo_is_commented_out(self):
        """npm:promptfoo must be disabled (moved to Brewfile)."""
        raw = (REPO_ROOT / "mise.toml").read_text()
        # The key should only appear in a comment, never as an active tool
        found = False
        for line in raw.splitlines():
            stripped = line.strip()
            if "npm:promptfoo" in stripped:
                found = True
                assert stripped.startswith("#"), "npm:promptfoo should be commented out (moved to Brewfile)"
        assert found, "npm:promptfoo missing from mise.toml"

    def test_npm_promptfoo_comment_explains_reason(self):
        """The comment for npm:promptfoo should mention why it was moved."""
        raw = (REPO_ROOT / "mise.toml").read_text()
        found = False
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and "npm:promptfoo" in stripped:
                found = True
                lower = stripped.lower()
                assert "brewfile" in lower or "brew" in lower, (
                    "Comment should mention Brewfile as the new home for promptfoo"
                )
                break
        assert found, "Commented npm:promptfoo entry not found in mise.toml"

    def test_mise_toml_is_valid_toml(self):
        """Whole file must parse as valid TOML without errors."""
        data = _load_mise()
        assert isinstance(data, dict)

    def test_other_tasks_not_removed(self):
        """Pre-existing tasks must still be present."""
        tasks = _load_mise()["tasks"]
        assert "test:cli" in tasks
        assert "pre-commit" in tasks
        assert "docs:build" in tasks
        assert "docs:serve" in tasks


# ===========================================================================
# promptfooconfig.yaml tests
# ===========================================================================


class TestPromptfooConfig:
    def test_file_exists(self):
        """promptfooconfig.yaml must exist at the repo root."""
        assert (REPO_ROOT / "promptfooconfig.yaml").exists()

    def test_description_present(self):
        """Top-level description field must be set."""
        data = _load_promptfoo_yaml()
        assert "description" in data
        assert isinstance(data["description"], str)
        assert data["description"].strip() != ""

    def test_description_value(self):
        """Description identifies the evaluation target."""
        data = _load_promptfoo_yaml()
        assert "MTPLX" in data["description"]

    def test_prompts_list_present(self):
        """prompts must be a non-empty list."""
        data = _load_promptfoo_yaml()
        assert "prompts" in data
        assert isinstance(data["prompts"], list)
        assert len(data["prompts"]) > 0

    def test_prompt_contains_diff_variable(self):
        """Each prompt must reference the {{diff}} variable."""
        data = _load_promptfoo_yaml()
        for prompt in data["prompts"]:
            assert "{{diff}}" in prompt, f"Prompt does not contain {{{{diff}}}} template variable: {prompt!r}"

    def test_providers_list_present(self):
        """providers must be a non-empty list."""
        data = _load_promptfoo_yaml()
        assert "providers" in data
        assert isinstance(data["providers"], list)
        assert len(data["providers"]) > 0

    def test_provider_id_format(self):
        """Provider id must follow the openai:chat:<model> pattern."""
        data = _load_promptfoo_yaml()
        for provider in data["providers"]:
            assert "id" in provider
            assert provider["id"].startswith("openai:chat:"), (
                f"Provider id should start with 'openai:chat:': {provider['id']!r}"
            )

    def test_provider_uses_mtplx_model(self):
        """The MTPLX local model must be the configured provider."""
        data = _load_promptfoo_yaml()
        provider_ids = [p["id"] for p in data["providers"]]
        assert "openai:chat:MTPLX" in provider_ids

    def test_provider_api_base_url(self):
        """Provider must point to the local inference server."""
        data = _load_promptfoo_yaml()
        for provider in data["providers"]:
            if provider["id"] == "openai:chat:MTPLX":
                assert "config" in provider
                cfg = provider["config"]
                assert "apiBaseUrl" in cfg
                assert cfg["apiBaseUrl"] == "http://localhost:8000/v1"

    def test_provider_has_api_key(self):
        """Provider config must include an apiKey field (even if dummy)."""
        data = _load_promptfoo_yaml()
        for provider in data["providers"]:
            if provider["id"] == "openai:chat:MTPLX":
                cfg = provider["config"]
                assert "apiKey" in cfg
                assert isinstance(cfg["apiKey"], str)

    def test_tests_list_present(self):
        """tests section must be a non-empty list."""
        data = _load_promptfoo_yaml()
        assert "tests" in data
        assert isinstance(data["tests"], list)
        assert len(data["tests"]) > 0

    def test_test_case_has_diff_var(self):
        """Each test case must supply a `diff` variable."""
        data = _load_promptfoo_yaml()
        for case in data["tests"]:
            assert "vars" in case, "Test case missing 'vars' key"
            assert "diff" in case["vars"], "Test case missing 'diff' variable"

    def test_test_case_diff_is_valid_unified_diff(self):
        """The diff variable must look like a valid unified diff."""
        data = _load_promptfoo_yaml()
        for case in data["tests"]:
            diff_text = case["vars"]["diff"]
            assert "diff --git" in diff_text
            assert "+++" in diff_text
            assert "---" in diff_text

    def test_test_case_has_assertions(self):
        """Each test case must have at least one assertion."""
        data = _load_promptfoo_yaml()
        for case in data["tests"]:
            assert "assert" in case, "Test case missing 'assert' key"
            assert isinstance(case["assert"], list)
            assert len(case["assert"]) > 0

    def test_assertion_type_is_javascript(self):
        """The assertion type for the baseline test is 'javascript'."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        assertion_types = [a["type"] for a in first_case["assert"]]
        assert "javascript" in assertion_types

    def test_javascript_assertion_checks_output_length(self):
        """The javascript assertion must verify output is non-trivially long."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript":
                value = assertion["value"]
                assert "output" in value, "Assertion must reference 'output'"
                assert "length" in value, "Assertion should check output length"
                # Verify the minimum length threshold is greater than 0
                assert ">" in value

    def test_javascript_assertion_trims_whitespace(self):
        """The javascript assertion should call trim() to ignore leading/trailing whitespace."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript":
                assert "trim()" in assertion["value"]

    def test_yaml_parses_without_error(self):
        """The entire promptfooconfig.yaml must be parseable YAML."""
        data = _load_promptfoo_yaml()
        assert isinstance(data, dict)

    def test_no_unknown_top_level_keys(self):
        """Only recognised promptfoo top-level keys should be present."""
        known_keys = {"description", "prompts", "providers", "tests", "defaultTest", "outputPath", "sharing", "env"}
        data = _load_promptfoo_yaml()
        unknown = set(data.keys()) - known_keys
        assert not unknown, f"Unexpected top-level keys in promptfooconfig.yaml: {unknown}"
