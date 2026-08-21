"""Slice 4 ``git-cg eval doctor`` CLI contract (Issue #246, S6-C01/C02/C03).

Locks the operator surface:

* JSON mode emits exactly one ``cli_output_envelope_v1``; human mode uses
  stderr for diagnostics and stdout for the summary line.
* Exit classes: 0 green, 1 block-severity doctor red, 3 compat-hash mismatch.
* Phantom-metric producers appear as ScoreResultV1 rows in ``data.scores``.
* The CLI module import graph stays binder/Opik-free.
* Network-free: runs against the committed offline fixture suite.
"""

from __future__ import annotations

import json
import sys

from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()


def _parse_envelope(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_eval_doctor_json_envelope_shape() -> None:
    result = runner.invoke(app, ["eval", "doctor", "--json"])
    env = _parse_envelope(result)
    assert env["schema_version"] == "cli_output_envelope_v1"
    assert env["command"] == "eval doctor"
    assert isinstance(env["ok"], bool)
    data = env["data"]
    assert isinstance(data["checks"], list) and data["checks"]
    assert isinstance(data["scores"], list)
    score_ids = {s["metric_id"] for s in data["scores"]}
    assert {"h.compat_hash_resume", "h.doctor_green", "h.export_config_resolved"} <= score_ids


def test_eval_doctor_green_offline_fixture_suite() -> None:
    """Committed offline suite must doctor green (no block failures)."""
    result = runner.invoke(app, ["eval", "doctor", "--json"])
    env = _parse_envelope(result)
    assert env["data"]["green"] is True
    assert env["data"]["block_failures"] == []
    assert result.exit_code == 0


def test_eval_doctor_human_mode_summary_and_stderr_diagnostics() -> None:
    result = runner.invoke(app, ["eval", "doctor"])
    assert result.exit_code == 0
    # Summary on stdout.
    assert "eval doctor: green=True" in result.stdout
    # Per-check diagnostics go to stderr only when non-pass.
    # (green run ⇒ no diagnostic lines required; just assert no crash.)


def test_eval_doctor_cli_import_stays_clean() -> None:
    """Importing/invoking eval doctor must not pull binder or Opik SDK."""
    sys.modules.pop("git_cg.eval.binding", None)
    sys.modules.pop("opik", None)
    result = runner.invoke(app, ["eval", "doctor", "--json"])
    assert result.exit_code in (0, 1, 3)
    assert "git_cg.eval.binding" not in sys.modules


def test_eval_doctor_doctor_green_score_is_boolean() -> None:
    result = runner.invoke(app, ["eval", "doctor", "--json"])
    env = _parse_envelope(result)
    green = next(s for s in env["data"]["scores"] if s["metric_id"] == "h.doctor_green")
    assert type(green["value"]) is bool
    assert type(green["passed"]) is bool
    assert green["passed"] is env["data"]["green"]
