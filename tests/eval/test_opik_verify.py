"""S7-1b / S7-2b: optional online Opik verify (advisory, injectable client)."""

from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from git_cg.eval.mirror.opik_verify import OPIK_VERIFY_AUTHORITY, run_opik_verify
from git_cg.main import app

runner = CliRunner()


class _FakeClient:
    def __init__(
        self,
        *,
        projects: list[str] | None = None,
        fds: dict[str, dict[str, Any]] | None = None,
        fail_list_projects: Exception | None = None,
        fail_create: Exception | None = None,
        created: list[str] | None = None,
    ) -> None:
        self.projects = list(projects or [])
        self.fds = dict(fds or {})
        self.fail_list_projects = fail_list_projects
        self.fail_create = fail_create
        self.created = created if created is not None else []

    def list_projects(self):
        if self.fail_list_projects is not None:
            raise self.fail_list_projects
        return list(self.projects)

    def create_project(self, name: str) -> None:
        if self.fail_create is not None:
            raise self.fail_create
        self.created.append(name)
        self.projects.append(name)

    def list_feedback_definitions(self):
        return dict(self.fds)


def test_verify_offline_default_skips() -> None:
    report = run_opik_verify(remote=False)
    assert report.ok is True
    assert report.remote is False
    assert report.exit_code == 0
    assert report.authority == OPIK_VERIFY_AUTHORITY
    assert report.product_accept_blocked is False
    assert report.doctor_authority is False
    assert any(r.status == "skip" for r in report.rows)


def test_verify_remote_projects_and_fd_alignment() -> None:
    local_fd = {
        "schema_version": "feedback_definition_v1",
        "definitions": {
            "user_acceptance": {"type": "numerical", "scale_min": 0.0, "scale_max": 1.0},
            "human.regime_label": {"type": "categorical", "categories": ["A", "B", "unknown"]},
        },
    }
    client = _FakeClient(
        projects=["gitCommitGenerator", "git-cg-eval", "git-cg-ci", "git-cg-import"],
        fds={
            "user_acceptance": {"type": "numerical", "scale_min": 0.0, "scale_max": 1.0},
            "human.regime_label": {"type": "categorical", "categories": ["A", "B", "unknown"]},
            "extra_remote_only": {"type": "boolean"},
        },
    )
    report = run_opik_verify(
        remote=True,
        config={
            "mode": "mirror",
            "projects": {
                "live": "gitCommitGenerator",
                "eval": "git-cg-eval",
                "ci": "git-cg-ci",
                "import": "git-cg-import",
            },
        },
        client=client,
        local_feedback_definitions=local_fd,
    )
    assert report.ok is True
    assert report.exit_code == 0
    statuses = {r.check_id: r.status for r in report.rows}
    assert statuses["opik.verify.project.live"] == "pass"
    assert statuses["opik.fd.extra"] == "warn"
    assert "opik.fd.aligned" not in statuses  # extra present ⇒ no full align row


def test_verify_create_missing_opt_in() -> None:
    client = _FakeClient(projects=["git-cg-eval"], fds={})
    report = run_opik_verify(
        remote=True,
        create_missing=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval", "live": "gitCommitGenerator"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert "gitCommitGenerator" in client.created
    assert any(r.check_id == "opik.verify.project.live" and r.status == "pass" for r in report.rows)


def test_verify_list_failure_skips_create_missing() -> None:
    client = _FakeClient(fail_list_projects=RuntimeError("dns boom"))
    report = run_opik_verify(
        remote=True,
        create_missing=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval", "live": "gitCommitGenerator"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert client.created == []
    assert report.ok is True
    assert report.exit_code == 0
    assert any("unverified (list failed)" in r.message for r in report.rows)


def test_verify_network_failure_is_warning_only() -> None:
    client = _FakeClient(fail_list_projects=RuntimeError("dns boom super-secret-token"))
    report = run_opik_verify(
        remote=True,
        config={"mode": "mirror", "projects": {"eval": "git-cg-eval"}},
        client=client,
        local_feedback_definitions={"schema_version": "feedback_definition_v1", "definitions": {}},
    )
    assert report.ok is True
    assert report.exit_code == 0
    blob = json.dumps(report.to_data())
    assert "super-secret-token" not in blob
    assert any(r.status == "warn" for r in report.rows)


def test_cli_verify_requires_remote_for_create(monkeypatch) -> None:
    result = runner.invoke(app, ["eval", "opik", "verify", "--create-missing"])
    assert result.exit_code == 2
    assert "--remote" in (result.stdout + result.stderr)


def test_cli_verify_offline_json() -> None:
    result = runner.invoke(app, ["eval", "opik", "verify", "--json"])
    assert result.exit_code == 0
    env = json.loads(result.stdout)
    assert env["command"] == "eval opik verify"
    assert env["data"]["authority"] == OPIK_VERIFY_AUTHORITY
    assert env["data"]["remote"] is False
