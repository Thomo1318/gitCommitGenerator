"""S4a export_queue_item_v1 Layer-A tests (state machine, idempotent enqueue)."""

from __future__ import annotations

import json

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import build_export_batches
from git_cg.eval.mirror.queue import (
    ExportQueueError,
    enqueue_export_batch,
    export_queue_dir,
    load_queue_item,
    mark_queue_item,
)


def _batch(items: list[tuple[str, dict]] | None = None) -> dict:
    return build_export_batches(items or [("i-1", {"pad": "x" * 20})], RedactionProfile.DEFAULT_SCRUB)[0]


def test_enqueue_writes_pending_row(tmp_path) -> None:
    batch = _batch()
    path = enqueue_export_batch(batch, repo_root=tmp_path)
    assert path.is_file()
    assert path.parent == export_queue_dir(tmp_path)
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["schema_version"] == "export_queue_item_v1"
    assert row["status"] == "pending"
    assert row["redaction_profile"] == "default_scrub"
    assert row["queue_id"] == batch["meta"]["idempotency_key"]


def test_enqueue_is_idempotent_same_batch_same_row(tmp_path) -> None:
    batch = _batch()
    p1 = enqueue_export_batch(batch, repo_root=tmp_path)
    p2 = enqueue_export_batch(batch, repo_root=tmp_path)
    assert p1 == p2  # same queue row, no duplicate


def test_enqueue_requires_idempotency_key(tmp_path) -> None:
    with pytest.raises(ExportQueueError, match="idempotency"):
        enqueue_export_batch({"schema_version": "export_batch_v1"}, repo_root=tmp_path)


def test_enqueue_rejects_path_escape_queue_id(tmp_path) -> None:
    batch = _batch()
    batch["meta"]["idempotency_key"] = "../escape"
    batch["batch_id"] = "../escape"
    with pytest.raises(ExportQueueError, match="invalid queue_id"):
        enqueue_export_batch(batch, repo_root=tmp_path)


def test_state_machine_happy_path(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = batch["meta"]["idempotency_key"]

    mark_queue_item(qid, "sending", repo_root=tmp_path)
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "sending"

    mark_queue_item(qid, "sent", repo_root=tmp_path)
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "sent"


def test_failed_can_retry(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = batch["meta"]["idempotency_key"]
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(qid, "failed", repo_root=tmp_path)
    mark_queue_item(qid, "sending", repo_root=tmp_path)  # retry
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "sending"


def test_illegal_transition_fails_closed(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = batch["meta"]["idempotency_key"]
    with pytest.raises(ExportQueueError, match="illegal queue transition"):
        mark_queue_item(qid, "sent", repo_root=tmp_path)  # pending → sent skips sending


def test_sent_is_terminal(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = batch["meta"]["idempotency_key"]
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(qid, "sent", repo_root=tmp_path)
    with pytest.raises(ExportQueueError, match="illegal queue transition"):
        mark_queue_item(qid, "sending", repo_root=tmp_path)


def test_unknown_status_fails_closed(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    with pytest.raises(ExportQueueError, match="unknown queue status"):
        mark_queue_item(batch["meta"]["idempotency_key"], "bogus", repo_root=tmp_path)


def test_load_missing_item_fails_closed(tmp_path) -> None:
    with pytest.raises(ExportQueueError, match="no export queue item"):
        load_queue_item("does-not-exist", repo_root=tmp_path)


def test_mark_records_notes(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = batch["meta"]["idempotency_key"]
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(qid, "failed", repo_root=tmp_path, notes="export_network: timeout")
    row = load_queue_item(qid, repo_root=tmp_path)
    assert row["status"] == "failed"
    assert "export_network" in row["notes"]
