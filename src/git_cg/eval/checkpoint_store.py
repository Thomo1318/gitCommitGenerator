"""Layer-A ``evaluation_checkpoint_v1`` store + GC (Issue #246 Slice 3).

Authoritative rows live under ``.eval/checkpoints/<checkpoint_id>.json``.
Rebuildable index rows live under ``.eval/index/checkpoints/<checkpoint_id>.json``
and are never sole authority.

GC law:
* retention unit = checkpoint files keyed by monotonic ``(started_at, checkpoint_id)``
* default ``--keep-last 10`` applies per ``suite_id`` family
* failed runs retain their last checkpoint until a later completed run supersedes
* pruning deletes matching index rows with the file (no dangling index entries)
* ``export_only`` must not create checkpoints (enforced by orchestrator)
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from git_cg.eval.binding.paths import (
    LayerAPathError,
    atomic_write_json,
    checkpoints_dir,
    index_dir,
)
from git_cg.eval.schema_pack import SchemaPackError, validate_instance

__all__ = [
    "CheckpointIndexRow",
    "CheckpointInventoryRow",
    "CheckpointStoreError",
    "build_checkpoint_record",
    "delete_checkpoint",
    "list_checkpoint_ids",
    "list_checkpoint_inventory",
    "list_index_rows",
    "load_checkpoint",
    "prune_checkpoints",
    "short_pin",
    "utc_now_iso",
    "write_checkpoint",
]

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,190}$")

CheckpointStatus = Literal["running", "failed", "completed"]


class CheckpointStoreError(ValueError):
    """Checkpoint IO / validation / containment failure."""

    def __init__(self, message: str, *, code: str = "EVAL_CHECKPOINT_IO") -> None:
        """Initialize structured error/context fields for operator engines."""
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CheckpointIndexRow:
    """Rebuildable cache row for GC ordering (not sole authority)."""

    checkpoint_id: str
    suite_id: str
    experiment_id: str
    started_at: str
    last_progress_at: str
    status: CheckpointStatus
    mode: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize one checkpoint index row for durable store writes."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "suite_id": self.suite_id,
            "experiment_id": self.experiment_id,
            "started_at": self.started_at,
            "last_progress_at": self.last_progress_at,
            "status": self.status,
            "mode": self.mode,
            "path": self.path,
        }


def utc_now_iso() -> str:
    """UTC timestamp with second precision and ``Z`` suffix."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_safe_id(value: str, *, field: str) -> str:
    """Fail closed when an identifier is empty or path-unsafe."""
    text = str(value or "").strip()
    if not text or not _SAFE_ID.fullmatch(text):
        raise CheckpointStoreError(
            f"invalid {field}: {value!r}",
            code="EVAL_CHECKPOINT_IO",
        )
    return text


def checkpoint_file(repo_root: Path, checkpoint_id: str) -> Path:
    """Return the governed on-disk path for a checkpoint id."""
    cid = _require_safe_id(checkpoint_id, field="checkpoint_id")
    return checkpoints_dir(repo_root) / f"{cid}.json"


def index_file(repo_root: Path, checkpoint_id: str) -> Path:
    """Return the governed checkpoint index path under the repo store."""
    cid = _require_safe_id(checkpoint_id, field="checkpoint_id")
    return index_dir(repo_root) / "checkpoints" / f"{cid}.json"


def build_checkpoint_record(
    *,
    checkpoint_id: str,
    experiment_id: str,
    compat_hash: str,
    completed_case_ids: Sequence[str],
    pending_case_ids: Sequence[str],
    mode: str,
    last_progress_at: str | None = None,
    suite_id: str | None = None,
    snapshot_id: str | None = None,
    schema_pack: str | None = None,
    metric_catalog: str | None = None,
    cursor: str | None = None,
    notes: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``evaluation_checkpoint_v1`` document (not yet written)."""
    cid = _require_safe_id(checkpoint_id, field="checkpoint_id")
    eid = str(experiment_id or "").strip()
    if not eid:
        raise CheckpointStoreError("experiment_id is required", code="EVAL_CHECKPOINT_IO")
    ch = str(compat_hash or "").strip().lower()
    if len(ch) != 64 or any(c not in "0123456789abcdef" for c in ch):
        raise CheckpointStoreError("compat_hash must be 64-char sha256 hex", code="EVAL_CHECKPOINT_IO")
    record: dict[str, Any] = {
        "schema_version": "evaluation_checkpoint_v1",
        "id": record_id or cid,
        "checkpoint_id": cid,
        "experiment_id": eid,
        "compat_hash": ch,
        "completed_case_ids": [str(x) for x in completed_case_ids],
        "pending_case_ids": [str(x) for x in pending_case_ids],
        "last_progress_at": last_progress_at or utc_now_iso(),
        "mode": mode,
    }
    if suite_id is not None:
        record["suite_id"] = suite_id
    if snapshot_id is not None:
        record["snapshot_id"] = snapshot_id
    if schema_pack is not None:
        record["schema_pack"] = schema_pack
    if metric_catalog is not None:
        record["metric_catalog"] = metric_catalog
    if cursor is not None:
        record["cursor"] = cursor
    if notes is not None:
        record["notes"] = notes
    try:
        validate_instance("evaluation_checkpoint_v1", record)
    except SchemaPackError as exc:
        raise CheckpointStoreError(str(exc), code="EVAL_CHECKPOINT_IO") from exc
    return record


def write_checkpoint(
    repo_root: Path,
    record: Mapping[str, Any],
    *,
    started_at: str | None = None,
    status: CheckpointStatus = "running",
) -> Path:
    """Validate + atomically persist checkpoint and matching index row."""
    payload = dict(record)
    try:
        validate_instance("evaluation_checkpoint_v1", payload)
    except SchemaPackError as exc:
        raise CheckpointStoreError(str(exc), code="EVAL_CHECKPOINT_IO") from exc

    cid = _require_safe_id(str(payload["checkpoint_id"]), field="checkpoint_id")
    path = checkpoint_file(repo_root, cid)
    try:
        written = atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise CheckpointStoreError(str(exc), code="EVAL_CHECKPOINT_IO") from exc

    suite_id = str(payload.get("suite_id") or "")
    experiment_id = str(payload.get("experiment_id") or "")
    last_progress_at = str(payload.get("last_progress_at") or utc_now_iso())
    mode = str(payload.get("mode") or "")
    started = started_at or last_progress_at
    row = CheckpointIndexRow(
        checkpoint_id=cid,
        suite_id=suite_id,
        experiment_id=experiment_id,
        started_at=started,
        last_progress_at=last_progress_at,
        status=status,
        mode=mode,
        path=str(written),
    )
    try:
        atomic_write_json(index_file(repo_root, cid), row.to_dict())
    except LayerAPathError as exc:
        raise CheckpointStoreError(str(exc), code="EVAL_CHECKPOINT_IO") from exc
    return written


def load_checkpoint(repo_root: Path, checkpoint_id: str) -> dict[str, Any]:
    """Load + validate a checkpoint; missing/corrupt → store error."""
    path = checkpoint_file(repo_root, checkpoint_id)
    if not path.is_file():
        raise CheckpointStoreError(
            f"checkpoint not found: {checkpoint_id}",
            code="EVAL_CHECKPOINT_MISSING",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointStoreError(
            f"unreadable checkpoint {checkpoint_id}: {exc}",
            code="EVAL_CHECKPOINT_IO",
        ) from exc
    if not isinstance(payload, dict):
        raise CheckpointStoreError(
            f"checkpoint {checkpoint_id} is not a JSON object",
            code="EVAL_CHECKPOINT_IO",
        )
    try:
        validate_instance("evaluation_checkpoint_v1", payload)
    except SchemaPackError as exc:
        raise CheckpointStoreError(str(exc), code="EVAL_CHECKPOINT_IO") from exc
    return payload


def list_checkpoint_ids(repo_root: Path) -> list[str]:
    """Return checkpoint ids present on disk (unsorted)."""
    root = checkpoints_dir(repo_root)
    if not root.is_dir():
        return []
    out: list[str] = []
    for path in root.glob("*.json"):
        if path.is_file():
            out.append(path.stem)
    return out


def list_index_rows(repo_root: Path, *, suite_id: str | None = None) -> list[CheckpointIndexRow]:
    """Load rebuildable index rows; synthesize from files when index missing."""
    rows: list[CheckpointIndexRow] = []
    seen: set[str] = set()
    idx_root = index_dir(repo_root) / "checkpoints"
    if idx_root.is_dir():
        for path in sorted(idx_root.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            if not isinstance(raw, dict):
                continue
            cid = str(raw.get("checkpoint_id") or path.stem)
            sid = str(raw.get("suite_id") or "")
            if suite_id is not None and sid != suite_id:
                continue
            status = str(raw.get("status") or "running")
            if status not in {"running", "failed", "completed"}:
                status = "running"
            rows.append(
                CheckpointIndexRow(
                    checkpoint_id=cid,
                    suite_id=sid,
                    experiment_id=str(raw.get("experiment_id") or ""),
                    started_at=str(raw.get("started_at") or ""),
                    last_progress_at=str(raw.get("last_progress_at") or ""),
                    status=status,  # type: ignore[arg-type]
                    mode=str(raw.get("mode") or ""),
                    path=str(raw.get("path") or ""),
                )
            )
            seen.add(cid)

    # Synthesize missing index rows from authoritative files.
    for cid in list_checkpoint_ids(repo_root):
        if cid in seen:
            continue
        try:
            record = load_checkpoint(repo_root, cid)
        except CheckpointStoreError:
            continue
        sid = str(record.get("suite_id") or "")
        if suite_id is not None and sid != suite_id:
            continue
        ts = str(record.get("last_progress_at") or "")
        rows.append(
            CheckpointIndexRow(
                checkpoint_id=cid,
                suite_id=sid,
                experiment_id=str(record.get("experiment_id") or ""),
                started_at=ts,
                last_progress_at=ts,
                status="running",
                mode=str(record.get("mode") or ""),
                path=str(checkpoint_file(repo_root, cid)),
            )
        )
    return rows


def short_pin(value: str | None, *, width: int = 12) -> str:
    """Return a short operator-facing pin/hash fragment (empty when absent)."""
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    if "@" in text_value:
        # schema_pack_v0@<hex> → digest side
        text_value = text_value.rsplit("@", 1)[-1]
    text_value = text_value.lower()
    if len(text_value) <= width:
        return text_value
    return text_value[:width]


def _file_mtime_iso(path: Path) -> str:
    """UTC second-precision mtime for a checkpoint file (empty when unavailable)."""
    try:
        ts = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(ts, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class CheckpointInventoryRow:
    """Read-only operator inventory row for ``eval checkpoint list``."""

    checkpoint_id: str
    mtime: str
    suite_id: str
    experiment_id: str
    status: str
    mode: str
    compat_hash_short: str
    pin_short: str
    live_match: bool
    completed_count: int
    pending_count: int
    path: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize one inventory row for JSON envelopes."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "mtime": self.mtime,
            "suite_id": self.suite_id,
            "experiment_id": self.experiment_id,
            "status": self.status,
            "mode": self.mode,
            "compat_hash_short": self.compat_hash_short,
            "pin_short": self.pin_short,
            "live_match": self.live_match,
            "completed_count": self.completed_count,
            "pending_count": self.pending_count,
            "path": self.path,
        }


def _live_match_for_checkpoint(record: Mapping[str, Any]) -> bool:
    """True when stored compat_hash matches live schema/metric pins + suite/snapshot.

    Missing fields or compute failures are non-matching (False).
    """
    stored = str(record.get("compat_hash") or "").strip().lower()
    suite_id = str(record.get("suite_id") or "").strip()
    snapshot_id = str(record.get("snapshot_id") or "").strip()
    if not stored or not suite_id or not snapshot_id:
        return False
    try:
        from git_cg.eval.compat import compute_compat_hash
        from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

        live = compute_compat_hash(
            schema_pack_pin=schema_pack_pin(),
            metric_catalog_pin=metric_catalog_pin(),
            suite_id=suite_id,
            snapshot_hash=snapshot_id,
        )
    except Exception:
        return False
    return stored == live


def list_checkpoint_inventory(
    repo_root: Path,
    *,
    suite_id: str | None = None,
) -> list[CheckpointInventoryRow]:
    """Build a read-only checkpoint inventory (no mutation).

    Newest ``mtime`` first, then checkpoint_id. Unreadable or schema-invalid
    files are skipped.
    """
    index_by_id = {row.checkpoint_id: row for row in list_index_rows(repo_root, suite_id=suite_id)}
    rows: list[CheckpointInventoryRow] = []
    for cid in list_checkpoint_ids(repo_root):
        try:
            path = checkpoint_file(repo_root, cid)
            record = load_checkpoint(repo_root, cid)
        except CheckpointStoreError:
            continue
        sid = str(record.get("suite_id") or "")
        if suite_id is not None and sid != suite_id:
            continue
        idx = index_by_id.get(cid)
        status = str(idx.status if idx is not None else "running")
        mode = str(record.get("mode") or (idx.mode if idx is not None else "") or "")
        experiment_id = str(record.get("experiment_id") or (idx.experiment_id if idx is not None else "") or "")
        pin_source = (
            str(record.get("schema_pack") or "").strip()
            or str(record.get("snapshot_id") or "").strip()
            or str(record.get("metric_catalog") or "").strip()
        )
        completed = record.get("completed_case_ids") or []
        pending = record.get("pending_case_ids") or []
        completed_count = len(completed) if isinstance(completed, list) else 0
        pending_count = len(pending) if isinstance(pending, list) else 0
        mtime = _file_mtime_iso(path) or str(record.get("last_progress_at") or "")
        rows.append(
            CheckpointInventoryRow(
                checkpoint_id=cid,
                mtime=mtime,
                suite_id=sid,
                experiment_id=experiment_id,
                status=status,
                mode=mode,
                compat_hash_short=short_pin(str(record.get("compat_hash") or "")),
                pin_short=short_pin(pin_source),
                live_match=_live_match_for_checkpoint(record),
                completed_count=completed_count,
                pending_count=pending_count,
                path=str(path),
            )
        )
    rows.sort(key=lambda r: (r.mtime, r.checkpoint_id), reverse=True)
    return rows


def delete_checkpoint(repo_root: Path, checkpoint_id: str) -> None:
    """Delete checkpoint file + matching index row (best-effort index)."""
    cid = _require_safe_id(checkpoint_id, field="checkpoint_id")
    path = checkpoint_file(repo_root, cid)
    idx = index_file(repo_root, cid)
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        raise CheckpointStoreError(f"failed to delete checkpoint {cid}: {exc}") from exc
    try:
        if idx.exists():
            idx.unlink()
    except OSError as exc:
        raise CheckpointStoreError(f"failed to delete checkpoint index {cid}: {exc}") from exc


def _sort_key(row: CheckpointIndexRow) -> tuple[str, str]:
    """Sort key for deterministic checkpoint/index ordering."""
    return (row.started_at or row.last_progress_at or "", row.checkpoint_id)


def prune_checkpoints(
    repo_root: Path,
    *,
    suite_id: str,
    keep_last: int = 10,
    protect_ids: Iterable[str] | None = None,
) -> list[str]:
    """Prune oldest checkpoints for ``suite_id`` down to ``keep_last``.

    Failed-run checkpoints are retained regardless of age until a later
    ``completed`` checkpoint exists for the same suite family (then normal
    keep-last applies, still honouring ``protect_ids``).
    """
    if keep_last < 0:
        raise CheckpointStoreError("keep_last must be >= 0", code="EVAL_USAGE")
    protected = {str(x) for x in (protect_ids or ())}
    rows = [r for r in list_index_rows(repo_root, suite_id=suite_id)]
    rows_sorted = sorted(rows, key=_sort_key)
    has_completed = any(r.status == "completed" for r in rows_sorted)

    retain: list[CheckpointIndexRow] = []
    candidates: list[CheckpointIndexRow] = []
    for row in rows_sorted:
        if row.checkpoint_id in protected:
            retain.append(row)
            continue
        if row.status == "failed" and not has_completed:
            retain.append(row)
            continue
        if row.status == "running":
            # Active/incomplete runs are not GC'd by keep-last alone.
            retain.append(row)
            continue
        candidates.append(row)

    # Newest candidates first for retention window.
    candidates_newest_first = list(reversed(candidates))
    keep_n = max(0, keep_last)
    # Protected/running/failed-without-green do not consume the keep_last budget
    # for completed history; keep_last bounds completed/failed-after-green set.
    doomed = candidates_newest_first[keep_n:]

    pruned: list[str] = []
    for row in doomed:
        delete_checkpoint(repo_root, row.checkpoint_id)
        pruned.append(row.checkpoint_id)
    _ = retain  # retained intentionally
    return pruned
