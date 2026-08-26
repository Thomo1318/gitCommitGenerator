"""``export_batch_v1`` envelope builder (plan §7.2.10, P0-2 / P1-2 / P1-13 / E7 / E10).

Three distinct layers (do not collapse):

* **transport payload** — redacted projection body (content-addressed artifact)
* **``export_batch_v1`` envelope** — this module; pins, item_refs, size, status
* **queue record** — ops state machine under ``.eval/export_queue/``

Law:

* Idempotency key = SHA-256 over canonical JSON of identity inputs (D10 / P1-2).
* Size ceiling measures the **final envelope** canonical body (P1-13), not only
  per-item sizes. Default 4 MB; configurable downward.
* ``ExportStatus`` (envelope) is distinct from ``QueueStatus`` (ops) — E7.
* No network, no Opik, no scoring — pure offline builder.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final

from git_cg.eval.corpus.canonical import canonical_json_bytes, content_sha256
from git_cg.eval.enums import RedactionProfile
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "DEFAULT_MAX_BATCH_BYTES",
    "ENVELOPE_HEADROOM_BYTES",
    "EXPORT_STATUSES",
    "ExportSizeError",
    "ExportStatus",
    "batch_idempotency_key",
    "build_export_batches",
    "envelope_size_bytes",
    "map_queue_status_to_export_status",
]

#: Default max batch payload: 4 MB (plan §8.4 / D9; configurable downward only).
DEFAULT_MAX_BATCH_BYTES = 4 * 1024 * 1024

#: Reserved headroom when packing items so post-envelope framing fits under ceiling.
ENVELOPE_HEADROOM_BYTES = 256 * 1024


class ExportStatus(StrEnum):
    """Envelope status vocabulary (plan §7.2.10) — distinct from QueueStatus."""

    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


EXPORT_STATUSES: Final[tuple[str, ...]] = tuple(s.value for s in ExportStatus)
assert EXPORT_STATUSES and len(EXPORT_STATUSES) == len(set(EXPORT_STATUSES))


class ExportSizeError(ValueError):
    """A single item or final envelope exceeds the batch ceiling (``export_size``)."""


def map_queue_status_to_export_status(queue_status: str) -> ExportStatus:
    """Exporter-boundary mapping only (E7) — never serialize QueueStatus on envelope."""
    mapping = {
        "pending": ExportStatus.PENDING,
        "sending": ExportStatus.PENDING,
        "sent": ExportStatus.OK,
        "failed": ExportStatus.FAILED,
        "dropped": ExportStatus.SKIPPED,
    }
    return mapping.get(queue_status, ExportStatus.FAILED)


def batch_idempotency_key(
    *,
    bundle_hashes: list[str],
    project_lane: str,
    environment: str,
    dataset_id: str,
    redaction_profile: RedactionProfile | str,
    schema_pin: str,
    catalog_pin: str,
    experiment_id: str = "",
    payload_sha256: str | None = None,
) -> str:
    """Deterministic D10/P1-2 idempotency key over canonical JSON identity.

    Inputs intentionally include lane/env/dataset/profile/pins (and optional
    payload content hash + experiment id) so the same item refs under two
    projects or two payload bodies never collide.
    """
    profile = redaction_profile.value if isinstance(redaction_profile, RedactionProfile) else str(redaction_profile)
    identity: dict[str, Any] = {
        "bundle_hashes": sorted(str(h) for h in bundle_hashes),
        "catalog_pin": catalog_pin,
        "dataset_id": str(dataset_id or ""),
        "environment": str(environment or ""),
        "experiment_id": str(experiment_id or ""),
        "payload_sha256": payload_sha256,
        "project_lane": str(project_lane or ""),
        "redaction_profile": profile,
        "schema_pin": schema_pin,
    }
    return content_sha256(identity)


def envelope_size_bytes(batch: dict[str, Any]) -> int:
    """Canonical uncompressed size of the envelope body (E10 / P1-13)."""
    return len(canonical_json_bytes(batch))


def _build_batch(
    *,
    item_refs: list[str],
    item_payloads: list[dict[str, Any]],
    profile: RedactionProfile,
    max_bytes: int,
    schema_pin: str,
    catalog_pin: str,
    project: str,
    experiment_id: str,
    environment: str,
    dataset_id: str,
    project_lane: str,
    status: ExportStatus,
) -> dict[str, Any]:
    """Build and validate one ``export_batch_v1`` envelope.

    Computes content-addressed ``payload_sha256`` over the transport body,
    derives the deterministic idempotency key (P1-2), measures final
    ``size_bytes``, and fails closed via ``ExportSizeError`` when the
    envelope exceeds ``max_bytes``.
    """
    # Transport body for this batch slice (redacted items keyed by ref).
    transport_body = {
        "items": [{"item_ref": ref, "payload": payload} for ref, payload in zip(item_refs, item_payloads, strict=True)],
        "redaction_profile": profile.value,
        "schema_pack": schema_pin,
        "metric_catalog": catalog_pin,
    }
    payload_sha = content_sha256(transport_body)
    bundle_hashes = [content_sha256(p) for p in item_payloads]
    key = batch_idempotency_key(
        bundle_hashes=bundle_hashes,
        project_lane=project_lane or project,
        environment=environment,
        dataset_id=dataset_id,
        redaction_profile=profile,
        schema_pin=schema_pin,
        catalog_pin=catalog_pin,
        experiment_id=experiment_id,
        payload_sha256=payload_sha,
    )

    # Provisional envelope without size_bytes, then measure final body.
    batch: dict[str, Any] = {
        "schema_version": "export_batch_v1",
        "id": f"export_batch_{key[:16]}",
        "batch_id": key,
        "project": project,
        "experiment_id": experiment_id or f"exp_{key[:16]}",
        "item_refs": list(item_refs),
        "idempotency_key": key,
        "size_bytes": 0,
        "status": status.value,
        "redaction_profile": profile.value,
        "schema_pack": schema_pin,
        "metric_catalog": catalog_pin,
        "payload_ref": f"sha256:{payload_sha}",
        "payload_sha256": payload_sha,
        "payload_size_bytes": len(canonical_json_bytes(transport_body)),
        "max_bytes": max_bytes,
        "meta": {
            "dataset_id": dataset_id,
            "environment": environment,
            "item_count": len(item_refs),
            "project_lane": project_lane or project,
            "transport_body": transport_body,
        },
    }
    size = envelope_size_bytes(batch)
    batch["size_bytes"] = size
    # Re-measure after writing size_bytes (stable once set if digit width stable;
    # recompute once more for honesty around digit-length edge cases).
    size = envelope_size_bytes(batch)
    batch["size_bytes"] = size
    if size > max_bytes:
        raise ExportSizeError(f"batch envelope {size} bytes exceeds ceiling {max_bytes} bytes (export_size)")
    validate_instance("export_batch_v1", batch)
    return batch


def build_export_batches(
    items: list[tuple[str, dict[str, Any]]],
    profile: RedactionProfile | str,
    max_bytes: int = DEFAULT_MAX_BATCH_BYTES,
    *,
    project: str = "git-cg-eval",
    experiment_id: str = "",
    environment: str = "eval",
    dataset_id: str = "",
    project_lane: str = "eval",
    status: ExportStatus | str = ExportStatus.PENDING,
) -> list[dict[str, Any]]:
    """Build one or more schema-valid ``export_batch_v1`` envelopes.

    Parameters:
        items: ``(item_ref, redacted_payload)`` pairs.
        profile: R14 redaction profile applied to every batch in the set.
        max_bytes: hard ceiling on the **final envelope** canonical size.
        project / experiment_id / environment / dataset_id / project_lane:
            D10 identity inputs bound into the idempotency key and envelope.
        status: initial ``ExportStatus`` (default ``pending``).

    Raises:
        ExportSizeError: a single item (plus minimum envelope framing) exceeds
            ``max_bytes``, or a packed envelope still exceeds after split.
        ValueError: ``max_bytes < 1``.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be >= 1")

    prof = profile if isinstance(profile, RedactionProfile) else RedactionProfile(str(profile))
    st = status if isinstance(status, ExportStatus) else ExportStatus(str(status))
    schema_pin = schema_pack_pin()
    catalog_pin = metric_catalog_pin()

    def try_batch(item_refs: list[str], item_payloads: list[dict[str, Any]]) -> dict[str, Any]:
        """Attempt one fixed packing of item_refs/payloads into an envelope.

        Raises ``ExportSizeError`` when the measured envelope exceeds
        ``max_bytes`` (size authority is the envelope, not a pre-count).
        """
        return _build_batch(
            item_refs=item_refs,
            item_payloads=item_payloads,
            profile=prof,
            max_bytes=max_bytes,
            schema_pin=schema_pin,
            catalog_pin=catalog_pin,
            project=project,
            experiment_id=experiment_id,
            environment=environment,
            dataset_id=dataset_id,
            project_lane=project_lane,
            status=st,
        )

    # Pre-validate every singleton against the *final* envelope ceiling. Item
    # payload size alone is insufficient because transport_body + envelope
    # framing can dominate (P1-13 / E10).
    validated: list[tuple[str, dict[str, Any]]] = []
    for item_ref, payload in items:
        if not isinstance(payload, dict):
            raise TypeError(f"item payload must be a dict, got {type(payload).__name__}")
        ref = str(item_ref)
        try:
            try_batch([ref], [payload])
        except ExportSizeError as exc:
            raise ExportSizeError(
                f"item {ref!r} alone exceeds final envelope ceiling {max_bytes} bytes (export_size)"
            ) from exc
        validated.append((ref, payload))

    batches: list[dict[str, Any]] = []
    current_refs: list[str] = []
    current_payloads: list[dict[str, Any]] = []

    def flush() -> None:
        """Flush buffered work through the governed write path."""
        nonlocal current_refs, current_payloads
        if not current_refs:
            return
        batches.append(try_batch(current_refs, current_payloads))
        current_refs = []
        current_payloads = []

    for item_ref, payload in validated:
        if not current_refs:
            current_refs = [item_ref]
            current_payloads = [payload]
            continue
        candidate_refs = [*current_refs, item_ref]
        candidate_payloads = [*current_payloads, payload]
        try:
            try_batch(candidate_refs, candidate_payloads)
        except ExportSizeError:
            flush()
            current_refs = [item_ref]
            current_payloads = [payload]
        else:
            current_refs = candidate_refs
            current_payloads = candidate_payloads
    flush()
    return batches
