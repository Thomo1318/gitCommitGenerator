"""
Tests for project configuration files added/modified in this PR:
  - Brewfile       (added `brew "promptfoo"`)
  - mise.toml      (added commented npm:promptfoo, added [tasks."setup:brew"])
  - promptfooconfig.yaml  (new file)
"""

import tomllib
from pathlib import Path

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
        has_length_check = False
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript":
                value = assertion["value"]
                if "output" in value and "length" in value:
                    has_length_check = True
                    # Verify the minimum length threshold is greater than 0
                    assert ">" in value
                    break
        assert has_length_check, "At least one JS assertion should check output length"

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
        known_keys = {
            "description",
            "prompts",
            "providers",
            "tests",
            "defaultTest",
            "outputPath",
            "sharing",
            "env",
            "redteam",
        }
        data = _load_promptfoo_yaml()
        unknown = set(data.keys()) - known_keys
        assert not unknown, f"Unexpected top-level keys in promptfooconfig.yaml: {unknown}"

    # -----------------------------------------------------------------------
    # Tests for the redteam section added in this PR
    # -----------------------------------------------------------------------

    def test_redteam_section_present(self):
        """Top-level 'redteam' key must be present after this PR."""
        data = _load_promptfoo_yaml()
        assert "redteam" in data, "promptfooconfig.yaml must contain a 'redteam' section"

    def test_redteam_has_plugins_list(self):
        """redteam section must define a non-empty 'plugins' list."""
        data = _load_promptfoo_yaml()
        redteam = data["redteam"]
        assert "plugins" in redteam, "redteam section must have a 'plugins' key"
        assert isinstance(redteam["plugins"], list)
        assert len(redteam["plugins"]) > 0, "redteam.plugins must be non-empty"

    def test_redteam_includes_hijacking_plugin(self):
        """The 'hijacking' red-team plugin must be configured."""
        data = _load_promptfoo_yaml()
        plugins = data["redteam"]["plugins"]
        assert "hijacking" in plugins, "redteam.plugins must include 'hijacking'"

    def test_redteam_includes_indirect_prompt_injection(self):
        """The 'indirect-prompt-injection' red-team plugin must be configured."""
        data = _load_promptfoo_yaml()
        plugins = data["redteam"]["plugins"]
        assert "indirect-prompt-injection" in plugins, "redteam.plugins must include 'indirect-prompt-injection'"

    def test_redteam_includes_pii_direct_plugin(self):
        """The 'pii:direct' red-team plugin must be configured."""
        data = _load_promptfoo_yaml()
        plugins = data["redteam"]["plugins"]
        assert "pii:direct" in plugins, "redteam.plugins must include 'pii:direct'"

    # -----------------------------------------------------------------------
    # Tests for the updated assertion logic added in this PR
    # -----------------------------------------------------------------------

    def test_length_assertion_has_upper_bound(self):
        """The JS length assertion must enforce an upper bound (<=72)."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        has_upper_bound = False
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript":
                value = assertion["value"]
                if "length" in value and ("<=" in value or "< 73" in value):
                    has_upper_bound = True
                    break
        assert has_upper_bound, "At least one JS assertion must enforce an upper bound on output length"

    def test_length_assertion_enforces_72_char_limit(self):
        """The upper bound in the JS length assertion must be 72 characters."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript":
                value = assertion["value"]
                if "length" in value and "<=" in value:
                    assert "72" in value, "The upper bound must be 72 characters"
                    return
        # If we reach here the assertion wasn't found — let the has_upper_bound test handle it

    def test_conventional_commit_regex_assertion_present(self):
        """Checks that the first Promptfoo test case includes a JavaScript assertion using a regular expression to validate conventional-commit format."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        regex_assertions = [a for a in first_case["assert"] if a["type"] == "javascript" and ".test(" in a["value"]]
        assert len(regex_assertions) >= 1, (
            "At least one JS assertion must use a regex .test() for conventional-commit format"
        )

    def test_conventional_commit_regex_references_output(self):
        """The conventional-commit regex assertion must test the 'output' variable."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript" and ".test(" in assertion["value"]:
                assert "output" in assertion["value"], "The regex assertion must reference 'output'"
                return
        raise AssertionError("No regex-based JS assertion found")

    def test_conventional_commit_regex_uses_trim(self):
        """Ensures the conventional commit regex assertion trims the output before matching.

        Parameters:
        """
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        for assertion in first_case["assert"]:
            if assertion["type"] == "javascript" and ".test(" in assertion["value"]:
                assert "trim()" in assertion["value"], "Regex assertion should call trim() before testing"
                return

    def test_at_least_two_javascript_assertions_in_first_test(self):
        """After this PR, the first test case must have at least two JS assertions."""
        data = _load_promptfoo_yaml()
        first_case = data["tests"][0]
        js_assertions = [a for a in first_case["assert"] if a["type"] == "javascript"]
        assert len(js_assertions) >= 2, f"Expected at least 2 JS assertions, got {len(js_assertions)}"


# ===========================================================================
# New mise.toml tests for eval:promptfoo task (added in this PR)
# ===========================================================================


class TestMiseTomlEvalPromptfoo:
    def test_eval_promptfoo_task_exists(self):
        """[tasks.'eval:promptfoo'] must be present in mise.toml after this PR."""
        data = _load_mise()
        assert "tasks" in data
        assert "eval:promptfoo" in data["tasks"], "'eval:promptfoo' task must be present in mise.toml tasks"

    def test_eval_promptfoo_has_description(self):
        """The eval:promptfoo task must carry a non-empty description."""
        task = _load_mise()["tasks"]["eval:promptfoo"]
        assert "description" in task
        assert task["description"].strip() != ""

    def test_eval_promptfoo_description_mentions_opik(self):
        """The eval:promptfoo description must reference Opik as the sync target."""
        task = _load_mise()["tasks"]["eval:promptfoo"]
        assert "opik" in task["description"].lower() or "Opik" in task["description"], (
            "eval:promptfoo description should mention Opik"
        )

    def test_eval_promptfoo_run_invokes_promptfoo_eval(self):
        """The run script must call 'promptfoo eval'."""
        task = _load_mise()["tasks"]["eval:promptfoo"]
        run = task["run"]
        assert "promptfoo eval" in run, "eval:promptfoo run must invoke 'promptfoo eval'"

    def test_eval_promptfoo_run_invokes_redteam(self):
        """The run script must call 'promptfoo redteam run'."""
        task = _load_mise()["tasks"]["eval:promptfoo"]
        run = task["run"]
        assert "redteam run" in run, "eval:promptfoo run must invoke 'promptfoo redteam run'"

    def test_eval_promptfoo_run_syncs_eval_results_to_opik(self):
        """Checks that the eval:promptfoo task syncs Promptfoo results to Opik.

        Returns:
            None
        """
        task = _load_mise()["tasks"]["eval:promptfoo"]
        run = task["run"]
        assert "sync_promptfoo_to_opik.py" in run, "eval:promptfoo must call sync_promptfoo_to_opik.py"
        assert "promptfoo_results.json" in run, "eval:promptfoo must pass promptfoo_results.json to the sync script"

    def test_eval_promptfoo_run_syncs_redteam_results_to_opik(self):
        """The run script must also sync promptfoo_redteam_results.json to Opik."""
        task = _load_mise()["tasks"]["eval:promptfoo"]
        run = task["run"]
        assert "promptfoo_redteam_results.json" in run, (
            "eval:promptfoo must pass promptfoo_redteam_results.json to the sync script"
        )

    def test_eval_promptfoo_outputs_json_file(self):
        """The eval command must write output with -o flag to a .json file."""
        task = _load_mise()["tasks"]["eval:promptfoo"]
        run = task["run"]
        assert "-o promptfoo_results.json" in run, (
            "eval:promptfoo must use '-o promptfoo_results.json' to capture output"
        )

    def test_eval_promptfoo_output_files_are_gitignored(self):
        """promptfoo_*.json output files must be listed in .gitignore."""
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        assert "promptfoo_*.json" in gitignore, "promptfoo_*.json must be excluded via .gitignore"
