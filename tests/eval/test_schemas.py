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
    "cli_output_envelope_v1",
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


def test_s0_a_expected_prefix_rejected_in_generation_task_input() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance(
            "ape_bundle_v1",
            _load("ape_bundle.bad.expected_prefix_in_generation_input.json"),
        )


def test_s0_a_bound_false_requires_unbound_reason() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance(
            "ape_bundle_v1",
            _load("ape_bundle.bad.bound_false_missing_reason.json"),
        )


def test_s0_a_pin_fields_require_sha256() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance("eval_suite_v1", _load("eval_suite.bad.short_pin.json"))
    validate_instance("eval_suite_v1", _load("eval_suite.good.json"))


def test_s0_a_export_batch_rejects_raw_dev_unsafe() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance(
            "export_batch_v1",
            _load("export_batch.bad.raw_dev_unsafe.json"),
        )


def test_s0_a_opik_config_requires_project_when_enabled() -> None:
    with pytest.raises(SchemaPackError):
        validate_instance(
            "git_cg_opik_config_v1",
            _load("git_cg_opik_config.bad.missing_project.json"),
        )
    validate_instance(
        "git_cg_opik_config_v1",
        _load("git_cg_opik_config.good.off.json"),
    )
    validate_instance(
        "git_cg_opik_config_v1",
        _load("git_cg_opik_config.good.mirror.json"),
    )
    validate_instance(
        "git_cg_opik_config_v1",
        _load("git_cg_opik_config.good.local_only.json"),
    )
    validate_instance(
        "git_cg_opik_config_v1",
        _load("git_cg_opik_config.good.strict_mirror.json"),
    )
    with pytest.raises(SchemaPackError):
        validate_instance(
            "git_cg_opik_config_v1",
            _load("git_cg_opik_config.bad.raw_dev_unsafe.json"),
        )


def test_s0_a_human_review_advisory_authority_and_redaction() -> None:
    payload = _load("human_review.good.json")
    validate_instance("human_review_v1", payload)
    assert payload["authority"] == "advisory"
    assert "scores" in payload
    assert "rating" not in payload


def test_s6_s1_greenfield_schemas_validate_good_fixtures() -> None:
    """Slice 1 re-freeze: six greenfield S6 schemas + cli envelope validate known-good fixtures."""
    validate_instance("evaluation_checkpoint_v1", _load("evaluation_checkpoint.good.json"))
    validate_instance("amend_brief_v1", _load("amend_brief.good.json"))
    validate_instance("diag_issue_v1", _load("diag_issue.good.json"))
    validate_instance("replay_compare_v1", _load("replay_compare.good.json"))
    validate_instance("human_review_v1", _load("human_review.good.json"))
    validate_instance("dogfood_attachment_v1", _load("dogfood_attachment.good.json"))
    validate_instance("dogfood_attachment_v1", _load("dogfood_attachment.sample.good.json"))
    validate_instance("cli_output_envelope_v1", _load("cli_output_envelope.good.json"))


def test_s6_s1_human_review_rejects_legacy_top_level_rating() -> None:
    """No dual-shape window: top-level rating is rejected after scores migration."""
    legacy = {
        "schema_version": "human_review_v1",
        "id": "hr-legacy",
        "review_id": "hr-legacy",
        "authority": "advisory",
        "redaction_profile": "meta_eval_scrub",
        "rating": 4,
        "scores": {},
    }
    with pytest.raises(SchemaPackError):
        validate_instance("human_review_v1", legacy)


def test_s6_s1_human_review_scores_keys_are_closed() -> None:
    payload = _load("human_review.good.json")
    payload = dict(payload)
    scores = dict(payload["scores"])
    scores["human.unknown_metric"] = 1
    payload["scores"] = scores
    with pytest.raises(SchemaPackError):
        validate_instance("human_review_v1", payload)


def test_s6_s1_checkpoint_mode_is_closed() -> None:
    payload = _load("evaluation_checkpoint.good.json")
    payload = dict(payload)
    payload["mode"] = "partial_merge"
    with pytest.raises(SchemaPackError):
        validate_instance("evaluation_checkpoint_v1", payload)


def test_s6_s1_diag_issue_status_is_closed() -> None:
    payload = _load("diag_issue.good.json")
    payload = dict(payload)
    payload["status"] = "wontfix"
    with pytest.raises(SchemaPackError):
        validate_instance("diag_issue_v1", payload)


def test_s6_s1_live_writer_optional_fields_remain_valid() -> None:
    """Additive optional fields must not break existing good fixtures."""
    validate_instance("commit_session_thread_v1", _load("commit_session_thread.good.json"))
    validate_instance("train_row_v1", _load("train_row.good.json"))
    validate_instance("train_export_v1", _load("train_export.good.json"))
    session = dict(_load("commit_session_thread.good.json"))
    session["repo_fingerprints"] = {"head": "abc1234"}
    session["train_label"] = "unlabeled"
    session["opik_thread_ref"] = "opik-thread-1"
    session["stages"] = [{"name": "accept", "status": "ok"}]
    session["preference_pairs"] = [{"chosen_version_id": "v2", "rejected_version_ids": ["v1"], "owner_approved": True}]
    validate_instance("commit_session_thread_v1", session)
    row = dict(_load("train_row.good.json"))
    row["split_group_id"] = "split-a"
    row["scrub_report"] = {"status": "ok", "fields_quarantined": []}
    row["vault_destination"] = "antipattern_vault"
    validate_instance("train_row_v1", row)


def test_s6_s1_cli_output_envelope_validates_good_fixture() -> None:
    validate_instance("cli_output_envelope_v1", _load("cli_output_envelope.good.json"))


def test_s6_s1_cli_output_envelope_meta_keys_are_closed() -> None:
    payload = dict(_load("cli_output_envelope.good.json"))
    meta = dict(payload.get("meta") or {})
    meta["scores"] = {"gate.deterministic_pass": True}
    payload["meta"] = meta
    with pytest.raises(SchemaPackError):
        validate_instance("cli_output_envelope_v1", payload)


def test_s6_s1_cli_output_envelope_message_items_require_code_and_message() -> None:
    payload = dict(_load("cli_output_envelope.good.json"))
    payload["ok"] = False
    payload["errors"] = [{"message": "missing code"}]
    with pytest.raises(SchemaPackError):
        validate_instance("cli_output_envelope_v1", payload)


def test_s6_s7_dogfood_sample_requires_repro_fields() -> None:
    """Slice 7: mode=sample requires seed/rate/population + selected identity."""
    bad = _load("dogfood_attachment.good.json")
    bad["mode"] = "sample"
    with pytest.raises(SchemaPackError):
        validate_instance("dogfood_attachment_v1", bad)
