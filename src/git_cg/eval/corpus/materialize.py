"""Materialize checked-in golden bundles and optional snapshot dumps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_suite_fixtures
from git_cg.eval.corpus.snapshots import build_snapshot
from git_cg.eval.corpus.suites import load_suite


def _write_json(path: Path, obj: Any) -> None:
    """Persist a governed artifact via atomic write (fail closed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Pretty for reviewability; identity still proven via content hashes / re-encode tests.
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def materialize_suite_bundles(
    suite_id: str = "cm-eval-fixtures-core",
    *,
    fixture_root: Path | None = None,
    bundles_dir: Path | None = None,
    validate: bool = True,
) -> list[Path]:
    """Encode suite fixtures and write checked-in ape_bundle_v1 JSON files.

    Returns paths written under ``tests/fixtures/eval/bundles/<suite_id>/``.
    """
    root = fixture_root or default_fixture_root()
    suite = load_suite(suite_id, fixture_root=root)
    out_dir = bundles_dir or (root / "bundles" / suite["suite_id"])
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for case_id, fixture in load_suite_fixtures(suite, fixture_root=root):
        encoded = encode_fixture(fixture, case_id=case_id, suite_id=suite["suite_id"], validate=validate)
        path = out_dir / f"{case_id}.ape_bundle_v1.json"
        _write_json(path, encoded["bundle"])
        # sidecar identity for quick CI assertion without full snapshot rebuild
        sidec = out_dir / f"{case_id}.identity.json"
        _write_json(
            sidec,
            {
                "case_id": case_id,
                "bundle_ref": encoded["bundle_ref"],
                "bundle_hash": encoded["bundle_hash"],
                "case_hash": encoded["case_hash"],
                "schema_pack": encoded["bundle"]["schema_pack"],
                "metric_catalog": encoded["bundle"]["metric_catalog"],
            },
        )
        written.extend([path, sidec])
    return written


def materialize_suite_snapshot(
    suite_id: str = "cm-eval-fixtures-core",
    *,
    fixture_root: Path | None = None,
    snapshots_dir: Path | None = None,
    validate: bool = True,
) -> Path:
    """Build and write a dataset_snapshot_v1 JSON for a suite."""
    root = fixture_root or default_fixture_root()
    result = build_snapshot(suite_id, fixture_root=root, validate=validate)
    out_dir = snapshots_dir or (root / "snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['suite']['suite_id']}.dataset_snapshot_v1.json"
    _write_json(path, result["snapshot"])
    return path


def materialize_core_goldens(*, fixture_root: Path | None = None) -> dict[str, Any]:
    """Materialize core suite bundles + snapshot goldens."""
    root = fixture_root or default_fixture_root()
    bundles = materialize_suite_bundles("cm-eval-fixtures-core", fixture_root=root)
    snapshot = materialize_suite_snapshot("cm-eval-fixtures-core", fixture_root=root)
    # archive ramp is optional only when the suite manifest is absent.
    archive_paths: list[Path] = []
    archive_snap = None
    archive_suite_path = root / "suites" / "204-archive.json"
    if archive_suite_path.is_file():
        archive_paths = materialize_suite_bundles("204-archive", fixture_root=root)
        archive_snap = materialize_suite_snapshot("204-archive", fixture_root=root)
    return {
        "core_bundles": bundles,
        "core_snapshot": snapshot,
        "archive_bundles": archive_paths,
        "archive_snapshot": archive_snap,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for core-golden materialization."""
    import argparse

    parser = argparse.ArgumentParser(description="Materialize checked-in golden bundles/snapshots")
    parser.add_argument("--suite", default="all", help="Suite id or 'all' (core + 204-archive)")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root
    if args.suite == "all":
        result = materialize_core_goldens(fixture_root=root)
        print("core_snapshot", result["core_snapshot"])
        if result["archive_snapshot"]:
            print("archive_snapshot", result["archive_snapshot"])
        print("core_bundles", len(result["core_bundles"]))
        print("archive_bundles", len(result["archive_bundles"]))
    else:
        paths = materialize_suite_bundles(args.suite, fixture_root=root)
        snap = materialize_suite_snapshot(args.suite, fixture_root=root)
        print("bundles", len(paths))
        print("snapshot", snap)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
