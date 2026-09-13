"""S4 Slice 3 — export_batch_v1 envelope (P0-2 / P1-2 / P1-13 / E7 / E10)."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import (
    DEFAULT_MAX_BATCH_BYTES,
    EXPORT_STATUSES,
    MAX_SIZE_CONVERGENCE_PASSES,
    ExportSizeError,
    ExportStatus,
    batch_idempotency_key,
    build_export_batches,
    envelope_size_bytes,
    map_queue_status_to_export_status,
)
from git_cg.eval.mirror.queue import QUEUE_STATUSES
from git_cg.eval.mirror.redaction import sanitize_export_tree
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


#: Payload whose envelope crosses the 10_000-byte digit-width boundary when
#: ``max_bytes`` stays at the 7-digit default (``4194304``).
_DIGIT_WIDTH_PAD = 8800
_DIGIT_WIDTH_STALE_SIZE = 10_000
_DIGIT_WIDTH_CONVERGED_SIZE = 10_001

#: Same framing, but with a 5-digit serialized ``max_bytes=10000`` the two-pass
#: writer would store 10_000 while the converged envelope is 10_001.
_CEILING_BYPASS_PAD = 8802
_CEILING_BYPASS_MAX_BYTES = 10_000


@pytest.mark.parametrize("pad", [10, 100, _DIGIT_WIDTH_PAD, 20_000, 98_798])
def test_emitted_size_bytes_matches_envelope_across_magnitudes(pad: int) -> None:
    batches = build_export_batches(
        [("item-0", {"pad": "x" * pad})],
        RedactionProfile.DEFAULT_SCRUB,
    )
    assert len(batches) == 1
    batch = batches[0]
    assert batch["size_bytes"] == envelope_size_bytes(batch)
    assert batch["payload_size_bytes"] <= batch["size_bytes"]


def test_digit_width_transition_stores_converged_envelope_size() -> None:
    batches = build_export_batches(
        [("item-0", {"pad": "x" * _DIGIT_WIDTH_PAD})],
        RedactionProfile.DEFAULT_SCRUB,
    )
    batch = batches[0]
    assert batch["size_bytes"] == envelope_size_bytes(batch)
    assert batch["size_bytes"] == _DIGIT_WIDTH_CONVERGED_SIZE
    assert batch["size_bytes"] != _DIGIT_WIDTH_STALE_SIZE


def test_converged_size_cannot_bypass_ceiling() -> None:
    with pytest.raises(ExportSizeError, match="export_size"):
        build_export_batches(
            [("item-0", {"pad": "x" * _CEILING_BYPASS_PAD})],
            RedactionProfile.DEFAULT_SCRUB,
            max_bytes=_CEILING_BYPASS_MAX_BYTES,
        )


def test_exact_ceiling_admits_converged_envelope() -> None:
    items = [("item-0", {"pad": "x" * _CEILING_BYPASS_PAD})]
    generous = 15_000
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=generous)
    assert len(batches) == 1
    ceiling = batches[0]["size_bytes"]
    assert len(str(ceiling)) == len(str(generous))
    exact = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB, max_bytes=ceiling)
    assert len(exact) == 1
    assert exact[0]["size_bytes"] == ceiling
    assert exact[0]["size_bytes"] == envelope_size_bytes(exact[0])
    assert exact[0]["max_bytes"] == ceiling


def test_size_convergence_does_not_change_batch_identity() -> None:
    items = [("item-0", {"pad": "x" * _DIGIT_WIDTH_PAD})]
    first = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    second = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    assert first[0]["batch_id"] == second[0]["batch_id"]
    assert first[0]["idempotency_key"] == second[0]["idempotency_key"]


def test_final_sanitize_does_not_change_envelope_size() -> None:
    batches = build_export_batches(
        [("item-0", {"pad": "x" * _DIGIT_WIDTH_PAD})],
        RedactionProfile.DEFAULT_SCRUB,
    )
    batch = batches[0]
    before = envelope_size_bytes(batch)
    cleaned = sanitize_export_tree(batch)
    assert isinstance(cleaned, dict)
    assert envelope_size_bytes(cleaned) == before
    assert cleaned["size_bytes"] == envelope_size_bytes(cleaned)


def test_size_bytes_raises_when_measurement_does_not_converge(monkeypatch: pytest.MonkeyPatch) -> None:
    sizes = iter(range(100, 100 + MAX_SIZE_CONVERGENCE_PASSES + 1))
    monkeypatch.setattr(
        "git_cg.eval.mirror.batch.envelope_size_bytes",
        lambda _batch: next(sizes),
    )
    with pytest.raises(ExportSizeError, match="export_size") as exc_info:
        build_export_batches(_items(1, 10), RedactionProfile.DEFAULT_SCRUB)
    cause = exc_info.value.__cause__
    assert isinstance(cause, ExportSizeError)
    assert "converge" in str(cause)
