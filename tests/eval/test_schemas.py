"""S0-A: schema pack freeze — offline only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.paths import SCHEMA_DIR
from git_cg.eval.schema_pack import SchemaPackError, list_schema_names, validate_instance

FIXTURES = Path(__file__).parent / "fixtures"

REQUIRED_SCHEMAS = {
    "ape_bundle_v1",
    "score_result_v1",
    "eval_suite_v1",
    "eval_case_v1",
    "dataset_snapshot_v1",
    "experiment_v1",
    "evaluation_checkpoint_v1",
    "trajectory_evidence_v1",
    "human_review_v1",
    "judge_meta_eval_v1",
    "thread_eval_v1",
    "amend_brief_v1",
    "dogfood_attachment_v1",
    "export_batch_v1",
    "trace_topology_v1",
    "correlation_envelope_v1",
    "diag_issue_v1",
    "git_cg_opik_config_v1",
    "replay_compare_v1",
    "git_cg_pipeline_graph_v1",
    "prompt_pack_v1",
    "export_queue_item_v1",
    "commit_session_thread_v1",
    "train_row_v1",
    "train_export_v1",
}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_s0_a01_required_schemas_exist() -> None:
    names = set(list_schema_names())
    missing = sorted(REQUIRED_SCHEMAS - names)
    assert not missing, f"missing schemas: {missing}"
    assert SCHEMA_DIR.is_dir()


def test_s0_a02_known_good_core_fixtures_validate() -> None:
    validate_instance("score_result_v1", _load("score_result.good.json"))
    validate_instance("ape_bundle_v1", _load("ape_bundle.good.json"))
    validate_instance("eval_suite_v1", _load("eval_suite.good.json"))


def test_s0_a03_known_bad_score_result_rejects() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance("score_result_v1", _load("score_result.bad.missing_authority.json"))


def test_s0_a04_session_train_stubs_validate() -> None:
    validate_instance("commit_session_thread_v1", _load("commit_session_thread.good.json"))
    validate_instance("train_row_v1", _load("train_row.good.json"))
    validate_instance("train_export_v1", _load("train_export.good.json"))


def test_s0_a05_unknown_artifact_class_rejected() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance("ape_bundle_v1", _load("ape_bundle.bad.unknown_artifact_class.json"))


def test_s0_a_expected_not_in_generation_task_input() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance(
            "ape_bundle_v1",
            _load("ape_bundle.bad.expected_in_generation_input.json"),
        )
