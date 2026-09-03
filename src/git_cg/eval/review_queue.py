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
  ``approve_promote`` is the human leg (advisory only).
* Tier-1 Feedback Definition vocabulary for human scores is bound to
  ``human.craft_rating`` / ``human.gold_dispute`` / ``human.regime_label``
  only — scores are never accept/golden authority.
* Annotation payloads are metadata + reference oriented: no raw diff bodies.
* Review never writes fixtures/gold directly.

Import law: import-light. Path / schema helpers are lazy.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from git_cg.eval.evidence_scrub import mask_optional_operator_text

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
        """Attach review-queue failure code, exit class, and operator hint."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint


def _normalize_reviewer_handle(
    value: object,
    *,
    field: str,
    message: str | None = None,
    hint: str | None = None,
) -> str:
    """Strip and validate an opaque local reviewer handle.

    Producer boundaries raise ``EVAL_USAGE`` / exit 2. Does not casefold.
    """
    handle = value.strip() if isinstance(value, str) else ""
    if not handle or not _REVIEWER_RE.fullmatch(handle):
        raise ReviewQueueError(
            message
            or (
                f"{field} must be an opaque local handle matching "
                r"[A-Za-z0-9._:-]{1,128}"
            ),
            code="EVAL_USAGE",
            exit_code=2,
            hint=hint,
        )
    return handle


def _assert_reviewer_identity_integrity(review: dict[str, Any]) -> None:
    """Reject both-present-unequal reviewer dual fields as damaged data.

    Shared write-path integrity boundary: mismatch raises
    ``EVAL_STORE_INTEGRITY`` / exit 4. Single-field rows remain permitted
    for legacy readability.
    """
    rev = review.get("reviewer")
    rid = review.get("reviewer_id")
    if not isinstance(rev, str) or not isinstance(rid, str):
        return
    if rev.strip() != rid.strip():
        raise ReviewQueueError(
            "human_review identity damaged: reviewer and reviewer_id disagree",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            hint="Repair the dual identity fields so they match, or drop one legacy field.",
        )


def _resolve_reviewer_identity(review: dict[str, Any]) -> str | None:
    """Project reviewer identity for reads.

    * both present and equal: canonical stripped handle
    * both present and unequal: fail closed (``EVAL_STORE_INTEGRITY``)
    * single field: permissive ``reviewer`` or ``reviewer_id`` fallback
    """
    _assert_reviewer_identity_integrity(review)
    rev = review.get("reviewer")
    rid = review.get("reviewer_id")
    rev_s = rev.strip() if isinstance(rev, str) and rev.strip() else None
    rid_s = rid.strip() if isinstance(rid, str) and rid.strip() else None
    return rev_s or rid_s


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 Zulu string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _queue_dir(repo: Path) -> Path:
    """Resolve the governed review-queue store directory."""
    from git_cg.eval.binding.paths import LayerAPathError, review_queue_dir

    try:
        return review_queue_dir(repo)
    except LayerAPathError as exc:
        raise ReviewQueueError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write JSON through the Layer-A path helper (fail closed)."""
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise ReviewQueueError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _validate_human_review(row: dict[str, Any]) -> None:
    """Validate a payload against the closed schema/contract (fail closed).

    When both ``reviewer`` and ``reviewer_id`` are present they must be equal
    after strip. Mismatch is damaged store data (``EVAL_STORE_INTEGRITY``),
    not producer usage.
    """
    from git_cg.eval.schema_pack import SchemaPackError, validate_instance

    try:
        validate_instance(SCHEMA_NAME, row)
    except SchemaPackError as exc:
        raise ReviewQueueError(
            f"human_review_v1 validation failed: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
        ) from exc
    _assert_reviewer_identity_integrity(row)


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
    """Load a JSON object from disk; map I/O and decode failures to the module error type."""
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
    """Resolve one queue/store item path with containment checks."""
    if not _SAFE_ID.fullmatch(review_id):
        raise ReviewQueueError(f"invalid review_id: {review_id!r}", code="EVAL_USAGE", exit_code=2)
    return _queue_dir(repo) / f"{review_id}.json"


def _read_item(repo: Path, review_id: str) -> tuple[dict[str, Any], Path]:
    """Read one queue item JSON document (fail closed)."""
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
    """Persist a governed artifact via atomic write (fail closed)."""
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


#: Tier-1 human Feedback Definition names bound into review UX (S7-2/S7-3).
#: Kept local (not imported from feedback_definitions) so review_queue stays
#: import-light and the drift-guard can still assert emitter parity by source.
BOUND_HUMAN_SCORE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "human.craft_rating",
        "human.gold_dispute",
        "human.regime_label",
    }
)

#: Annotation payload keys that must never ride on human_review rows.
_FORBIDDEN_ANNOTATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "diff",
        "diff_body",
        "raw_diff",
        "patch",
        "unified_diff",
        "full_diff",
        "message_body",
        "commit_message",
    }
)


def _build_scores(
    *,
    craft_rating: float | None,
    gold_dispute: bool | None,
    regime_label: str | None,
) -> dict[str, Any]:
    """Build Tier-1 human.* scores for the nested human_review_v1 payload.

    Score names are the bound Feedback Definition vocabulary only. They are
    advisory metadata for review UX / rollup — never accept or golden authority.
    """
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


def _reject_raw_annotation_payload(payload: dict[str, Any], *, where: str) -> None:
    """Fail closed when annotation-like payloads try to carry raw diff bodies."""
    bad = sorted(k for k in payload if k in _FORBIDDEN_ANNOTATION_KEYS)
    if not bad:
        return
    raise ReviewQueueError(
        f"{where} rejects raw diff/annotation bodies: {bad}",
        code="EVAL_USAGE",
        exit_code=2,
        hint="Annotation payloads are metadata + reference only; no raw diffs.",
    )


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
    who = _normalize_reviewer_handle(
        reviewer,
        field="reviewer",
        message="reviewer must be an opaque local handle matching [A-Za-z0-9._:-]{1,128}",
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
        "reviewer": who,
        "reviewer_id": who,
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
    safe_notes = mask_optional_operator_text(notes)
    if safe_notes is not None:
        review["notes"] = safe_notes

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
                    "reviewer": _resolve_reviewer_identity(review),
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


def _claim_lock_path(repo: Path, review_id: str) -> Path:
    """Return the exclusive claim lock path beside the queue row."""
    return _item_path(repo, review_id).with_suffix(".claim")


def _acquire_claim_lock(repo: Path, review_id: str, reviewer: str) -> Path:
    """Acquire an O_EXCL claim lock for contention-safe row transitions."""
    import os

    lock_path = _claim_lock_path(repo, review_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags, 0o600)
    except FileExistsError as exc:
        raise ReviewQueueError(
            f"review {review_id!r} is already under claim contention",
            code="EVAL_USAGE",
            exit_code=2,
            hint="Another operator is claiming this row; retry after it settles.",
        ) from exc
    try:
        os.write(fd, reviewer.encode("utf-8"))
    finally:
        os.close(fd)
    return lock_path


def _release_claim_lock(lock_path: Path | None) -> None:
    """Best-effort release of a claim lock file."""
    if lock_path is None:
        return
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        return


def claim(
    repo: Path,
    *,
    review_id: str,
    reviewer: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Claim a pending item → in_review.

    Uses an exclusive ``.claim`` lock beside the queue row to reduce
    duplicate/over-claim races between concurrent operators, then relies on
    atomic JSON replace for the row write.
    """
    who = _normalize_reviewer_handle(
        reviewer,
        field="reviewer",
        message="claim requires opaque --reviewer handle",
    )
    lock_path: Path | None = None
    try:
        if not dry_run:
            lock_path = _acquire_claim_lock(repo, review_id, who)
        item, path = _read_item(repo, review_id)
        current = str(item.get("status") or "")
        if current != STATUS_PENDING:
            # Idempotent re-claim by same reviewer while in_review.
            if current == STATUS_IN_REVIEW and item.get("claimed_by") == who:
                return {"item": item, "path": str(path), "changed": False, "dry_run": dry_run}
            raise ReviewQueueError(
                f"illegal claim from status={current!r} (need pending)",
                code="EVAL_USAGE",
                exit_code=2,
                hint="Only pending items can be claimed (duplicate/over-claim rejected).",
            )
        now = _utc_now()
        item["status"] = STATUS_IN_REVIEW
        item["claimed_by"] = who
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
    finally:
        # Lock is only needed across the read→decide→write window.
        _release_claim_lock(lock_path)


def _transition_guard(item: dict[str, Any], target: str) -> None:
    """Enforce a closed state-machine transition guard."""
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
    who = _normalize_reviewer_handle(
        (adjudicator or item.get("claimed_by") or "operator"),
        field="adjudicator",
        message="adjudicator must be an opaque local handle",
    )

    adjudication: dict[str, Any] = {
        "outcome": oc if oc != OUTCOME_DISMISS else OUTCOME_DISMISS,
        "adjudicated_at": now,
        "adjudicated_by": who,
        "authority": "advisory",
        # Typed reference consumed by promote (never a gold mint token).
        "outcome_ref": f"review_outcome:{item['review_id']}:{oc}",
    }
    safe_hint = mask_optional_operator_text(destination_hint)
    if safe_hint is not None:
        adjudication["destination_hint"] = safe_hint
    safe_notes = mask_optional_operator_text(notes)
    if safe_notes is not None:
        adjudication["notes"] = safe_notes

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


def _target_key(item: dict[str, Any]) -> tuple[str, str] | None:
    """Return stable grouping key: prefer case_id, else bundle_id."""
    review = item.get("review") if isinstance(item.get("review"), dict) else {}
    case_id = review.get("case_id")
    bundle_id = review.get("bundle_id")
    if isinstance(case_id, str) and case_id.strip():
        return ("case_id", case_id.strip())
    if isinstance(bundle_id, str) and bundle_id.strip():
        return ("bundle_id", bundle_id.strip())
    return None


def _iter_queue_items(repo: Path) -> list[dict[str, Any]]:
    """Iterate governed store rows while skipping unreadable/foreign files safely."""
    root = _queue_dir(repo)
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            item, _ = _read_item(repo, path.stem)
        except ReviewQueueError:
            continue
        items.append(item)
    return items


def _mean(values: list[float]) -> float | None:
    """Return the arithmetic mean, or ``None`` when the series is empty."""
    if not values:
        return None
    return sum(values) / len(values)


def _majority_bool(votes: list[bool]) -> str:
    """Majority-bool rollup over rater votes (ties stay unset/False by policy)."""
    if not votes:
        return "none"
    trues = sum(1 for v in votes if v)
    falses = len(votes) - trues
    if trues == falses:
        return "split"
    return "true" if trues > falses else "false"


def _majority_str(votes: list[str]) -> str:
    """Majority-string rollup over rater votes (ties stay unset by policy)."""
    if not votes:
        return "none"
    counts: dict[str, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
        return "split"
    return ranked[0][0]


def rollup_reviews(
    repo: Path,
    *,
    case_id: str | None = None,
    bundle_id: str | None = None,
) -> dict[str, Any]:
    """Deterministic multi-rater advisory rollup over human_review_v1 rows (NTH-05).

    Groups queue items by ``case_id`` (preferred) or ``bundle_id``. Read-only:
    never promotes gold, never mutates the store, never elevates authority
    above ``advisory``.

    Disagreement rules (closed, deterministic):
    * craft ratings → min/max/mean/spread; ``disagreement`` when spread > 1.0
    * gold_dispute → majority true/false; ``split`` on ties
    * regime_label → majority among {A,B,unknown}; ``split`` on ties
    * outcomes → majority adjudicated outcome; ``split``/``none`` otherwise
    """
    if case_id is not None and not str(case_id).strip():
        raise ReviewQueueError("empty --case filter", code="EVAL_USAGE", exit_code=2)
    if bundle_id is not None and not str(bundle_id).strip():
        raise ReviewQueueError("empty --bundle-id filter", code="EVAL_USAGE", exit_code=2)

    want_case = case_id.strip() if isinstance(case_id, str) and case_id.strip() else None
    want_bundle = bundle_id.strip() if isinstance(bundle_id, str) and bundle_id.strip() else None

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in _iter_queue_items(repo):
        review = item.get("review") if isinstance(item.get("review"), dict) else {}
        item_case = (
            review.get("case_id").strip()
            if isinstance(review.get("case_id"), str) and review.get("case_id").strip()
            else None
        )
        item_bundle = (
            review.get("bundle_id").strip()
            if isinstance(review.get("bundle_id"), str) and review.get("bundle_id").strip()
            else None
        )
        if want_case is not None and item_case != want_case:
            continue
        if want_bundle is not None and item_bundle != want_bundle:
            continue
        key = _target_key(item)
        if key is None:
            continue
        groups.setdefault(key, []).append(item)

    rollups: list[dict[str, Any]] = []
    for (kind, tid), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        reviewers: list[str] = []
        craft_vals: list[float] = []
        dispute_votes: list[bool] = []
        regime_votes: list[str] = []
        outcome_votes: list[str] = []
        status_counts: dict[str, int] = {}
        review_ids: list[str] = []

        for item in items:
            review = item.get("review") if isinstance(item.get("review"), dict) else {}
            rid = str(item.get("review_id") or review.get("review_id") or "")
            if rid:
                review_ids.append(rid)
            reviewer = _resolve_reviewer_identity(review)
            if reviewer is not None:
                reviewers.append(reviewer)
            status = str(item.get("status") or "")
            status_counts[status] = status_counts.get(status, 0) + 1
            scores = review.get("scores") if isinstance(review.get("scores"), dict) else {}
            craft = scores.get("human.craft_rating")
            if isinstance(craft, (int, float)) and not isinstance(craft, bool):
                craft_vals.append(float(craft))
            dispute = scores.get("human.gold_dispute")
            if isinstance(dispute, bool):
                dispute_votes.append(dispute)
            regime = scores.get("human.regime_label")
            if isinstance(regime, str) and regime.strip():
                regime_votes.append(regime.strip())
            adj = item.get("adjudication") if isinstance(item.get("adjudication"), dict) else {}
            outcome = adj.get("outcome")
            if isinstance(outcome, str) and outcome.strip():
                outcome_votes.append(outcome.strip())

        craft_min = min(craft_vals) if craft_vals else None
        craft_max = max(craft_vals) if craft_vals else None
        craft_mean = _mean(craft_vals)
        craft_spread = (
            (craft_max - craft_min) if craft_vals and craft_min is not None and craft_max is not None else None
        )
        craft_disagreement = bool(craft_spread is not None and craft_spread > 1.0)
        unique_reviewers = sorted(set(reviewers))
        rollups.append(
            {
                "target_kind": kind,
                "target_id": tid,
                "review_count": len(items),
                "reviewer_count": len(unique_reviewers),
                "reviewers": unique_reviewers,
                "review_ids": sorted(set(review_ids)),
                "status_counts": dict(sorted(status_counts.items())),
                "dimensions": {
                    "human.craft_rating": {
                        "count": len(craft_vals),
                        "min": craft_min,
                        "max": craft_max,
                        "mean": craft_mean,
                        "spread": craft_spread,
                        "disagreement": craft_disagreement,
                    },
                    "human.gold_dispute": {
                        "count": len(dispute_votes),
                        "majority": _majority_bool(dispute_votes),
                        "true_count": sum(1 for v in dispute_votes if v),
                        "false_count": sum(1 for v in dispute_votes if not v),
                    },
                    "human.regime_label": {
                        "count": len(regime_votes),
                        "majority": _majority_str(regime_votes),
                        "votes": sorted(regime_votes),
                    },
                },
                "outcomes": {
                    "count": len(outcome_votes),
                    "majority": _majority_str(outcome_votes),
                    "votes": sorted(outcome_votes),
                },
                "authority": "advisory",
                "can_sole_promote_gold": False,
            }
        )

    return {
        "rollups": rollups,
        "rollup_count": len(rollups),
        "authority": "advisory",
        "can_sole_promote_gold": False,
        "filters": {
            "case_id": want_case,
            "bundle_id": want_bundle,
        },
    }


__all__ = [
    "BOUND_HUMAN_SCORE_NAMES",
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
    "rollup_reviews",
    "show_review",
]
