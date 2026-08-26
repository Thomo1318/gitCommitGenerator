"""Slice 6 ``eval replay`` law (Issue #246 / FIND-023 / INT-18).

Locks offline structural replay against frozen schemas:

* Writes a **new** replay bundle + schema-valid ``replay_compare_v1``.
* Preserves ``session_thread_id``; mints new replay identity / trace / hash.
* Never mutates the source bundle bytes.
* Pins harness + metric catalog + schema pack on the compare record.
* Dry-run validates without writing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import acceptpath_bundles_dir, atomic_write_json, experiments_dir, replays_dir
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.replay import ReplayError, replay, show_replay
from git_cg.eval.schema_pack import validate_instance


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
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def _seed_acceptpath(repo: Path, bundle: dict | None = None, stem: str = "thread-src-1") -> Path:
    b = bundle or _bundle()
    path = acceptpath_bundles_dir(repo) / f"{stem}.json"
    atomic_write_json(path, b)
    return path


def test_replay_writes_new_bundle_and_compare_without_mutating_source(repo: Path) -> None:
    source_path = _seed_acceptpath(repo)
    before = source_path.read_bytes()

    result = replay(repo, bundle="thread-src-1")
    compare = result["compare"]
    replay_bundle = result["replay_bundle"]

    assert result["source_mutated"] is False
    assert source_path.read_bytes() == before

    validate_instance("replay_compare_v1", compare)
    validate_instance("ape_bundle_v1", replay_bundle)

    assert compare["schema_version"] == "replay_compare_v1"
    assert compare["session_thread_id"] == "thread-src-1"
    assert compare["source_trace_id"] == "trace-src-1"
    assert compare["replay_trace_id"] != "trace-src-1"
    assert compare["source_bundle_hash"] != compare["replay_bundle_hash"]
    assert compare["lineage_ok"] is True
    assert compare["regression_status"] == "unchanged"
    assert compare["deltas"]["input_equal"] is True
    assert compare["pinned"]["schema_pack"] == schema_pack_pin()
    assert compare["pinned"]["metric_catalog"] == metric_catalog_pin()
    assert compare["pinned"]["harness_version"]

    # New identity, preserved thread.
    assert replay_bundle["session_thread_id"] == "thread-src-1"
    assert replay_bundle["case_id"].startswith("replay:")
    assert replay_bundle["meta"]["binding"]["trace_id"] == compare["replay_trace_id"]
    assert replay_bundle["meta"]["replay_of_bundle_hash"] == compare["source_bundle_hash"]
    assert replay_bundle["meta"]["split_group_id"] == "sg:thread-src-1"

    # On disk under .eval/replays/
    assert Path(result["compare_path"]).is_file()
    assert Path(result["replay_bundle_path"]).is_file()
    assert Path(result["compare_path"]).parent == replays_dir(repo)


def test_replay_dry_run_does_not_write(repo: Path) -> None:
    _seed_acceptpath(repo)
    result = replay(repo, bundle="thread-src-1", dry_run=True)
    assert result["dry_run"] is True
    assert not Path(result["compare_path"]).exists()
    assert not Path(result["replay_bundle_path"]).exists()
    validate_instance("replay_compare_v1", result["compare"])


def test_replay_from_experiment_case(repo: Path) -> None:
    _seed_acceptpath(repo)
    atomic_write_json(
        experiments_dir(repo) / "exp-a" / "cases" / "case-fail.json",
        {
            "schema_version": "local_case_score_v0",
            "experiment_id": "exp-a",
            "case_id": "case-fail",
            "session_thread_id": "thread-src-1",
            "deterministic_pass": False,
            "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
            "evaluator_errors": [],
            "scores": [],
            "gates": [],
            "failed_metric_ids": [],
        },
    )
    result = replay(repo, experiment_id="exp-a", case_id="case-fail")
    assert result["compare"]["session_thread_id"] == "thread-src-1"


def test_replay_missing_source_exit_usage(repo: Path) -> None:
    with pytest.raises(ReplayError) as ei:
        replay(repo, bundle="missing-thread")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_replay_requires_selector(repo: Path) -> None:
    with pytest.raises(ReplayError) as ei:
        replay(repo)
    assert ei.value.exit_code == 2


def test_show_replay(repo: Path) -> None:
    _seed_acceptpath(repo)
    result = replay(repo, bundle="thread-src-1")
    rid = result["compare"]["replay_id"]
    shown = show_replay(repo, replay_id=rid)
    assert shown["compare"]["replay_id"] == rid


def test_replay_explicit_path(repo: Path, tmp_path: Path) -> None:
    # Explicit path outside acceptpath is allowed for read-only source.
    external = tmp_path / "external.json"
    external.write_text(json.dumps(_bundle()), encoding="utf-8")
    # Need .git for repo containment of writes; source can be external.
    result = replay(repo, bundle=str(external))
    assert result["compare"]["session_thread_id"] == "thread-src-1"
    assert external.read_text(encoding="utf-8")  # still present


def test_replay_mints_synthetic_thread_when_source_lacks_session(repo: Path, tmp_path: Path) -> None:
    """Source bundles without session_thread_id mint a stable thread:{replay_id}."""
    bundle = _bundle()
    bundle.pop("session_thread_id", None)
    external = tmp_path / "no-thread.json"
    external.write_text(json.dumps(bundle), encoding="utf-8")
    result = replay(repo, bundle=str(external))
    compare = result["compare"]
    rid = compare["replay_id"]
    assert compare["session_thread_id"] == f"thread:{rid}"
    # Replay bundle on disk also carries the minted thread.
    bundle_path = Path(result["replay_bundle_path"])
    if bundle_path.is_file():
        replayed = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert replayed.get("session_thread_id") == f"thread:{rid}"
