"""S4 Slice 3 — export_queue_item_v1 ops rows (P0-3 / P1-11 / E7 / E11)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import build_export_batches
from git_cg.eval.mirror.payload import export_payloads_dir, load_payload_artifact
from git_cg.eval.mirror.queue import (
    ExportQueueError,
    claim_queue_item,
    enqueue_export_batch,
    export_queue_dir,
    list_claimable_items,
    load_queue_item,
    load_queue_payload,
    mark_queue_item,
    release_stale_leases,
)


def _batch(items: list[tuple[str, dict]] | None = None) -> dict:
    return build_export_batches(items or [("i-1", {"pad": "x" * 20})], RedactionProfile.DEFAULT_SCRUB)[0]


def _qid(batch: dict) -> str:
    return str(batch["idempotency_key"])


def test_enqueue_writes_pending_row_and_payload_artifact(tmp_path) -> None:
    batch = _batch()
    path = enqueue_export_batch(batch, repo_root=tmp_path)
    assert path.is_file()
    assert path.parent == export_queue_dir(tmp_path)
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["schema_version"] == "export_queue_item_v1"
    assert row["status"] == "pending"
    assert row["redaction_profile"] == "default_scrub"
    assert row["queue_id"] == _qid(batch)
    assert row["payload_ref"].startswith("sha256:")
    assert len(row["payload_sha256"]) == 64
    assert row["payload_size_bytes"] > 0
    assert row["batch_id"] == batch["batch_id"]
    assert row["project"] == batch["project"]
    assert row["experiment_id"] == batch["experiment_id"]
    assert row["envelope_status"] == "pending"
    assert row["attempt_count"] == 0

    body = load_payload_artifact(row["payload_ref"], repo_root=tmp_path, expected_sha256=row["payload_sha256"])
    assert "items" in body
    assert (export_payloads_dir(tmp_path) / f"{row['payload_sha256']}.json").is_file()

    loaded = load_queue_payload(row["queue_id"], repo_root=tmp_path)
    assert loaded == body


def test_enqueue_is_idempotent_same_batch_same_row(tmp_path) -> None:
    batch = _batch()
    p1 = enqueue_export_batch(batch, repo_root=tmp_path)
    p2 = enqueue_export_batch(batch, repo_root=tmp_path)
    assert p1 == p2


def test_enqueue_does_not_reset_sent_row(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(qid, "sent", repo_root=tmp_path)
    enqueue_export_batch(batch, repo_root=tmp_path)
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "sent"


def test_enqueue_does_not_reset_sending_row(tmp_path) -> None:
    """Re-enqueue must not clear lease ownership or reset attempt_count."""
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    claimed = claim_queue_item(qid, repo_root=tmp_path, claimed_by="worker-a")
    assert claimed is not None
    before = load_queue_item(qid, repo_root=tmp_path)
    assert before["status"] == "sending"
    assert before["claimed_by"] == "worker-a"
    assert int(before["attempt_count"]) >= 1
    lease = before.get("lease_expires_at")

    enqueue_export_batch(batch, repo_root=tmp_path)
    after = load_queue_item(qid, repo_root=tmp_path)
    assert after["status"] == "sending"
    assert after["claimed_by"] == "worker-a"
    assert after["attempt_count"] == before["attempt_count"]
    assert after.get("lease_expires_at") == lease


def test_enqueue_requires_idempotency_key(tmp_path) -> None:
    with pytest.raises(ExportQueueError, match="idempotency"):
        enqueue_export_batch({"schema_version": "export_batch_v1"}, repo_root=tmp_path)


def test_enqueue_rejects_path_escape_queue_id(tmp_path) -> None:
    batch = _batch()
    batch["idempotency_key"] = "../escape"
    batch["batch_id"] = "../escape"
    with pytest.raises(ExportQueueError, match="invalid queue_id"):
        enqueue_export_batch(batch, repo_root=tmp_path)


def test_enqueue_without_transport_body_fails_closed(tmp_path) -> None:
    batch = _batch()
    batch["meta"] = {"item_count": 1}
    with pytest.raises(ExportQueueError, match="transport_body"):
        enqueue_export_batch(batch, repo_root=tmp_path)


def test_state_machine_happy_path(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)

    mark_queue_item(qid, "sending", repo_root=tmp_path)
    row = load_queue_item(qid, repo_root=tmp_path)
    assert row["status"] == "sending"
    assert row["envelope_status"] == "pending"
    assert row.get("claimed_by")
    assert row.get("lease_expires_at")

    mark_queue_item(qid, "sent", repo_root=tmp_path, clear_lease=True)
    row = load_queue_item(qid, repo_root=tmp_path)
    assert row["status"] == "sent"
    assert row["envelope_status"] == "ok"
    assert "claimed_by" not in row


def test_failed_can_retry(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(qid, "failed", repo_root=tmp_path, last_error_class="export_network")
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "sending"


def test_illegal_transition_fails_closed(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    with pytest.raises(ExportQueueError, match="illegal queue transition"):
        mark_queue_item(qid, "sent", repo_root=tmp_path)


def test_sent_is_terminal(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(qid, "sent", repo_root=tmp_path)
    with pytest.raises(ExportQueueError, match="illegal queue transition"):
        mark_queue_item(qid, "sending", repo_root=tmp_path)


def test_unknown_status_fails_closed(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    with pytest.raises(ExportQueueError, match="unknown queue status"):
        mark_queue_item(_qid(batch), "bogus", repo_root=tmp_path)


def test_load_missing_item_fails_closed(tmp_path) -> None:
    with pytest.raises(ExportQueueError, match="no export queue item"):
        load_queue_item("does-not-exist", repo_root=tmp_path)


def test_mark_records_notes_and_error_class(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    mark_queue_item(qid, "sending", repo_root=tmp_path)
    mark_queue_item(
        qid,
        "failed",
        repo_root=tmp_path,
        notes="export_network: timeout",
        last_error_class="export_network",
    )
    row = load_queue_item(qid, repo_root=tmp_path)
    assert row["status"] == "failed"
    assert "export_network" in row["notes"]
    assert row["last_error_class"] == "export_network"
    assert row["envelope_status"] == "failed"


def test_claim_moves_pending_to_sending_with_attempt(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    claimed = claim_queue_item(qid, repo_root=tmp_path, claimed_by="drainer-1")
    assert claimed is not None
    assert claimed["status"] == "sending"
    assert claimed["claimed_by"] == "drainer-1"
    assert claimed["attempt_count"] == 1
    assert claimed.get("lease_expires_at")


def test_double_claim_loses_race(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    assert claim_queue_item(qid, repo_root=tmp_path, claimed_by="a") is not None
    assert claim_queue_item(qid, repo_root=tmp_path, claimed_by="b") is None


def test_stale_sending_is_reclaimed(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    mark_queue_item(qid, "sending", repo_root=tmp_path, claimed_by="old", lease_seconds=1)
    row = load_queue_item(qid, repo_root=tmp_path)
    past = (datetime.now(UTC) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row["lease_expires_at"] = past
    path = export_queue_dir(tmp_path) / f"{qid}.json"
    path.write_text(json.dumps(row), encoding="utf-8")

    reclaimed = release_stale_leases(repo_root=tmp_path)
    assert qid in reclaimed
    assert load_queue_item(qid, repo_root=tmp_path)["status"] == "pending"
    assert list_claimable_items(repo_root=tmp_path)


def test_list_claimable_after_reclaim(tmp_path) -> None:
    batch = _batch()
    enqueue_export_batch(batch, repo_root=tmp_path)
    qid = _qid(batch)
    mark_queue_item(qid, "sending", repo_root=tmp_path, lease_seconds=1)
    row = load_queue_item(qid, repo_root=tmp_path)
    row["lease_expires_at"] = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (export_queue_dir(tmp_path) / f"{qid}.json").write_text(json.dumps(row), encoding="utf-8")
    claimable = list_claimable_items(repo_root=tmp_path)
    assert len(claimable) == 1
    assert claimable[0]["queue_id"] == qid


def test_network_export_refuses_unresolved_git_sha_before_enqueue(tmp_path) -> None:
    """P1-12: network export with zeroed/unresolved SHA fails before queue write."""
    batch = _batch()
    with pytest.raises(ExportQueueError, match="unresolved git SHA") as ei:
        enqueue_export_batch(
            batch,
            repo_root=tmp_path,
            network_export=True,
            git_sha="0" * 40,
        )
    assert ei.value.error_class == "export_validation"
    assert not export_queue_dir(tmp_path).exists() or not any(export_queue_dir(tmp_path).glob("*.json"))
    assert not export_payloads_dir(tmp_path).exists() or not any(export_payloads_dir(tmp_path).glob("*.json"))


def test_network_export_accepts_resolved_git_sha(tmp_path) -> None:
    batch = _batch()
    path = enqueue_export_batch(
        batch,
        repo_root=tmp_path,
        network_export=True,
        git_sha="abc1234def56",
    )
    assert path.is_file()
    assert load_queue_item(path.stem, repo_root=tmp_path)["status"] == "pending"


def test_local_enqueue_still_allows_missing_git_sha(tmp_path) -> None:
    """Local/offline durability remains usable without a resolved SHA."""
    batch = _batch()
    path = enqueue_export_batch(batch, repo_root=tmp_path, network_export=False)
    assert path.is_file()
