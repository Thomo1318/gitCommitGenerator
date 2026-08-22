"""S6 Slice 6 local HITL review queue (Issue #246 / R4 / §7.2.7).

Local SoT: ``.eval/review_queue/<review_id>.json``.

Laws:
* Atomic governed writes only (N19.3 via ``atomic_write_json``).
* Nested ``review`` payload MUST validate as frozen ``human_review_v1``.
* ``authority`` is always ``advisory`` — human scores never override
  deterministic fail and cannot sole-promote golden (enforced at promote).
* Lifecycle (queue envelope, not schema-frozen):
  ``pending → in_review → {adjudicated | dismissed}``
  with closed transitions; claim is the only path into ``in_review``.
* Adjudication emits a typed outcome reference consumed by ``eval promote``;
  review never writes fixtures/gold directly.

Import law: import-light. Path / schema helpers are lazy.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

SCHEMA_NAME: Final[str] = "human_review_v1"
SCHEMA_VERSION: Final[str] = "human_review_v1"
QUEUE_SCHEMA_VERSION: Final[str] = "review_queue_item_v0"

STATUS_PENDING: Final[str] = "pending"
STATUS_IN_REVIEW: Final[str] = "in_review"
STATUS_ADJUDICATED: Final[str] = "adjudicated"
STATUS_DISMISSED: Final[str] = "dismissed"

TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    STATUS_PENDING: frozenset({STATUS_IN_REVIEW, STATUS_DISMISSED}),
    STATUS_IN_REVIEW: frozenset({STATUS_ADJUDICATED, STATUS_DISMISSED, STATUS_PENDING}),
    STATUS_ADJUDICATED: frozenset(),
    STATUS_DISMISSED: frozenset(),
}

OUTCOME_APPROVE_PROMOTE: Final[str] = "approve_promote"
OUTCOME_REJECT: Final[str] = "reject"
OUTCOME_NEEDS_WORK: Final[str] = "needs_work"
OUTCOME_DISMISS: Final[str] = "dismiss"

OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        OUTCOME_APPROVE_PROMOTE,
        OUTCOME_REJECT,
        OUTCOME_NEEDS_WORK,
        OUTCOME_DISMISS,
    }
)

REDACTION_PROFILES: Final[frozenset[str]] = frozenset(
    {
        "public_ci",
        "default_scrub",
        "private_message",
        "train_rich",
        "antipattern_vault",
        "message_only",
        "meta_eval_scrub",
        "raw_dev_unsafe",
    }
)

_SAFE_ID: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_REVIEWER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REGIME: Final[frozenset[str]] = frozenset({"A", "B", "unknown"})


class ReviewQueueError(ValueError):
    """Deterministic review-queue failure (fail-closed)."""

    def __init__(self, message: str, *, code: str, exit_code: int, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _queue_dir(repo: Path) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, review_queue_dir

    try:
        return review_queue_dir(repo)
    except LayerAPathError as exc:
        raise ReviewQueueError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise ReviewQueueError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _validate_human_review(row: dict[str, Any]) -> None:
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_NAME, row)
    except SchemaPackError as exc:
        raise ReviewQueueError(
            f"human_review_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReviewQueueError(f"cannot read {path.name}: {exc}", code=code, exit_code=exit_code) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReviewQueueError(f"{path.name} is not valid JSON: {exc}", code=code, exit_code=exit_code) from exc
    if not isinstance(obj, dict):
        raise ReviewQueueError(f"{path.name} must contain a JSON object", code=code, exit_code=exit_code)
    return obj


def _item_path(repo: Path, review_id: str) -> Path:
    if not _SAFE_ID.fullmatch(review_id):
        raise ReviewQueueError(f"invalid review_id: {review_id!r}", code="EVAL_USAGE", exit_code=2)
    return _queue_dir(repo) / f"{review_id}.json"


def _read_item(repo: Path, review_id: str) -> tuple[dict[str, Any], Path]:
    path = _item_path(repo, review_id)
    if not path.is_file():
        raise ReviewQueueError(
            f"review not found: {review_id!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Pass a review_id from `git-cg eval review list`.",
        )
    item = _load_json(path)
    if item.get("schema_version") != QUEUE_SCHEMA_VERSION:
        # Backward-compatible: bare human_review_v1 rows are treated as pending.
        if item.get("schema_version") == SCHEMA_VERSION:
            wrapped = {
                "schema_version": QUEUE_SCHEMA_VERSION,
                "review_id": str(item.get("review_id") or item.get("id") or review_id),
                "status": STATUS_PENDING,
                "created_at": item.get("created_at") or _utc_now(),
                "updated_at": item.get("created_at") or _utc_now(),
                "review": item,
                "adjudication": None,
                "claimed_by": None,
                "claimed_at": None,
            }
            return wrapped, path
        raise ReviewQueueError(
            f"review row has unexpected schema: {review_id!r}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )
    return item, path


def _write_item(repo: Path, item: dict[str, Any]) -> Path:
    review = item.get("review")
    if not isinstance(review, dict):
        raise ReviewQueueError(
            "queue item missing nested human_review_v1 payload",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        )
    _validate_human_review(review)
    review_id = str(item.get("review_id") or "")
    path = _item_path(repo, review_id)
    # Drop nulls for cleaner on-disk rows.
    cleaned = {k: v for k, v in item.items() if v is not None}
    return _atomic_write(path, cleaned)


def _build_scores(
    *,
    craft_rating: float | None,
    gold_dispute: bool | None,
    regime_label: str | None,
) -> dict[str, Any]:
    scores: dict[str, Any] = {}
    if craft_rating is not None:
        scores["human.craft_rating"] = float(craft_rating)
    if gold_dispute is not None:
        scores["human.gold_dispute"] = bool(gold_dispute)
    if regime_label is not None:
        label = regime_label.strip()
        if label not in _REGIME:
            raise ReviewQueueError(
                f"invalid human.regime_label: {regime_label!r}",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Allowed: A | B | unknown",
            )
        scores["human.regime_label"] = label
    return scores


def enqueue(
    repo: Path,
    *,
    case_id: str | None = None,
    bundle_id: str | None = None,
    reviewer: str,
    redaction_profile: str = "meta_eval_scrub",
    craft_rating: float | None = None,
    gold_dispute: bool | None = None,
    regime_label: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Enqueue a new advisory human_review_v1 row (status=pending)."""
    if not reviewer or not _REVIEWER_RE.fullmatch(reviewer.strip()):
        raise ReviewQueueError(
            "reviewer must be an opaque local handle matching [A-Za-z0-9._:-]{1,128}",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Do not store email/display names.",
        )
    if redaction_profile not in REDACTION_PROFILES:
        raise ReviewQueueError(
            f"invalid redaction_profile: {redaction_profile!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed: {sorted(REDACTION_PROFILES)}",
        )
    if not (case_id and case_id.strip()) and not (bundle_id and bundle_id.strip()):
        raise ReviewQueueError(
            "enqueue requires --case and/or --bundle-id",
            code="EVAL_USAGE",
            exit_code=2,
        )

    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin

    review_id = f"hr-{uuid.uuid4().hex[:12]}"
    now = _utc_now()
    scores = _build_scores(
        craft_rating=craft_rating,
        gold_dispute=gold_dispute,
        regime_label=regime_label,
    )
    review: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": review_id,
        "review_id": review_id,
        "reviewer": reviewer.strip(),
        "reviewer_id": reviewer.strip(),
        "created_at": now,
        "authority": "advisory",
        "redaction_profile": redaction_profile,
        "scores": scores,
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    if case_id and case_id.strip():
        review["case_id"] = case_id.strip()
    if bundle_id and bundle_id.strip():
        review["bundle_id"] = bundle_id.strip()
    if notes and notes.strip():
        review["notes"] = notes.strip()

    _validate_human_review(review)

    item: dict[str, Any] = {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "review_id": review_id,
        "status": STATUS_PENDING,
        "created_at": now,
        "updated_at": now,
        "review": review,
        "adjudication": None,
        "claimed_by": None,
        "claimed_at": None,
    }

    path = _item_path(repo, review_id)
    if not dry_run:
        _write_item(repo, item)

    return {
        "item": {k: v for k, v in item.items() if v is not None},
        "path": str(path),
        "dry_run": dry_run,
    }


def list_reviews(repo: Path, *, status: str | None = None) -> dict[str, Any]:
    """List queue items (newest updated_at first)."""
    root = _queue_dir(repo)
    if status is not None and status not in TRANSITIONS:
        raise ReviewQueueError(
            f"invalid status filter: {status!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed: {sorted(TRANSITIONS)}",
        )
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                item, _ = _read_item(repo, path.stem)
            except ReviewQueueError:
                continue
            if status is not None and item.get("status") != status:
                continue
            review = item.get("review") if isinstance(item.get("review"), dict) else {}
            items.append(
                {
                    "review_id": item.get("review_id"),
                    "status": item.get("status"),
                    "case_id": review.get("case_id"),
                    "bundle_id": review.get("bundle_id"),
                    "reviewer": review.get("reviewer") or review.get("reviewer_id"),
                    "authority": review.get("authority", "advisory"),
                    "updated_at": item.get("updated_at") or item.get("created_at"),
                    "claimed_by": item.get("claimed_by"),
                    "outcome": (item.get("adjudication") or {}).get("outcome")
                    if isinstance(item.get("adjudication"), dict)
                    else None,
                }
            )
    items.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return {"reviews": items, "review_count": len(items)}


def show_review(repo: Path, *, review_id: str) -> dict[str, Any]:
    """Load one queue item (full envelope + nested human_review_v1)."""
    item, path = _read_item(repo, review_id)
    return {"item": item, "path": str(path)}


def claim(
    repo: Path,
    *,
    review_id: str,
    reviewer: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Claim a pending item → in_review."""
    if not reviewer or not _REVIEWER_RE.fullmatch(reviewer.strip()):
        raise ReviewQueueError(
            "claim requires opaque --reviewer handle",
            code="EVAL_USAGE",
            exit_code=2,
        )
    item, path = _read_item(repo, review_id)
    current = str(item.get("status") or "")
    if current != STATUS_PENDING:
        # Idempotent re-claim by same reviewer while in_review.
        if current == STATUS_IN_REVIEW and item.get("claimed_by") == reviewer.strip():
            return {"item": item, "path": str(path), "changed": False, "dry_run": dry_run}
        raise ReviewQueueError(
            f"illegal claim from status={current!r} (need pending)",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Only pending items can be claimed.",
        )
    now = _utc_now()
    item["status"] = STATUS_IN_REVIEW
    item["claimed_by"] = reviewer.strip()
    item["claimed_at"] = now
    item["updated_at"] = now
    if not dry_run:
        _write_item(repo, item)
    return {
        "item": {k: v for k, v in item.items() if v is not None},
        "path": str(path),
        "changed": True,
        "dry_run": dry_run,
    }


def _transition_guard(item: dict[str, Any], target: str) -> None:
    current = str(item.get("status") or "")
    allowed = TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ReviewQueueError(
            f"illegal transition {current!r} → {target!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed from {current!r}: {sorted(allowed) or '∅ (terminal)'}",
        )


def adjudicate(
    repo: Path,
    *,
    review_id: str,
    outcome: str,
    adjudicator: str | None = None,
    destination_hint: str | None = None,
    notes: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Adjudicate an in_review item → adjudicated with typed outcome ref.

    Does **not** write fixtures/gold. Outcome is consumed later by ``eval promote``
    via ``--review-id`` (advisory only; cannot sole-promote golden).
    """
    oc = outcome.strip()
    if oc not in OUTCOMES:
        raise ReviewQueueError(
            f"invalid outcome: {outcome!r}",
            code="EVAL_USAGE",
            exit_code=2,
            hint=f"Allowed: {sorted(OUTCOMES)}",
        )
    item, path = _read_item(repo, review_id)
    if oc == OUTCOME_DISMISS:
        target = STATUS_DISMISSED
        if str(item.get("status")) not in {STATUS_PENDING, STATUS_IN_REVIEW}:
            raise ReviewQueueError(
                f"illegal dismiss from status={item.get('status')!r}",
                code="EVAL_USAGE",
                exit_code=2,
            )
        _transition_guard(item, STATUS_DISMISSED)
    else:
        _transition_guard(item, STATUS_ADJUDICATED)
        target = STATUS_ADJUDICATED

    now = _utc_now()
    who = (adjudicator or item.get("claimed_by") or "operator").strip()
    if not _REVIEWER_RE.fullmatch(who):
        raise ReviewQueueError(
            "adjudicator must be an opaque local handle",
            code="EVAL_USAGE",
            exit_code=2,
        )

    adjudication: dict[str, Any] = {
        "outcome": oc if oc != OUTCOME_DISMISS else OUTCOME_DISMISS,
        "adjudicated_at": now,
        "adjudicated_by": who,
        "authority": "advisory",
        # Typed reference consumed by promote (never a gold mint token).
        "outcome_ref": f"review_outcome:{item['review_id']}:{oc}",
    }
    if destination_hint and destination_hint.strip():
        adjudication["destination_hint"] = destination_hint.strip()
    if notes and notes.strip():
        adjudication["notes"] = notes.strip()

    item["status"] = target
    item["adjudication"] = adjudication
    item["updated_at"] = now
    if not dry_run:
        _write_item(repo, item)
    return {
        "item": {k: v for k, v in item.items() if v is not None},
        "path": str(path),
        "outcome_ref": adjudication["outcome_ref"],
        "dry_run": dry_run,
    }


def dismiss(
    repo: Path,
    *,
    review_id: str,
    reason: str,
    adjudicator: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Dismiss a pending/in_review item (terminal)."""
    if not reason or not reason.strip():
        raise ReviewQueueError(
            "dismiss requires --reason",
            code="EVAL_USAGE",
            exit_code=2,
        )
    return adjudicate(
        repo,
        review_id=review_id,
        outcome=OUTCOME_DISMISS,
        adjudicator=adjudicator,
        notes=reason.strip(),
        dry_run=dry_run,
    )


__all__ = [
    "OUTCOMES",
    "OUTCOME_APPROVE_PROMOTE",
    "OUTCOME_DISMISS",
    "OUTCOME_NEEDS_WORK",
    "OUTCOME_REJECT",
    "QUEUE_SCHEMA_VERSION",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "STATUS_ADJUDICATED",
    "STATUS_DISMISSED",
    "STATUS_IN_REVIEW",
    "STATUS_PENDING",
    "TRANSITIONS",
    "ReviewQueueError",
    "adjudicate",
    "claim",
    "dismiss",
    "enqueue",
    "list_reviews",
    "show_review",
]
