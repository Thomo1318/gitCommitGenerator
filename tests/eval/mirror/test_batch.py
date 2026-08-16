"""S4a export_batch_v1 builder tests (4MB ceiling, idempotency, pins)."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import (
    DEFAULT_MAX_BATCH_BYTES,
    ExportSizeError,
    batch_idempotency_key,
    build_export_batches,
)
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin


def _items(n: int, size_each: int = 10) -> list[tuple[str, dict]]:
    return [(f"item-{i}", {"pad": "x" * size_each}) for i in range(n)]


def test_single_batch_when_under_ceiling() -> None:
    batches = build_export_batches(_items(3, 100), RedactionProfile.DEFAULT_SCRUB)
    assert len(batches) == 1
    assert batches[0]["schema_version"] == "export_batch_v1"
    assert batches[0]["item_ids"] == ["item-0", "item-1", "item-2"]
    assert batches[0]["max_bytes"] == DEFAULT_MAX_BATCH_BYTES


def test_batch_carries_pin_set() -> None:
    batches = build_export_batches(_items(1), RedactionProfile.DEFAULT_SCRUB)
    assert batches[0]["schema_pack"] == schema_pack_pin()
    assert batches[0]["metric_catalog"] == metric_catalog_pin()


def test_idempotency_key_deterministic_and_order_independent() -> None:
    pins = (schema_pack_pin(), metric_catalog_pin())
    k1 = batch_idempotency_key(["b", "a"], RedactionProfile.DEFAULT_SCRUB, *pins)
    k2 = batch_idempotency_key(["a", "b"], RedactionProfile.DEFAULT_SCRUB, *pins)
    assert k1 == k2  # sorted internally


def test_idempotency_key_changes_with_profile() -> None:
    pins = (schema_pack_pin(), metric_catalog_pin())
    k1 = batch_idempotency_key(["a"], RedactionProfile.DEFAULT_SCRUB, *pins)
    k2 = batch_idempotency_key(["a"], RedactionProfile.PUBLIC_CI, *pins)
    assert k1 != k2


def test_reexport_reuses_batch_identity() -> None:
    b1 = build_export_batches(_items(2, 50), RedactionProfile.DEFAULT_SCRUB)
    b2 = build_export_batches(_items(2, 50), RedactionProfile.DEFAULT_SCRUB)
    assert b1[0]["batch_id"] == b2[0]["batch_id"]
    assert b1[0]["meta"]["idempotency_key"] == b2[0]["meta"]["idempotency_key"]


def test_splits_when_ceiling_exceeded() -> None:
    # 3 items of ~600 bytes each with a 1000-byte ceiling → 3 batches.
    items = [(f"item-{i}", {"pad": "x" * 600}) for i in range(3)]
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=1000)
    assert len(batches) == 3
    for batch in batches:
        assert len(batch["item_ids"]) == 1


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
    batches = build_export_batches(_items(2, 20), RedactionProfile.DEFAULT_SCRUB)
    for batch in batches:
        # validate_instance ran inside the builder; reaching here implies valid.
        assert batch["redaction_profile"] == "default_scrub"
        assert batch["meta"]["item_count"] == len(batch["item_ids"])
