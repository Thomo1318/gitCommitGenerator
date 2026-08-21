"""Slice 4 ``git-cg eval opik doctor`` CLI contract (Issue #246, S6-C05/C08).

Locks the secret-safe Opik/export health doctor:

* Reuses S4 ``resolve_opik_config`` / ``operator_config_health`` /
  ``public_config_view`` / ``mask_secret`` — no transport, no network.
* Raw token values and prefixes are never printed (masked ``•••[len=N]`` only).
* ``h.export_config_resolved`` and ``h.doctor_green`` project as ScoreResultV1.
* Config-error mode fails closed with exit 2.
* The landed flat ``eval config show`` alias keeps its deprecation pointer.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()

SECRET = "sk-test-secret-token-value-0123456789"


def _parse(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_opik_doctor_envelope_and_scores_off() -> None:
    env = _parse(runner.invoke(app, ["eval", "opik", "doctor", "--json"]))
    assert env["schema_version"] == "cli_output_envelope_v1"
    assert env["command"] == "eval opik doctor"
    data = env["data"]
    score_ids = {s["metric_id"] for s in data["scores"]}
    assert {"h.export_config_resolved", "h.doctor_green"} <= score_ids
    # Default offline env ⇒ mode off ⇒ config resolves (not config_error).
    assert env["ok"] is True


def test_opik_doctor_never_prints_raw_token(monkeypatch) -> None:
    monkeypatch.setenv("OPIK_API_KEY", SECRET)
    result = runner.invoke(app, ["eval", "opik", "doctor"])
    combined = result.stdout + result.stderr
    assert SECRET not in combined
    assert "sk-test" not in combined  # no prefix leak
    # Masked length form is the only permitted representation.
    assert f"•••[len={len(SECRET)}]" in combined


def test_opik_doctor_json_never_prints_raw_token(monkeypatch) -> None:
    monkeypatch.setenv("OPIK_API_KEY", SECRET)
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert SECRET not in result.stdout
    assert "sk-test" not in result.stdout
    env = _parse(result)
    # json.dumps escapes non-ASCII; assert against the parsed check messages.
    messages = [c["message"] for c in env["data"]["checks"]]
    assert any(f"•••[len={len(SECRET)}]" in m for m in messages)


def test_opik_doctor_config_error_fails_closed(monkeypatch) -> None:
    """Invalid mode token ⇒ config_error ⇒ exit 2, ok=False."""
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "not-a-real-mode")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 2
    env = _parse(result)
    assert env["ok"] is False
    export = next(s for s in env["data"]["scores"] if s["metric_id"] == "h.export_config_resolved")
    assert export["passed"] is False
    assert "EVAL_CONFIG_ERROR" in (export.get("failure_ids") or [])


def test_opik_doctor_human_mode_masks_token(monkeypatch) -> None:
    monkeypatch.setenv("OPIK_API_KEY", SECRET)
    result = runner.invoke(app, ["eval", "opik", "doctor"])
    assert result.exit_code == 0
    assert "eval opik doctor: green=" in result.stdout
    assert SECRET not in result.stdout


def test_flat_config_show_alias_keeps_deprecation_pointer() -> None:
    """The retained flat alias still emits its deprecation warning."""
    result = runner.invoke(app, ["eval", "config", "show", "--json"])
    env = json.loads(result.stdout)
    codes = {w.get("code") for w in env.get("warnings", [])}
    assert "EVAL_CLI_DEPRECATED" in codes
    assert any("git-cg eval opik config show" in (w.get("message") or "") for w in env.get("warnings", []))
