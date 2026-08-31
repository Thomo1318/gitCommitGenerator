"""Read-only checkpoint list inventory CLI contracts."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from git_cg.eval.checkpoint_store import (
    build_checkpoint_record,
    list_checkpoint_inventory,
    write_checkpoint,
)
from git_cg.eval.compat import compute_compat_hash
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.main import app

runner = CliRunner()


def _hash(n: int = 1) -> str:
    return (format(n, "x") * 64)[:64]


def test_checkpoint_list_inventory_fields(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    suite = "suite-inv"
    snapshot = "snap-live-1"
    live = compute_compat_hash(
        schema_pack_pin=schema_pack_pin(),
        metric_catalog_pin=metric_catalog_pin(),
        suite_id=suite,
        snapshot_hash=snapshot,
    )
    match_rec = build_checkpoint_record(
        checkpoint_id="ckpt-live",
        experiment_id="exp-live",
        compat_hash=live,
        completed_case_ids=["c1", "c2"],
        pending_case_ids=["c3"],
        mode="fresh_suite_run",
        suite_id=suite,
        snapshot_id=snapshot,
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    stale_rec = build_checkpoint_record(
        checkpoint_id="ckpt-stale",
        experiment_id="exp-stale",
        compat_hash=_hash(9),
        completed_case_ids=["a"],
        pending_case_ids=["b", "c"],
        mode="resume_missing",
        suite_id=suite,
        snapshot_id=snapshot,
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    other = build_checkpoint_record(
        checkpoint_id="ckpt-other",
        experiment_id="exp-other",
        compat_hash=_hash(3),
        completed_case_ids=[],
        pending_case_ids=["z"],
        mode="fresh_suite_run",
        suite_id="other-suite",
        snapshot_id="snap-other",
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    write_checkpoint(tmp_path, match_rec, started_at="2026-08-20T12:00:00Z", status="running")
    write_checkpoint(tmp_path, stale_rec, started_at="2026-08-20T11:00:00Z", status="failed")
    write_checkpoint(tmp_path, other, started_at="2026-08-20T10:00:00Z", status="completed")

    rows = list_checkpoint_inventory(tmp_path, suite_id=suite)
    assert {r.checkpoint_id for r in rows} == {"ckpt-live", "ckpt-stale"}
    by_id = {r.checkpoint_id: r for r in rows}
    assert by_id["ckpt-live"].live_match is True
    assert by_id["ckpt-stale"].live_match is False
    assert by_id["ckpt-live"].completed_count == 2
    assert by_id["ckpt-live"].pending_count == 1
    assert len(by_id["ckpt-live"].compat_hash_short) == 12
    assert by_id["ckpt-live"].pin_short

    result = runner.invoke(app, ["eval", "checkpoint", "list", "--root", str(tmp_path), "--suite", suite])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "2 checkpoint(s)" in out
    assert "ckpt-live:" in out
    assert "live_match=true" in out
    assert "live_match=false" in out
    assert "completed=2" in out
    assert "pending=1" in out
    assert "ckpt-other" not in out

    result_json = runner.invoke(
        app, ["eval", "checkpoint", "list", "--root", str(tmp_path), "--suite", suite, "--json"]
    )
    assert result_json.exit_code == 0, result_json.output
    env = json.loads(result_json.output)
    assert env["ok"] is True
    assert env["command"] == "eval checkpoint list"
    data = env["data"]
    assert data["checkpoint_count"] == 2
    assert data["suite_id"] == suite
    ids = {row["checkpoint_id"] for row in data["checkpoints"]}
    assert ids == {"ckpt-live", "ckpt-stale"}
    live_row = next(r for r in data["checkpoints"] if r["checkpoint_id"] == "ckpt-live")
    for key in (
        "mtime",
        "suite_id",
        "compat_hash_short",
        "pin_short",
        "live_match",
        "completed_count",
        "pending_count",
    ):
        assert key in live_row
    assert live_row["live_match"] is True

    ckpt_dir = tmp_path / ".eval" / "checkpoints"
    assert (ckpt_dir / "ckpt-live.json").is_file()
    assert (ckpt_dir / "ckpt-stale.json").is_file()
    assert (ckpt_dir / "ckpt-other.json").is_file()


def test_checkpoint_list_empty_repo(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["eval", "checkpoint", "list", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "0 checkpoint(s)" in result.output


def test_checkpoint_list_skips_corrupt(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    ckpt_dir = tmp_path / ".eval" / "checkpoints"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / "bad.json").write_text("{not-json", encoding="utf-8")
    good = build_checkpoint_record(
        checkpoint_id="ckpt-good",
        experiment_id="exp-good",
        compat_hash=_hash(1),
        completed_case_ids=[],
        pending_case_ids=["c1"],
        mode="fresh_suite_run",
        suite_id="suite-a",
        snapshot_id="snap-a",
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    write_checkpoint(tmp_path, good, started_at="2026-08-20T12:00:00Z", status="running")
    result = runner.invoke(app, ["eval", "checkpoint", "list", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    env = json.loads(result.output)
    assert env["data"]["checkpoint_count"] == 1
    assert env["data"]["checkpoints"][0]["checkpoint_id"] == "ckpt-good"


def test_inventory_skips_invalid_checkpoint_filenames(tmp_path: Path) -> None:
    """Corrupt/path-unsafe checkpoint filenames must be skipped, not abort inventory."""
    from git_cg.eval.checkpoint_store import checkpoints_dir

    (tmp_path / ".git").mkdir()
    suite = "suite-bad"
    snapshot = "snap-bad"
    live = compute_compat_hash(
        schema_pack_pin=schema_pack_pin(),
        metric_catalog_pin=metric_catalog_pin(),
        suite_id=suite,
        snapshot_hash=snapshot,
    )
    good = build_checkpoint_record(
        checkpoint_id="ckpt-good",
        experiment_id="exp-good",
        compat_hash=live,
        completed_case_ids=["c1"],
        pending_case_ids=[],
        mode="fresh_suite_run",
        suite_id=suite,
        snapshot_id=snapshot,
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    write_checkpoint(tmp_path, good)
    # Path.glob("*.json") can surface stems that fail _require_safe_id.
    bad = checkpoints_dir(tmp_path) / "bad name.json"
    bad.write_text("{}", encoding="utf-8")
    rows = list_checkpoint_inventory(tmp_path)
    assert [r.checkpoint_id for r in rows] == ["ckpt-good"]
