"""Plain Opik config-show summary CLI contracts."""

from __future__ import annotations

import json

import conftest as _cq
import pytest
from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()


def _scrub_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear project lanes plus optional workspace/redaction pins."""
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.delenv("GIT_CG_OPIK_WORKSPACE", raising=False)
    monkeypatch.delenv("GIT_CG_OPIK_REDACTION_PROFILE", raising=False)


def test_opik_config_show_plain_summary_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "local_only")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "proj-eval")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "proj-live")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_CI", "proj-ci")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_IMPORT", "proj-import")
    monkeypatch.setenv("GIT_CG_OPIK_WORKSPACE", "ws-demo")
    monkeypatch.setenv("GIT_CG_OPIK_REDACTION_PROFILE", "default_scrub")
    monkeypatch.setenv("OPIK_API_KEY", "super-secret-key-value")
    monkeypatch.delenv("GIT_CG_OPIK_API_KEY", raising=False)

    result = runner.invoke(app, ["eval", "opik", "config", "show"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "mode=local_only" in out
    assert "health=deferred" in out
    assert "workspace=ws-demo" in out
    assert "project.live=proj-live" in out
    assert "project.eval=proj-eval" in out
    assert "project.ci=proj-ci" in out
    assert "project.import=proj-import" in out
    assert "api_key_present=true" in out
    assert "api_key=•••[len=" in out
    assert "redaction_profile=default_scrub" in out
    assert "product_accept_blocked=false" in out
    assert "super-secret-key-value" not in out
    assert '"config"' not in out
    assert out.strip().startswith("eval opik config show:")


def test_opik_config_show_json_keeps_full_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "off")
    _scrub_config_env(monkeypatch)
    monkeypatch.setenv("OPIK_API_KEY", "json-secret-value")
    monkeypatch.delenv("GIT_CG_OPIK_API_KEY", raising=False)

    result = runner.invoke(app, ["eval", "opik", "config", "show", "--json"])
    assert result.exit_code == 0, result.output
    env = json.loads(result.output)
    assert env["ok"] is True
    assert env["command"] == "eval opik config show"
    data = env["data"]
    assert set(data) >= {"config", "secrets", "health_hint", "mirror_result"}
    assert data["secrets"]["api_key_present"] is True
    assert data["secrets"]["api_key"] == "•••[len=17]"
    assert "json-secret-value" not in result.output
    assert data["mirror_result"]["product_accept_blocked"] is False


def test_opik_config_show_plain_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    _scrub_config_env(monkeypatch)
    result = runner.invoke(app, ["eval", "opik", "config", "show"])
    assert result.exit_code == 2, result.output
    out = result.output
    assert "invalid (fail-closed)" in out
    assert "health=config_error" in out
    assert "api_key_present=false" in out
    assert "product_accept_blocked=false" in out
    assert '"config"' not in out
