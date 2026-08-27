"""evaluation_checkpoint_v1 store + GC (Issue #246 Slice 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from git_cg.eval.checkpoint_store import (
    CheckpointStoreError,
    build_checkpoint_record,
    delete_checkpoint,
    list_checkpoint_ids,
    list_index_rows,
    load_checkpoint,
    prune_checkpoints,
    write_checkpoint,
)


def _hash(n: int = 1) -> str:
    return (format(n, "x") * 64)[:64]


def _record(cid: str, *, suite: str = "suite-a", mode: str = "fresh_suite_run", completed=None, pending=None):
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
    )


def test_write_load_roundtrip(tmp_path: Path) -> None:
    rec = _record("ckpt-1")
    path = write_checkpoint(tmp_path, rec, started_at="2026-08-20T12:00:00Z", status="running")
    assert path.is_file()
    loaded = load_checkpoint(tmp_path, "ckpt-1")
    assert loaded["checkpoint_id"] == "ckpt-1"
    assert loaded["compat_hash"] == rec["compat_hash"]
    rows = list_index_rows(tmp_path, suite_id="suite-a")
    assert len(rows) == 1
    assert rows[0].status == "running"


def test_missing_checkpoint(tmp_path: Path) -> None:
    with pytest.raises(CheckpointStoreError) as ei:
        load_checkpoint(tmp_path, "nope")
    assert ei.value.code == "EVAL_CHECKPOINT_MISSING"


def test_prune_keep_last_and_failed_protection(tmp_path: Path) -> None:
    # Create 12 completed checkpoints with increasing started_at.
    for i in range(12):
        cid = f"ckpt-c{i:02d}"
        rec = _record(cid)
        write_checkpoint(
            tmp_path,
            rec,
            started_at=f"2026-08-20T12:{i:02d}:00Z",
            status="completed",
        )
    # One failed older than window — after completed exists, it is eligible.
    fail = _record("ckpt-fail")
    write_checkpoint(tmp_path, fail, started_at="2026-08-20T11:00:00Z", status="failed")
    # One running must be retained.
    run = _record("ckpt-run")
    write_checkpoint(tmp_path, run, started_at="2026-08-20T10:00:00Z", status="running")

    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=10)
    ids = set(list_checkpoint_ids(tmp_path))
    assert "ckpt-run" in ids
    # keep newest 10 completed/failed candidates; older completed + failed may prune
    assert len(ids) >= 11  # 10 candidates + running at minimum
    assert "ckpt-c00" not in ids or "ckpt-fail" not in ids
    assert isinstance(pruned, list)


def test_failed_retained_until_completed(tmp_path: Path) -> None:
    fail = _record("ckpt-fail-only")
    write_checkpoint(tmp_path, fail, started_at="2026-08-20T11:00:00Z", status="failed")
    pruned = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    assert pruned == []
    assert "ckpt-fail-only" in list_checkpoint_ids(tmp_path)

    done = _record("ckpt-done")
    write_checkpoint(tmp_path, done, started_at="2026-08-20T12:00:00Z", status="completed")
    pruned2 = prune_checkpoints(tmp_path, suite_id="suite-a", keep_last=0)
    # keep_last=0 with a completed present may prune both failed and completed
    assert "ckpt-fail-only" not in list_checkpoint_ids(tmp_path) or "ckpt-fail-only" in pruned2


def test_delete_removes_index(tmp_path: Path) -> None:
    rec = _record("ckpt-del")
    write_checkpoint(tmp_path, rec, status="completed")
    delete_checkpoint(tmp_path, "ckpt-del")
    assert list_checkpoint_ids(tmp_path) == []
    assert list_index_rows(tmp_path) == []
