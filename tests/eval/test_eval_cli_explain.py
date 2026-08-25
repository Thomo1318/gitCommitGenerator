"""Slice 5 ``git-cg eval`` CLI wiring for failures/explain/compare/diagnose/issue.

Locks the operator contract end-to-end through the Typer tree:

* JSON mode emits exactly one ``cli_output_envelope_v1`` on stdout.
* Human mode writes a summary line (no crash) and exits 0 on success.
* Exit classes: 0 success, 2 usage (not found / illegal transition / missing
  required verb args), 4 store-integrity.
* The ``eval issue`` verbs enforce the closed transition matrix + required
  evidence/reason at the CLI boundary.
* The CLI module import graph stays binder/Opik-free.

All offline: each test seeds a tmp repo ``.eval`` tree and isolates
``resolve_repo_root`` so the CLI reads the fixture, never the real repo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_cg.eval.binding import paths as binding_paths
from git_cg.eval.binding.paths import atomic_write_json, experiments_dir, issues_dir
from git_cg.eval.diagnose import diagnose
from git_cg.eval.scoring.result_builder import make_score
from git_cg.main import app as cli_app

runner = CliRunner()


def _fp() -> dict:
    return {
        "metric_ids": ["i.counter_span_consistent"],
        "failure_ids": ["EVAL_TOPOLOGY"],
        "blame_span": "regeneration",
        "missing_required_spans": ["regeneration"],
        "artifact_class": "final_accept",
        "regime": "B",
        "path_class_key": "code_change",
    }


def _seed(repo: Path, experiment_id: str = "exp-a", case_id: str = "case-fail") -> None:
    (repo / ".git").mkdir(exist_ok=True)
    score = make_score(
        "i.counter_span_consistent",
        False,
        passed=False,
        reason="counter_span_mismatch",
        evidence={"diag_fingerprint_inputs": _fp(), "prevention_ids": ["PREV-001"], "severity": "block"},
        failure_ids=["EVAL_TOPOLOGY"],
        product_authority="git_cg.eval.scoring.family_i",
    )
    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": experiment_id,
        "case_id": case_id,
        "deterministic_pass": False,
        "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
        "evaluator_errors": [],
        "scores": [score.model_dump(mode="json")],
        "gates": [],
        "failed_metric_ids": ["i.counter_span_consistent"],
        "trace_id": "trace-1",
        "session_thread_id": "thread-9",
    }
    atomic_write_json(experiments_dir(repo) / experiment_id / "cases" / f"{case_id}.json", payload)
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


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed a failing run in tmp_path and pin the CLI's repo-root discovery to it."""
    _seed(tmp_path)
    # ``_resolve_repo`` lazily imports ``resolve_repo_root`` from binding.paths, so
    # patching the attribute on the binding.paths module covers every call site.
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda start=None: tmp_path)
    return tmp_path


def _env(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


# --------------------------------------------------------------------------
# failures
# --------------------------------------------------------------------------


def test_cli_failures_json_envelope(repo: Path) -> None:
    result = runner.invoke(cli_app, ["eval", "failures", "--json"])
    env = _env(result)
    assert result.exit_code == 0
    assert env["schema_version"] == "cli_output_envelope_v1"
    assert env["command"] == "eval failures"
    assert env["ok"] is True
    case = env["data"]["failing_cases"][0]
    assert case["metric_ids"] == ["i.counter_span_consistent"]
    assert case["failure_ids"] == ["EVAL_TOPOLOGY"]


def test_cli_failures_human_mode(repo: Path) -> None:
    result = runner.invoke(cli_app, ["eval", "failures"])
    assert result.exit_code == 0
    assert "eval failures:" in result.stdout
    assert "case-fail" in result.stdout


# --------------------------------------------------------------------------
# explain
# --------------------------------------------------------------------------


def test_cli_explain_json_contract(repo: Path) -> None:
    result = runner.invoke(cli_app, ["eval", "explain", "--case", "case-fail", "--json"])
    env = _env(result)
    assert result.exit_code == 0
    assert env["command"] == "eval explain"
    case = env["data"]["cases"][0]
    assert case["blame_span"] == "regeneration"
    assert case["failure_ids"] == ["EVAL_TOPOLOGY"]
    assert case["prevention_ids"] == ["PREV-001"]
    assert "git-cg eval replay" in case["replay_command"]
    # No opaque LLM RCA leaks.
    blob = json.dumps(env).lower()
    for forbidden in ("ollie", "llm_rca", "root_cause_analysis"):
        assert forbidden not in blob


def test_cli_explain_missing_case_exit_2(repo: Path) -> None:
    result = runner.invoke(cli_app, ["eval", "explain", "--case", "nope", "--json"])
    env = _env(result)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "EVAL_USAGE"


# --------------------------------------------------------------------------
# diagnose + issue lifecycle
# --------------------------------------------------------------------------


def test_cli_diagnose_creates_issue(repo: Path) -> None:
    result = runner.invoke(cli_app, ["eval", "diagnose", "--case", "case-fail", "--json"])
    env = _env(result)
    assert result.exit_code == 0
    assert env["command"] == "eval diagnose"
    issue = env["data"]["issue"]
    assert issue["status"] == "open"
    assert issue["fingerprint"]
    assert (issues_dir(repo) / f"{issue['issue_id']}.json").is_file()


def test_cli_issue_full_lifecycle(repo: Path) -> None:
    created = diagnose(repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    iid = created["issue_id"]

    # list
    res = runner.invoke(cli_app, ["eval", "issue", "list", "--json"])
    env = _env(res)
    assert res.exit_code == 0
    assert env["data"]["issue_count"] == 1

    # show
    res = runner.invoke(cli_app, ["eval", "issue", "show", iid, "--json"])
    env = _env(res)
    assert res.exit_code == 0
    assert env["data"]["issue"]["issue_id"] == iid

    # resolve requires evidence -> exit 2 without it
    res = runner.invoke(cli_app, ["eval", "issue", "resolve", iid, "--json"])
    assert res.exit_code != 0  # typer missing-option error

    # resolve with evidence
    res = runner.invoke(
        cli_app,
        ["eval", "issue", "resolve", iid, "--resolution-evidence", "fixed", "--json"],
    )
    env = _env(res)
    assert res.exit_code == 0
    assert env["data"]["to"] == "resolved"

    # reopen (allowed from resolved)
    res = runner.invoke(cli_app, ["eval", "issue", "reopen", iid, "--json"])
    assert _env(res)["data"]["to"] == "reopened"

    # suppress requires reason -> enforce
    res = runner.invoke(cli_app, ["eval", "issue", "suppress", iid, "--json"])
    assert res.exit_code != 0  # missing required --reason
    res = runner.invoke(cli_app, ["eval", "issue", "suppress", iid, "--reason", "known", "--json"])
    assert _env(res)["data"]["to"] == "suppressed"


def test_cli_issue_illegal_transition_exit_2(repo: Path) -> None:
    created = diagnose(repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    iid = created["issue_id"]
    # open -> reopened is illegal.
    res = runner.invoke(cli_app, ["eval", "issue", "reopen", iid, "--json"])
    env = _env(res)
    assert res.exit_code == 2
    assert env["ok"] is False


def test_cli_issue_show_missing_exit_2(repo: Path) -> None:
    res = runner.invoke(cli_app, ["eval", "issue", "show", "issue-nope", "--json"])
    assert _env(res)["ok"] is False
    assert res.exit_code == 2


# --------------------------------------------------------------------------
# Import isolation (locked law)
# --------------------------------------------------------------------------


def test_cli_import_graph_stays_opik_free() -> None:
    sys.modules.pop("opik", None)
    import importlib

    importlib.import_module("git_cg.eval.cli")
    assert "opik" not in sys.modules


def test_cli_explain_and_diagnose_never_print_raw_token(repo: Path) -> None:
    """S6-C08 CLI negative: explain/diagnose stdout never carries raw tokens."""
    secret = "sk-test-secret-token-value-0123456789"
    # Poison the seeded case with a secret-shaped evaluator error + trace id.
    case_path = experiments_dir(repo) / "exp-a" / "cases" / "case-fail.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["evaluator_errors"] = [f"token={secret}"]
    payload["trace_id"] = secret
    case_path.write_text(json.dumps(payload), encoding="utf-8")

    explain_result = runner.invoke(
        cli_app,
        ["eval", "explain", "--experiment-id", "exp-a", "--case", "case-fail", "--json"],
    )
    assert explain_result.exit_code == 0, explain_result.output
    assert secret not in explain_result.stdout
    assert "sk-test" not in explain_result.stdout
    explain_env = json.loads(explain_result.stdout)
    explain_flat = json.dumps(explain_env, ensure_ascii=False)
    assert "•••[len=" in explain_flat

    diagnose_result = runner.invoke(
        cli_app,
        [
            "eval",
            "diagnose",
            "--experiment-id",
            "exp-a",
            "--case",
            "case-fail",
            "--title",
            f"title {secret}",
            "--notes",
            f"api_key={secret}",
            "--json",
        ],
    )
    assert diagnose_result.exit_code == 0, diagnose_result.output
    combined = diagnose_result.stdout + diagnose_result.stderr
    assert secret not in combined
    assert "sk-test" not in combined
    diagnose_env = json.loads(diagnose_result.stdout)
    assert "•••[len=" in json.dumps(diagnose_env, ensure_ascii=False)

    # Store row must also be secret-safe.
    issue = diagnose_env["data"]["issue"]
    on_disk = json.loads((issues_dir(repo) / f"{issue['issue_id']}.json").read_text("utf-8"))
    disk_blob = json.dumps(on_disk, ensure_ascii=False)
    assert secret not in disk_blob
    assert "sk-test" not in disk_blob
    assert "•••[len=" in disk_blob


def test_cli_failures_filters_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path)
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda: tmp_path)
    result = runner.invoke(
        cli_app,
        ["eval", "failures", "--experiment-id", "exp-a", "--family", "I", "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["case_count"] == 1
    assert payload["data"]["filters"]["family"] == "I"


def test_cli_diagnose_dry_run_no_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path)
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda: tmp_path)
    result = runner.invoke(
        cli_app,
        ["eval", "diagnose", "--experiment-id", "exp-a", "--case", "case-fail", "--dry-run", "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["would_write"]["issue_path"]
    assert list(issues_dir(tmp_path).glob("*.json")) == []
