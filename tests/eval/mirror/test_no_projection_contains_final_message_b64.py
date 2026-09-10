"""Export copies must never carry local ``final_message_b64`` bytes."""

from __future__ import annotations

import copy
import json
from typing import Any

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import build_export_batches
from git_cg.eval.mirror.composition import build_export_plan
from git_cg.eval.mirror.health import ExportHealth
from git_cg.eval.mirror.payload import load_payload_artifact, persist_payload_artifact
from git_cg.eval.mirror.projections import (
    authority_annotations,
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
)
from git_cg.eval.mirror.queue import enqueue_export_batch, load_queue_item, load_queue_payload
from git_cg.eval.mirror.queue_projector import _projection_payload, project_review_queue_live
from git_cg.eval.mirror.redaction import redact_bundle_for_export
from git_cg.eval.mirror.result import build_mirror_result, evaluation_job_result, export_result
from git_cg.eval.mirror.train import build_train_projection, filter_positive_gold, project_train_row

FORBIDDEN = "final_message_b64"
_BOOKKEEPING_PATH_KEYS = frozenset({"redaction_denied_keys", "redaction_quarantine"})

CONFIG = {
    "schema_version": "git_cg_opik_config_v1",
    "id": "git_cg_opik_config_v1",
    "mode": "mirror",
    "environment": "eval",
    "redaction_profile": "default_scrub",
    "flush_timeout_ms": 5000,
    "track_disable": False,
    "check_tls_certificate": True,
    "projects": {
        "live": "eval-project",
        "eval": "eval-project",
        "ci": "eval-project",
        "import": "eval-project",
    },
    "project_name": "eval-project",
}


def _without_bookkeeping_paths(value: object) -> object:
    """Copy ``value`` omitting redaction path-bookkeeping lists.

    Denied-path strings such as ``meta.final_message_b64`` are required
    production bookkeeping, not export payload keys.
    """
    if isinstance(value, dict):
        return {
            key: _without_bookkeeping_paths(child) for key, child in value.items() if key not in _BOOKKEEPING_PATH_KEYS
        }
    if isinstance(value, list):
        return [_without_bookkeeping_paths(child) for child in value]
    if isinstance(value, tuple):
        return tuple(_without_bookkeeping_paths(child) for child in value)
    return value


def assert_no_final_message_b64(payload: object) -> None:
    """Fail if the exact key (or its serialized form) appears in an export copy."""
    stack: list[object] = [payload]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        ident = id(current)
        if ident in seen:
            continue
        if isinstance(current, (dict, list, tuple)):
            seen.add(ident)
        if isinstance(current, dict):
            assert FORBIDDEN not in current
            assert all(key != FORBIDDEN for key in current)
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    blob = json.dumps(_without_bookkeeping_paths(payload), default=str)
    assert FORBIDDEN not in blob


def _poisoned_bundle() -> dict[str, Any]:
    """Authoritative local bundle that is allowed to retain ``final_message_b64``."""
    return {
        "schema_version": "ape_bundle_v1",
        "id": "bundle_b64_guard",
        "case_id": "case-b64-guard",
        "artifact_class": "final_accept",
        "session_thread_id": "sess_b64_guard",
        "attempts": [
            {
                "final_message": "✨ feat(scope): subject",
                "scored_target": "final_message",
                "artifact_class": "final_accept",
                FORBIDDEN: "attempt-local-bytes",
            }
        ],
        "gate": {"deterministic_pass": True, FORBIDDEN: "gate-local-bytes"},
        "score_card": {
            "format_compliance": 1.0,
            "subject_length": 0.9,
            "deterministic_flag": True,
            FORBIDDEN: 1.0,
            "nested": {FORBIDDEN: "score-nested-bytes"},
        },
        "product_card": {FORBIDDEN: "product-local-bytes"},
        "meta": {
            "redaction_profile": "default_scrub",
            "applied_redaction_profile": "default_scrub",
            "artifact_class": "final_accept",
            "label": "acceptpath-live",
            "train_label": "positive",
            "split": "train",
            "split_group_id": "sg-b64-guard",
            "provenance_label": "acceptpath-live",
            "regime": "A",
            FORBIDDEN: "meta-top-local-bytes",
            "score_card": {
                "nested_score": 0.5,
                FORBIDDEN: "meta-score-local-bytes",
            },
        },
    }


def _poisoned_session() -> dict[str, Any]:
    """Session twin with nested local-only message bytes."""
    return {
        "schema_version": "commit_session_thread_v1",
        "session_thread_id": "sess_b64_guard",
        "redaction_profile": "default_scrub",
        "attempt_ids": ["a1"],
        "message_versions": [
            {
                "role": "assistant",
                "content": "draft",
                FORBIDDEN: "thread-message-bytes",
            }
        ],
        "meta": {
            "lifecycle": "closed",
            "trace_id": "t-b64",
            "generation_thread_id": "gen-b64",
            FORBIDDEN: "thread-meta-bytes",
        },
    }


class TestLocalAuthorityRetainsFinalMessageB64:
    def test_input_bundle_keeps_local_bytes_and_is_not_mutated(self) -> None:
        bundle = _poisoned_bundle()
        snapshot = copy.deepcopy(bundle)
        redact_bundle_for_export(bundle, RedactionProfile.DEFAULT_SCRUB)
        project_bundle_to_trace(bundle, experiment_name="exp")
        project_train_row(bundle)
        assert bundle == snapshot
        assert bundle["meta"][FORBIDDEN] == "meta-top-local-bytes"
        assert bundle["score_card"][FORBIDDEN] == 1.0
        assert bundle["attempts"][0][FORBIDDEN] == "attempt-local-bytes"


class TestExportBuildersDropFinalMessageB64:
    def test_redaction_drops_nested_and_top_level_keys(self) -> None:
        out = redact_bundle_for_export(_poisoned_bundle(), RedactionProfile.DEFAULT_SCRUB)
        assert_no_final_message_b64(out)
        denied = (out.get("meta") or {}).get("redaction_denied_keys") or []
        assert any(str(path).endswith(FORBIDDEN) for path in denied)

    def test_trace_feedback_and_authority_annotations(self) -> None:
        bundle = _poisoned_bundle()
        trace = project_bundle_to_trace(bundle, experiment_name="exp")
        feedback = project_score_card_to_feedback(bundle, experiment_name="exp")
        annotations = authority_annotations(
            bundle,
            experiment_name="exp",
            extra={FORBIDDEN: "annotation-extra", "score_card_key": "format_compliance"},
        )
        assert_no_final_message_b64(trace)
        assert_no_final_message_b64(feedback)
        assert_no_final_message_b64(annotations)
        assert annotations["train_label"] == "positive"
        assert annotations["split_group_id"] == "sg-b64-guard"
        assert annotations["score_card_key"] == "format_compliance"

    def test_session_thread_projection(self) -> None:
        thread = project_session_thread(_poisoned_session(), experiment_name="exp")
        assert_no_final_message_b64(thread)
        assert thread["thread_id"] == "sess_b64_guard"
        assert thread["messages"][0]["content"] == "draft"

    def test_train_row_and_projection(self) -> None:
        bundle = _poisoned_bundle()
        row = project_train_row(bundle)
        assert row is not None
        assert_no_final_message_b64(row)
        proj = build_train_projection([bundle])
        assert_no_final_message_b64(proj)
        gold = filter_positive_gold(
            [
                {
                    "bundle_id": "p",
                    "label": "positive",
                    "regime": "A",
                    FORBIDDEN: "gold-bytes",
                    "score_card": {FORBIDDEN: "gold-nested"},
                }
            ]
        )
        assert_no_final_message_b64(gold)

    def test_batch_queue_and_payload_persist(self, tmp_path) -> None:
        payload = {
            "trace": project_bundle_to_trace(_poisoned_bundle(), experiment_name="exp"),
            "feedback": project_score_card_to_feedback(_poisoned_bundle(), experiment_name="exp"),
            "thread": project_session_thread(_poisoned_session(), experiment_name="exp"),
            "gate": {FORBIDDEN: "batch-gate-bytes"},
            "score_card": {FORBIDDEN: "batch-score-bytes", "nested": {FORBIDDEN: "batch-nested"}},
        }
        batches = build_export_batches(
            [("bundle_b64_guard", payload)],
            RedactionProfile.DEFAULT_SCRUB,
            project="eval-project",
            experiment_id="exp",
            environment="eval",
            dataset_id="ds-b64",
            project_lane="eval",
        )
        assert len(batches) == 1
        assert_no_final_message_b64(batches[0])

        path = enqueue_export_batch(batches[0], repo_root=tmp_path)
        row = load_queue_item(path.stem, repo_root=tmp_path)
        body = load_queue_payload(path.stem, repo_root=tmp_path)
        assert_no_final_message_b64(row)
        assert_no_final_message_b64(body)

        artifact = persist_payload_artifact({FORBIDDEN: "persist-bytes", "ok": True}, repo_root=tmp_path)
        loaded = load_payload_artifact(artifact["payload_ref"], repo_root=tmp_path)
        assert_no_final_message_b64(loaded)
        assert loaded["ok"] is True

    def test_result_axes(self) -> None:
        result = build_mirror_result(
            mode="mirror",
            health=ExportHealth.SUCCESS,
            attempted=1,
            succeeded=1,
            notes=("export ok",),
        )
        mapping = {
            **result.to_dict(),
            FORBIDDEN: "result-bytes",
            "notes": ["ok", {FORBIDDEN: "note-nested"}],
        }
        assert_no_final_message_b64(export_result(result))
        assert_no_final_message_b64(evaluation_job_result(result))
        assert_no_final_message_b64(export_result(mapping))
        assert_no_final_message_b64(evaluation_job_result(mapping))

    def test_queue_projector_payload(self) -> None:
        payload = _projection_payload(
            {
                "review_id": "r-b64",
                "status": "open",
                FORBIDDEN: "review-top",
                "review": {
                    "case_id": "case-b64",
                    "bundle_id": "bundle_b64_guard",
                    FORBIDDEN: "review-nested",
                },
            }
        )
        assert_no_final_message_b64(payload)

        class _Recorder:
            def __init__(self) -> None:
                self.items: list[dict[str, Any]] = []

            def project_items(self, items, *, project: str) -> int:
                self.items = [dict(item) for item in items]
                return len(self.items)

        recorder = _Recorder()
        project_review_queue_live(
            config={"mode": "mirror", "projects": {"eval": "eval-project"}},
            enable_live=True,
            projector=recorder,
        )
        assert_no_final_message_b64(recorder.items)

    def test_composition_plan_and_enqueued_payload(self, tmp_path) -> None:
        plan = build_export_plan(
            {"bundles": [_poisoned_bundle()], "session_threads": [_poisoned_session()], "include_train": True},
            CONFIG,
            repo_root=tmp_path,
            git_sha="abc1234",
            enqueue=True,
        )
        assert plan.product_accept_blocked is False
        assert_no_final_message_b64(plan.train)
        assert plan.queue_row_refs
        for qid in plan.queue_row_refs:
            assert_no_final_message_b64(load_queue_item(qid, repo_root=tmp_path))
            assert_no_final_message_b64(load_queue_payload(qid, repo_root=tmp_path))
