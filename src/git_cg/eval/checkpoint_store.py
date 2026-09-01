"""Layer-A ``evaluation_checkpoint_v1`` store and GC.

Authoritative rows live under ``.eval/checkpoints/<checkpoint_id>.json``.
Rebuildable index rows live under ``.eval/index/checkpoints/<checkpoint_id>.json``
and are never sole authority.

GC law:
* retention unit = checkpoint files keyed by monotonic ``(started_at, checkpoint_id)``
* default ``--keep-last 10`` applies per ``suite_id`` family
* failed runs retain their last checkpoint until a later completed run supersedes
* pruning deletes matching index rows with the file (no dangling index entries)
* ``export_only`` must not create checkpoints (enforced by orchestrator)

Durability:
* optional durable ``status`` + canonical ``started_at`` on the authoritative payload
* builder and writer share one field-resolution precedence
* list/inventory/prune are authority-first and single-pass
"""

from __future__ import annotations

import json
import re
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args

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
    "CheckpointStatus",
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
_CANONICAL_TS = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

CheckpointStatus = Literal["running", "failed", "completed"]
_CHECKPOINT_STATUS_VALUES: frozenset[str] = frozenset(get_args(CheckpointStatus))


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


def _is_canonical_started_at(value: str) -> bool:
    """Return True when ``value`` matches the strict UTC-second ``Z`` form."""
    return bool(_CANONICAL_TS.fullmatch(str(value or "")))


def _normalize_timestamp_candidate(value: Any) -> str | None:
    """Normalize a loose ISO-8601 candidate to canonical UTC-second ``Z`` form.

    Returns ``None`` when the value is empty or unparseable. Already-canonical
    values are returned unchanged.
    """
    text = str(value or "").strip()
    if not text:
        return None
    if _is_canonical_started_at(text):
        return text
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_checkpoint_status(value: Any) -> CheckpointStatus | None:
    """Return a closed-set status token, or None when outside the vocabulary."""
    text = str(value or "").strip()
    if text == "running" or text == "failed" or text == "completed":
        return text
    return None


def _coerce_status(value: Any, *, default: CheckpointStatus = "running") -> CheckpointStatus:
    """Coerce a status token into the closed runtime vocabulary."""
    return _as_checkpoint_status(value) or default


def _resolve_durable_status(
    *,
    explicit: CheckpointStatus | None,
    existing: Any = None,
) -> CheckpointStatus:
    """Resolve durable status: explicit → existing → ``running``."""
    if explicit is not None:
        status = _as_checkpoint_status(explicit)
        if status is None:
            raise CheckpointStoreError(
                f"invalid status: {explicit!r}",
                code="EVAL_CHECKPOINT_IO",
            )
        return status
    return _as_checkpoint_status(existing) or "running"


def _resolve_durable_started_at(
    *,
    explicit: str | None,
    existing: Any = None,
    last_progress_at: Any = None,
    require_explicit_canonical: bool = True,
) -> str:
    """Resolve durable started_at with shared builder/writer precedence.

    Explicit kwargs must already be canonical when ``require_explicit_canonical``
    is True. Fallback candidates (existing record / last_progress_at) normalize
    deterministically or are skipped.
    """
    if explicit is not None:
        text = str(explicit).strip()
        if require_explicit_canonical and not _is_canonical_started_at(text):
            raise CheckpointStoreError(
                f"started_at must be canonical UTC-second Z timestamp, got {explicit!r}",
                code="EVAL_CHECKPOINT_IO",
            )
        if _is_canonical_started_at(text):
            return text
        normalized_explicit = _normalize_timestamp_candidate(text)
        if normalized_explicit is not None:
            return normalized_explicit
        raise CheckpointStoreError(
            f"started_at must be canonical UTC-second Z timestamp, got {explicit!r}",
            code="EVAL_CHECKPOINT_IO",
        )

    for candidate in (existing, last_progress_at):
        normalized = _normalize_timestamp_candidate(candidate)
        if normalized is not None:
            return normalized
    return utc_now_iso()


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
    status: CheckpointStatus | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``evaluation_checkpoint_v1`` document (not yet written)."""
    cid = _require_safe_id(checkpoint_id, field="checkpoint_id")
    eid = str(experiment_id or "").strip()
    if not eid:
        raise CheckpointStoreError("experiment_id is required", code="EVAL_CHECKPOINT_IO")
    ch = str(compat_hash or "").strip().lower()
    if len(ch) != 64 or any(c not in "0123456789abcdef" for c in ch):
        raise CheckpointStoreError("compat_hash must be 64-char sha256 hex", code="EVAL_CHECKPOINT_IO")
    progress = last_progress_at or utc_now_iso()
    resolved_status = _resolve_durable_status(explicit=status, existing=None)
    resolved_started = _resolve_durable_started_at(
        explicit=started_at,
        existing=None,
        last_progress_at=progress,
    )
    record: dict[str, Any] = {
        "schema_version": "evaluation_checkpoint_v1",
        "id": record_id or cid,
        "checkpoint_id": cid,
        "experiment_id": eid,
        "compat_hash": ch,
        "completed_case_ids": [str(x) for x in completed_case_ids],
        "pending_case_ids": [str(x) for x in pending_case_ids],
        "last_progress_at": progress,
        "mode": mode,
        "status": resolved_status,
        "started_at": resolved_started,
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
    status: CheckpointStatus | None = None,
) -> Path:
    """Validate + atomically persist checkpoint and matching index row.

    Durable ``status`` / ``started_at`` are resolved with the same precedence as
    :func:`build_checkpoint_record` (explicit → existing payload → default),
    injected into the authoritative payload **before** validation, then mirrored
    onto the rebuildable index row. Index-write failure leaves the authoritative
    payload durable and raises ``EVAL_CHECKPOINT_IO``.
    """
    payload = dict(record)
    resolved_status = _resolve_durable_status(
        explicit=status,
        existing=payload.get("status"),
    )
    resolved_started = _resolve_durable_started_at(
        explicit=started_at,
        existing=payload.get("started_at"),
        last_progress_at=payload.get("last_progress_at"),
    )
    payload["status"] = resolved_status
    payload["started_at"] = resolved_started

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
    row = CheckpointIndexRow(
        checkpoint_id=cid,
        suite_id=suite_id,
        experiment_id=experiment_id,
        started_at=resolved_started,
        last_progress_at=last_progress_at,
        status=resolved_status,
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


def _read_index_raw(repo_root: Path, checkpoint_id: str) -> dict[str, Any] | None:
    """Best-effort load of one rebuildable index row (None when missing/corrupt)."""
    try:
        path = index_file(repo_root, checkpoint_id)
    except CheckpointStoreError:
        return None
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _load_authoritative_raw(
    repo_root: Path,
    checkpoint_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Load + validate one authoritative checkpoint.

    Returns ``(payload, diagnostic)`` where payload is None on missing/corrupt
    files. Diagnostics cover unknown durable status and schema failures so
    operators can distinguish silent skips from authority degradation.
    """
    try:
        path = checkpoint_file(repo_root, checkpoint_id)
    except CheckpointStoreError as exc:
        return None, str(exc)
    if not path.is_file():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable checkpoint {checkpoint_id}: {exc}"
    if not isinstance(payload, dict):
        return None, f"checkpoint {checkpoint_id} is not a JSON object"
    # Unknown durable status is corruption, not a silent skip.
    status_raw = payload.get("status", None)
    if status_raw is not None and str(status_raw).strip() not in _CHECKPOINT_STATUS_VALUES:
        return None, (
            f"checkpoint {checkpoint_id} has unknown durable status {status_raw!r}; "
            "treating authoritative payload as corrupt"
        )
    try:
        validate_instance("evaluation_checkpoint_v1", payload)
    except SchemaPackError as exc:
        return None, f"invalid checkpoint {checkpoint_id}: {exc}"
    return payload, None


def _row_from_index_raw(
    *,
    cid: str,
    raw: Mapping[str, Any],
    path_fallback: str = "",
) -> CheckpointIndexRow | None:
    """Build an index row from raw index JSON (last-known-good fallback)."""
    status = _coerce_status(raw.get("status"), default="running")
    started = _normalize_timestamp_candidate(raw.get("started_at")) or str(raw.get("started_at") or "")
    last_progress = str(raw.get("last_progress_at") or "")
    if not started:
        started = _normalize_timestamp_candidate(last_progress) or last_progress
    return CheckpointIndexRow(
        checkpoint_id=cid,
        suite_id=str(raw.get("suite_id") or ""),
        experiment_id=str(raw.get("experiment_id") or ""),
        started_at=started,
        last_progress_at=last_progress,
        status=status,
        mode=str(raw.get("mode") or ""),
        path=str(raw.get("path") or path_fallback or ""),
    )


def _row_from_authoritative(
    *,
    repo_root: Path,
    cid: str,
    record: Mapping[str, Any],
    index_raw: Mapping[str, Any] | None = None,
) -> CheckpointIndexRow:
    """Authority-first row: payload wins for status/started_at/suite_id."""
    last_progress = str(record.get("last_progress_at") or "")
    status = _resolve_durable_status(explicit=None, existing=record.get("status"))
    started = _resolve_durable_started_at(
        explicit=None,
        existing=record.get("started_at"),
        last_progress_at=last_progress or (index_raw or {}).get("last_progress_at"),
        require_explicit_canonical=False,
    )
    suite_id = str(record.get("suite_id") or "")
    experiment_id = str(record.get("experiment_id") or (index_raw or {}).get("experiment_id") or "")
    mode = str(record.get("mode") or (index_raw or {}).get("mode") or "")
    path = str(checkpoint_file(repo_root, cid))
    if index_raw and index_raw.get("path"):
        # Prefer recorded path string when present, but authority fields still win.
        path = str(index_raw.get("path") or path)
    return CheckpointIndexRow(
        checkpoint_id=cid,
        suite_id=suite_id,
        experiment_id=experiment_id,
        started_at=started,
        last_progress_at=last_progress or str((index_raw or {}).get("last_progress_at") or started),
        status=status,
        mode=mode,
        path=path,
    )


@dataclass(frozen=True, slots=True)
class _ResolvedCheckpoint:
    """Single-pass authority-first resolution unit (private)."""

    checkpoint_id: str
    row: CheckpointIndexRow | None
    record: dict[str, Any] | None
    diagnostic: str | None
    excluded: bool


def _resolve_checkpoints(
    repo_root: Path,
    *,
    suite_id: str | None = None,
) -> list[_ResolvedCheckpoint]:
    """Load each checkpoint at most once and reconcile index metadata.

    Authority-first tiers:
    1. readable authoritative → status/started_at/suite_id win
    2. corrupt authoritative + index → last-known-good index fallback
    3. corrupt authoritative + no index → excluded (never pruned)
    """
    ids = set(list_checkpoint_ids(repo_root))
    idx_root = index_dir(repo_root) / "checkpoints"
    if idx_root.is_dir():
        for path in idx_root.glob("*.json"):
            if path.is_file():
                ids.add(path.stem)

    resolved: list[_ResolvedCheckpoint] = []
    for cid in sorted(ids):
        try:
            _require_safe_id(cid, field="checkpoint_id")
        except CheckpointStoreError:
            continue

        record, diagnostic = _load_authoritative_raw(repo_root, cid)
        index_raw = _read_index_raw(repo_root, cid)

        if record is not None:
            row = _row_from_authoritative(
                repo_root=repo_root,
                cid=cid,
                record=record,
                index_raw=index_raw,
            )
            if suite_id is not None and row.suite_id != suite_id:
                continue
            resolved.append(
                _ResolvedCheckpoint(
                    checkpoint_id=cid,
                    row=row,
                    record=record,
                    diagnostic=None,
                    excluded=False,
                )
            )
            continue

        if index_raw is not None:
            if diagnostic:
                warnings.warn(
                    f"checkpoint {cid}: {diagnostic}; using index last-known-good",
                    stacklevel=2,
                )
            row = _row_from_index_raw(cid=cid, raw=index_raw)
            if row is None:
                continue
            if suite_id is not None and row.suite_id != suite_id:
                continue
            resolved.append(
                _ResolvedCheckpoint(
                    checkpoint_id=cid,
                    row=row,
                    record=None,
                    diagnostic=diagnostic,
                    excluded=False,
                )
            )
            continue

        # Corrupt/missing authoritative + no index → exclude, never prune.
        if diagnostic:
            warnings.warn(
                f"checkpoint {cid}: {diagnostic}; excluded from listing/GC",
                stacklevel=2,
            )
        # Only track exclusion when an authoritative file existed (corrupt).
        auth_path = checkpoints_dir(repo_root) / f"{cid}.json"
        if auth_path.is_file():
            resolved.append(
                _ResolvedCheckpoint(
                    checkpoint_id=cid,
                    row=None,
                    record=None,
                    diagnostic=diagnostic,
                    excluded=True,
                )
            )
    return resolved


def list_index_rows(repo_root: Path, *, suite_id: str | None = None) -> list[CheckpointIndexRow]:
    """Load rebuildable index rows; synthesize from files when index missing.

    Authority-first: readable authoritative payloads override missing **and**
    stale index metadata for ``status``, ``started_at``, and ``suite_id``.
    """
    rows: list[CheckpointIndexRow] = []
    for item in _resolve_checkpoints(repo_root, suite_id=suite_id):
        if item.excluded or item.row is None:
            continue
        rows.append(item.row)
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
    files are skipped unless a last-known-good index row can represent them.
    Status comes from the shared authority-first resolution path.
    """
    rows: list[CheckpointInventoryRow] = []
    for item in _resolve_checkpoints(repo_root, suite_id=suite_id):
        if item.excluded or item.row is None:
            continue
        row = item.row
        record = item.record
        path = checkpoint_file(repo_root, row.checkpoint_id) if record is not None else Path(row.path or "")
        if record is not None:
            mode = str(record.get("mode") or row.mode or "")
            experiment_id = str(record.get("experiment_id") or row.experiment_id or "")
            pin_source = (
                str(record.get("schema_pack") or "").strip()
                or str(record.get("snapshot_id") or "").strip()
                or str(record.get("metric_catalog") or "").strip()
            )
            completed = record.get("completed_case_ids") or []
            pending = record.get("pending_case_ids") or []
            completed_count = len(completed) if isinstance(completed, list) else 0
            pending_count = len(pending) if isinstance(pending, list) else 0
            mtime = _file_mtime_iso(path) or str(record.get("last_progress_at") or row.last_progress_at or "")
            live_match = _live_match_for_checkpoint(record)
            compat_short = short_pin(str(record.get("compat_hash") or ""))
            path_str = str(path)
        else:
            # Index last-known-good only (corrupt authoritative).
            mode = row.mode
            experiment_id = row.experiment_id
            pin_source = ""
            completed_count = 0
            pending_count = 0
            mtime = row.last_progress_at or row.started_at
            live_match = False
            compat_short = ""
            path_str = row.path or str(checkpoints_dir(repo_root) / f"{row.checkpoint_id}.json")
        rows.append(
            CheckpointInventoryRow(
                checkpoint_id=row.checkpoint_id,
                mtime=mtime,
                suite_id=row.suite_id,
                experiment_id=experiment_id,
                status=row.status,
                mode=mode,
                compat_hash_short=compat_short,
                pin_short=short_pin(pin_source),
                live_match=live_match,
                completed_count=completed_count,
                pending_count=pending_count,
                path=path_str,
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

    Authority-first reconstructed terminal statuses re-enter the keep-last
    candidate set after index loss. Excluded/corrupt-without-index rows are
    never pruned.
    """
    if keep_last < 0:
        raise CheckpointStoreError("keep_last must be >= 0", code="EVAL_USAGE")
    protected = {str(x) for x in (protect_ids or ())}
    resolved = _resolve_checkpoints(repo_root, suite_id=suite_id)
    # Excluded corrupt rows are retained by omission (never enter candidates).
    rows = [item.row for item in resolved if item.row is not None and not item.excluded]
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
            # Bounded stale-running reclamation remains a separate opt-in path.
            retain.append(row)
            continue
        candidates.append(row)

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
