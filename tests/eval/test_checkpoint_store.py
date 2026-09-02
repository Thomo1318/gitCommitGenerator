"""evaluation_checkpoint_v1 store and GC tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

import pytest

from git_cg.eval.checkpoint_store import (
    CheckpointStatus,
    CheckpointStoreError,
    build_checkpoint_record,
    delete_checkpoint,
    index_file,
    list_checkpoint_ids,
    list_checkpoint_inventory,
    list_index_rows,
    load_checkpoint,
    prune_checkpoints,
    write_checkpoint,
)
from git_cg.eval.schema_pack import load_schema


def _hash(n: int = 1) -> str:
    return (format(n, "x") * 64)[:64]


def _record(
    cid: str,
    *,
    suite: str = "suite-a",
    mode: str = "fresh_suite_run",
    completed=None,
    pending=None,
    status=None,
    started_at=None,
    last_progress_at=None,
):
    return build_checkpoint_record(
        checkpoint_id=cid,
        experiment_id=f"exp-{cid}",
        compat_hash=_hash(),
        completed_case_ids=completed or [],
        pending_case_ids=pending or ["c1"],
        mode=mode,
        suite_id=suite,
        snapshot_id="snap-1",
        schema_pack="schema_pack_v0@" + ("a" * 64),
        metric_catalog="metric_catalog_v0@" + ("b" * 64),
        status=status,
        started_at=started_at,
        last_progress_at=last_progress_at,
    )


def _legacy_payload(cid: str, *, suite: str = "suite-a", last_progress_at: str = "2026-08-20T12:00:00Z") -> dict:
    """Legacy authoritative payload without durable status/started_at."""
    return {
        "schema_version": "evaluation_checkpoint_v1",
        "id": cid,
        "checkpoint_id": cid,
        "experiment_id": f"exp-{cid}",
        "compat_hash": _hash(),
        "completed_case_ids": [],
        "pending_case_ids": ["c1"],
        "last_progress_at": last_progress_at,
        "mode": "fresh_suite_run",
        "suite_id": suite,
        "snapshot_id": "snap-1",
        "schema_pack": "schema_pack_v0@" + ("a" * 64),
        "metric_catalog": "metric_catalog_v0@" + ("b" * 64),
    }


def test_write_load_roundtrip(tmp_path: Path) -> None:
    rec = _record("ckpt-1")
    path = write_checkpoint(tmp_path, rec, started_at="2026-08-20T12:00:00Z", status="running")
    assert path.is_file()
    loaded = load_checkpoint(tmp_path, "ckpt-1")
    assert loaded["checkpoint_id"] == "ckpt-1"
    assert loaded["compat_hash"] == rec["compat_hash"]
    assert loaded["status"] == "running"
    assert loaded["started_at"] == "2026-08-20T12:00:00Z"
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "running"


def test_write_persists_status_started_at(tmp_path: Path) -> None:
    rec = _record("ckpt-durable", status="failed", started_at="2026-08-20T11:30:00Z")
    write_checkpoint(tmp_path, rec)
    loaded = load_checkpoint(tmp_path, "ckpt-durable")
    assert loaded["status"] == "failed"
    assert loaded["started_at"] == "2026-08-20T11:30:00Z"
    raw = json.loads((tmp_path / ".eval" / "checkpoints" / "ckpt-durable.json").read_text(encoding="utf-8"))
    assert raw["status"] == "failed"
    assert raw["started_at"] == "2026-08-20T11:30:00Z"


def test_reconstruct_from_authoritative(tmp_path: Path) -> None:
    rec = _record("ckpt-recon", status="completed", started_at="2026-08-20T09:00:00Z")
    write_checkpoint(tmp_path, rec)
    index_file(tmp_path, "ckpt-recon").unlink()
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "completed"
    assert rows[0].started_at == "2026-08-20T09:00:00Z"
    assert rows[0].suite_id == "suite-a"


def test_stale_index_does_not_override_authoritative(tmp_path: Path) -> None:
    rec = _record("ckpt-stale", status="completed", started_at="2026-08-20T08:00:00Z")
    write_checkpoint(tmp_path, rec)
    # Poison the rebuildable index with stale metadata.
    idx = index_file(tmp_path, "ckpt-stale")
    idx.write_text(
        json.dumps(
            {
                "checkpoint_id": "ckpt-stale",
                "suite_id": "suite-a",
                "experiment_id": "exp-ckpt-stale",
                "started_at": "2020-01-01T00:00:00Z",
                "last_progress_at": "2020-01-01T00:00:00Z",
                "status": "running",
                "mode": "fresh_suite_run",
                "path": str(tmp_path / ".eval" / "checkpoints" / "ckpt-stale.json"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "completed"
    assert rows[0].started_at == "2026-08-20T08:00:00Z"


def test_prune_respects_reconstructed_status(tmp_path: Path) -> None:
    # Many completed checkpoints + one failed whose index is deleted.
    for i in range(3):
        cid = f"ckpt-c{i:02d}"
        write_checkpoint(
            tmp_path,
            _record(cid, status="completed", started_at=f"2026-08-20T12:{i:02d}:00Z"),
            status="completed",
            started_at=f"2026-08-20T12:{i:02d}:00Z",
        )
    fail = _record("ckpt-fail-recon", status="failed", started_at="2026-08-20T11:00:00Z")
    write_checkpoint(tmp_path, fail, status="failed", started_at="2026-08-20T11:00:00Z")
    index_file(tmp_path, "ckpt-fail-recon").unlink()

    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    ids = set(list_checkpoint_ids(tmp_path))
    # With a completed present, reconstructed failed enters keep-last candidates and is pruned at 0.
    assert "ckpt-fail-recon" not in ids
    assert "ckpt-fail-recon" in pruned


def test_legacy_checkpoint_loads_without_status_started_at(tmp_path: Path) -> None:
    cid = "ckpt-legacy"
    path = tmp_path / ".eval" / "checkpoints" / f"{cid}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_legacy_payload(cid), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    loaded = load_checkpoint(tmp_path, cid)
    assert "status" not in loaded
    assert "started_at" not in loaded
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "running"
    assert rows[0].started_at == "2026-08-20T12:00:00Z"
    # Read must not rewrite the legacy authoritative file.
    after = path.read_text(encoding="utf-8")
    assert '"status"' not in after
    assert '"started_at"' not in after


def test_malformed_started_at_rejected(tmp_path: Path) -> None:
    rec = _record("ckpt-bad-ts")
    with pytest.raises(CheckpointStoreError) as ei:
        write_checkpoint(tmp_path, rec, started_at="not-a-timestamp", status="running")
    assert ei.value.code == "EVAL_CHECKPOINT_IO"
    with pytest.raises(CheckpointStoreError) as ei2:
        build_checkpoint_record(
            checkpoint_id="ckpt-bad-ts2",
            experiment_id="exp",
            compat_hash=_hash(),
            completed_case_ids=[],
            pending_case_ids=["c1"],
            mode="fresh_suite_run",
            started_at="2026-08-20T12:00:00+00:00",
        )
    assert ei2.value.code == "EVAL_CHECKPOINT_IO"


def test_noncanonical_fallback_normalized_or_skipped(tmp_path: Path) -> None:
    # Existing noncanonical started_at on payload is normalized on write.
    rec = _record("ckpt-norm")
    rec.pop("started_at", None)
    rec["started_at"] = "2026-08-20T12:00:00+00:00"
    path = write_checkpoint(tmp_path, rec, status="running")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["started_at"] == "2026-08-20T12:00:00Z"

    # Unparseable last_progress_at fallback is skipped → utc_now_iso-shaped default.
    rec2 = _record("ckpt-skip")
    rec2.pop("started_at", None)
    rec2["last_progress_at"] = "not-a-date"
    path2 = write_checkpoint(tmp_path, rec2, status="failed")
    loaded2 = json.loads(path2.read_text(encoding="utf-8"))
    assert loaded2["started_at"].endswith("Z")
    assert "T" in loaded2["started_at"]


def test_cross_suite_stale_index_prune_safety(tmp_path: Path) -> None:
    a = _record("ckpt-a", suite="suite-a", status="completed", started_at="2026-08-20T10:00:00Z")
    b = _record("ckpt-b", suite="suite-b", status="completed", started_at="2026-08-20T10:00:00Z")
    write_checkpoint(tmp_path, a, status="completed", started_at="2026-08-20T10:00:00Z")
    write_checkpoint(tmp_path, b, status="completed", started_at="2026-08-20T10:00:00Z")
    # Stale index claims ckpt-b belongs to suite-a.
    idx = index_file(tmp_path, "ckpt-b")
    raw = json.loads(idx.read_text(encoding="utf-8"))
    raw["suite_id"] = "suite-a"
    idx.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    ids = set(list_checkpoint_ids(tmp_path))
    assert "ckpt-b" in ids  # authoritative suite-b must not be deleted by suite-a prune
    assert "ckpt-b" not in pruned
    assert "ckpt-a" not in ids


def test_index_write_failure_preserves_authoritative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import checkpoint_store as store

    rec = _record("ckpt-idx-fail", status="completed", started_at="2026-08-20T07:00:00Z")
    calls = {"n": 0}
    real_atomic = store.atomic_write_json

    def flaky(path: Path, payload: object) -> object:
        calls["n"] += 1
        # First call = authoritative; second = index.
        if calls["n"] == 1:
            return real_atomic(path, payload)
        raise store.LayerAPathError("injected index failure")

    monkeypatch.setattr(store, "atomic_write_json", flaky)
    with pytest.raises(CheckpointStoreError) as ei:
        write_checkpoint(tmp_path, rec, status="completed", started_at="2026-08-20T07:00:00Z")
    assert ei.value.code == "EVAL_CHECKPOINT_IO"

    loaded = load_checkpoint(tmp_path, "ckpt-idx-fail")
    assert loaded["status"] == "completed"
    assert loaded["started_at"] == "2026-08-20T07:00:00Z"
    assert not index_file(tmp_path, "ckpt-idx-fail").exists()

    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "completed"
    assert rows[0].started_at == "2026-08-20T07:00:00Z"

    # Later successful write repairs the index.
    monkeypatch.setattr(store, "atomic_write_json", real_atomic)
    write_checkpoint(tmp_path, loaded, status=None, started_at=None)
    assert index_file(tmp_path, "ckpt-idx-fail").is_file()
    idx = json.loads(index_file(tmp_path, "ckpt-idx-fail").read_text(encoding="utf-8"))
    assert idx["status"] == "completed"


def test_corrupt_authoritative_falls_back_to_index(tmp_path: Path) -> None:
    rec = _record("ckpt-corrupt-fb", status="failed", started_at="2026-08-20T06:00:00Z")
    write_checkpoint(tmp_path, rec, status="failed", started_at="2026-08-20T06:00:00Z")
    auth = tmp_path / ".eval" / "checkpoints" / "ckpt-corrupt-fb.json"
    auth.write_text("{not-json", encoding="utf-8")
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].started_at == "2026-08-20T06:00:00Z"


def test_corrupt_authoritative_without_index_excluded(tmp_path: Path) -> None:
    cid = "ckpt-corrupt-x"
    path = tmp_path / ".eval" / "checkpoints" / f"{cid}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    assert list_index_rows(tmp_path) == []
    assert list_checkpoint_inventory(tmp_path) == []
    # Excluded rows are never pruned (file remains).
    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    assert pruned == []
    assert path.is_file()


def test_invalid_index_status_does_not_override_authoritative(tmp_path: Path) -> None:
    rec = _record("ckpt-bad-idx-status", status="completed", started_at="2026-08-20T05:00:00Z")
    write_checkpoint(tmp_path, rec, status="completed", started_at="2026-08-20T05:00:00Z")
    idx = index_file(tmp_path, "ckpt-bad-idx-status")
    raw = json.loads(idx.read_text(encoding="utf-8"))
    raw["status"] = "bogus"
    idx.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert rows[0].status == "completed"


def test_inventory_status_matches_list_index_rows(tmp_path: Path) -> None:
    write_checkpoint(
        tmp_path,
        _record("ckpt-inv-1", status="completed", started_at="2026-08-20T04:00:00Z"),
        status="completed",
        started_at="2026-08-20T04:00:00Z",
    )
    write_checkpoint(
        tmp_path,
        _record("ckpt-inv-2", suite="suite-b", status="failed", started_at="2026-08-20T03:00:00Z"),
        status="failed",
        started_at="2026-08-20T03:00:00Z",
    )
    index_file(tmp_path, "ckpt-inv-1").unlink()
    list_rows = {r.checkpoint_id: r for r in list_index_rows(tmp_path)}
    inv_rows = {r.checkpoint_id: r for r in list_checkpoint_inventory(tmp_path)}
    assert set(list_rows) == set(inv_rows)
    for cid, row in list_rows.items():
        assert inv_rows[cid].status == row.status
        assert inv_rows[cid].suite_id == row.suite_id
    # Suite filter agreement.
    assert {r.checkpoint_id for r in list_index_rows(tmp_path, suite_id="suite-a")} == {"ckpt-inv-1"}
    assert {r.checkpoint_id for r in list_checkpoint_inventory(tmp_path, suite_id="suite-a")} == {"ckpt-inv-1"}


def test_status_none_preserves_loaded_completed(tmp_path: Path) -> None:
    rec = _record("ckpt-preserve", status="completed", started_at="2026-08-20T02:00:00Z")
    write_checkpoint(tmp_path, rec, status="completed", started_at="2026-08-20T02:00:00Z")
    loaded = load_checkpoint(tmp_path, "ckpt-preserve")
    write_checkpoint(tmp_path, loaded, status=None, started_at=None)
    again = load_checkpoint(tmp_path, "ckpt-preserve")
    assert again["status"] == "completed"
    assert again["started_at"] == "2026-08-20T02:00:00Z"


def test_read_does_not_rewrite_index_or_legacy_files(tmp_path: Path) -> None:
    cid = "ckpt-readonly"
    auth = tmp_path / ".eval" / "checkpoints" / f"{cid}.json"
    auth.parent.mkdir(parents=True)
    payload = _legacy_payload(cid, last_progress_at="2026-08-20T01:00:00Z")
    auth.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before_auth = auth.read_bytes()
    # No index present.
    list_index_rows(tmp_path)
    list_checkpoint_inventory(tmp_path)
    assert auth.read_bytes() == before_auth
    assert not index_file(tmp_path, cid).exists()


def test_builder_and_disk_record_are_equal(tmp_path: Path) -> None:
    built = _record("ckpt-eq", status="failed", started_at="2026-08-20T00:30:00Z")
    path = write_checkpoint(tmp_path, built, status="failed", started_at="2026-08-20T00:30:00Z")
    disk = json.loads(path.read_text(encoding="utf-8"))
    # Builder output already includes durable fields; disk must match on those keys.
    assert disk["status"] == built["status"] == "failed"
    assert disk["started_at"] == built["started_at"] == "2026-08-20T00:30:00Z"
    assert disk["checkpoint_id"] == built["checkpoint_id"]
    assert disk["compat_hash"] == built["compat_hash"]


def test_durable_field_precedence(tmp_path: Path) -> None:
    # Explicit kwargs win over existing payload values.
    rec = _record("ckpt-prec", status="running", started_at="2026-08-19T00:00:00Z")
    path = write_checkpoint(
        tmp_path,
        rec,
        status="completed",
        started_at="2026-08-20T00:00:00Z",
    )
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert disk["status"] == "completed"
    assert disk["started_at"] == "2026-08-20T00:00:00Z"

    # Builder explicit wins the same way.
    built = build_checkpoint_record(
        checkpoint_id="ckpt-prec-b",
        experiment_id="exp",
        compat_hash=_hash(),
        completed_case_ids=[],
        pending_case_ids=["c1"],
        mode="fresh_suite_run",
        status="failed",
        started_at="2026-08-21T00:00:00Z",
        last_progress_at="2026-08-18T00:00:00Z",
    )
    assert built["status"] == "failed"
    assert built["started_at"] == "2026-08-21T00:00:00Z"


def test_status_enum_matches_runtime_literal() -> None:
    schema = load_schema("evaluation_checkpoint_v1")
    enum = set(schema["properties"]["status"]["enum"])
    runtime = set(get_args(CheckpointStatus))
    assert enum == runtime == {"running", "failed", "completed"}


def test_unknown_durable_status_is_corruption_not_silent_skip(tmp_path: Path) -> None:
    cid = "ckpt-unknown-status"
    # Write a valid checkpoint + index, then corrupt durable status on disk.
    write_checkpoint(
        tmp_path,
        _record(cid, status="completed", started_at="2026-08-19T12:00:00Z"),
        status="completed",
        started_at="2026-08-19T12:00:00Z",
    )
    auth = tmp_path / ".eval" / "checkpoints" / f"{cid}.json"
    raw = json.loads(auth.read_text(encoding="utf-8"))
    raw["status"] = "exploded"
    auth.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.warns(UserWarning, match="unknown durable status"):
        rows = list_index_rows(tmp_path, suite_id="suite-a")
    # Index last-known-good keeps the row visible when the payload is corrupt.
    assert len(rows) == 1
    assert rows[0].status == "completed"

    # Without index → excluded, never pruned.
    index_file(tmp_path, cid).unlink()
    with pytest.warns(UserWarning, match="unknown durable status"):
        assert list_index_rows(tmp_path, suite_id="suite-a") == []
    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    assert pruned == []
    assert auth.is_file()


def test_missing_checkpoint(tmp_path: Path) -> None:
    with pytest.raises(CheckpointStoreError) as ei:
        load_checkpoint(tmp_path, "nope")
    assert ei.value.code == "EVAL_CHECKPOINT_MISSING"


def test_prune_keep_last_and_failed_protection(tmp_path: Path) -> None:
    # Create 12 completed checkpoints with increasing started_at.
    for i in range(12):
        cid = f"ckpt-c{i:02d}"
        rec = _record(cid, status="completed", started_at=f"2026-08-20T12:{i:02d}:00Z")
        write_checkpoint(
            tmp_path,
            rec,
            started_at=f"2026-08-20T12:{i:02d}:00Z",
            status="completed",
        )
    # One failed older than window — after completed exists, it is eligible.
    fail = _record("ckpt-fail", status="failed", started_at="2026-08-20T11:00:00Z")
    write_checkpoint(tmp_path, fail, started_at="2026-08-20T11:00:00Z", status="failed")
    # One running must be retained.
    run = _record("ckpt-run", status="running", started_at="2026-08-20T10:00:00Z")
    write_checkpoint(tmp_path, run, started_at="2026-08-20T10:00:00Z", status="running")

    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=10)
    ids = set(list_checkpoint_ids(tmp_path))
    assert "ckpt-run" in ids
    # keep newest 10 completed/failed candidates; older completed + failed may prune
    assert len(ids) >= 11  # 10 candidates + running at minimum
    assert "ckpt-c00" not in ids or "ckpt-fail" not in ids
    assert isinstance(pruned, list)


def test_failed_retained_until_completed(tmp_path: Path) -> None:
    fail = _record("ckpt-fail-only", status="failed", started_at="2026-08-20T11:00:00Z")
    write_checkpoint(tmp_path, fail, started_at="2026-08-20T11:00:00Z", status="failed")
    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    assert pruned == []
    assert "ckpt-fail-only" in list_checkpoint_ids(tmp_path)

    done = _record("ckpt-done", status="completed", started_at="2026-08-20T12:00:00Z")
    write_checkpoint(tmp_path, done, started_at="2026-08-20T12:00:00Z", status="completed")
    pruned2 = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    # keep_last=0 with a completed present may prune both failed and completed
    assert "ckpt-fail-only" not in list_checkpoint_ids(tmp_path) or "ckpt-fail-only" in pruned2


def test_delete_removes_index(tmp_path: Path) -> None:
    rec = _record("ckpt-del", status="completed", started_at="2026-08-20T12:00:00Z")
    write_checkpoint(tmp_path, rec, status="completed", started_at="2026-08-20T12:00:00Z")
    delete_checkpoint(tmp_path, "ckpt-del")
    assert list_checkpoint_ids(tmp_path) == []
    assert list_index_rows(tmp_path) == []


def test_stale_running_disabled_by_default(tmp_path: Path) -> None:
    """Unset bound retains an aged running row."""
    old = "2026-08-01T00:00:00Z"
    run = _record("ckpt-old-run", status="running", started_at=old, last_progress_at=old)
    write_checkpoint(tmp_path, run, status="running", started_at=old)
    done = _record("ckpt-done", status="completed", started_at="2026-08-20T12:00:00Z")
    write_checkpoint(tmp_path, done, status="completed", started_at="2026-08-20T12:00:00Z")

    baseline = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=10)
    ids = set(list_checkpoint_ids(tmp_path))
    assert "ckpt-old-run" in ids
    assert "ckpt-old-run" not in baseline

    again = prune_checkpoints(
        tmp_path,
        suite_id="suite-a",
        keep_last=10,
        stale_running_after_seconds=None,
        now=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
    )
    assert again == baseline
    assert "ckpt-old-run" in list_checkpoint_ids(tmp_path)


def test_stale_running_reclaimed_when_bound_exceeded(tmp_path: Path) -> None:
    """Aged running row past the bound is pruned when reclaim is enabled."""
    old = "2026-08-01T00:00:00Z"
    run = _record("ckpt-stale", status="running", started_at=old, last_progress_at=old)
    write_checkpoint(tmp_path, run, status="running", started_at=old)
    done = _record("ckpt-done", status="completed", started_at="2026-08-20T12:00:00Z")
    write_checkpoint(tmp_path, done, status="completed", started_at="2026-08-20T12:00:00Z")

    pruned = prune_checkpoints(
        tmp_path,
        suite_id="suite-a",
        keep_last=10,
        stale_running_after_seconds=3600,
        now=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
    )
    assert "ckpt-stale" in pruned
    assert "ckpt-stale" not in list_checkpoint_ids(tmp_path)
    assert "ckpt-done" in list_checkpoint_ids(tmp_path)


def test_stale_running_respects_protect_ids(tmp_path: Path) -> None:
    """protect_ids retains aged running rows past the reclaim bound."""
    old = "2026-08-01T00:00:00Z"
    run = _record("ckpt-protected", status="running", started_at=old)
    write_checkpoint(tmp_path, run, status="running", started_at=old)
    pruned = prune_checkpoints(
        tmp_path,
        suite_id="suite-a",
        keep_last=0,
        protect_ids=["ckpt-protected"],
        stale_running_after_seconds=60,
        now=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
    )
    assert pruned == []
    assert "ckpt-protected" in list_checkpoint_ids(tmp_path)


def test_stale_running_ignores_fresh_running(tmp_path: Path) -> None:
    """Running rows younger than the bound stay retained."""
    fresh = "2026-08-20T11:59:00Z"
    run = _record("ckpt-fresh", status="running", started_at=fresh)
    write_checkpoint(tmp_path, run, status="running", started_at=fresh)
    pruned = prune_checkpoints(
        tmp_path,
        suite_id="suite-a",
        keep_last=0,
        stale_running_after_seconds=3600,
        now=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
    )
    assert pruned == []
    assert "ckpt-fresh" in list_checkpoint_ids(tmp_path)


def test_stale_running_never_prunes_excluded_rows(tmp_path: Path) -> None:
    """Corrupt authoritative with no index is never reclaimed."""
    cid = "ckpt-corrupt-old"
    auth = tmp_path / ".eval" / "checkpoints" / f"{cid}.json"
    auth.parent.mkdir(parents=True, exist_ok=True)
    auth.write_text("{not-json", encoding="utf-8")
    pruned = prune_checkpoints(
        tmp_path,
        suite_id="suite-a",
        keep_last=0,
        stale_running_after_seconds=1,
        now=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
    )
    assert pruned == []
    assert auth.is_file()


def test_stale_running_never_reclaims_index_only_fallback(tmp_path: Path) -> None:
    """Index last-known-good running rows require a readable authoritative payload."""
    cid = "ckpt-index-only"
    old = "2026-08-01T00:00:00Z"
    run = _record(cid, status="running", started_at=old)
    write_checkpoint(tmp_path, run, status="running", started_at=old)
    auth = tmp_path / ".eval" / "checkpoints" / f"{cid}.json"
    auth.write_text("{broken", encoding="utf-8")
    assert index_file(tmp_path, cid).is_file()

    pruned = prune_checkpoints(
        tmp_path,
        suite_id="suite-a",
        keep_last=0,
        stale_running_after_seconds=1,
        now=datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC),
    )
    assert pruned == []
    assert auth.is_file()
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert any(r.checkpoint_id == cid and r.status == "running" for r in rows)


def test_invalid_reclaim_bound_rejected(tmp_path: Path) -> None:
    """Zero/negative reclaim bounds fail closed with EVAL_USAGE."""
    for bad in (0, -1, -100):
        with pytest.raises(CheckpointStoreError) as ei:
            prune_checkpoints(
                tmp_path,
                suite_id="suite-a",
                keep_last=10,
                stale_running_after_seconds=bad,
            )
        assert ei.value.code == "EVAL_USAGE"
