"""S7 NTH: Opik doctor exit-code x credential matrix (offline authority)."""

from __future__ import annotations

import json

import conftest as _cq
from typer.testing import CliRunner

from git_cg.eval.doctor import OPIK_DOCTOR_EXIT_MATRIX, opik_doctor_exit_matrix
from git_cg.main import app

runner = CliRunner()


def _parse(result):
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_matrix_constant_covers_required_cases() -> None:
    cases = {row["case"] for row in opik_doctor_exit_matrix()}
    assert cases == {row["case"] for row in OPIK_DOCTOR_EXIT_MATRIX}
    required = {
        "mode_off_missing_pins",
        "local_config_shape_invalid",
        "active_complete_pins_no_key",
        "active_partial_pins",
        "remote_network_failure",
        "optional_remote_verification",
    }
    assert required <= cases


def test_matrix_mode_off_missing_pins(monkeypatch) -> None:
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.delenv("GIT_CG_OPIK_MODE", raising=False)
    monkeypatch.delenv("OPIK_API_KEY", raising=False)
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 0
    env = _parse(result)
    assert env["ok"] is True
    assert env["data"]["exit_code"] == 0
    assert env["data"]["green"] is True


def test_matrix_local_config_shape_invalid(monkeypatch) -> None:
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "not-a-real-mode")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 2
    env = _parse(result)
    assert env["ok"] is False
    assert env["data"]["exit_code"] == 2
    assert env["data"]["green"] is False


def test_matrix_active_complete_pins_no_key(monkeypatch) -> None:
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    for lane in ("LIVE", "EVAL", "CI", "IMPORT"):
        monkeypatch.setenv(f"GIT_CG_OPIK_PROJECT_{lane}", f"proj-{lane.lower()}")
    monkeypatch.delenv("OPIK_API_KEY", raising=False)
    monkeypatch.delenv("GIT_CG_OPIK_API_KEY", raising=False)
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 0, result.output
    env = _parse(result)
    assert env["data"]["green"] is True
    api = next(c for c in env["data"]["checks"] if c["check_id"] == "opik.api_key_present")
    assert api["status"] == "warn"
    assert api["severity"] == "warn"


def test_matrix_active_partial_pins(monkeypatch) -> None:
    _cq.scrub_opik_project_lanes(monkeypatch)
    monkeypatch.setenv("GIT_CG_OPIK_MODE", "mirror")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_LIVE", "l")
    monkeypatch.setenv("GIT_CG_OPIK_PROJECT_EVAL", "e")
    result = runner.invoke(app, ["eval", "opik", "doctor", "--json"])
    assert result.exit_code == 2
    env = _parse(result)
    assert env["data"]["green"] is False


def test_matrix_remote_rows_are_non_authoritative() -> None:
    remote_rows = [r for r in OPIK_DOCTOR_EXIT_MATRIX if r["case"].startswith("remote") or "remote" in r["case"]]
    assert remote_rows
    for row in remote_rows:
        assert row["exit_code"] == 0
        assert row["green"] == "unchanged"
