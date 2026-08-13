"""Checked-in golden bundles + fixture index generator — offline only."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from git_cg.eval.corpus.fixtures import default_fixture_root
from git_cg.eval.corpus.index import build_fixture_index, write_fixture_index
from git_cg.eval.corpus.materialize import (
    materialize_core_goldens,
    materialize_suite_bundles,
)
from git_cg.eval.corpus.snapshots import build_snapshot
from git_cg.eval.schema_pack import validate_instance


def _sandbox_fixture_root(tmp_path: Path) -> Path:
    """Copy committed fixtures into a temp tree so materialize never mutates tracked goldens."""
    src = default_fixture_root()
    dst = tmp_path / "fixtures"
    # Copy suite/case sources only; omit checked-in generated goldens/index.
    (dst / "suites").mkdir(parents=True)
    (dst / "cases").mkdir(parents=True)
    shutil.copytree(src / "suites", dst / "suites", dirs_exist_ok=True)
    shutil.copytree(src / "cases", dst / "cases", dirs_exist_ok=True)
    return dst


def test_materialize_core_and_archive_goldens(tmp_path: Path) -> None:
    root = _sandbox_fixture_root(tmp_path)
    result = materialize_core_goldens(fixture_root=root)
    assert result["core_snapshot"].is_file()
    assert result["archive_snapshot"] is not None and result["archive_snapshot"].is_file()
    assert len(result["core_bundles"]) >= 6  # 3 bundles + 3 identity sidecars
    assert len(result["archive_bundles"]) >= 12

    core_snap = json.loads(result["core_snapshot"].read_text(encoding="utf-8"))
    validate_instance("dataset_snapshot_v1", core_snap)
    live = build_snapshot("cm-eval-fixtures-core", fixture_root=root)
    assert core_snap["snapshot_hash"] == live["snapshot_hash"]

    # live tracked goldens still match live encode from committed fixtures
    live_committed = build_snapshot("cm-eval-fixtures-core")
    assert core_snap["snapshot_hash"] == live_committed["snapshot_hash"]

    archive_snap = json.loads(result["archive_snapshot"].read_text(encoding="utf-8"))
    validate_instance("dataset_snapshot_v1", archive_snap)
    live_a = build_snapshot("204-archive", fixture_root=root)
    assert archive_snap["snapshot_hash"] == live_a["snapshot_hash"]

    bundle_path = root / "bundles/cm-eval-fixtures-core/seed-v1-valid-fixture.ape_bundle_v1.json"
    assert bundle_path.is_file()
    validate_instance("ape_bundle_v1", json.loads(bundle_path.read_text(encoding="utf-8")))


def test_fixture_index_lists_suites_and_cases(tmp_path: Path) -> None:
    root = _sandbox_fixture_root(tmp_path)
    md = build_fixture_index(fixture_root=root)
    assert "# Eval fixture index" in md
    assert "`cm-eval-fixtures-core`" in md
    assert "`204-archive`" in md
    assert "seed-a1-session12-regime-a" in md
    assert "seed-b4-quality-package-dogfood" in md
    assert "seed-n-counter-mismatch" in md
    path = write_fixture_index(fixture_root=root, out_path=tmp_path / "FIXTURE_INDEX.md")
    assert path.is_file()
    assert "SEED-B4" in path.read_text(encoding="utf-8")


def test_materialize_suite_bundles_returns_paths(tmp_path: Path) -> None:
    root = _sandbox_fixture_root(tmp_path)
    paths = materialize_suite_bundles(
        "cm-eval-fixtures-core",
        fixture_root=root,
        bundles_dir=tmp_path / "out-bundles",
    )
    assert paths
    assert all(path.is_file() for path in paths)
    assert all(path.is_relative_to(tmp_path) for path in paths)
