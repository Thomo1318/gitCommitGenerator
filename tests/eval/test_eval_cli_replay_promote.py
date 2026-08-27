"""Slice 6 CLI wiring: replay / promote / review queue.

Locks operator contract end-to-end through the Typer tree:

* JSON mode emits exactly one ``cli_output_envelope_v1`` on stdout.
* Exit classes: 0 success, 2 usage, 4 store-integrity.
* Source immutability on replay.
* Promote denial taxonomy surfaces ``denial_reason`` in JSON data.
* Review queue lifecycle verbs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from git_cg.eval.binding import paths as binding_paths
from git_cg.eval.binding.paths import acceptpath_bundles_dir, atomic_write_json, review_queue_dir
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.main import app as cli_app

runner = CliRunner()


def _bundle(**over) -> dict:
    base = {
        "schema_version": "ape_bundle_v1",
        "case_id": "case-src-1",
        "artifact_class": "final_accept",
        "bound": True,
        "session_thread_id": "thread-src-1",
        "final_message": "docs(eval): freeze schema pack\n",
        "provenance_label": "final_accept",
        "redaction_profile": "default_scrub",
        "regime": "A",
        "path_class_gate": "docs_only",
        "generation_task_input": {
            "diff_summary": "docs only",
            "path_class_gate": "docs_only",
            "ranked_intent_id": "documentation_update",
        },
        "failure_ids": [],
        "meta": {
            "binding": {"trace_id": "trace-src-1", "state": "bound"},
            "split_group_id": "sg:thread-src-1",
        },
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    base.update(over)
    return base


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".git").mkdir()
    atomic_write_json(acceptpath_bundles_dir(tmp_path) / "thread-src-1.json", _bundle())
    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda start=None: tmp_path)
    return tmp_path


def _env(result) -> dict:
    assert result.exit_code in (0, 1, 2, 3, 4), result.output
    return json.loads(result.stdout)


def test_cli_replay_json(repo: Path) -> None:
    source = acceptpath_bundles_dir(repo) / "thread-src-1.json"
    before = source.read_bytes()
    result = runner.invoke(cli_app, ["eval", "replay", "--bundle", "thread-src-1", "--json"])
    env = _env(result)
    assert result.exit_code == 0
    assert env["command"] == "eval replay"
    assert env["ok"] is True
    compare = env["data"]["compare"]
    assert compare["session_thread_id"] == "thread-src-1"
    assert compare["schema_version"] == "replay_compare_v1"
    assert env["data"]["source_mutated"] is False
    assert source.read_bytes() == before


def test_cli_replay_missing_usage(repo: Path) -> None:
    result = runner.invoke(cli_app, ["eval", "replay", "--bundle", "nope", "--json"])
    env = _env(result)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["errors"][0]["code"] == "EVAL_USAGE"


def test_cli_promote_json_happy(repo: Path) -> None:
    result = runner.invoke(
        cli_app,
        [
            "eval",
            "promote",
            "--bundle",
            "thread-src-1",
            "--destination",
            "observability_fixture",
            "--owner",
            "owner-1",
            "--label",
            "obs-candidate",
            "--provenance",
            "diag_issue",
            "--redaction-profile",
            "default_scrub",
            "--json",
        ],
    )
    env = _env(result)
    assert result.exit_code == 0
    assert env["command"] == "eval promote"
    assert env["data"]["accepted"] is True
    assert env["data"]["decision"]["destination"] == "observability_fixture"


def test_cli_promote_denies_gold_with_reason(repo: Path) -> None:
    result = runner.invoke(
        cli_app,
        [
            "eval",
            "promote",
            "--bundle",
            "thread-src-1",
            "--destination",
            "fixture_lane_a",
            "--owner",
            "owner-1",
            "--label",
            "gold",
            "--provenance",
            "user_acceptance",
            "--redaction-profile",
            "default_scrub",
            "--popularity-signal",
            "--json",
        ],
    )
    env = _env(result)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["data"]["accepted"] is False
    assert env["data"]["denial_reason"] == "popularity_promotion_forbidden"


def test_cli_review_lifecycle(repo: Path) -> None:
    res = runner.invoke(
        cli_app,
        [
            "eval",
            "review",
            "enqueue",
            "--case",
            "case-src-1",
            "--reviewer",
            "rev-1",
            "--craft-rating",
            "3",
            "--json",
        ],
    )
    env = _env(res)
    assert res.exit_code == 0
    rid = env["data"]["item"]["review_id"]
    assert (review_queue_dir(repo) / f"{rid}.json").is_file()

    res = runner.invoke(cli_app, ["eval", "review", "list", "--json"])
    env = _env(res)
    assert env["data"]["review_count"] == 1

    res = runner.invoke(cli_app, ["eval", "review", "claim", rid, "--reviewer", "rev-1", "--json"])
    env = _env(res)
    assert env["data"]["item"]["status"] == "in_review"

    res = runner.invoke(
        cli_app,
        [
            "eval",
            "review",
            "adjudicate",
            rid,
            "--outcome",
            "approve_promote",
            "--destination-hint",
            "observability_fixture",
            "--json",
        ],
    )
    env = _env(res)
    assert res.exit_code == 0
    assert env["data"]["item"]["status"] == "adjudicated"
    assert env["data"]["outcome_ref"].startswith("review_outcome:")

    # Human sole gold still denied even with adjudicated review.
    res = runner.invoke(
        cli_app,
        [
            "eval",
            "promote",
            "--bundle",
            "thread-src-1",
            "--destination",
            "fixture_lane_a",
            "--owner",
            "owner-1",
            "--label",
            "golden",
            "--provenance",
            "human_review",
            "--redaction-profile",
            "default_scrub",
            "--review-id",
            rid,
            "--json",
        ],
    )
    env = _env(res)
    assert res.exit_code == 2
    assert env["data"]["denial_reason"] in {
        "human_review_cannot_sole_promote_golden",
        "silent_gold_mint_forbidden",
    }


def test_cli_review_dismiss(repo: Path) -> None:
    res = runner.invoke(
        cli_app,
        ["eval", "review", "enqueue", "--case", "c1", "--reviewer", "rev-1", "--json"],
    )
    rid = _env(res)["data"]["item"]["review_id"]
    res = runner.invoke(
        cli_app,
        ["eval", "review", "dismiss", rid, "--reason", "duplicate", "--json"],
    )
    env = _env(res)
    assert res.exit_code == 0
    assert env["data"]["item"]["status"] == "dismissed"


def test_cli_promote_denial_persists_audit(repo: Path) -> None:
    """S6-E09: CLI denial surfaces named reason + retained candidate audit path."""
    result = runner.invoke(
        cli_app,
        [
            "eval",
            "promote",
            "--bundle",
            "thread-src-1",
            "--destination",
            "fixture_lane_a",
            "--owner",
            "owner-1",
            "--label",
            "gold",
            "--provenance",
            "user_acceptance",
            "--redaction-profile",
            "default_scrub",
            "--popularity-signal",
            "--json",
        ],
    )
    env = _env(result)
    assert result.exit_code == 2
    assert env["ok"] is False
    assert env["data"]["accepted"] is False
    assert env["data"]["denial_reason"] == "popularity_promotion_forbidden"
    assert "decision" in env["data"]
    assert env["data"]["decision"]["accepted"] is False
    assert env["data"]["decision"]["denial_reason"] == env["data"]["denial_reason"]
    assert env["data"]["decision"]["candidate_class"] == "scrubbed_candidate"
    decision_path = Path(env["data"]["decision_path"])
    assert decision_path.is_file()
    # No destination fixture minted on denial.
    assert (
        not (repo / ".eval" / "index" / "fixture_lane_a_candidates").exists()
        or list((repo / ".eval" / "index" / "fixture_lane_a_candidates").glob("*.json")) == []
    )


def test_cli_review_rollup_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").mkdir(exist_ok=True)
    # isolate repo root
    from git_cg.eval.binding import paths as binding_paths

    monkeypatch.setattr(binding_paths, "resolve_repo_root", lambda start=None: tmp_path)
    # seed two reviews via library
    from git_cg.eval.review_queue import enqueue

    enqueue(tmp_path, case_id="c1", reviewer="alice", craft_rating=3.0, regime_label="A")
    enqueue(tmp_path, case_id="c1", reviewer="bob", craft_rating=4.0, regime_label="A")
    result = runner.invoke(cli_app, ["eval", "review", "rollup", "--case", "c1", "--json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["can_sole_promote_gold"] is False
    assert payload["data"]["authority"] == "advisory"
    assert payload["data"]["rollup_count"] == 1
