"""
Tests for CI/CD and packaging configuration changes in this PR:
  - .github/workflows/ci.yml    (codecov-action SHA-pinned; `files`; #170 OIDC layout; #177 WP2 majors)
  - .github/workflows/docs.yml  (removed `--strict` from `zensical build`)
  - pyproject.toml              (requires-python gained an upper bound `<4.0`)
  - uv.lock                     (requires-python mirrors pyproject.toml)
  - .gitignore                  (new `bom.syft.json` ignore pattern, Issue #170 nice-to-have)
"""

import fnmatch
import subprocess
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
    """Tests for the dedicated Codecov OIDC upload job of ci.yml."""

    def _workflow(self) -> dict:
        """Load the CI workflow configuration."""
        return _load_yaml(".github/workflows/ci.yml")

    def _upload_job(self) -> dict:
        """Return the dedicated same-repo Codecov upload job."""
        jobs = self._workflow()["jobs"]
        assert "upload-coverage" in jobs, "upload-coverage job not found in ci.yml"
        return jobs["upload-coverage"]

    def _codecov_step(self) -> dict:
        """
        Finds the Codecov upload step in the dedicated upload job.

        Returns:
                dict: The configuration for the Codecov upload step.

        Raises:
                AssertionError: If the Codecov upload step is not present.
        """
        steps = self._upload_job()["steps"]
        for step in steps:
            if step.get("name") == "Upload coverage to Codecov":
                return step
        raise AssertionError("Codecov upload step not found in upload-coverage job")

    def test_file_is_valid_yaml(self):
        """ci.yml must parse as valid YAML."""
        assert isinstance(self._workflow(), dict)

    def test_codecov_action_pinned_to_allowed_major_sha(self):
        """Codecov upload must use the WP2-pinned codecov-action v7 commit SHA."""
        step = self._codecov_step()
        assert step["uses"] == ("codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f")

    def test_codecov_action_not_floating_tag(self):
        """Codecov must not use a floating tag ref (SHA pin required)."""
        step = self._codecov_step()
        uses = step["uses"]
        assert uses.startswith("codecov/codecov-action@")
        ref = uses.split("@", 1)[1]
        assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)
        assert uses != "codecov/codecov-action@v7"
        assert uses != "codecov/codecov-action@v4"

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
        """Fork PRs must skip the dedicated Codecov upload job entirely."""
        job = self._upload_job()
        # Exact same-repo eligibility gate (excludes fork PRs).
        assert job.get("if") == (
            "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"
        )
        # Gate is job-level so fork PR code never receives id-token: write.
        assert "if" not in self._codecov_step()

    def test_upload_job_permissions_exact_keys(self):
        """upload-coverage must grant exactly `contents: read` and `id-token: write` (no extra scopes)."""
        job = self._upload_job()
        perms = job["permissions"]
        assert set(perms.keys()) == {"contents", "id-token"}
        assert perms["contents"] == "read"
        assert perms["id-token"] == "write"

    def test_oidc_comment_relocated_inline_above_id_token(self):
        """
        The OIDC token-exchange rationale comment moved from a standalone line above
        `permissions:` to an inline comment directly above `id-token: write` (Issue #170).
        """
        raw = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        job_block = raw.split("upload-coverage:", 1)[1]

        # The old standalone comment (above `permissions:`) must be gone.
        assert "# Codecov action v4 OIDC token exchange — scoped to this upload job only." not in job_block

        # The new inline comment text must be present.
        assert "elevated permission scoped to this" in job_block
        assert "same-repo upload job only (fork PRs never reach this job)." in job_block

        # Ordering: contents: read -> comment -> id-token: write, all within `permissions:`.
        contents_idx = job_block.index("contents: read")
        comment_idx = job_block.index("elevated permission scoped to this")
        id_token_idx = job_block.index("id-token: write")
        assert contents_idx < comment_idx < id_token_idx

    def test_upload_job_depends_on_test_and_coverage(self):
        """Coverage upload must wait for the test job that produces coverage.xml."""
        job = self._upload_job()
        needs = job.get("needs")
        if isinstance(needs, str):
            needs = [needs]
        assert needs == ["test-and-coverage"]

    def test_test_job_uploads_coverage_artifact(self):
        """test-and-coverage must publish coverage.xml for the OIDC upload job."""
        steps = self._workflow()["jobs"]["test-and-coverage"]["steps"]
        names = [s.get("name") for s in steps]
        assert "Upload coverage artifact" in names
        assert names.index("Run Tests with Coverage") < names.index("Upload coverage artifact")
        artifact_step = next(s for s in steps if s.get("name") == "Upload coverage artifact")
        assert artifact_step["uses"].startswith("actions/upload-artifact@")
        assert artifact_step["with"]["name"] == "coverage-xml"
        assert artifact_step["with"]["path"] == "./coverage.xml"
        assert artifact_step["with"]["if-no-files-found"] == "error"
        # Upload must not remain in the test job (OIDC stays on upload-coverage only).
        assert "Upload coverage to Codecov" not in names

    def test_upload_job_downloads_coverage_artifact(self):
        """upload-coverage must restore coverage.xml before invoking Codecov."""
        steps = self._upload_job()["steps"]
        names = [s.get("name") for s in steps]
        assert names.index("Download coverage artifact") < names.index("Upload coverage to Codecov")
        download = next(s for s in steps if s.get("name") == "Download coverage artifact")
        assert download["uses"].startswith("actions/download-artifact@")
        assert download["with"]["name"] == "coverage-xml"

    def test_codecov_step_runs_after_test_step(self):
        """Codecov upload is a dependent job after tests produce coverage.xml."""
        wf = self._workflow()
        test_names = [s.get("name") for s in wf["jobs"]["test-and-coverage"]["steps"]]
        upload_names = [s.get("name") for s in self._upload_job()["steps"]]
        assert "Run Tests with Coverage" in test_names
        assert upload_names.index("Upload coverage to Codecov") == len(upload_names) - 1

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

    def _test_job_steps(self) -> list:
        """Return the steps configured for the test-and-coverage job."""
        return self._workflow()["jobs"]["test-and-coverage"]["steps"]

    def test_test_job_installs_betterleaks_via_mise(self):
        """test-and-coverage must install betterleaks so live redaction probes work in CI."""
        step = next(s for s in self._test_job_steps() if s.get("name") == "Install betterleaks via mise")
        uses = step["uses"]
        assert uses.startswith("jdx/mise-action@")
        ref = uses.split("@", 1)[1]
        assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
            f"Install betterleaks via mise must be pinned to a full commit SHA, got {uses!r}"
        )
        assert step["with"]["install"] is True
        assert step["with"]["cache"] is True
        assert step["with"]["install_args"] == "betterleaks"

    def test_test_job_betterleaks_install_before_pytest(self):
        """betterleaks must be on PATH before Run Tests with Coverage."""
        names = [s.get("name") for s in self._test_job_steps()]
        assert "Install betterleaks via mise" in names
        assert names.index("Install betterleaks via mise") < names.index("Run Tests with Coverage")
        # Checkout first; uv/python can follow or precede the tool install, but
        # the redaction binary must exist before pytest launches.
        assert names.index("Checkout repository") < names.index("Install betterleaks via mise")

    def test_test_job_and_lint_share_mise_action_pin(self):
        """Lint and test jobs must use the same SHA-pinned mise-action."""
        lint_steps = self._workflow()["jobs"]["lint"]["steps"]
        lint_step = next(s for s in lint_steps if s.get("name") == "Install mise tools")
        test_step = next(s for s in self._test_job_steps() if s.get("name") == "Install betterleaks via mise")
        assert lint_step["uses"] == test_step["uses"]


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
        """Load the CI workflow configuration from its repository YAML file.

        Returns:
                dict: The parsed CI workflow configuration.
        """
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
        """id-token: write must be confined to the dedicated Codecov upload job."""
        wf = self._workflow()
        upload_perms = wf["jobs"]["upload-coverage"]["permissions"]
        assert upload_perms.get("id-token") == "write"
        test_perms = wf["jobs"]["test-and-coverage"]["permissions"]
        assert test_perms.get("id-token") != "write"
        lint_job = wf["jobs"]["lint"]
        lint_perms = lint_job.get("permissions", {})
        assert lint_perms.get("id-token") != "write"
        # Top-level must not grant id-token write
        assert wf["permissions"].get("id-token") != "write"

    def test_checkout_and_setup_uv_pinned_to_sha(self):
        """Retain explicit checkout/setup-uv pin checks (subset of all-uses SHA lock)."""
        wf = self._workflow()
        for job_name in ("lint", "test-and-coverage", "upload-coverage"):
            for step in wf["jobs"][job_name]["steps"]:
                uses = step.get("uses", "")
                if uses.startswith("actions/checkout@") or uses.startswith("astral-sh/setup-uv@"):
                    ref = uses.split("@", 1)[1]
                    assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
                        f"{job_name}: {uses} must be full commit SHA"
                    )

    def test_all_uses_are_full_shas(self):
        """Every third-party action in ci.yml must be full 40-char commit SHA-pinned."""
        wf = self._workflow()
        for job_name, job in wf["jobs"].items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if not uses:
                    continue
                assert "@" in uses, f"{job_name}: {uses}"
                ref = uses.split("@", 1)[1]
                assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
                    f"{job_name}: action not SHA-pinned: {uses}"
                )

    def test_checkout_disables_persist_credentials(self):
        wf = self._workflow()
        for job_name, job in wf["jobs"].items():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if uses.startswith("actions/checkout@"):
                    with_block = step.get("with") or {}
                    assert with_block.get("persist-credentials") is False, (
                        f"{job_name}: checkout must set persist-credentials: false"
                    )

    def test_lint_job_exists(self):
        assert "lint" in self._workflow()["jobs"]

    def _lint_steps(self) -> list:
        """Return the steps configured for the lint job."""
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

    def test_lint_fetches_pr_base_branch(self):
        steps = self._lint_steps()
        step = next(s for s in steps if s.get("name") == "Fetch PR base branch for hk --pr")
        assert step.get("if") == "github.event_name == 'pull_request'"
        env = step.get("env") or {}
        # GitHub expressions must live in env, not interpolated inside run.
        assert env.get("BASE_REF") == "${{ github.base_ref }}"
        assert env.get("REPO") == "${{ github.repository }}"
        assert env.get("GH_TOKEN") == "${{ github.token }}"
        run = step["run"]
        assert "git fetch" in run
        assert "refs/remotes/origin/" in run
        assert "${BASE_REF}" in run
        assert "${REPO}" in run
        assert "${GH_TOKEN}" in run
        assert "${{ github." not in run
        # Must run before hk check PR step
        names = [s.get("name") for s in steps]
        assert names.index("Fetch PR base branch for hk --pr") < names.index("hk check (pull_request)")

    def test_no_prepare_commit_msg_in_ci(self):
        """Ensure the CI workflow does not configure commit-message preparation hooks."""
        raw = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "prepare-commit-msg" not in raw
        assert "commit-msg" not in raw
        assert "validate-commit" not in raw

    def test_concurrency_group_formula_exact(self):
        """The concurrency group formula must exactly match the documented contract."""
        wf = self._workflow()
        assert wf["concurrency"]["group"] == (
            "${{ github.workflow }}-${{ github.event.pull_request.number || github.ref || github.run_id }}"
        )

    def test_only_lint_and_coverage_jobs_present(self):
        """CI must only define lint, tests, and the dedicated Codecov upload job."""
        wf = self._workflow()
        assert set(wf["jobs"].keys()) == {"lint", "test-and-coverage", "upload-coverage"}

    def test_top_level_permissions_only_contents(self):
        """Top-level permissions must be scoped to `contents: read` only (no extra keys)."""
        wf = self._workflow()
        assert set(wf["permissions"].keys()) == {"contents"}

    def test_lint_job_permissions_only_contents(self):
        """
        Verify that the lint job grants only read access to repository contents.
        """
        wf = self._workflow()
        lint_perms = wf["jobs"]["lint"].get("permissions", {})
        assert set(lint_perms.keys()) == {"contents"}
        assert lint_perms["contents"] == "read"

    def test_mise_action_pinned_and_configured_in_lint_job(self):
        """The `Install mise tools` step must be SHA-pinned with install/cache enabled."""
        step = next(s for s in self._lint_steps() if s.get("name") == "Install mise tools")
        uses = step["uses"]
        assert uses.startswith("jdx/mise-action@")
        ref = uses.split("@", 1)[1]
        assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
            f"Install mise tools must be pinned to a full commit SHA, got {uses!r}"
        )
        assert step["with"]["install"] is True
        assert step["with"]["cache"] is True

    def test_install_dependencies_step_uses_uv_sync_all_extras(self):
        """The lint job must install the full dev/extras dependency set for hk steps."""
        step = next(s for s in self._lint_steps() if s.get("name") == "Install dependencies")
        assert step["run"] == "uv sync --all-extras --dev"

    def test_hk_validate_step_runs_unconditionally(self):
        """`hk validate` must run on every trigger (no `if` gate)."""
        step = next(s for s in self._lint_steps() if s.get("name") == "hk validate")
        assert step["run"] == "hk validate"
        assert "if" not in step

    def test_lint_step_order(self):
        """Lint job steps must run in the documented dependency order."""
        names = [s.get("name") for s in self._lint_steps()]
        expected_order = [
            "Checkout repository",
            "Fetch PR base branch for hk --pr",
            "Install mise tools",
            "Install uv",
            "Set up Python",
            "Install dependencies",
            "hk validate",
            "hk check (pull_request)",
            "hk check (push / workflow_dispatch)",
        ]
        assert names == expected_order

    def test_lint_pr_and_push_checks_are_mutually_exclusive_conditions(self):
        """The pull_request and push/dispatch hk check steps must use complementary `if` guards."""
        pr_step = next(s for s in self._lint_steps() if s.get("name") == "hk check (pull_request)")
        push_step = next(s for s in self._lint_steps() if s.get("name") == "hk check (push / workflow_dispatch)")
        assert pr_step["if"] == "github.event_name == 'pull_request'"
        assert push_step["if"] == "github.event_name != 'pull_request'"


# ===========================================================================
# .gitignore - bom.syft.json pattern (Issue #170 nice-to-have)
# ===========================================================================


class TestGitignoreBomSyftPattern:
    """Tests for the new `bom.syft.json` ignore pattern added alongside `bom.json`."""

    def _lines(self) -> list:
        """Return the lines of the repository's .gitignore file."""
        return (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    def test_bom_syft_json_pattern_present(self):
        """The literal `bom.syft.json` pattern must exist as its own line in .gitignore."""
        assert "bom.syft.json" in self._lines()

    def test_bom_json_pattern_still_present(self):
        """The pre-existing `bom.json` entry must not have been removed by this change."""
        assert "bom.json" in self._lines()

    def test_bom_syft_json_immediately_follows_bom_json(self):
        """The new pattern was added directly below the existing `bom.json` line."""
        lines = self._lines()
        idx = lines.index("bom.json")
        assert lines[idx + 1] == "bom.syft.json"

    def test_bom_patterns_precede_vscode_unignore_rule(self):
        """Both bom patterns must remain above the trailing `!.vscode/` unignore rule."""
        lines = self._lines()
        assert lines.index("bom.syft.json") < lines.index("!.vscode/")

    def test_bom_syft_json_matches_generated_sbom_filename(self):
        """The pattern must match the exact filename produced by `syft . -o syft-json=bom.syft.json`."""
        assert fnmatch.fnmatch("bom.syft.json", "bom.syft.json")

    def test_bom_syft_json_pattern_is_distinct_from_bom_json(self):
        """`bom.syft.json` and `bom.json` are distinct, non-overlapping literal patterns."""
        assert not fnmatch.fnmatch("bom.json", "bom.syft.json")
        assert not fnmatch.fnmatch("bom.syft.json", "bom.json")

    def test_git_check_ignore_reports_bom_syft_json_as_ignored(self):
        """Functional check: `git check-ignore` must classify `bom.syft.json` as ignored."""
        result = subprocess.run(
            ["git", "check-ignore", "-q", "bom.syft.json"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, "bom.syft.json should be reported as ignored by git"


# ===========================================================================
# codecov.yml residual locks (component map must not churn)
# ===========================================================================


class TestCodecovYmlContracts:
    """Lock landed #169 Codecov semantics without brittle full-file snapshots."""

    def _cfg(self) -> dict:
        """Load the Codecov configuration as a dictionary."""
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

    def test_all_component_paths_and_names_stable(self):
        """Full component taxonomy lock beyond IDs (Issue #170 nice-to-have)."""
        comps = {c["component_id"]: c for c in self._cfg()["component_management"]["individual_components"]}
        expected = {
            "semantic_core": {
                "name": "semantic-core",
                "paths": {
                    "src/git_cg/ast_parser.py",
                    "src/git_cg/fingerprints.py",
                    "src/git_cg/similarity.py",
                    "src/git_cg/git_index.py",
                    "src/git_cg/graph_context.py",
                    "src/git_cg/semantic_flags.py",
                },
            },
            "telemetry": {
                "name": "telemetry",
                "paths": {
                    "src/git_cg/telemetry.py",
                    "src/git_cg/sentry_config.py",
                },
            },
            "cli_main": {
                "name": "cli-main",
                "paths": {"src/git_cg/main.py"},
            },
            "intent_ranker": {
                "name": "intent-ranker",
                "paths": {
                    "src/git_cg/intent.py",
                    "src/git_cg/regeneration.py",
                    "src/git_cg/models.py",
                    "src/git_cg/sop.py",
                },
            },
        }
        assert set(comps) == set(expected)
        for cid, exp in expected.items():
            assert comps[cid]["name"] == exp["name"]
            assert set(comps[cid]["paths"]) == exp["paths"]

    def test_root_patch_has_no_paths_or_flags(self):
        """Verify that the root patch coverage configuration has an 80% target without path or flag filters."""
        patch_default = self._cfg()["coverage"]["status"]["patch"]["default"]
        assert "paths" not in patch_default
        assert "flags" not in patch_default
        assert patch_default.get("target") == "80%"


# ===========================================================================
# Cross-workflow SHA pin matrix (Issue #177 WP2)
# ===========================================================================


def _load_workflow(name: str) -> dict:
    """Load a workflow YAML document from ``.github/workflows/{name}``."""
    import yaml

    path = REPO_ROOT / ".github" / "workflows" / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _assert_uses_full_sha(workflow_name: str, uses: str) -> None:
    """
    Validate that a workflow action reference uses a full lowercase commit SHA.

    Parameters:
        workflow_name (str): Name of the workflow containing the action reference.
        uses (str): Action reference to validate.
    """
    assert "@" in uses, f"{workflow_name}: {uses}"
    ref = uses.split("@", 1)[1].split()[0]  # strip trailing comments if any
    # YAML loader already drops comments; keep split for safety.
    assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
        f"{workflow_name}: action not SHA-pinned: {uses}"
    )


class TestWorkflowShaPinMatrix:
    """Every third-party action under .github/workflows must be full-SHA pinned."""

    WORKFLOWS = (
        "ci.yml",
        "security.yml",
        "docs.yml",
        "codeql.yml",
        "pr-review.yml",
        "pr-review-comment.yml",
    )

    def test_all_workflow_uses_are_full_shas(self):
        for name in self.WORKFLOWS:
            wf = _load_workflow(name)
            for job_name, job in (wf.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    uses = step.get("uses")
                    if not uses:
                        continue
                    _assert_uses_full_sha(f"{name}:{job_name}", uses)

    def test_pr_review_workflows_are_sha_pinned(self):
        """Former floating @v7/@v8 tags must be full SHAs after WP2."""
        for name in ("pr-review.yml", "pr-review-comment.yml"):
            wf = _load_workflow(name)
            for job in (wf.get("jobs") or {}).values():
                for step in job.get("steps") or []:
                    uses = step.get("uses")
                    if not uses:
                        continue
                    _assert_uses_full_sha(name, uses)

    def test_pr_review_checkout_disables_persist_credentials(self):
        wf = _load_workflow("pr-review.yml")
        for step in wf["jobs"]["review"]["steps"]:
            uses = step.get("uses", "")
            if uses.startswith("actions/checkout@"):
                assert (step.get("with") or {}).get("persist-credentials") is False


# ===========================================================================
# Cross-workflow SHA pin *consistency* matrix (Issue #177 WP2)
#
# TestWorkflowShaPinMatrix (above) only proves every `uses:` is *some* 40-char
# SHA. These tests additionally lock the exact upgraded SHAs and prove the
# same action is pinned to the *same* commit everywhere it appears, so a
# partial/inconsistent major bump across workflows cannot land silently.
# ===========================================================================


class TestActionShaVersionConsistency:
    """Exact SHA pins introduced by WP2 must be identical across every workflow using them."""

    CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"  # v7.0.1
    SETUP_UV_SHA = "c771a70e6277c0a99b617c7a806ffedaca235ff9"  # v9.0.0
    UPLOAD_ARTIFACT_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"  # v7.0.1
    DOWNLOAD_ARTIFACT_SHA = "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"  # v8.0.1
    CODECOV_ACTION_SHA = "fb8b3582c8e4def4969c97caa2f19720cb33a72f"  # v7.0.0
    CODEQL_ACTION_SHA = "e4fba868fa4b1b91e1fdab776edc8cfbe6e9fb81"  # v4.37.3
    SETUP_PYTHON_SHA = "5fda3b95a4ea91299a34e894583c3862153e4b97"  # v7.0.0
    CRG_ACTION_SHA = "6a1ee1c7063cc35cfa5ff12b8198c29360f3e4ad"  # v2.3.7

    def _all_uses(self) -> list[tuple[str, str, str]]:
        """Return (workflow, job, uses) triples for every step across all workflows."""
        out: list[tuple[str, str, str]] = []
        for name in TestWorkflowShaPinMatrix.WORKFLOWS:
            wf = _load_workflow(name)
            for job_name, job in (wf.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    uses = step.get("uses")
                    if uses:
                        out.append((name, job_name, uses))
        return out

    def _uses_for_action(self, action: str) -> list[str]:
        """Return every `uses:` value whose action name matches ``action`` exactly."""
        return [uses for _wf, _job, uses in self._all_uses() if uses.split("@", 1)[0] == action]

    def test_checkout_pinned_identically_everywhere(self):
        uses_values = self._uses_for_action("actions/checkout")
        assert uses_values, "expected at least one actions/checkout step"
        assert all(u == f"actions/checkout@{self.CHECKOUT_SHA}" for u in uses_values)

    def test_setup_uv_pinned_identically_everywhere(self):
        uses_values = self._uses_for_action("astral-sh/setup-uv")
        assert uses_values, "expected at least one astral-sh/setup-uv step"
        assert all(u == f"astral-sh/setup-uv@{self.SETUP_UV_SHA}" for u in uses_values)

    def test_upload_artifact_pinned_identically_everywhere(self):
        uses_values = self._uses_for_action("actions/upload-artifact")
        assert uses_values, "expected at least one actions/upload-artifact step"
        assert all(u == f"actions/upload-artifact@{self.UPLOAD_ARTIFACT_SHA}" for u in uses_values)

    def test_download_artifact_pinned_identically_everywhere(self):
        uses_values = self._uses_for_action("actions/download-artifact")
        assert uses_values, "expected at least one actions/download-artifact step"
        assert all(u == f"actions/download-artifact@{self.DOWNLOAD_ARTIFACT_SHA}" for u in uses_values)

    def test_codecov_action_sha_matches_expected_v7(self):
        uses_values = self._uses_for_action("codecov/codecov-action")
        assert uses_values == [f"codecov/codecov-action@{self.CODECOV_ACTION_SHA}"]

    def test_codeql_action_init_and_analyze_share_sha(self):
        init_uses = self._uses_for_action("github/codeql-action/init")
        analyze_uses = self._uses_for_action("github/codeql-action/analyze")
        assert init_uses == [f"github/codeql-action/init@{self.CODEQL_ACTION_SHA}"]
        assert analyze_uses == [f"github/codeql-action/analyze@{self.CODEQL_ACTION_SHA}"]

    def test_setup_python_sha_matches_expected_v7(self):
        uses_values = self._uses_for_action("actions/setup-python")
        assert uses_values == [f"actions/setup-python@{self.SETUP_PYTHON_SHA}"]

    def test_code_review_graph_action_sha_matches_expected_v2_3_7(self):
        uses_values = self._uses_for_action("tirth8205/code-review-graph")
        assert uses_values == [f"tirth8205/code-review-graph@{self.CRG_ACTION_SHA}"]

    def test_no_workflow_still_uses_pre_wp2_checkout_shas(self):
        """Guard against reintroducing the stale pre-WP2 checkout SHAs."""
        stale_shas = {
            "11bd71901bbe5b1630ceea73d27597364c9af683",
            "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
        }
        for _wf, _job, uses in self._all_uses():
            if uses.startswith("actions/checkout@"):
                ref = uses.split("@", 1)[1]
                assert ref not in stale_shas, uses

    def test_pr_review_yml_checkout_step_has_explicit_name(self):
        """The formerly anonymous `- uses: actions/checkout@v7` step must now be named."""
        wf = _load_workflow("pr-review.yml")
        first_step = wf["jobs"]["review"]["steps"][0]
        assert first_step.get("name") == "Checkout repository"
        assert first_step["uses"] == f"actions/checkout@{self.CHECKOUT_SHA}"


# ===========================================================================
# pyproject.toml — Issue #177 WP1 dependency floor *semantics* (SpecifierSet
# boundary checks, not just substring matches on the raw text)
# ===========================================================================


class TestPyprojectDependencyFloorSemantics:
    """Boundary-check the WP1 floors using real version resolution, not string matching."""

    def _dependency_specifiers(self) -> dict:
        """Map dependency name -> SpecifierSet for `[project.dependencies]`."""
        from packaging.requirements import Requirement

        data = _load_pyproject()
        return {Requirement(d).name: Requirement(d).specifier for d in data["project"]["dependencies"]}

    def _dev_group_specifiers(self) -> dict:
        """Map dependency name -> SpecifierSet for the `dev` dependency group."""
        from packaging.requirements import Requirement

        data = _load_pyproject()
        return {Requirement(d).name: Requirement(d).specifier for d in data["dependency-groups"]["dev"]}

    def test_tree_sitter_language_pack_bounds(self):
        spec = self._dependency_specifiers()["tree-sitter-language-pack"]
        assert Version("0.13.0") in spec
        assert Version("0.99.0") in spec
        assert Version("0.12.9") not in spec
        assert Version("1.0.0") not in spec

    def test_tree_sitter_bounds(self):
        spec = self._dependency_specifiers()["tree-sitter"]
        assert Version("0.26.0") in spec
        assert Version("0.26.9") in spec
        assert Version("0.25.9") not in spec
        assert Version("0.27.0") not in spec

    def test_rich_bounds(self):
        spec = self._dependency_specifiers()["rich"]
        assert Version("14.3.4") in spec
        assert Version("15.9.9") in spec
        assert Version("14.3.3") not in spec
        assert Version("16.0.0") not in spec

    def test_code_review_graph_floor(self):
        spec = self._dependency_specifiers()["code-review-graph"]
        assert Version("2.3.7") in spec
        assert Version("2.3.6") not in spec

    def test_dev_group_pytest_and_pytest_cov_floors(self):
        dev_specs = self._dev_group_specifiers()
        assert Version("9.1.1") in dev_specs["pytest"]
        assert Version("8.9.9") not in dev_specs["pytest"]
        assert Version("7.0.0") in dev_specs["pytest-cov"]
        assert Version("6.9.9") not in dev_specs["pytest-cov"]


# ===========================================================================
# uv.lock — locked versions must actually satisfy the pyproject.toml floors
# introduced by Issue #177 WP1/WP5, and code-review-graph's new transitive
# dependency (pyyaml) must be reflected in the lock graph.
# ===========================================================================


class TestUvLockSatisfiesDependencyFloors:
    def _uv_lock_package(self, name: str) -> dict:
        """Return the `[[package]]` table entry for ``name`` from uv.lock."""
        data = _load_uv_lock()
        for pkg in data["package"]:
            if pkg["name"] == name:
                return pkg
        raise AssertionError(f"package {name!r} not found in uv.lock")

    def test_locked_dependency_versions_satisfy_pyproject_floors(self):
        from packaging.requirements import Requirement

        pyproject = _load_pyproject()
        specs = {Requirement(d).name: Requirement(d).specifier for d in pyproject["project"]["dependencies"]}
        for name in ("tree-sitter", "tree-sitter-language-pack", "rich", "code-review-graph"):
            locked_version = Version(self._uv_lock_package(name)["version"])
            assert locked_version in specs[name], f"{name} locked={locked_version} spec={specs[name]}"

    def test_locked_dev_versions_satisfy_pyproject_floors(self):
        from packaging.requirements import Requirement

        pyproject = _load_pyproject()
        dev_specs = {Requirement(d).name: Requirement(d).specifier for d in pyproject["dependency-groups"]["dev"]}
        for name in ("pytest", "pytest-cov"):
            locked_version = Version(self._uv_lock_package(name)["version"])
            assert locked_version in dev_specs[name], f"{name} locked={locked_version} spec={dev_specs[name]}"

    def test_locked_versions_match_expected_wp5_bumps(self):
        """Exact locked versions after the WP5 dependency bumps in this PR."""
        assert self._uv_lock_package("tree-sitter")["version"] == "0.26.0"
        assert self._uv_lock_package("pytest")["version"] == "9.1.1"
        assert self._uv_lock_package("code-review-graph")["version"] == "2.3.7"

    def test_code_review_graph_lock_entry_depends_on_pyyaml(self):
        """code-review-graph 2.3.7 must declare pyyaml as a new transitive dependency."""
        pkg = self._uv_lock_package("code-review-graph")
        dep_names = {d["name"] for d in pkg.get("dependencies", [])}
        assert "pyyaml" in dep_names

    def test_pyproject_metadata_code_review_graph_requirement_bumped(self):
        """uv.lock's [package.metadata] requires-dist must mirror the >=2.3.7 floor."""
        data = _load_uv_lock()
        root_pkg = next(p for p in data["package"] if p["name"] == "gitcommitgenerator")
        entries = root_pkg["metadata"]["requires-dist"]
        crg_entry = next(e for e in entries if e["name"] == "code-review-graph")
        assert crg_entry["specifier"] == ">=2.3.7"
