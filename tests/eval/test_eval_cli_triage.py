"""Slice 8 ``git-cg eval triage`` CLI contract (Issue #246 / D27)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_cg.eval.binding import paths as binding_paths
from git_cg.eval.binding.paths import atomic_write_json, experiments_dir
from git_cg.eval.scoring.result_builder import make_score
from git_cg.main import app as cli_app

runner = CliRunner()


def _fp() -> dict:
    return {
        "metric_ids": ["i.counter_span_consistent"],
        "failure_ids": ["EVAL_TOPOLOGY"],
        "blame_span": "regeneration",
        "first_divergent_span": "regeneration",
        "missing_required_spans": ["regeneration"],
        "artifact_class": "final_accept",
        "regime": "B",
        "path_class_key": "code_change",
    }


def _seed(repo: Path, *, cases: list[tuple[str, bool]], experiment_id: str = "exp-a") -> None:
    (repo / ".git").mkdir(exist_ok=True)
    atomic_write_json(
        experiments_dir(repo) / experiment_id / "experiment.json",
        {
            "schema_version": "experiment_v1",
            "id": experiment_id,
            "experiment_name": experiment_id,
            "lane": "suite",
            "git_sha": "deadbeef",
            "catalog_pin": "metric_catalog_v1@" + "a" * 64,
            "schema_pack": "schema_pack_v1@" + "b" * 64,
            "metric_catalog": "metric_catalog_v1@" + "a" * 64,
            "meta": {"pins": {"project_lane": "suite", "environment": "local"}},
        },
    )
    for case_id, passed in cases:
        score = make_score(
            "i.counter_span_consistent",
            passed,
            passed=passed,
            reason=None if passed else "counter_span_mismatch",
            evidence={
                "diag_fingerprint_inputs": _fp(),
                "prevention_ids": ["PREV-001"],
                "severity": "block",
            },
            failure_ids=None if passed else ["EVAL_TOPOLOGY"],
            product_authority="git_cg.eval.scoring.family_i",
        )
        payload = {
            "schema_version": "local_case_score_v0",
            "experiment_id": experiment_id,
            "case_id": case_id,
            "deterministic_pass": passed,
            "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
            "evaluator_errors": [],
            "scores": [score.model_dump(mode="json")],
            "gates": [],
            "failed_metric_ids": [] if passed else ["i.counter_span_consistent"],
            "trace_id": "trace-1",
            "session_thread_id": "thread-9",
        }
        atomic_write_json(
            experiments_dir(repo) / experiment_id / "cases" / f"{case_id}.json",
            payload,
        )


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _seed(tmp_path, cases=[("case-fail", False)])
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda start=None: tmp_path)
    return tmp_path


def _env(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_cli_triage_json_envelope(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.doctor as doctor_mod

    doctor = type(
        "D",
        (),
        {
            "green": True,
            "exit_code": 0,
            "to_data": lambda self: {
                "green": True,
                "exit_code": 0,
                "suite_id": "cm-eval-fixtures-core",
                "checks": [],
                "scores": [],
                "block_failures": [],
                "warn_failures": [],
            },
        },
    )()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    result = runner.invoke(cli_app, ["eval", "triage", "--json"])
    env = _env(result)
    assert result.exit_code == 0
    assert env["schema_version"] == "cli_output_envelope_v1"
    assert env["command"] == "eval triage"
    assert env["ok"] is True
    data = env["data"]
    assert data["schema_version"] == "eval_triage_v0"
    assert data["authority"] == "advisory_offline_router"
    assert data["not_score_law"] is True
    assert data["doctor"]["green"] is True
    assert data["failures"]["case_count"] == 1
    assert data["explain"] is not None
    assert data["explain"]["cases"][0]["case_id"] == "case-fail"
    blob = json.dumps(env).lower()
    assert "user_acceptance" not in blob
    assert "search_traces" not in blob


def test_cli_triage_human_mode(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.doctor as doctor_mod

    doctor = type(
        "D",
        (),
        {
            "green": True,
            "exit_code": 0,
            "to_data": lambda self: {
                "green": True,
                "exit_code": 0,
                "suite_id": "s",
                "checks": [],
                "scores": [],
                "block_failures": [],
                "warn_failures": [],
            },
        },
    )()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    result = runner.invoke(cli_app, ["eval", "triage"])
    assert result.exit_code == 0
    assert "eval triage:" in result.stdout
    assert "case-fail" in result.stdout
    assert "git-cg eval triage" in result.stdout


def test_cli_triage_multiple_failures_omits_explain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.doctor as doctor_mod

    _seed(tmp_path, cases=[("case-a", False), ("case-b", False)])
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda start=None: tmp_path)
    doctor = type(
        "D",
        (),
        {
            "green": True,
            "exit_code": 0,
            "to_data": lambda self: {
                "green": True,
                "exit_code": 0,
                "suite_id": "s",
                "checks": [],
                "scores": [],
                "block_failures": [],
                "warn_failures": [],
            },
        },
    )()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    result = runner.invoke(cli_app, ["eval", "triage", "--json"])
    env = _env(result)
    assert result.exit_code == 0
    assert env["data"]["explain"] is None
    assert any("pass --case" in n for n in env["data"]["notes"])


def test_cli_triage_invalid_case_exit_2(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.doctor as doctor_mod

    doctor = type(
        "D",
        (),
        {
            "green": True,
            "exit_code": 0,
            "to_data": lambda self: {
                "green": True,
                "exit_code": 0,
                "suite_id": "s",
                "checks": [],
                "scores": [],
                "block_failures": [],
                "warn_failures": [],
            },
        },
    )()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    result = runner.invoke(cli_app, ["eval", "triage", "--case", "nope", "--json"])
    env = _env(result)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "EVAL_USAGE"


def test_cli_triage_all_skipped_exit_2(repo: Path) -> None:
    result = runner.invoke(
        cli_app,
        [
            "eval",
            "triage",
            "--skip-doctor",
            "--skip-failures",
            "--skip-explain",
            "--json",
        ],
    )
    env = _env(result)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "EVAL_USAGE"


def test_cli_triage_import_stays_clean(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.doctor as doctor_mod

    doctor = type(
        "D",
        (),
        {
            "green": True,
            "exit_code": 0,
            "to_data": lambda self: {
                "green": True,
                "exit_code": 0,
                "suite_id": "s",
                "checks": [],
                "scores": [],
                "block_failures": [],
                "warn_failures": [],
            },
        },
    )()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)
    sys.modules.pop("opik", None)
    result = runner.invoke(
        cli_app,
        ["eval", "triage", "--skip-doctor", "--skip-explain", "--json"],
    )
    assert result.exit_code == 0
    assert "opik" not in sys.modules


def test_eval_help_lists_triage() -> None:
    result = runner.invoke(cli_app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "triage" in result.output
