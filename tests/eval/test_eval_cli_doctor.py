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
from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_cg.main import app

runner = CliRunner()


@pytest.fixture()
def clean_doctor_repo(isolated_eval_repo: Path) -> Path:
    """Doctor-CLI alias for shared ``isolated_eval_repo`` isolation.

    Doctor still loads the committed offline fixture suite by suite_id; only the
    checkpoint/queue scan root is redirected so local scratch checkpoints cannot
    flip ``compat.hash_resume`` red during CLI contract tests.
    """
    return isolated_eval_repo


def _parse_envelope(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_eval_doctor_json_envelope_shape(clean_doctor_repo: Path) -> None:
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


def test_eval_doctor_green_offline_fixture_suite(clean_doctor_repo: Path) -> None:
    """Committed offline suite must doctor green (no block failures)."""
    result = runner.invoke(app, ["eval", "doctor", "--json"])
    env = _parse_envelope(result)
    assert env["data"]["green"] is True
    assert env["data"]["block_failures"] == []
    assert result.exit_code == 0


def test_eval_doctor_human_mode_summary_and_stderr_diagnostics(clean_doctor_repo: Path) -> None:
    result = runner.invoke(app, ["eval", "doctor"])
    assert result.exit_code == 0
    # Summary on stdout.
    assert "eval doctor: green=True" in result.stdout
    # Per-check diagnostics go to stderr only when non-pass.
    # (green run ⇒ no diagnostic lines required; just assert no crash.)


def test_eval_doctor_cli_import_stays_clean(tmp_path: Path) -> None:
    """Importing/invoking eval doctor must not pull binder or Opik SDK.

    Contract (S8-S6-03 / import-light packages):
    * ``git_cg.eval.binding.paths`` may load for repo-root resolution.
    * ``git_cg.eval.binding.binder`` must stay out of ``sys.modules``.
    * ``git_cg.eval.binding.accept_hook`` must stay out of ``sys.modules``.
    * doctor invocation must not (re)import the Opik SDK.

    Runs in a fresh interpreter so the assertion is not polluted by other
    tests' binder imports, and so popping binder from the shared pytest
    process cannot create dual ``BindResult`` class identities.

    Note: ``git_cg.main`` may already import Opik for product telemetry. The
    doctor contract is that the doctor command path itself does not require or
    re-import Opik after that residue is cleared.
    """
    import subprocess
    import textwrap

    repo = tmp_path
    (repo / ".git").mkdir()
    probe = textwrap.dedent(
        f"""
        from __future__ import annotations

        import sys
        from pathlib import Path

        from typer.testing import CliRunner

        from git_cg.eval.binding import paths as binding_paths
        from git_cg.main import app

        repo = Path({str(repo)!r})
        binding_paths.resolve_repo_root = lambda start=None: repo

        # paths import must remain binder-free under the lazy package law.
        assert "git_cg.eval.binding.paths" in sys.modules
        assert "git_cg.eval.binding.binder" not in sys.modules
        assert "git_cg.eval.binding.accept_hook" not in sys.modules

        # Clear any Opik residue pulled by product main/telemetry so doctor
        # cannot hide behind a pre-existing SDK import.
        for name in list(sys.modules):
            if name == "opik" or name.startswith("opik."):
                sys.modules.pop(name, None)
        assert "opik" not in sys.modules

        result = CliRunner().invoke(app, ["eval", "doctor", "--json"])
        assert result.exit_code in (0, 1, 3), result.output

        assert "git_cg.eval.binding.paths" in sys.modules
        assert "git_cg.eval.binding.binder" not in sys.modules
        assert "git_cg.eval.binding.accept_hook" not in sys.modules
        assert "opik" not in sys.modules
        assert not any(name.startswith("opik.") for name in sys.modules)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        "eval doctor cold import graph must stay binder/Opik-free; "
        f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
    )


def test_eval_doctor_doctor_green_score_is_boolean(clean_doctor_repo: Path) -> None:
    result = runner.invoke(app, ["eval", "doctor", "--json"])
    env = _parse_envelope(result)
    green = next(s for s in env["data"]["scores"] if s["metric_id"] == "h.doctor_green")
    assert type(green["value"]) is bool
    assert type(green["passed"]) is bool
    assert green["passed"] is env["data"]["green"]
