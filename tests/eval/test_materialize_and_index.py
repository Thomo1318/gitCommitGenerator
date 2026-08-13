"""Checked-in golden bundles + fixture index generator — offline only."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.index import build_fixture_index, write_fixture_index
from git_cg.eval.corpus.materialize import materialize_core_goldens, materialize_suite_bundles
from git_cg.eval.corpus.snapshots import build_snapshot
from git_cg.eval.schema_pack import validate_instance


def test_materialize_core_and_archive_goldens(tmp_path, monkeypatch) -> None:
    # write into a temp tree copy of fixture root would be heavy; write into repo
    # bundles dir which is the intended goldens location, then verify reload.
    result = materialize_core_goldens()
    assert result["core_snapshot"].is_file()
    assert result["archive_snapshot"] is not None and result["archive_snapshot"].is_file()
    assert len(result["core_bundles"]) >= 6  # 3 bundles + 3 identity sidecars
    assert len(result["archive_bundles"]) >= 12

    core_snap = json.loads(result["core_snapshot"].read_text(encoding="utf-8"))
    validate_instance("dataset_snapshot_v1", core_snap)
    live = build_snapshot("cm-eval-fixtures-core")
    assert core_snap["snapshot_hash"] == live["snapshot_hash"]

    archive_snap = json.loads(result["archive_snapshot"].read_text(encoding="utf-8"))
    validate_instance("dataset_snapshot_v1", archive_snap)
    live_a = build_snapshot("204-archive")
    assert archive_snap["snapshot_hash"] == live_a["snapshot_hash"]

    # spot-check one core bundle validates
    bundle_path = Path("tests/fixtures/eval/bundles/cm-eval-fixtures-core/seed-v1-valid-fixture.ape_bundle_v1.json")
    assert bundle_path.is_file()
    validate_instance("ape_bundle_v1", json.loads(bundle_path.read_text(encoding="utf-8")))


def test_fixture_index_lists_suites_and_cases() -> None:
    md = build_fixture_index()
    assert "# Eval fixture index" in md
    assert "`cm-eval-fixtures-core`" in md
    assert "`204-archive`" in md
    assert "seed-a1-session12-regime-a" in md
    assert "seed-b4-quality-package-dogfood" in md
    assert "seed-n-counter-mismatch" in md
    path = write_fixture_index()
    assert path.is_file()
    assert "SEED-B4" in path.read_text(encoding="utf-8")


def test_materialize_suite_bundles_returns_paths() -> None:
    paths = materialize_suite_bundles("cm-eval-fixtures-core")
    assert all(p.is_file() for p in paths)
