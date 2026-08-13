"""dataset_snapshot_v1 builder + stable content hash."""

from __future__ import annotations

from typing import Any

from git_cg.eval.corpus.canonical import content_sha256
from git_cg.eval.corpus.encoder import CorpusEncodeError, encode_fixture
from git_cg.eval.corpus.fixtures import FixtureLoadError, default_fixture_root, load_suite_fixtures
from git_cg.eval.corpus.suites import SuiteLoadError, load_suite
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import SchemaPackError, validate_instance


class SnapshotBuildError(ValueError):
    """Snapshot build failure."""


def build_snapshot(
    suite_id: str = "cm-eval-fixtures-core",
    *,
    fixture_root=None,
    validate: bool = True,
) -> dict[str, Any]:
    """Build a dataset_snapshot_v1 for a committed suite.

    Snapshot hash covers ordered case_ids + each case's bundle_hash + case_hash +
    S0 pin identities. No timestamps or env paths enter the hash.
    """
    root = fixture_root or default_fixture_root()
    try:
        suite = load_suite(suite_id, fixture_root=root)
    except SuiteLoadError as exc:
        raise SnapshotBuildError(str(exc)) from exc

    try:
        pairs = load_suite_fixtures(suite, fixture_root=root)
    except FixtureLoadError as exc:
        raise SnapshotBuildError(str(exc)) from exc

    items: list[dict[str, Any]] = []
    encoded_cases: list[dict[str, Any]] = []
    encoded_bundles: list[dict[str, Any]] = []
    for case_id, fixture in pairs:
        try:
            encoded = encode_fixture(fixture, case_id=case_id, suite_id=suite["suite_id"], validate=validate)
        except CorpusEncodeError as exc:
            raise SnapshotBuildError(f"{case_id}: {exc}") from exc
        items.append(
            {
                "case_id": case_id,
                "bundle_ref": encoded["bundle_ref"],
                "bundle_hash": encoded["bundle_hash"],
                "case_hash": encoded["case_hash"],
                "artifact_class": encoded["bundle"]["artifact_class"],
            }
        )
        encoded_cases.append(encoded["case"])
        encoded_bundles.append(encoded["bundle"])

    pack = schema_pack_pin()
    catalog = metric_catalog_pin()
    hash_payload = {
        "suite_id": suite["suite_id"],
        "schema_pack": pack,
        "metric_catalog": catalog,
        "items": items,  # already ordered by suite.case_ids
    }
    snapshot_hash = content_sha256(hash_payload)

    snapshot: dict[str, Any] = {
        "schema_version": "dataset_snapshot_v1",
        "id": f"snapshot:{suite['suite_id']}",
        "snapshot_hash": snapshot_hash,
        "item_count": len(items),
        "schema_pack": pack,
        "metric_catalog": catalog,
        "meta": {
            "producer": "fixture_encoder_s1",
            "suite_id": suite["suite_id"],
            "case_ids": [i["case_id"] for i in items],
            "items": items,
            "network_policy": "offline_required",
        },
        "notes": f"Offline Lane A snapshot for {suite['suite_id']}",
    }

    if validate:
        try:
            validate_instance("dataset_snapshot_v1", snapshot)
        except SchemaPackError as exc:
            raise SnapshotBuildError(str(exc)) from exc
        # Also bind snapshot_hash onto suite view for callers that want a pinned suite record
        suite_view = {
            k: v
            for k, v in suite.items()
            if k
            in {
                "schema_version",
                "id",
                "suite_id",
                "schema_pack_pin",
                "metric_catalog_pin",
                "schema_pack",
                "metric_catalog",
                "case_ids",
                "notes",
                "meta",
            }
        }
        suite_view["snapshot_hash"] = snapshot_hash
        try:
            validate_instance("eval_suite_v1", suite_view)
        except SchemaPackError as exc:
            raise SnapshotBuildError(f"suite+snapshot pin view invalid: {exc}") from exc

    return {
        "snapshot": snapshot,
        "suite": suite,
        "cases": encoded_cases,
        "bundles": encoded_bundles,
        "snapshot_hash": snapshot_hash,
        "items": items,
    }


def build_core_snapshot(*, fixture_root=None, validate: bool = True) -> dict[str, Any]:
    """Build ``cm-eval-fixtures-core`` and return the snapshot object only."""
    result = build_snapshot("cm-eval-fixtures-core", fixture_root=fixture_root, validate=validate)
    return result["snapshot"]
