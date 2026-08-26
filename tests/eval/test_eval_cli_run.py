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
