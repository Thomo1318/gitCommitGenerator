"""size_bytes fixed-point / digit-width honesty for export envelopes."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.batch import (
    MAX_SIZE_BYTES_CONVERGENCE_ITERS,
    ExportSizeError,
    ExportStatus,
    _build_batch,
    _converge_size_bytes,
    build_export_batches,
    envelope_size_bytes,
)
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin


def test_size_bytes_digit_width_regression() -> None:
    """Envelope remains honest when size_bytes digit width can change."""
    items = [("item-0", {"pad": "x" * 50_000})]
    batches = build_export_batches(items, RedactionProfile.DEFAULT_SCRUB)
    assert len(batches) == 1
    batch = batches[0]
    assert batch["size_bytes"] == envelope_size_bytes(batch)
    batch["size_bytes"] = 9  # force a narrower digit width than the measured size
    size = _converge_size_bytes(batch)
    assert size == envelope_size_bytes(batch)
    assert batch["size_bytes"] == size


def test_size_bytes_fixed_point_convergence() -> None:
    batch = {
        "schema_version": "export_batch_v1",
        "id": "export_batch_test",
        "batch_id": "x" * 64,
        "project": "git-cg-eval",
        "experiment_id": "exp_test",
        "item_refs": ["item-0"],
        "idempotency_key": "y" * 64,
        "size_bytes": 0,
        "status": "pending",
        "redaction_profile": "default_scrub",
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
        "payload_ref": "sha256:" + ("a" * 64),
        "payload_sha256": "a" * 64,
        "payload_size_bytes": 12,
        "max_bytes": 4 * 1024 * 1024,
        "meta": {
            "dataset_id": "",
            "environment": "eval",
            "item_count": 1,
            "project_lane": "eval",
            "transport_body": {"items": []},
        },
    }
    size = _converge_size_bytes(batch)
    assert size == batch["size_bytes"] == envelope_size_bytes(batch)


def test_size_bytes_non_convergence_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def oscillating(_batch: dict) -> int:
        calls["n"] += 1
        # Alternate widths so a fixed point never lands.
        return 9_999_999 if calls["n"] % 2 else 10_000_000

    monkeypatch.setattr("git_cg.eval.mirror.batch.envelope_size_bytes", oscillating)
    batch = {"size_bytes": 0}
    with pytest.raises(ExportSizeError, match="converge"):
        _converge_size_bytes(batch)
    assert calls["n"] >= MAX_SIZE_BYTES_CONVERGENCE_ITERS


def test_ceiling_honesty_preserved() -> None:
    """Exact post-envelope ceiling validation still rejects oversize envelopes."""
    with pytest.raises(ExportSizeError, match="export_size"):
        _build_batch(
            item_refs=["big"],
            item_payloads=[{"pad": "x" * 10_000}],
            profile=RedactionProfile.DEFAULT_SCRUB,
            max_bytes=100,
            schema_pin=schema_pack_pin(),
            catalog_pin=metric_catalog_pin(),
            project="git-cg-eval",
            experiment_id="",
            environment="eval",
            dataset_id="",
            project_lane="eval",
            status=ExportStatus.PENDING,
        )
