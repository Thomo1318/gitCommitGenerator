"""CLI wiring for eval run / resume / recompute-scores (Issue #246 Slice 3)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Strip ANSI SGR codes so help assertions survive FORCE_COLOR/CI."""
    return _ANSI_ESCAPE_RE.sub("", text)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"


def test_run_help_lists_slice3_options() -> None:
    result = runner.invoke(app, ["eval", "run", "--help"], terminal_width=120)
    assert result.exit_code == 0
    out = _strip_ansi(result.output)
    assert "--suite" in out
    assert "--mode" in out
    assert "--keep-last" in out
    assert "--keep-checkpoint" in out
    assert "--json" in out


def test_run_json_fresh_case_filter(tmp_path: Path, monkeypatch) -> None:
    # Isolate Layer-A writes inside tmp_path by forcing repo root resolution.
    monkeypatch.setenv("GIT_DIR", str(tmp_path / ".git"))
    # Initialize a tiny git repo so resolve_repo_root works if used.
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Patch resolve_repo_root used by orchestrator path.
    import git_cg.eval.run_orchestrator as orch

    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--suite",
            "cm-eval-fixtures-core",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--case",
            "seed-v1-valid-fixture",
            "--keep-checkpoint",
            "--json",
        ],
    )
    assert result.exit_code in {0, 1}, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "cli_output_envelope_v1"
    assert payload["command"] == "eval run"
    assert payload["data"]["mode"] == "fresh_suite_run"
    assert payload["data"]["status"] in {"completed", "failed"}
    assert payload["ok"] is (result.exit_code == 0)
    assert payload["data"]["experiment_id"]
    assert payload["data"]["checkpoint_id"]
    assert "seed-v1-valid-fixture" in payload["data"]["completed_case_ids"]


def test_resume_requires_checkpoint_json() -> None:
    result = runner.invoke(app, ["eval", "resume", "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_USAGE"


def test_recompute_requires_experiment_json() -> None:
    result = runner.invoke(app, ["eval", "recompute-scores", "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_USAGE"


def test_replay_mode_refused_json(tmp_path: Path, monkeypatch) -> None:
    import git_cg.eval.run_orchestrator as orch

    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)
    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--mode",
            "replay_generation",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--json",
        ],
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_USAGE"


def _fake_run_result(req, *, checkpoint_id: str = "ckpt-fake"):
    """Minimal completed RunResult for CLI wiring tests."""
    from git_cg.eval.run_orchestrator import RunResult

    return RunResult(
        status="completed",
        mode=req.mode,
        suite_id=req.suite_id or "cm-eval-fixtures-core",
        experiment_id="exp-fake",
        parent_experiment_id=None,
        checkpoint_id=checkpoint_id,
        compat_hash="a" * 64,
        completed_case_ids=["c1"],
        pending_case_ids=[],
        case_results=[],
        all_pass=True,
        keep_last=req.keep_last,
        pruned_checkpoint_ids=[],
        exit_code=0,
    )


def test_run_help_lists_reclaim_stale_running() -> None:
    """Run help documents --reclaim-stale-running."""
    result = runner.invoke(app, ["eval", "run", "--help"], terminal_width=120)
    assert result.exit_code == 0
    out = _strip_ansi(result.output)
    assert "--reclaim-stale-running" in out


def test_resume_help_lists_reclaim_stale_running() -> None:
    """Resume help documents --reclaim-stale-running."""
    result = runner.invoke(app, ["eval", "resume", "--help"], terminal_width=120)
    assert result.exit_code == 0
    out = _strip_ansi(result.output)
    assert "--reclaim-stale-running" in out


def test_run_default_off_does_not_pass_reclaim_bound(tmp_path: Path, monkeypatch) -> None:
    """eval run without --reclaim-stale-running leaves bound unset (default off)."""
    import git_cg.eval.run_orchestrator as orch

    captured: dict = {}

    def _fake_run(req):
        captured["req"] = req
        return _fake_run_result(req)

    monkeypatch.setattr(orch, "run_evaluation", _fake_run)
    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--suite",
            "cm-eval-fixtures-core",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "req" in captured
    assert captured["req"].stale_running_after_seconds is None


def test_resume_default_off_does_not_pass_reclaim_bound(tmp_path: Path, monkeypatch) -> None:
    """eval resume without flag leaves reclaim bound unset."""
    import git_cg.eval.run_orchestrator as orch

    captured: dict = {}

    def _fake_run(req):
        captured["req"] = req
        return _fake_run_result(req, checkpoint_id=req.checkpoint_id or "ckpt-fake")

    monkeypatch.setattr(orch, "run_evaluation", _fake_run)
    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)

    result = runner.invoke(
        app,
        [
            "eval",
            "resume",
            "--checkpoint",
            "ckpt-existing",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["req"].stale_running_after_seconds is None
    assert captured["req"].checkpoint_id == "ckpt-existing"
    assert captured["req"].mode == "resume_missing"


def test_run_reclaim_flag_forwards_exact_bound(tmp_path: Path, monkeypatch) -> None:
    """--reclaim-stale-running forwards the exact positive bound."""
    import git_cg.eval.run_orchestrator as orch

    captured: dict = {}

    def _fake_run(req):
        captured["req"] = req
        return _fake_run_result(req)

    monkeypatch.setattr(orch, "run_evaluation", _fake_run)
    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--suite",
            "cm-eval-fixtures-core",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--reclaim-stale-running",
            "7200",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["req"].stale_running_after_seconds == 7200


def test_run_invalid_reclaim_value_no_checkpoint_mutation(tmp_path: Path, monkeypatch) -> None:
    """Non-integer reclaim value is a usage error and mutates no checkpoints."""
    import git_cg.eval.run_orchestrator as orch
    from git_cg.eval.checkpoint_store import build_checkpoint_record, list_checkpoint_ids, write_checkpoint
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    # Durable checkpoint must remain untouched on usage failure.
    rec = build_checkpoint_record(
        checkpoint_id="ckpt-preexisting",
        experiment_id="exp-preexisting",
        compat_hash="a" * 64,
        completed_case_ids=[],
        pending_case_ids=["c1"],
        mode="fresh_suite_run",
        suite_id="cm-eval-fixtures-core",
        snapshot_id="snap-1",
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
        status="running",
        started_at="2026-08-01T00:00:00Z",
    )
    write_checkpoint(tmp_path, rec, status="running", started_at="2026-08-01T00:00:00Z")
    before = set(list_checkpoint_ids(tmp_path))

    called = {"n": 0}

    def _should_not_run(req):
        called["n"] += 1
        raise AssertionError("run_evaluation must not be called for invalid reclaim flag")

    monkeypatch.setattr(orch, "run_evaluation", _should_not_run)
    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--suite",
            "cm-eval-fixtures-core",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--reclaim-stale-running",
            "nope",
            "--json",
        ],
    )
    assert result.exit_code != 0
    assert called["n"] == 0
    assert set(list_checkpoint_ids(tmp_path)) == before


def test_run_zero_reclaim_bound_fails_closed_without_mutation(tmp_path: Path, monkeypatch) -> None:
    """Reclaim bound 0 fails closed without mutating durable checkpoints."""
    import git_cg.eval.run_orchestrator as orch
    from git_cg.eval.checkpoint_store import (
        build_checkpoint_record,
        list_checkpoint_ids,
        write_checkpoint,
    )
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
    from git_cg.eval.run_orchestrator import RunOrchestratorError

    rec = build_checkpoint_record(
        checkpoint_id="ckpt-pre-zero",
        experiment_id="exp-pre-zero",
        compat_hash="a" * 64,
        completed_case_ids=[],
        pending_case_ids=["c1"],
        mode="fresh_suite_run",
        suite_id="cm-eval-fixtures-core",
        snapshot_id="snap-1",
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
        status="running",
        started_at="2026-08-01T00:00:00Z",
    )
    write_checkpoint(tmp_path, rec, status="running", started_at="2026-08-01T00:00:00Z")
    before_ids = set(list_checkpoint_ids(tmp_path))
    before_bytes = (tmp_path / ".eval" / "checkpoints" / "ckpt-pre-zero.json").read_bytes()

    def _reject_zero(req):
        # Non-positive bound is EVAL_USAGE (same as store/orchestrator gate).
        if req.stale_running_after_seconds is not None and req.stale_running_after_seconds <= 0:
            raise RunOrchestratorError(
                "stale_running_after_seconds must be > 0 when set",
                code="EVAL_USAGE",
                exit_code=2,
            )
        raise AssertionError("unexpected call")

    monkeypatch.setattr(orch, "run_evaluation", _reject_zero)
    monkeypatch.setattr(orch, "resolve_repo_root", lambda start=None: tmp_path)

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--suite",
            "cm-eval-fixtures-core",
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--reclaim-stale-running",
            "0",
            "--json",
        ],
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_USAGE"
    assert set(list_checkpoint_ids(tmp_path)) == before_ids
    assert (tmp_path / ".eval" / "checkpoints" / "ckpt-pre-zero.json").read_bytes() == before_bytes
