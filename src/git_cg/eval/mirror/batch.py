"""``export_batch_v1`` builder (plan §7.2.10, §8.4 deliverables 1-2).

Builds schema-valid export batch envelopes from redacted bundle item refs.

Law:

* **Idempotency (scoped reuse):** ``batch_id`` and the queue idempotency key
  derive deterministically from the sorted item ids + redaction profile +
  pins, so a re-export of the same item set under the same profile reuses the
  same batch identity (AC: "idempotent re-export does not duplicate
  corruptly").
* **Size ceiling (D-4MB):** default max batch payload is **4 MB**
  (``DEFAULT_MAX_BATCH_BYTES``), configurable downward. The builder *splits*
  items across multiple batches when the ceiling would be exceeded; a single
  item that alone exceeds the ceiling raises :class:`ExportSizeError`
  (``export_size`` class) — never a silent oversize payload.
* **Pin set:** every batch carries ``schema_pack`` and ``metric_catalog``
  content pins so the export is reproducible against the frozen floor.
* **No network, no Opik, no scoring** — this is a pure offline builder.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "DEFAULT_MAX_BATCH_BYTES",
    "ExportSizeError",
    "batch_idempotency_key",
    "build_export_batches",
]

#: Default max batch payload: 4 MB (plan §8.4; configurable downward only).
DEFAULT_MAX_BATCH_BYTES = 4 * 1024 * 1024


class ExportSizeError(ValueError):
    """A single item exceeds the batch ceiling (``export_size`` class)."""


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def batch_idempotency_key(
    item_ids: list[str],
    profile: RedactionProfile,
    schema_pin: str,
    catalog_pin: str,
) -> str:
    """Deterministic idempotency key for a batch.

    Derived from sorted item ids + profile + pins so re-export of the same
    logical batch reuses identity (scoped idempotent reuse, S3 pattern).
    """
    h = hashlib.sha256()
    h.update(schema_pin.encode("utf-8"))
    h.update(b"\x00")
    h.update(catalog_pin.encode("utf-8"))
    h.update(b"\x00")
    h.update(profile.value.encode("utf-8"))
    for item_id in sorted(item_ids):
        h.update(b"\x00")
        h.update(item_id.encode("utf-8"))
    return h.hexdigest()


def _build_batch(
    item_ids: list[str],
    profile: RedactionProfile,
    max_bytes: int,
    schema_pin: str,
    catalog_pin: str,
) -> dict[str, Any]:
    """Build and validate one ``export_batch_v1`` envelope."""
    key = batch_idempotency_key(item_ids, profile, schema_pin, catalog_pin)
    batch: dict[str, Any] = {
        "schema_version": "export_batch_v1",
        "id": f"export_batch_{key[:16]}",
        "batch_id": key,
        "item_ids": sorted(item_ids),
        "redaction_profile": profile.value,
        "schema_pack": schema_pin,
        "metric_catalog": catalog_pin,
        "max_bytes": max_bytes,
        "meta": {
            "idempotency_key": key,
            "item_count": len(item_ids),
        },
    }
    # Fail closed: the batch we claim must validate against the frozen schema.
    validate_instance("export_batch_v1", batch)
    return batch


def build_export_batches(
    items: list[tuple[str, dict[str, Any]]],
    profile: RedactionProfile | str,
    max_bytes: int = DEFAULT_MAX_BATCH_BYTES,
) -> list[dict[str, Any]]:
    """Build one or more schema-valid ``export_batch_v1`` envelopes.

    Parameters:
        items: ``(item_id, redacted_bundle)`` pairs. The bundle payload size is
            what counts against the ceiling (the batch stores refs; the
            payload budget guards the eventual transport body).
        profile: R14 redaction profile applied to every batch in the set.
        max_bytes: payload ceiling; must be ``>= 1`` and is honoured as a hard
            split bound. Default 4 MB.

    Returns a list of validated batch envelopes (one when everything fits).

    Raises:
        ExportSizeError: a single item's payload alone exceeds ``max_bytes``
            (``export_size`` class) — we never emit an oversize batch.
        ValueError: ``max_bytes < 1``.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be >= 1")

    prof = profile if isinstance(profile, RedactionProfile) else RedactionProfile(str(profile))
    schema_pin = schema_pack_pin()
    catalog_pin = metric_catalog_pin()

    # Pre-flight: refuse any single oversize item (export_size class).
    sized: list[tuple[str, int]] = []
    for item_id, payload in items:
        size = len(_canonical_bytes(payload))
        if size > max_bytes:
            raise ExportSizeError(
                f"item {item_id!r} payload {size} bytes exceeds batch ceiling {max_bytes} bytes (export_size)"
            )
        sized.append((item_id, size))

    # Greedy split: accumulate item ids until the next would blow the ceiling.
    batches: list[dict[str, Any]] = []
    current: list[str] = []
    current_bytes = 0
    for item_id, size in sized:
        if current and current_bytes + size > max_bytes:
            batches.append(_build_batch(current, prof, max_bytes, schema_pin, catalog_pin))
            current = []
            current_bytes = 0
        current.append(item_id)
        current_bytes += size
    if current:
        batches.append(_build_batch(current, prof, max_bytes, schema_pin, catalog_pin))

    return batches
