"""``.eval/export_queue/`` Layer-A ops rows (plan §8.4, P0-3 / P1-11 / E7 / E11).

Local export queue: each ``export_batch_v1`` is enqueued as an
``export_queue_item_v1`` **ops record** after the redacted transport body is
persisted as a content-addressed payload artifact.

State machine (schema-closed ``QueueStatus`` — distinct from envelope ExportStatus):

    pending → sending → sent
                  ↘ failed → (retry → pending|sending) | dropped
    pending → dropped

Law:

* **Payload durability (P0-3):** enqueue persists the redacted body under
  ``.eval/export_payloads/<sha256>.json`` and stores ``payload_ref`` +
  ``payload_sha256`` + ``payload_size_bytes`` on the row.
* **Atomic claim + lease (P1-11):** ``claim_queue_item`` transitions
  ``pending|failed → sending`` with owner token + lease expiry; stale
  ``sending`` rows become reclaimable after lease.
* **Idempotent enqueue:** queue id = batch idempotency key.
* **Network identity gate (P1-12):** unresolved/zeroed git SHA is local/diag only;
  ``network_export=True`` fails ``export_validation`` before enqueue.
* **Fail-open for product:** queue errors raise :class:`ExportQueueError`
  (``export_*`` class) and never touch product accept / ``gate.deterministic_pass``.
* **No network, no Opik** — local durable layer only.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from git_cg.eval.binding.paths import atomic_write_json, eval_tree_root, resolve_repo_root
from git_cg.eval.mirror.batch import ExportStatus, map_queue_status_to_export_status
from git_cg.eval.mirror.experiments import (
    ExportGitShaError,
    require_resolved_git_sha,
)
from git_cg.eval.mirror.payload import (
    ExportPayloadError,
    load_payload_artifact,
    persist_payload_artifact,
)
from git_cg.eval.schema_pack import validate_instance

__all__ = [
    "DEFAULT_LEASE_SECONDS",
    "EXPORT_QUEUE_DIRNAME",
    "QUEUE_STATUSES",
    "ExportQueueError",
    "claim_queue_item",
    "enqueue_export_batch",
    "export_queue_dir",
    "list_claimable_items",
    "load_queue_item",
    "load_queue_payload",
    "mark_queue_item",
    "release_stale_leases",
]

#: Locked sub-path under ``.eval/`` (D2-style).
EXPORT_QUEUE_DIRNAME = "export_queue"

#: Schema-closed QueueStatus vocabulary (E7 — distinct from ExportStatus).
QUEUE_STATUSES = frozenset({"pending", "sending", "sent", "failed", "dropped"})

#: Default claim lease duration.
DEFAULT_LEASE_SECONDS = 300

#: Legal transitions.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"sending", "dropped"}),
    "sending": frozenset({"sent", "failed", "pending"}),  # pending = lease reclaim
    "failed": frozenset({"sending", "pending", "dropped"}),  # pending = operator retry (P1-4)
    "sent": frozenset(),
    "dropped": frozenset(),
}


class ExportQueueError(ValueError):
    """Export queue failure (fail-closed; ``export_*`` class, never product)."""

    def __init__(self, message: str, *, error_class: str = "export_validation") -> None:
        """Queue error with closed ``error_class`` (default ``export_validation``)."""
        self.error_class = error_class
        super().__init__(message)


def export_queue_dir(repo_root: Path) -> Path:
    """Return the contained ``.eval/export_queue/`` dir (not created here)."""
    return eval_tree_root(repo_root) / EXPORT_QUEUE_DIRNAME


def _queue_item_path(repo_root: Path, queue_id: str) -> Path:
    """Path for ``queue_id.json`` under the export queue dir.

    Rejects empty ids and path-traversal tokens (``/``, ``..``, leading ``.``).
    """
    if not queue_id or "/" in queue_id or ".." in queue_id or queue_id.startswith("."):
        raise ExportQueueError(f"invalid queue_id: {queue_id!r}")
    return export_queue_dir(repo_root) / f"{queue_id}.json"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    """Format a datetime as UTC ``Z`` timestamp."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO/``Z`` timestamp to UTC; invalid input yields ``None``."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _transport_body_from_batch(batch: dict[str, Any]) -> dict[str, Any]:
    """Extract durable ``meta.transport_body`` from a batch envelope.

    Fails closed when missing - refuses item-id-only enqueue that cannot
    be drained offline (P1-1 content-addressed payload contract).
    """
    meta = batch.get("meta") if isinstance(batch.get("meta"), dict) else {}
    body = meta.get("transport_body")
    if isinstance(body, dict):
        return body
    # Fail closed: envelope without durable body cannot be enqueued meaningfully.
    raise ExportQueueError(
        "export batch missing meta.transport_body — refuse empty item-id-only enqueue",
        error_class="export_validation",
    )


def enqueue_export_batch(
    batch: dict[str, Any],
    repo_root: Path | None = None,
    *,
    force: bool = False,
    network_export: bool = False,
    git_sha: str | None = None,
) -> Path:
    """Persist payload artifact + pending ``export_queue_item_v1`` for ``batch``.

    The queue row id is the batch ``idempotency_key`` (fallback ``batch_id``).
    Re-enqueue is idempotent: any existing valid queue row is left untouched
    unless ``force=True``. This preserves in-flight ``sending`` lease ownership
    and attempt counters as well as terminal ``sent`` rows.

    When ``network_export=True`` (P1-12), an unresolved/zeroed git SHA fails
    closed as ``export_validation`` **before** any payload/queue write so
    network-bound rows never share a fake identity. Local/offline enqueue
    keeps the historical default (``network_export=False``).
    """
    root = repo_root if repo_root is not None else resolve_repo_root()

    if network_export:
        try:
            # Prefer explicit caller SHA, then envelope/meta git_sha if present.
            meta = batch.get("meta") if isinstance(batch.get("meta"), dict) else {}
            candidate = git_sha if git_sha is not None else meta.get("git_sha") or batch.get("git_sha")
            require_resolved_git_sha(candidate, repo_root=root, network_export=True)
        except ExportGitShaError as exc:
            raise ExportQueueError(str(exc), error_class=exc.error_class) from exc

    queue_id = str(batch.get("idempotency_key") or batch.get("batch_id") or "")
    if not queue_id:
        raise ExportQueueError("export batch carries no idempotency key / batch_id")

    # Idempotent short-circuit: never reset an existing valid queue row.
    path = _queue_item_path(root, queue_id)
    if path.is_file() and not force:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict) and existing.get("status") in QUEUE_STATUSES:
            return path

    transport_body = _transport_body_from_batch(batch)
    try:
        artifact = persist_payload_artifact(transport_body, repo_root=root)
    except ExportPayloadError as exc:
        raise ExportQueueError(str(exc), error_class=exc.error_class) from exc

    profile = batch.get("redaction_profile")
    envelope_status = str(batch.get("status") or ExportStatus.PENDING.value)
    item: dict[str, Any] = {
        "schema_version": "export_queue_item_v1",
        "id": f"export_queue_{queue_id[:16]}",
        "queue_id": queue_id,
        "status": "pending",
        "redaction_profile": profile,
        "payload_ref": artifact["payload_ref"],
        "payload_sha256": artifact["payload_sha256"],
        "payload_size_bytes": artifact["payload_size_bytes"],
        "batch_id": batch.get("batch_id") or queue_id,
        "project": batch.get("project") or "",
        "experiment_id": batch.get("experiment_id") or "",
        "envelope_status": envelope_status,
        "attempt_count": 0,
        "meta": {
            "item_refs": list(batch.get("item_refs") or []),
            "item_count": len(batch.get("item_refs") or []),
            "batch_id": batch.get("batch_id"),
            "max_bytes": batch.get("max_bytes"),
            "size_bytes": batch.get("size_bytes"),
            "environment": (batch.get("meta") or {}).get("environment"),
            "dataset_id": (batch.get("meta") or {}).get("dataset_id"),
            "project_lane": (batch.get("meta") or {}).get("project_lane"),
            "schema_pack": batch.get("schema_pack"),
            "metric_catalog": batch.get("metric_catalog"),
        },
    }
    if batch.get("schema_pack"):
        item["schema_pack"] = batch["schema_pack"]
    if batch.get("metric_catalog"):
        item["metric_catalog"] = batch["metric_catalog"]

    try:
        validate_instance("export_queue_item_v1", item)
    except Exception as exc:
        raise ExportQueueError(f"queue item failed schema validation: {exc}") from exc

    return atomic_write_json(path, item)


def load_queue_item(queue_id: str, repo_root: Path | None = None) -> dict[str, Any]:
    """Load a queue row by id. Raises ``ExportQueueError`` if absent/invalid."""
    root = repo_root if repo_root is not None else resolve_repo_root()
    path = _queue_item_path(root, queue_id)
    if not path.is_file():
        raise ExportQueueError(f"no export queue item: {queue_id!r}")
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ExportQueueError(f"unreadable export queue item {queue_id!r}: {exc}") from exc
    if not isinstance(item, dict):
        raise ExportQueueError(f"export queue item is not an object: {queue_id!r}")
    return item


def load_queue_payload(
    queue_id: str,
    *,
    repo_root: Path | None = None,
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load + verify the durable payload for a queue row (P0-3 / E11)."""
    root = repo_root if repo_root is not None else resolve_repo_root()
    item = row if row is not None else load_queue_item(queue_id, repo_root=root)
    ref = str(item.get("payload_ref") or "")
    sha = item.get("payload_sha256")
    size = item.get("payload_size_bytes")
    try:
        return load_payload_artifact(
            ref,
            repo_root=root,
            expected_sha256=str(sha) if sha else None,
            expected_size=int(size) if size is not None else None,
        )
    except ExportPayloadError as exc:
        raise ExportQueueError(str(exc), error_class=exc.error_class) from exc


def mark_queue_item(
    queue_id: str,
    status: str,
    repo_root: Path | None = None,
    notes: str | None = None,
    *,
    last_error_class: str | None = None,
    claimed_by: str | None = None,
    lease_seconds: int | None = None,
    clear_lease: bool = False,
    increment_attempt: bool = False,
) -> Path:
    """Transition a queue row to ``status`` under the closed state machine.

    Enforces legal transitions, mirrors ``envelope_status``, bounds notes,
    and manages claim lease fields for ``sending`` and terminal states.
    """
    if status not in QUEUE_STATUSES:
        raise ExportQueueError(f"unknown queue status: {status!r}")

    root = repo_root if repo_root is not None else resolve_repo_root()
    item = load_queue_item(queue_id, repo_root=root)
    current = str(item.get("status", "pending"))

    if status != current and status not in _TRANSITIONS.get(current, frozenset()):
        raise ExportQueueError(f"illegal queue transition {current!r} → {status!r}")

    item["status"] = status
    item["envelope_status"] = map_queue_status_to_export_status(status).value

    if notes is not None:
        # Scrub-bounded notes: never persist multi-KB exception dumps.
        item["notes"] = str(notes)[:200]

    if last_error_class is not None:
        item["last_error_class"] = last_error_class

    if increment_attempt:
        item["attempt_count"] = int(item.get("attempt_count") or 0) + 1

    if status == "sending":
        owner = claimed_by or f"drain-{uuid.uuid4().hex[:12]}"
        ttl = DEFAULT_LEASE_SECONDS if lease_seconds is None else max(1, int(lease_seconds))
        item["claimed_by"] = owner
        item["lease_expires_at"] = _iso(_utc_now() + timedelta(seconds=ttl))
    elif clear_lease or status in {"sent", "failed", "dropped", "pending"}:
        item.pop("claimed_by", None)
        item.pop("lease_expires_at", None)

    try:
        validate_instance("export_queue_item_v1", item)
    except Exception as exc:
        raise ExportQueueError(f"queue item failed schema validation: {exc}") from exc

    path = _queue_item_path(root, queue_id)
    return atomic_write_json(path, item)


def _lease_expired(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    """True when a ``sending`` row's lease is missing or past ``now``.

    Missing lease is immediately reclaimable (crash recovery).
    """
    exp = _parse_iso(item.get("lease_expires_at") if isinstance(item.get("lease_expires_at"), str) else None)
    if exp is None:
        # sending without lease is treated as immediately reclaimable (crash recovery).
        return True
    clock = now or _utc_now()
    return clock >= exp


def release_stale_leases(
    repo_root: Path | None = None,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Reclaim stale ``sending`` rows back to ``pending`` (P1-11).

    Never blocks product accept; returns reclaimed queue ids.
    """
    root = repo_root if repo_root is not None else resolve_repo_root()
    qdir = export_queue_dir(root)
    if not qdir.is_dir():
        return []
    reclaimed: list[str] = []
    clock = now or _utc_now()
    for path in sorted(qdir.glob("*.json")):
        try:
            item = load_queue_item(path.stem, repo_root=root)
        except ExportQueueError:
            continue
        if item.get("status") != "sending":
            continue
        if _lease_expired(item, now=clock):
            mark_queue_item(path.stem, "pending", repo_root=root, clear_lease=True, notes="lease_expired_reclaimed")
            reclaimed.append(path.stem)
    return reclaimed


def list_claimable_items(repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Return rows eligible for claim: reclaim stale leases, then list ``pending``."""
    root = repo_root if repo_root is not None else resolve_repo_root()
    release_stale_leases(repo_root=root)
    qdir = export_queue_dir(root)
    if not qdir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(qdir.glob("*.json")):
        try:
            item = load_queue_item(path.stem, repo_root=root)
        except ExportQueueError:
            continue
        if item.get("status") == "pending":
            out.append(item)
    return out


def claim_queue_item(
    queue_id: str,
    *,
    repo_root: Path | None = None,
    claimed_by: str | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> dict[str, Any] | None:
    """Atomically claim a pending (or reclaimed) row for drain.

    Uses exclusive create of a ``.claim`` lock file beside the row to reduce
    double-claim races between concurrent drainers, then transitions the row
    to ``sending``. Returns the claimed row, or ``None`` if not claimable.
    """
    root = repo_root if repo_root is not None else resolve_repo_root()
    # Reclaim first so stale sending becomes pending.
    release_stale_leases(repo_root=root)

    try:
        item = load_queue_item(queue_id, repo_root=root)
    except ExportQueueError:
        return None
    if item.get("status") not in {"pending", "failed"}:
        return None

    lock_path = _queue_item_path(root, queue_id).with_suffix(".json.claim")
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags, 0o600)
    except FileExistsError:
        # Another drainer holds the lock; if lock is ancient, break it.
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            age = 0
        if age < max(5, lease_seconds // 2):
            return None
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            return None
        try:
            fd = os.open(str(lock_path), flags, 0o600)
        except FileExistsError:
            return None
    try:
        os.write(fd, (claimed_by or "drain").encode("utf-8"))
    finally:
        os.close(fd)

    try:
        # Re-load under lock; only claim if still pending/failed.
        item = load_queue_item(queue_id, repo_root=root)
        if item.get("status") not in {"pending", "failed"}:
            return None
        owner = claimed_by or f"drain-{uuid.uuid4().hex[:12]}"
        mark_queue_item(
            queue_id,
            "sending",
            repo_root=root,
            claimed_by=owner,
            lease_seconds=lease_seconds,
            increment_attempt=True,
        )
        return load_queue_item(queue_id, repo_root=root)
    finally:
        with suppress(OSError):
            lock_path.unlink(missing_ok=True)
