"""
Tests for CI/CD and packaging configuration changes in this PR:
  - .github/workflows/ci.yml    (codecov-action pinned to v4, `file` -> `files`)
  - .github/workflows/docs.yml  (removed `--strict` from `zensical build`)
  - pyproject.toml              (requires-python gained an upper bound `<4.0`)
  - uv.lock                     (requires-python mirrors pyproject.toml)
"""

import tomllib
from pathlib import Path

import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _load_yaml(rel_path: str) -> dict:
    """
    Load and parse a YAML file relative to the repository root.

    Parameters:
        rel_path (str): Relative path to the YAML file.

    Returns:
        dict: Parsed YAML content with a bare `on` key preserved as a string.
    """
    data = yaml.safe_load((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    # PyYAML (1.1 resolver) parses the bare `on:` key as the boolean True.
    if isinstance(data, dict) and True in data:
        data["on"] = data.pop(True)
    return data


def _load_pyproject() -> dict:
    """
    Load and parse the repository's pyproject.toml configuration.

    Returns:
        dict: The parsed project configuration.
    """
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _load_uv_lock() -> dict:
    """Load and parse the repository's uv.lock file.

    Returns:
        dict: The parsed uv.lock configuration.
    """
    with open(REPO_ROOT / "uv.lock", "rb") as f:
        return tomllib.load(f)


# ===========================================================================
# .github/workflows/ci.yml - Codecov upload step
# ===========================================================================


class TestCiWorkflowCodecovStep:
    """Tests for the `Upload coverage to Codecov` step of ci.yml."""

    def _workflow(self) -> dict:
        """Load the CI workflow configuration."""
        return _load_yaml(".github/workflows/ci.yml")

    def _codecov_step(self) -> dict:
        """
        Finds the Codecov upload step in the CI workflow.

        Returns:
                dict: The configuration for the Codecov upload step.

        Raises:
                AssertionError: If the Codecov upload step is not present.
        """
        steps = self._workflow()["jobs"]["test-and-coverage"]["steps"]
        for step in steps:
            if step.get("name") == "Upload coverage to Codecov":
                return step
        raise AssertionError("Codecov upload step not found in ci.yml")

    def test_file_is_valid_yaml(self):
        """ci.yml must parse as valid YAML."""
        assert isinstance(self._workflow(), dict)

    def test_codecov_action_pinned_to_v4(self):
        """
        Verify that the Codecov upload step uses the pinned version 4 of the Codecov action.
        """
        step = self._codecov_step()
        assert step["uses"] == "codecov/codecov-action@b9fd7d16f6d7d1b5d2bec1a2887e65ceed900238"

    def test_codecov_action_not_v7(self):
        """Ensure the Codecov upload step uses a supported action version."""
        step = self._codecov_step()
        assert step["uses"] != "codecov/codecov-action@v7"

    def test_uses_plural_files_key(self):
        """The `with` block must use the `files` key (plural), not `file`."""
        step = self._codecov_step()
        assert "files" in step["with"], "codecov-action@v4 expects the 'files' input, not 'file'"
        assert "file" not in step["with"], "the singular 'file' key is not a valid input for codecov-action@v4"

    def test_files_value_points_to_coverage_xml(self):
        """The `files` input must reference the generated coverage.xml report."""
        step = self._codecov_step()
        assert step["with"]["files"] == "./coverage.xml"

    def test_oidc_upload_and_error_handling(self):
        """Same-repo uploads use OIDC (no token) with hard-fail on upload errors."""
        step = self._codecov_step()
        assert step["with"].get("use_oidc") is True
        assert "token" not in step.get("with", {}), "OIDC path must not set token input"
        assert step["with"]["fail_ci_if_error"] is True
        assert "continue-on-error" not in step

    def test_codecov_upload_skips_fork_prs(self):
        """Fork PRs must skip Codecov upload (tests still run in earlier steps)."""
        step = self._codecov_step()
        cond = step.get("if", "")
        assert "pull_request" in cond
        assert "head.repo.full_name" in cond
        assert "github.repository" in cond

    def test_codecov_step_runs_after_test_step(self):
        """The Codecov upload step must remain the final step, after running tests."""
        steps = self._workflow()["jobs"]["test-and-coverage"]["steps"]
        names = [s.get("name") for s in steps]
        assert names.index("Upload coverage to Codecov") == len(names) - 1
        assert names.index("Run Tests with Coverage") < names.index("Upload coverage to Codecov")

    def _validate_codecov_step(self) -> dict:
        """
        Finds the Validate codecov.yml step in the CI workflow.

        Returns:
            dict: The configuration for the validate step.

        Raises:
            AssertionError: If the validate step is not present.
        """
        steps = self._workflow()["jobs"]["test-and-coverage"]["steps"]
        for step in steps:
            if step.get("name") == "Validate codecov.yml":
                return step
        raise AssertionError("Validate codecov.yml step not found in ci.yml")

    def test_validate_codecov_step_exists(self):
        """The workflow must validate codecov.yml before running coverage tests."""
        step = self._validate_codecov_step()
        assert "run" in step
        assert "codecov.io/validate" in step["run"]
        assert "--connect-timeout" in step["run"]
        assert "--max-time" in step["run"]

    def test_validate_codecov_step_runs_before_tests(self):
        """Validate codecov.yml must precede Run Tests with Coverage."""
        steps = self._workflow()["jobs"]["test-and-coverage"]["steps"]
        names = [s.get("name") for s in steps]
        assert "Validate codecov.yml" in names
        assert names.index("Validate codecov.yml") < names.index("Run Tests with Coverage")


# ===========================================================================
# .github/workflows/docs.yml - Build site step
# ===========================================================================


class TestDocsWorkflowBuildStep:
    """Tests for the `Build site` step of docs.yml."""

    def _workflow(self) -> dict:
        """Load the documentation workflow configuration."""
        return _load_yaml(".github/workflows/docs.yml")

    def _build_step(self) -> dict:
        """
        Find the documentation workflow step responsible for building the site.

        Returns:
                dict: The configuration for the "Build site" step.

        Raises:
                AssertionError: If the "Build site" step is not present.
        """
        steps = self._workflow()["jobs"]["deploy"]["steps"]
        for step in steps:
            if step.get("name") == "Build site":
                return step
        raise AssertionError("Build site step not found in docs.yml")

    def test_file_is_valid_yaml(self):
        """docs.yml must parse as valid YAML."""
        assert isinstance(self._workflow(), dict)

    def test_build_command_does_not_use_strict_flag(self):
        """The `--strict` flag must have been removed from the zensical build command."""
        step = self._build_step()
        assert "--strict" not in step["run"], "the --strict flag should not be passed to `zensical build`"

    def test_build_command_is_exact(self):
        """The build step must run exactly `uv run zensical build`."""
        step = self._build_step()
        assert step["run"] == "uv run zensical build"

    def test_build_step_still_precedes_pages_setup(self):
        """The build step must still run before the Setup Pages step."""
        steps = self._workflow()["jobs"]["deploy"]["steps"]
        names = [s.get("name") for s in steps]
        assert names.index("Build site") < names.index("Setup Pages")


# ===========================================================================
# pyproject.toml - requires-python upper bound
# ===========================================================================


class TestPyprojectRequiresPython:
    """Tests for the `requires-python` upper bound added in pyproject.toml."""

    def test_pyproject_is_valid_toml(self):
        """pyproject.toml must parse as valid TOML."""
        assert isinstance(_load_pyproject(), dict)

    def test_requires_python_value(self):
        """requires-python must gain an explicit upper bound of <4.0."""
        data = _load_pyproject()
        assert data["project"]["requires-python"] == ">=3.14, <4.0"

    def test_requires_python_lower_bound_unchanged(self):
        """The existing lower bound (>=3.14) must be preserved."""
        data = _load_pyproject()
        assert ">=3.14" in data["project"]["requires-python"]

    def test_requires_python_has_upper_bound(self):
        """An upper bound must now be present (it was absent before this PR)."""
        data = _load_pyproject()
        assert "<4.0" in data["project"]["requires-python"]

    def test_requires_python_accepts_current_minimum(self):
        """Python 3.14.0 must satisfy the specifier."""
        spec = SpecifierSet(_load_pyproject()["project"]["requires-python"])
        assert Version("3.14.0") in spec

    def test_requires_python_accepts_future_3x_release(self):
        """A hypothetical future 3.x release (e.g. 3.99.99) must still satisfy the specifier."""
        spec = SpecifierSet(_load_pyproject()["project"]["requires-python"])
        assert Version("3.99.99") in spec

    def test_requires_python_rejects_below_minimum(self):
        """Python versions below 3.14 must be rejected."""
        spec = SpecifierSet(_load_pyproject()["project"]["requires-python"])
        assert Version("3.13.9") not in spec

    def test_requires_python_rejects_python_4(self):
        """Python 4.0 must be rejected by the new upper bound."""
        spec = SpecifierSet(_load_pyproject()["project"]["requires-python"])
        assert Version("4.0.0") not in spec

    def test_dependencies_unaffected(self):
        """The dependency list must remain untouched by this PR."""
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        assert isinstance(deps, list)
        assert any(d.startswith("pydantic") for d in deps)
        assert any(d.startswith("typer") for d in deps)


# ===========================================================================
# uv.lock - requires-python mirrors pyproject.toml
# ===========================================================================


class TestUvLockRequiresPython:
    """Tests for the `requires-python` value in uv.lock."""

    def test_uv_lock_is_valid_toml(self):
        """uv.lock must still parse as valid TOML after the change."""
        assert isinstance(_load_uv_lock(), dict)

    def test_requires_python_value(self):
        """uv.lock's requires-python must match the new upper-bounded specifier."""
        data = _load_uv_lock()
        assert data["requires-python"] == ">=3.14, <4.0"

    def test_lock_version_and_revision_unchanged(self):
        """The lock file format version/revision must be unaffected by this PR."""
        data = _load_uv_lock()
        assert data["version"] == 1
        assert data["revision"] == 3

    def test_requires_python_matches_pyproject(self):
        """uv.lock and pyproject.toml must declare an identical requires-python specifier."""
        lock_value = _load_uv_lock()["requires-python"]
        pyproject_value = _load_pyproject()["project"]["requires-python"]
        assert lock_value == pyproject_value

    def test_lock_still_has_packages(self):
        """The package list must remain intact (this PR only touches the header)."""
        data = _load_uv_lock()
        assert "package" in data
        assert isinstance(data["package"], list)
        assert len(data["package"]) > 0


# ===========================================================================
# .github/workflows/ci.yml - concurrency, permissions, hk lint job
# ===========================================================================


class TestCiWorkflowHardening:
    """Issue #170 residual CI contracts: concurrency, OIDC scope, hk parity."""

    def _workflow(self) -> dict:
        return _load_yaml(".github/workflows/ci.yml")

    def test_workflow_concurrency_group(self):
        wf = self._workflow()
        assert "concurrency" in wf
        group = wf["concurrency"]["group"]
        assert "github.workflow" in group
        assert "pull_request.number" in group
        assert "github.ref" in group or "github.run_id" in group
        assert wf["concurrency"].get("cancel-in-progress") is True

    def test_top_level_permissions_contents_read(self):
        """Ensure the workflow grants top-level read access to repository contents."""
        wf = self._workflow()
        assert wf["permissions"]["contents"] == "read"

    def test_id_token_write_only_on_coverage_job(self):
        wf = self._workflow()
        cov_perms = wf["jobs"]["test-and-coverage"]["permissions"]
        assert cov_perms.get("id-token") == "write"
        lint_job = wf["jobs"]["lint"]
        lint_perms = lint_job.get("permissions", {})
        assert lint_perms.get("id-token") != "write"
        # Top-level must not grant id-token write
        assert wf["permissions"].get("id-token") != "write"

    def test_checkout_and_setup_uv_pinned_to_sha(self):
        wf = self._workflow()
        for job_name in ("lint", "test-and-coverage"):
            for step in wf["jobs"][job_name]["steps"]:
                uses = step.get("uses", "")
                if uses.startswith("actions/checkout@") or uses.startswith("astral-sh/setup-uv@"):
                    ref = uses.split("@", 1)[1]
                    assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
                        f"{job_name}: {uses} must be full commit SHA"
                    )

    def test_lint_job_exists(self):
        assert "lint" in self._workflow()["jobs"]

    def _lint_steps(self) -> list:
        return self._workflow()["jobs"]["lint"]["steps"]

    def test_lint_runs_hk_validate(self):
        names = [s.get("name") for s in self._lint_steps()]
        assert "hk validate" in names

    def test_lint_pr_check_is_read_only_with_exact_skips(self):
        step = next(s for s in self._lint_steps() if s.get("name") == "hk check (pull_request)")
        run = step["run"]
        assert "--check" in run
        assert "--no-stage" in run
        assert "--pr" in run
        assert "--fail-fast" in run
        assert "--no-progress" in run
        assert step["env"]["HK_SKIP_STEPS"] == "pytest-cov,betterleaks,gen-docs,gen-toc"
        assert step.get("if") == "github.event_name == 'pull_request'"

    def test_lint_push_check_not_pr_only(self):
        step = next(s for s in self._lint_steps() if s.get("name") == "hk check (push / workflow_dispatch)")
        run = step["run"]
        assert "--check" in run
        assert "--no-stage" in run
        assert "--all" in run
        assert "--pr" not in run
        assert step["env"]["HK_SKIP_STEPS"] == "pytest-cov,betterleaks,gen-docs,gen-toc"
        assert "pull_request" in step.get("if", "")

    def test_lint_fetch_depth_zero(self):
        """Verify that the lint job checks out the repository with full history."""
        checkout = next(s for s in self._lint_steps() if s.get("name") == "Checkout repository")
        assert checkout["with"]["fetch-depth"] == 0

    def test_no_prepare_commit_msg_in_ci(self):
        raw = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "prepare-commit-msg" not in raw
        assert "commit-msg" not in raw or "validate-commit" not in raw


# ===========================================================================
# codecov.yml residual locks (component map must not churn)
# ===========================================================================


class TestCodecovYmlContracts:
    """Lock landed #169 Codecov semantics without brittle full-file snapshots."""

    def _cfg(self) -> dict:
        """Load and return the parsed Codecov configuration."""
        return _load_yaml("codecov.yml")

    def test_hide_project_coverage_and_require_head(self):
        comment = self._cfg()["comment"]
        assert comment.get("hide_project_coverage") is True
        assert comment.get("require_head") is True
        assert comment.get("require_changes") is True

    def test_annotations_enabled(self):
        assert self._cfg()["github_checks"]["annotations"] is True

    def test_component_ids_stable(self):
        comps = self._cfg()["component_management"]["individual_components"]
        ids = {c["component_id"] for c in comps}
        assert ids == {"semantic_core", "telemetry", "cli_main", "intent_ranker"}

    def test_semantic_core_paths_stable(self):
        comps = {c["component_id"]: c for c in self._cfg()["component_management"]["individual_components"]}
        paths = set(comps["semantic_core"]["paths"])
        assert paths == {
            "src/git_cg/ast_parser.py",
            "src/git_cg/fingerprints.py",
            "src/git_cg/similarity.py",
            "src/git_cg/git_index.py",
            "src/git_cg/graph_context.py",
            "src/git_cg/semantic_flags.py",
        }

    def test_root_patch_has_no_paths_or_flags(self):
        patch_default = self._cfg()["coverage"]["status"]["patch"]["default"]
        assert "paths" not in patch_default
        assert "flags" not in patch_default
        assert patch_default.get("target") == "80%"
