"""``.eval/export_queue/`` Layer-A rows (plan §8.4 v0.9.0 two-layer durability).

Local export queue: each ``export_batch_v1`` is persisted as an
``export_queue_item_v1`` row under ``.eval/export_queue/`` before any
transport is attempted (Layer A before export). The row carries a status
state machine so an interrupted or failed export can be retried/drained
without re-deriving the batch.

State machine (schema-closed ``status`` enum):

    pending → sending → sent
                  ↘ failed → (retry → sending) | dropped

Law:

* **Atomic persist / containment:** reuses the S3 Layer-A write law
  (:func:`git_cg.eval.binding.paths.atomic_write_json`, restrictive modes,
  ``.eval/`` containment). No partial authoritative rows.
* **Idempotent enqueue:** the queue row id is the batch idempotency key, so
  re-enqueueing the same batch overwrites the same row (no duplicate corrupt
  rows).
* **Fail-open:** queue errors raise :class:`ExportQueueError`
  (``export_*`` class) and never touch the product accept path or
  ``gate.deterministic_pass``.
* **No network, no Opik** — this is the local durable layer only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from git_cg.eval.binding.paths import atomic_write_json, eval_tree_root, resolve_repo_root
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "EXPORT_QUEUE_DIRNAME",
    "QUEUE_STATUSES",
    "ExportQueueError",
    "enqueue_export_batch",
    "export_queue_dir",
    "load_queue_item",
    "mark_queue_item",
]

#: Locked sub-path under ``.eval/`` (D2-style).
EXPORT_QUEUE_DIRNAME = "export_queue"

#: Schema-closed status vocabulary.
QUEUE_STATUSES = frozenset({"pending", "sending", "sent", "failed", "dropped"})

#: Legal transitions. ``failed`` may retry (→ ``sending``) or be dropped.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"sending", "dropped"}),
    "sending": frozenset({"sent", "failed"}),
    "failed": frozenset({"sending", "dropped"}),
    "sent": frozenset(),
    "dropped": frozenset(),
}


class ExportQueueError(ValueError):
    """Export queue failure (fail-closed; ``export_*`` class, never product)."""


def export_queue_dir(repo_root: Path) -> Path:
    """Return the contained ``.eval/export_queue/`` dir (not created here)."""
    tree = eval_tree_root(repo_root)
    return tree / EXPORT_QUEUE_DIRNAME


def _queue_item_path(repo_root: Path, queue_id: str) -> Path:
    if not queue_id or "/" in queue_id or ".." in queue_id:
        raise ExportQueueError(f"invalid queue_id: {queue_id!r}")
    return export_queue_dir(repo_root) / f"{queue_id}.json"


def enqueue_export_batch(
    batch: dict[str, Any],
    repo_root: Path | None = None,
) -> Path:
    """Persist an ``export_batch_v1`` as a pending ``export_queue_item_v1``.

    The queue row id is the batch's idempotency key (``meta.idempotency_key``
    falling back to ``batch_id``), so re-enqueueing the same logical batch
    reuses the same row — idempotent, no duplicate corrupt rows.

    Returns the written row path. Raises :class:`ExportQueueError` on any
    containment/validation failure (never propagates to product).
    """
    root = repo_root if repo_root is not None else resolve_repo_root()

    queue_id = str(batch.get("meta", {}).get("idempotency_key") or batch.get("batch_id") or "")
    if not queue_id:
        raise ExportQueueError("export batch carries no idempotency key / batch_id")

    profile = batch.get("redaction_profile")
    item: dict[str, Any] = {
        "schema_version": "export_queue_item_v1",
        "id": f"export_queue_{queue_id[:16]}",
        "queue_id": queue_id,
        "status": "pending",
        "redaction_profile": profile,
        "payload_ref": f"batch:{batch.get('batch_id', queue_id)}",
        "meta": {
            "item_ids": list(batch.get("item_ids") or []),
            "item_count": len(batch.get("item_ids") or []),
            "batch_id": batch.get("batch_id"),
            "max_bytes": batch.get("max_bytes"),
        },
    }
    if batch.get("schema_pack"):
        item["schema_pack"] = batch["schema_pack"]
    if batch.get("metric_catalog"):
        item["metric_catalog"] = batch["metric_catalog"]

    # Fail closed: the queue row we claim must validate against the schema.
    try:
        validate_instance("export_queue_item_v1", item)
    except Exception as exc:
        raise ExportQueueError(f"queue item failed schema validation: {exc}") from exc

    path = _queue_item_path(root, queue_id)
    return atomic_write_json(path, item)


def load_queue_item(queue_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    """Load a queue row by id. Raises :class:`ExportQueueError` if absent/invalid."""
    import json

    root = repo_root if repo_root is not None else resolve_repo_root()
    path = _queue_item_path(root, queue_id)
    if not path.is_file():
        raise ExportQueueError(f"no export queue item: {queue_id!r}")
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ExportQueueError(f"unreadable export queue item {queue_id!r}: {exc}") from exc
    return item


def mark_queue_item(
    queue_id: str,
    status: str,
    repo_root: Path | None = None,
    notes: str | None = None,
) -> Path:
    """Transition a queue row to ``status`` under the state machine.

    Raises :class:`ExportQueueError` on an illegal transition or unknown
    status (fail closed — a corrupt queue must not silently advance).
    """
    if status not in QUEUE_STATUSES:
        raise ExportQueueError(f"unknown queue status: {status!r}")

    root = repo_root if repo_root is not None else resolve_repo_root()
    item = load_queue_item(queue_id, repo_root=root)
    current = item.get("status", "pending")

    if status != current and status not in _TRANSITIONS.get(current, frozenset()):
        raise ExportQueueError(f"illegal queue transition {current!r} → {status!r}")

    item["status"] = status
    if notes is not None:
        item["notes"] = notes

    try:
        validate_instance("export_queue_item_v1", item)
    except Exception as exc:
        raise ExportQueueError(f"queue item failed schema validation: {exc}") from exc

    path = _queue_item_path(root, queue_id)
    return atomic_write_json(path, item)
