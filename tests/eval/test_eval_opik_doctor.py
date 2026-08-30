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

import conftest as _cq
from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()

SECRET = "sk-" + "test-fixture-token-value-0123456789"


def _parse(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_opik_doctor_envelope_and_scores_off(monkeypatch) -> None:
    for key in (
        "GIT_CG_OPIK_MODE",
        "OPIK_API_KEY",
        "OPIK_URL_OVERRIDE",
        "OPIK_WORKSPACE",
        "OPIK_PROJECT_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
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


# --- S7-1a: per-lane Opik project-pin doctor diagnostics ------------------

# Lane-pin env scrubbing is shared via tests/conftest.py (scrub_opik_project_lanes).


def _lane_checks(env: dict) -> dict:
    """Map lane → check row for the four opik.projects.* checks."""
    return {
        c["check_id"].rsplit(".", 1)[1]: c for c in env["data"]["checks"] if c["check_id"].startswith("opik.projects.")
    }


def test_doctor_off_mode_missing_lanes_warn_not_block(monkeypatch) -> None:
    """mode=off + no pins ⇒ exit 0, four WARN lane rows (never BLOCK)."""
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.delenv("GIT_CG_OPIK_MODE", raising=False)
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 0, result.output
    env = _parse(result)
    assert env["ok"] is True
    lanes = _lane_checks(env)
    assert set(lanes) == {"live", "eval", "ci", "import"}
    assert all(row["status"] == "warn" for row in lanes.values())
    assert all(row["severity"] == "warn" for row in lanes.values())  # never block
    for lane, row in lanes.items():
        assert f"GIT_CG_OPIK_PROJECT_{lane.upper()}" in row["message"]
        assert row.get("hint")


def test_doctor_eval_only_bootstrap_disclosed(monkeypatch) -> None:
    """EVAL-only pin bootstraps all four lanes with disclosed origin."""
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.delenv("GIT_CG_OPIK_MODE", raising=False)
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "my-eval-proj")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 0, result.output
    lanes = _lane_checks(_parse(result))
    assert all(row["status"] == "pass" for row in lanes.values())
    for row in lanes.values():
        assert "bootstrap" in row["message"]
        assert "GIT_CG_OPIK_PROJECT_EVAL" in row["message"]
        assert "my-eval-proj" in row["message"]


def test_doctor_legacy_bootstrap_disclosed(monkeypatch) -> None:
    """Legacy OPIK_PROJECT_NAME bootstraps all four lanes with disclosed origin."""
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.delenv("GIT_CG_OPIK_MODE", raising=False)
    monkeypatch.setenv("OPIK_PROJECT_NAME", "legacy-proj")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 0, result.output
    lanes = _lane_checks(_parse(result))
    assert all(row["status"] == "pass" for row in lanes.values())
    for row in lanes.values():
        assert "bootstrap" in row["message"]
        assert "OPIK_PROJECT_NAME" in row["message"]
        assert "legacy-proj" in row["message"]


def test_doctor_full_explicit_lanes_pass(monkeypatch) -> None:
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.delenv("GIT_CG_OPIK_MODE", raising=False)
    for lane in ("LIVE", "EVAL", "CI", "IMPORT"):
        monkeypatch.setenv(f"GIT_CG_OPIK_PROJECT_{lane}", f"proj-{lane.lower()}")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 0, result.output
    lanes = _lane_checks(_parse(result))
    assert all(row["status"] == "pass" for row in lanes.values())
    assert "proj-live" in lanes["live"]["message"]
    assert "GIT_CG_OPIK_PROJECT_IMPORT" in lanes["import"]["message"]


def test_doctor_active_mode_partial_lanes_fail_closed_with_lane_detail(monkeypatch) -> None:
    """Active mode + partial lanes ⇒ config BLOCK exit 2 AND named missing lanes."""
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "l")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "e")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 2, result.output
    env = _parse(result)
    assert env["ok"] is False
    config_row = next(c for c in env["data"]["checks"] if c["check_id"] == "opik.config_resolved")
    assert config_row["status"] == "fail"
    assert config_row["severity"] == "block"
    lanes = _lane_checks(env)
    # Populated lanes still report; the two missing lanes are named.
    assert lanes["live"]["status"] == "pass"
    assert lanes["eval"]["status"] == "pass"
    assert lanes["ci"]["status"] == "fail"
    assert lanes["import"]["status"] == "fail"
    assert "GIT_CG_OPIK_PROJECT_CI" in lanes["ci"]["message"]
    assert "GIT_CG_OPIK_PROJECT_IMPORT" in lanes["import"]["message"]


def test_doctor_lane_rows_never_leak_secret(monkeypatch) -> None:
    """Lane rows coexist with secret masking; no raw token/prefix anywhere."""
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.setenv("OPIK_API_KEY", SECRET)
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "my-eval-proj")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    combined = result.stdout + result.stderr
    assert SECRET not in combined
    assert "sk-test" not in combined
    # json.dumps escapes non-ASCII; assert masked form on the parsed messages.
    env = _parse(result)
    messages = [c["message"] for c in env["data"]["checks"]]
    assert any(f"•••[len={len(SECRET)}]" in m for m in messages)
