"""S4 Slice 3 — export_batch_v1 envelope (P0-2 / P1-2 / P1-13 / E7 / E10)."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import (
    DEFAULT_MAX_BATCH_BYTES,
    ENVELOPE_HEADROOM_BYTES,
    EXPORT_STATUSES,
    ExportSizeError,
    ExportStatus,
    batch_idempotency_key,
    build_export_batches,
    envelope_size_bytes,
    estimate_batch_bytes,
    map_queue_status_to_export_status,
)
from git_cg.eval.mirror.queue import QUEUE_STATUSES
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin


def _items(n: int, size_each: int = 10) -> list[tuple[str, dict]]:
    """Build ``n`` (item_ref, payload) pairs with padded bodies for size tests."""
    return [(f"item-{i}", {"pad": "x" * size_each}) for i in range(n)]


def _id_kwargs(**overrides: object) -> dict:
    """Default kwargs for batch idempotency-key tests (overridable)."""
    base = {
        "bundle_hashes": ["a", "b"],
        "project_lane": "eval",
        "environment": "eval",
        "dataset_id": "ds-1",
        "redaction_profile": RedactionProfile.DEFAULT_SCRUB,
        "schema_pin": schema_pack_pin(),
        "catalog_pin": metric_catalog_pin(),
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


def test_single_batch_when_under_ceiling() -> None:
    batches = build_export_batches(_items(3, 100), RedactionProfile.DEFAULT_SCRUB)
    assert len(batches) == 1
    b = batches[0]
    assert b["schema_version"] == "export_batch_v1"
    assert b["item_refs"] == ["item-0", "item-1", "item-2"]
    assert b["project"]
    assert b["experiment_id"]
    assert b["status"] == ExportStatus.PENDING.value
    assert b["size_bytes"] == envelope_size_bytes(b)
    assert b["max_bytes"] == DEFAULT_MAX_BATCH_BYTES
    assert "idempotency_key" in b
    assert b["payload_ref"].startswith("sha256:")


def test_batch_carries_pin_set() -> None:
    batches = build_export_batches(_items(1), RedactionProfile.DEFAULT_SCRUB)
    assert batches[0]["schema_pack"] == schema_pack_pin()
    assert batches[0]["metric_catalog"] == metric_catalog_pin()


def test_idempotency_key_deterministic_and_order_independent() -> None:
    k1 = batch_idempotency_key(**_id_kwargs(bundle_hashes=["b", "a"]))
    k2 = batch_idempotency_key(**_id_kwargs(bundle_hashes=["a", "b"]))
    assert k1 == k2


def test_idempotency_key_changes_with_profile() -> None:
    k1 = batch_idempotency_key(**_id_kwargs(redaction_profile=RedactionProfile.DEFAULT_SCRUB))
    k2 = batch_idempotency_key(**_id_kwargs(redaction_profile=RedactionProfile.PUBLIC_CI))
    assert k1 != k2


def test_idempotency_key_changes_with_lane_env_dataset_payload() -> None:
    base = batch_idempotency_key(**_id_kwargs())
    assert base != batch_idempotency_key(**_id_kwargs(project_lane="ci"))
    assert base != batch_idempotency_key(**_id_kwargs(environment="ci"))
    assert base != batch_idempotency_key(**_id_kwargs(dataset_id="ds-2"))
    assert base != batch_idempotency_key(**_id_kwargs(payload_sha256="a" * 64))
    assert base != batch_idempotency_key(**_id_kwargs(experiment_id="exp-other"))


def test_reexport_reuses_batch_identity() -> None:
    b1 = build_export_batches(_items(2, 50), RedactionProfile.DEFAULT_SCRUB)
    b2 = build_export_batches(_items(2, 50), RedactionProfile.DEFAULT_SCRUB)
    assert b1[0]["batch_id"] == b2[0]["batch_id"]
    assert b1[0]["idempotency_key"] == b2[0]["idempotency_key"]


def test_same_refs_different_payload_bytes_change_key() -> None:
    b1 = build_export_batches([("item-0", {"pad": "a" * 20})], RedactionProfile.DEFAULT_SCRUB)
    b2 = build_export_batches([("item-0", {"pad": "b" * 20})], RedactionProfile.DEFAULT_SCRUB)
    assert b1[0]["idempotency_key"] != b2[0]["idempotency_key"]


def test_splits_when_ceiling_exceeded() -> None:
    # One ~600-byte payload needs ~1800 envelope bytes after framing; choose a
    # ceiling that admits a singleton but forces multi-item batches to split.
    items = [(f"item-{i}", {"pad": "x" * 600}) for i in range(3)]
    ceiling = 1800
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=ceiling)
    assert len(batches) >= 2
    for batch in batches:
        assert batch["size_bytes"] <= ceiling
        assert len(batch["item_refs"]) >= 1


def test_single_oversize_item_raises_export_size() -> None:
    items = [("big", {"pad": "x" * (DEFAULT_MAX_BATCH_BYTES + 1)})]
    with pytest.raises(ExportSizeError, match="export_size"):
        build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)


def test_max_bytes_must_be_positive() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        build_export_batches(_items(1), RedactionProfile.DEFAULT_SCRUB, max_bytes=0)


def test_empty_items_yield_no_batches() -> None:
    assert build_export_batches([], RedactionProfile.DEFAULT_SCRUB) == []


def test_each_batch_validates_against_schema() -> None:
    batches = build_export_batches(_items(2, 20), RedactionProfile.DEFAULT_SCRUB, project="git-cg-eval")
    for batch in batches:
        assert batch["redaction_profile"] == "default_scrub"
        assert batch["meta"]["item_count"] == len(batch["item_refs"])
        assert batch["status"] in EXPORT_STATUSES
        assert "transport_body" in batch["meta"]


def test_export_status_distinct_from_queue_status() -> None:
    assert set(EXPORT_STATUSES).isdisjoint({"sending", "sent", "dropped"})
    assert map_queue_status_to_export_status("sent") == ExportStatus.OK
    assert map_queue_status_to_export_status("failed") == ExportStatus.FAILED
    assert map_queue_status_to_export_status("dropped") == ExportStatus.SKIPPED
    assert map_queue_status_to_export_status("sending") == ExportStatus.PENDING
    assert "sent" in QUEUE_STATUSES and "sent" not in EXPORT_STATUSES
    assert "ok" in EXPORT_STATUSES and "ok" not in QUEUE_STATUSES


def test_final_envelope_size_is_measured() -> None:
    batches = build_export_batches(_items(2, 40), RedactionProfile.DEFAULT_SCRUB)
    b = batches[0]
    assert b["size_bytes"] == envelope_size_bytes(b)
    assert b["size_bytes"] > b["payload_size_bytes"]


def _batch_identity(batches: list[dict]) -> list[tuple]:
    """Stable identity view for packing equivalence assertions."""
    out = []
    for batch in batches:
        out.append(
            (
                tuple(batch["item_refs"]),
                batch["idempotency_key"],
                batch["batch_id"],
                batch["size_bytes"],
                batch["payload_sha256"],
            )
        )
    return out


def test_packing_equivalence_vs_exact_algorithm() -> None:
    """Cached-estimate packer stays deterministic and ceiling-honest for mixed sizes."""
    items = [(f"item-{i}", {"pad": "x" * size}) for i, size in enumerate([20, 40, 80, 160, 320, 640, 50, 75])]
    ceiling = 2500  # small ceiling forces frequent exact boundary decisions
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=ceiling)
    assert batches
    again = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=ceiling)
    assert _batch_identity(batches) == _batch_identity(again)
    for batch in batches:
        assert batch["size_bytes"] <= ceiling
        assert batch["size_bytes"] == envelope_size_bytes(batch)


def test_oversize_singleton_still_fails() -> None:
    items = [("big", {"pad": "x" * (DEFAULT_MAX_BATCH_BYTES + 1)})]
    with pytest.raises(ExportSizeError, match="export_size"):
        build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)


def test_idempotency_key_unchanged_for_identical_inputs() -> None:
    items = _items(3, 100)
    b1 = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    b2 = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    assert [b["idempotency_key"] for b in b1] == [b["idempotency_key"] for b in b2]


def test_envelope_headroom_wired() -> None:
    assert ENVELOPE_HEADROOM_BYTES > 0
    estimate = estimate_batch_bytes([1000, 1000, 1000])
    assert estimate > 3000
    items = _items(20, 50)
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=DEFAULT_MAX_BATCH_BYTES)
    assert len(batches) == 1
    assert batches[0]["size_bytes"] < DEFAULT_MAX_BATCH_BYTES - ENVELOPE_HEADROOM_BYTES


def test_cached_sizes_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Payload canonicalization for size cache happens once per item in pre-validation."""
    from git_cg.eval.mirror import batch as batch_mod

    real = batch_mod.canonical_json_bytes
    calls: list[object] = []

    def wrapped(obj: object) -> bytes:
        calls.append(obj)
        return real(obj)

    monkeypatch.setattr(batch_mod, "canonical_json_bytes", wrapped)
    items = _items(5, 30)
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    assert batches
    payload_calls = [c for c in calls if isinstance(c, dict) and set(c.keys()) == {"pad"}]
    assert len(payload_calls) == 5


def test_benchmark_many_small_items() -> None:
    items = _items(200, 64)
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    assert batches
    assert sum(len(b["item_refs"]) for b in batches) == 200


def test_benchmark_near_ceiling_items() -> None:
    items = [(f"item-{i}", {"pad": "y" * 100_000}) for i in range(10)]
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    assert batches
    assert sum(len(b["item_refs"]) for b in batches) == 10
