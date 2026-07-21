"""
Regression tests for .github/workflows/security.yml (Issue #170 Slice 1).

Enforces supply-chain contracts:
  - Action SHA pins (no @main / floating major tags on touched actions)
  - TruffleHog action SHA + scanner version pin
  - No curl|sh installers for Syft/Grype/Grant
  - mise-based tool install + version verification
  - Correct ACT artifact condition
  - concurrency + least-privilege permissions
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _load_yaml(rel_path: str) -> dict:
    data = yaml.safe_load((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and True in data:
        data["on"] = data.pop(True)
    return data


class TestSecurityWorkflow:
    def _workflow(self) -> dict:
        return _load_yaml(".github/workflows/security.yml")

    def _raw(self) -> str:
        return (REPO_ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")

    def test_file_is_valid_yaml(self):
        assert isinstance(self._workflow(), dict)

    def test_concurrency_group_formula(self):
        wf = self._workflow()
        assert "concurrency" in wf
        group = wf["concurrency"]["group"]
        assert "${{ github.workflow }}" in group or "github.workflow" in group
        assert "pull_request.number" in group
        assert wf["concurrency"].get("cancel-in-progress") is True

    def test_top_level_permissions_contents_read_only(self):
        perms = self._workflow()["permissions"]
        assert perms.get("contents") == "read"
        assert set(perms.keys()) == {"contents"}

    def test_no_mutable_trufflehog_main(self):
        raw = self._raw()
        assert "trufflesecurity/trufflehog@main" not in raw
        assert "trufflesecurity/trufflehog@master" not in raw

    def test_no_curl_pipe_sh_installers(self):
        raw = self._raw()
        assert "curl" not in raw or "| sh" not in raw
        assert "install.sh | sh" not in raw
        assert "curl -sSfL" not in raw

    def test_no_latest_scanner_tags_in_workflow(self):
        # workflow must not install tools at floating latest; pins live in mise.toml
        raw = self._raw()
        assert 'version: "latest"' not in raw
        assert "version: latest" not in raw

    def test_all_uses_are_full_shas(self):
        wf = self._workflow()
        for job in wf["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if not uses:
                    continue
                assert "@" in uses, uses
                ref = uses.split("@", 1)[1]
                assert SHA40.match(ref), f"Action not SHA-pinned: {uses}"

    def test_trufflehog_version_pinned(self):
        step = None
        for s in self._workflow()["jobs"]["trufflehog"]["steps"]:
            if s.get("name") == "TruffleHog OSS":
                step = s
                break
        assert step is not None
        assert step["with"]["version"] == "3.95.9"
        assert SHA40.match(step["uses"].split("@", 1)[1])

    def test_trufflehog_event_aware_base_head(self):
        step = next(s for s in self._workflow()["jobs"]["trufflehog"]["steps"] if s.get("name") == "TruffleHog OSS")
        base = step["with"]["base"]
        head = step["with"]["head"]
        assert "pull_request" in base
        assert "base.sha" in base
        assert "github.event.before" in base or "before" in base
        assert "pull_request" in head
        assert "head.sha" in head or "github.sha" in head

    def test_trufflehog_checkout_fetch_depth_zero(self):
        checkout = next(s for s in self._workflow()["jobs"]["trufflehog"]["steps"] if "Checkout" in s.get("name", ""))
        assert checkout["with"]["fetch-depth"] == 0

    def test_sbom_uses_mise_action(self):
        steps = self._workflow()["jobs"]["sbom"]["steps"]
        mise_steps = [s for s in steps if "mise" in s.get("name", "").lower() or "mise-action" in s.get("uses", "")]
        assert mise_steps, "SBOM job must install tools via mise-action"
        assert any("jdx/mise-action@" in s.get("uses", "") for s in mise_steps)

    def test_sbom_verifies_tool_versions(self):
        step = next(
            s for s in self._workflow()["jobs"]["sbom"]["steps"] if s.get("name") == "Verify SBOM tool versions"
        )
        run = step["run"]
        assert "1.48.0" in run  # syft
        assert "0.116.0" in run  # grype
        assert "0.6.8" in run  # grant

    def test_act_condition_not_truthy_string_false(self):
        raw = self._raw()
        assert 'ACT: "false"' not in raw
        assert "!env.ACT" not in raw
        upload = next(s for s in self._workflow()["jobs"]["sbom"]["steps"] if s.get("name") == "Upload SBOM Artifact")
        assert upload["if"] == "${{ env.ACT != 'true' }}"

    def test_sbom_outputs_and_scans_preserved(self):
        raw = self._raw()
        assert "bom.json" in raw
        assert "bom.syft.json" in raw
        assert "grant check bom.syft.json --dry-run" in raw
        assert "grype sbom:bom.json --fail-on high" in raw

    def test_jobs_do_not_elevate_permissions(self):
        wf = self._workflow()
        for name, job in wf["jobs"].items():
            perms = job.get("permissions", {"contents": "read"})
            assert perms.get("contents") == "read", name
            assert "write" not in str(perms.values())

    def test_trufflehog_scans_full_repo_path(self):
        """TruffleHog must scan the full checked-out repository root."""
        step = next(s for s in self._workflow()["jobs"]["trufflehog"]["steps"] if s.get("name") == "TruffleHog OSS")
        assert step["with"]["path"] == "./"

    def test_trufflehog_only_verified_flag_preserved(self):
        """`--only-verified` must remain set to avoid noisy unverified findings."""
        step = next(s for s in self._workflow()["jobs"]["trufflehog"]["steps"] if s.get("name") == "TruffleHog OSS")
        assert step["with"]["extra_args"] == "--only-verified"

    def test_trufflehog_job_step_order(self):
        """The trufflehog job must checkout before running the TruffleHog action."""
        names = [s.get("name") for s in self._workflow()["jobs"]["trufflehog"]["steps"]]
        assert names == ["Checkout code", "TruffleHog OSS"]

    def test_sbom_mise_action_installs_and_caches(self):
        """The sbom job's mise-action step must enable install and cache."""
        step = next(
            s for s in self._workflow()["jobs"]["sbom"]["steps"] if s.get("name") == "Install mise tools"
        )
        assert step["uses"].startswith("jdx/mise-action@")
        assert step["with"]["install"] is True
        assert step["with"]["cache"] is True

    def test_sbom_job_step_order(self):
        """SBOM job steps must run in the documented dependency order."""
        names = [s.get("name") for s in self._workflow()["jobs"]["sbom"]["steps"]]
        expected_order = [
            "Checkout code",
            "Install mise tools",
            "Verify SBOM tool versions",
            "Generate SBOMs (Syft)",
            "Upload SBOM Artifact",
            "License Compliance (Grant)",
            "Vulnerability Scan (Grype)",
        ]
        assert names == expected_order

    def test_sbom_grant_and_grype_run_after_generation(self):
        """Grant and Grype must run after the SBOM has been generated, not before."""
        names = [s.get("name") for s in self._workflow()["jobs"]["sbom"]["steps"]]
        assert names.index("Generate SBOMs (Syft)") < names.index("License Compliance (Grant)")
        assert names.index("Generate SBOMs (Syft)") < names.index("Vulnerability Scan (Grype)")

    def test_verify_sbom_tool_versions_uses_strict_shell(self):
        """The version-verification step must fail fast on any pipeline error."""
        step = next(
            s for s in self._workflow()["jobs"]["sbom"]["steps"] if s.get("name") == "Verify SBOM tool versions"
        )
        assert "set -euo pipefail" in step["run"]

    def test_trufflehog_checkout_and_sbom_checkout_use_pinned_checkout(self):
        """Both jobs must checkout via the same SHA-pinned actions/checkout ref."""
        wf = self._workflow()
        trufflehog_checkout = next(
            s for s in wf["jobs"]["trufflehog"]["steps"] if s.get("name") == "Checkout code"
        )
        sbom_checkout = next(s for s in wf["jobs"]["sbom"]["steps"] if s.get("name") == "Checkout code")
        assert trufflehog_checkout["uses"] == sbom_checkout["uses"]
        assert trufflehog_checkout["uses"].startswith("actions/checkout@")
