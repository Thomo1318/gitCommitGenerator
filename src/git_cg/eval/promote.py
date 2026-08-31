"""S6 Slice 6 deterministic ``eval promote`` state machine (Issue #246).

§18.8 / INT-20 / INT-21 / INT-44 / FIND-024:

```
failure_or_capture
  → scrubbed_candidate
  → { fixture_lane_a | hard_negative | preference_pair
      | observability_fixture | quarantine | reject }
```

Required on promote: provenance, source bundle/thread/trace, owner, label,
destination, redaction profile, ``split_group_id`` contamination check, schema
validation.

Forbidden:
* silent gold mint from production accept / popularity
* human-review-alone golden promotion
* Expand-with-AI synthetic rows without quarantine
* antipattern rows into positive_train destinations
* unresolved HITL dispute / open review lifecycle on non-park destinations
* attached ``--review-id`` on non-park destinations without advisory
  ``adjudicate(outcome="approve_promote")`` human-leg binding (S7-3)
* human/advisory rollup evidence elevating into accept or sole-gold
  authority (``decision.human_rollup`` is advisory evidence only)

S6-E09 denial law: every rejection is a named ``denial_reason``. After the
source candidate is resolved, denials persist a candidate-class audit row
under ``.eval/index/promotions/`` (``accepted=false``) and never write
fixture/gold destination artifacts. ``--dry-run`` validates and previews
denial without writes.

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

SCHEMA_VERSION: Final[str] = "promotion_decision_v0"
BUNDLE_SCHEMA: Final[str] = "ape_bundle_v1"

STAGE_FAILURE_OR_CAPTURE: Final[str] = "failure_or_capture"
STAGE_SCRUBBED_CANDIDATE: Final[str] = "scrubbed_candidate"

DEST_FIXTURE_LANE_A: Final[str] = "fixture_lane_a"
DEST_HARD_NEGATIVE: Final[str] = "hard_negative"
DEST_PREFERENCE_PAIR: Final[str] = "preference_pair"
DEST_OBSERVABILITY_FIXTURE: Final[str] = "observability_fixture"
DEST_QUARANTINE: Final[str] = "quarantine"
DEST_REJECT: Final[str] = "reject"

#: Terminal destinations after scrubbed_candidate.
TERMINAL_DESTINATIONS: Final[frozenset[str]] = frozenset(
    {
        DEST_FIXTURE_LANE_A,
        DEST_HARD_NEGATIVE,
        DEST_PREFERENCE_PAIR,
        DEST_OBSERVABILITY_FIXTURE,
        DEST_QUARANTINE,
        DEST_REJECT,
    }
)

#: Closed denial taxonomy (explicit reasons; never silent).
DENY_MISSING_FIELD: Final[str] = "missing_required_field"
DENY_INVALID_DESTINATION: Final[str] = "invalid_destination"
DENY_INVALID_STAGE: Final[str] = "invalid_stage_transition"
DENY_SPLIT_CONTAMINATION: Final[str] = "split_group_contamination"
DENY_SILENT_GOLD: Final[str] = "silent_gold_mint_forbidden"
DENY_POPULARITY_GOLD: Final[str] = "popularity_promotion_forbidden"
DENY_HUMAN_SOLE_GOLD: Final[str] = "human_review_cannot_sole_promote_golden"
DENY_SYNTHETIC_UNQUARANTINED: Final[str] = "synthetic_expand_requires_quarantine"
DENY_ANTIPATTERN_POSITIVE: Final[str] = "antipattern_cannot_enter_positive_train"
DENY_SCHEMA: Final[str] = "schema_validation_failed"
DENY_SOURCE_MISSING: Final[str] = "source_bundle_missing"
DENY_PROVENANCE: Final[str] = "provenance_invalid"
DENY_UNRESOLVED_DISPUTE: Final[str] = "unresolved_dispute"
DENY_HUMAN_LEG: Final[str] = "human_leg_not_satisfied"

#: Every named denial class that S6-E09 must be able to surface.
DENIAL_REASONS: Final[frozenset[str]] = frozenset(
    {
        DENY_MISSING_FIELD,
        DENY_INVALID_DESTINATION,
        DENY_INVALID_STAGE,
        DENY_SPLIT_CONTAMINATION,
        DENY_SILENT_GOLD,
        DENY_POPULARITY_GOLD,
        DENY_HUMAN_SOLE_GOLD,
        DENY_SYNTHETIC_UNQUARANTINED,
        DENY_ANTIPATTERN_POSITIVE,
        DENY_SCHEMA,
        DENY_SOURCE_MISSING,
        DENY_PROVENANCE,
        DENY_UNRESOLVED_DISPUTE,
        DENY_HUMAN_LEG,
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
_GOLD_LABELS: Final[frozenset[str]] = frozenset(
    {
        "gold",
        "golden",
        "positive_gold",
        "gold_final",
        "gold-final",
        "positive_train",
    }
)
_POSITIVE_DEST_LABELS: Final[frozenset[str]] = frozenset(
    {
        "positive",
        "positive_gold",
        "positive_train",
        "gold",
        "golden",
    }
)


class PromoteError(ValueError):
    """Deterministic promote failure (fail-closed)."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        exit_code: int,
        hint: str | None = None,
        denial_reason: str | None = None,
        decision: dict[str, Any] | None = None,
        decision_path: str | None = None,
    ) -> None:
        """Attach machine-readable promote failure code, exit class, and hint."""
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint
        self.denial_reason = denial_reason
        self.decision = decision
        self.decision_path = decision_path


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 Zulu string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _promotions_dir(repo: Path) -> Path:
    """Governed promotions store under ``.eval/index/promotions/`` (cache+audit)."""
    from git_cg.eval.binding.paths import LayerAPathError, index_dir

    try:
        return index_dir(repo) / "promotions"
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _acceptpath_dir(repo: Path) -> Path:
    """Resolve the governed accept-path store directory."""
    from git_cg.eval.binding.paths import LayerAPathError, acceptpath_bundles_dir

    try:
        return acceptpath_bundles_dir(repo)
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    """Atomically write JSON through the Layer-A path helper (fail closed)."""
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
    """Load a JSON object from disk; map I/O and decode failures to the module error type."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromoteError(f"cannot read {path.name}: {exc}", code=code, exit_code=exit_code) from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PromoteError(f"{path.name} is not valid JSON: {exc}", code=code, exit_code=exit_code) from exc
    if not isinstance(obj, dict):
        raise PromoteError(f"{path.name} must contain a JSON object", code=code, exit_code=exit_code)
    return obj


def _bundle_hash(bundle: dict[str, Any]) -> str:
    """Compute the stable content hash used for bundle lineage."""
    from git_cg.eval.corpus.canonical import content_sha256

    return content_sha256(bundle)


def _extract_trace_id(bundle: dict[str, Any]) -> str:
    """Extract a typed field from a bundle/record without inventing defaults that mute integrity failures."""
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    binding = meta.get("binding") if isinstance(meta.get("binding"), dict) else {}
    for candidate in (binding.get("trace_id"), meta.get("trace_id"), bundle.get("trace_id")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_split_group(bundle: dict[str, Any], explicit: str | None) -> str:
    """Extract a typed field from a bundle/record without inventing defaults that mute integrity failures."""
    if explicit and explicit.strip():
        return explicit.strip()
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    for candidate in (meta.get("split_group_id"), bundle.get("split_group_id")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    session = bundle.get("session_thread_id")
    if isinstance(session, str) and session.strip():
        return f"sg:{session.strip()}"
    case_id = bundle.get("case_id")
    if isinstance(case_id, str) and case_id.strip():
        return f"sg:{case_id.strip()}"
    raise PromoteError(
        "split_group_id required for contamination control",
        code="EVAL_USAGE",
        exit_code=2,
        denial_reason=DENY_MISSING_FIELD,
        hint="Pass --split-group-id or ensure the source bundle carries one.",
    )


def _resolve_source_bundle(repo: Path, bundle: str) -> tuple[dict[str, Any], Path]:
    """Resolve a path/id against the governed store root (containment-checked)."""
    token = bundle.strip()
    if not token:
        raise PromoteError(
            "promote requires --bundle",
            code="EVAL_USAGE",
            exit_code=2,
            denial_reason=DENY_MISSING_FIELD,
        )
    as_path = Path(token)
    candidates: list[Path] = []
    if as_path.is_file():
        candidates.append(as_path)
    else:
        root = _acceptpath_dir(repo)
        if _SAFE_ID.fullmatch(token):
            candidates.append(root / f"{token}.json")
        candidates.append(root / token)
        if not token.endswith(".json"):
            candidates.append(root / f"{token}.json")
        # Also allow replay bundles under .eval/replays/
        from git_cg.eval.binding.paths import LayerAPathError, replays_dir

        try:
            rdir = replays_dir(repo)
            candidates.append(rdir / f"{token}.bundle.json")
            candidates.append(rdir / f"{token}.json")
        except LayerAPathError:
            pass
    for path in candidates:
        if path.is_file():
            obj = _load_json(path, code="EVAL_USAGE", exit_code=2)
            # Accept ape_bundle_v1 primarily; allow promotion decision sources that
            # embed a bundle under "bundle".
            if obj.get("schema_version") == BUNDLE_SCHEMA:
                return obj, path
            embedded = obj.get("bundle")
            if isinstance(embedded, dict) and embedded.get("schema_version") == BUNDLE_SCHEMA:
                return embedded, path
            raise PromoteError(
                f"source is not ape_bundle_v1: {path.name}",
                code="EVAL_USAGE",
                exit_code=2,
                denial_reason=DENY_SOURCE_MISSING,
            )
    raise PromoteError(
        f"source bundle not found: {token!r}",
        code="EVAL_USAGE",
        exit_code=2,
        denial_reason=DENY_SOURCE_MISSING,
        hint="Pass an accept-path or replay bundle path/id.",
    )


def _load_review(repo: Path, review_id: str | None) -> dict[str, Any] | None:
    """Load a governed artifact from the Layer-A store (fail closed)."""
    if not review_id or not review_id.strip():
        return None
    from git_cg.eval.review_queue import ReviewQueueError, show_review

    try:
        data = show_review(repo, review_id=review_id.strip())
    except ReviewQueueError as exc:
        raise PromoteError(
            str(exc),
            code=getattr(exc, "code", "EVAL_USAGE"),
            exit_code=int(getattr(exc, "exit_code", 2)),
            denial_reason=DENY_PROVENANCE,
            hint=getattr(exc, "hint", None),
        ) from exc
    return data.get("item")


def _is_synthetic_expand(bundle: dict[str, Any], meta_flags: dict[str, Any]) -> bool:
    """True when a promote candidate is synthetic-expand (not gold authority)."""
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    # Explicit boolean flags win (True only). False/None must not trip token scan.
    for key in ("synthetic", "expand_with_ai"):
        if meta.get(key) is True or meta_flags.get(key) is True:
            return True
        if meta.get(key) is False or meta_flags.get(key) is False:
            # Explicit negative short-circuits token matching for that flag family.
            pass
    markers = [
        meta.get("source_kind"),
        meta.get("producer"),
        meta_flags.get("source_kind"),
        bundle.get("provenance_label"),
    ]
    # String markers only — never stringify whole meta dicts (would match key names).
    for key in ("synthetic", "expand_with_ai"):
        for src in (meta, meta_flags):
            val = src.get(key)
            if isinstance(val, str) and val.strip():
                markers.append(val)
    blob = " ".join(str(m).lower() for m in markers if m is not None)
    return any(
        token in blob
        for token in (
            "expand-with-ai",
            "expand_with_ai",
            "expandwithai",
            "synthetic_expand",
            "synthetic",
        )
    )


def _is_antipattern(label: str, bundle: dict[str, Any]) -> bool:
    """True when a candidate belongs to the antipattern/hard-negative class."""
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    tokens = {
        label.lower(),
        str(meta.get("train_label") or "").lower(),
        str(meta.get("label") or "").lower(),
        str(bundle.get("provenance_label") or "").lower(),
    }
    return any("antipattern" in t for t in tokens if t)


def _destination_dir(repo: Path, destination: str) -> Path:
    """Resolve the destination directory for a promotion decision."""
    from git_cg.eval.binding.paths import (
        LayerAPathError,
        antipattern_vault_dir,
        index_dir,
        train_export_dir,
    )

    try:
        if destination == DEST_HARD_NEGATIVE:
            return antipattern_vault_dir(repo) / "hard_negatives"
        if destination == DEST_QUARANTINE:
            return index_dir(repo) / "quarantine"
        if destination == DEST_REJECT:
            return index_dir(repo) / "rejected"
        if destination == DEST_PREFERENCE_PAIR:
            return train_export_dir(repo) / "preference_pairs"
        if destination == DEST_OBSERVABILITY_FIXTURE:
            return index_dir(repo) / "observability_fixtures"
        if destination == DEST_FIXTURE_LANE_A:
            return index_dir(repo) / "fixture_lane_a_candidates"
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc
    raise PromoteError(
        f"unknown destination: {destination!r}",
        code="EVAL_USAGE",
        exit_code=2,
        denial_reason=DENY_INVALID_DESTINATION,
    )


def _scan_split_contamination(
    repo: Path,
    *,
    split_group_id: str,
    destination: str,
    label: str,
) -> list[str]:
    """Detect split_group_id already committed to an incompatible destination.

    Contamination unit = split_group_id. Preference pairs / replay descendants
    must not cross train/test-like destinations silently. For Slice 6 we fail
    closed when the same split_group_id already has a terminal promotion to a
    *different* destination class (except reject/quarantine re-entries).
    """
    root = _promotions_dir(repo)
    if not root.is_dir():
        return []
    conflicts: list[str] = []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("split_group_id") != split_group_id:
            continue
        rows.append(row)
    for row in rows:
        if not row.get("accepted"):
            continue
        prior_dest = str(row.get("destination") or "")
        if prior_dest in {DEST_REJECT, DEST_QUARANTINE, ""}:
            continue
        if prior_dest == destination:
            continue
        # Hard conflict: same family already landed elsewhere.
        conflicts.append(f"{row.get('promotion_id')}:{prior_dest}")
    # Positive train / gold labels cannot share a split with hard_negative vault.
    if label.lower() in _POSITIVE_DEST_LABELS or destination == DEST_FIXTURE_LANE_A:
        for row in rows:
            if row.get("accepted") and row.get("destination") == DEST_HARD_NEGATIVE:
                conflicts.append(f"{row.get('promotion_id')}:hard_negative_vs_positive")
    return sorted(set(conflicts))


def _deny(
    reason: str,
    message: str,
    *,
    hint: str | None = None,
    decision: dict[str, Any] | None = None,
    decision_path: str | None = None,
) -> PromoteError:
    """Record a denied promote candidate and fail closed."""
    return PromoteError(
        message,
        code="EVAL_USAGE",
        exit_code=2,
        denial_reason=reason,
        hint=hint,
        decision=decision,
        decision_path=decision_path,
    )


def _validate_source_bundle(source: dict[str, Any]) -> None:
    """Fail closed when the source is not a valid ``ape_bundle_v1`` instance."""
    from git_cg.eval.schema_pack import SchemaLoadError, SchemaPackError, validate_instance

    try:
        validate_instance(BUNDLE_SCHEMA, source)
    except SchemaLoadError as exc:
        raise PromoteError(
            f"schema pack unavailable for promote validation: {exc}",
            code="EVAL_STORE_INTEGRITY",
            exit_code=4,
            denial_reason=DENY_SCHEMA,
            hint="Repair the offline schema pack pin before promoting.",
        ) from exc
    except SchemaPackError as exc:
        raise _deny(
            DENY_SCHEMA,
            f"source bundle failed {BUNDLE_SCHEMA} validation: {exc}",
            hint="Fix the candidate bundle schema before promotion.",
        ) from exc


def _unresolved_dispute_message(review: dict[str, Any]) -> str | None:
    """Return a human message when an attached review still blocks promote.

    Unresolved means: lifecycle not adjudicated, or ``human.gold_dispute`` is
    still open (needs_work / dismissed / missing outcome). Reject/quarantine
    park paths may still proceed — callers decide whether to skip this gate.
    """
    status = str(review.get("status") or "").strip()
    review_id = str(review.get("review_id") or review.get("id") or "").strip() or "<unknown>"
    if status in {"pending", "in_review"}:
        return f"review {review_id} status={status!r} is unresolved"
    nested = review.get("review") if isinstance(review.get("review"), dict) else {}
    scores = nested.get("scores") if isinstance(nested.get("scores"), dict) else {}
    disputed = scores.get("human.gold_dispute") is True
    if not disputed:
        return None
    adjudication = review.get("adjudication") if isinstance(review.get("adjudication"), dict) else {}
    outcome = str(adjudication.get("outcome") or "").strip()
    if status != "adjudicated":
        return f"review {review_id} has human.gold_dispute=true without adjudicated resolution (status={status!r})"
    if outcome in {"", "needs_work"}:
        return f"review {review_id} human.gold_dispute remains open (outcome={outcome or 'none'!r})"
    return None


def _extract_human_leg(review: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract the advisory human-leg binding from an attached review row.

    ``adjudicate(outcome="approve_promote")`` is the accept leg. Satisfied only
    when the queue row is adjudicated with that outcome, authority remains
    advisory, and a typed ``outcome_ref`` is present. Tier-1 ``human.*`` scores
    are vocabulary metadata only — they never satisfy the leg and never
    sole-promote golden.
    """
    if not isinstance(review, dict):
        return None

    review_id = str(review.get("review_id") or review.get("id") or "").strip() or None
    status = str(review.get("status") or "").strip() or None
    nested = review.get("review") if isinstance(review.get("review"), dict) else {}
    adjudication = review.get("adjudication") if isinstance(review.get("adjudication"), dict) else {}

    # Prefer nested human_review_v1 authority; fall back to envelope/adjudication.
    authority = None
    for candidate in (
        nested.get("authority") if isinstance(nested, dict) else None,
        review.get("authority"),
        adjudication.get("authority"),
    ):
        if candidate is None:
            continue
        cleaned = str(candidate).strip()
        if cleaned:
            authority = cleaned
            break
    if authority is None:
        authority = "advisory"

    outcome = str(adjudication.get("outcome") or "").strip() or None
    outcome_ref = str(adjudication.get("outcome_ref") or "").strip() or None

    scores = nested.get("scores") if isinstance(nested.get("scores"), dict) else {}
    score_names = sorted(str(k) for k in scores if str(k).startswith("human."))

    satisfied = (
        status == "adjudicated"
        and outcome == "approve_promote"
        and authority == "advisory"
        and bool(outcome_ref)
        and outcome_ref.startswith("review_outcome:")
        and outcome_ref.endswith(":approve_promote")
    )

    leg: dict[str, Any] = {
        "satisfied": satisfied,
        "review_id": review_id,
        "status": status,
        "outcome": outcome,
        "outcome_ref": outcome_ref,
        "authority": authority,
        "score_names": score_names,
        "can_sole_promote_gold": False,
        "scores_are_accept_authority": False,
    }
    return {k: v for k, v in leg.items() if v is not None}


def _human_leg_block_message(review: dict[str, Any], human_leg: dict[str, Any] | None) -> str | None:
    """Return a message when an attached review cannot serve as the human leg.

    Non-park destinations that carry ``--review-id`` require an advisory
    ``approve_promote`` adjudication. Reject / needs_work / dismiss cover the
    override/defer paths and do not satisfy the leg. Park destinations skip
    this gate at the caller.
    """
    if human_leg is not None and human_leg.get("satisfied") is True:
        return None

    review_id = (
        (human_leg or {}).get("review_id")
        or str(review.get("review_id") or review.get("id") or "").strip()
        or "<unknown>"
    )
    status = (human_leg or {}).get("status") or str(review.get("status") or "").strip() or "unknown"
    outcome = (human_leg or {}).get("outcome") or "none"
    authority = (human_leg or {}).get("authority") or "advisory"
    return (
        f"review {review_id} does not satisfy the human leg "
        f"(status={status!r}, outcome={outcome!r}, authority={authority!r}; "
        "need adjudicated approve_promote with advisory authority)"
    )


def _build_human_rollup_evidence(repo: Path, source: dict[str, Any]) -> dict[str, Any]:
    """Attach landed ``rollup_reviews`` as advisory promote evidence.

    Lookup prefers source ``case_id``, then falls back to ``session_thread_id``
    as ``bundle_id`` when the case rollup is empty. Output is always stamped
    ``authority=advisory`` / ``can_sole_promote_gold=False`` and is never an
    accept gate — callers may consult it only to deny.
    """
    from git_cg.eval.review_queue import rollup_reviews

    case_raw = source.get("case_id")
    case_id = case_raw.strip() if isinstance(case_raw, str) and case_raw.strip() else None
    thread_raw = source.get("session_thread_id")
    bundle_id = thread_raw.strip() if isinstance(thread_raw, str) and thread_raw.strip() else None

    selected: list[dict[str, Any]] = []
    used_filter: dict[str, str | None] = {"case_id": None, "bundle_id": None}

    if case_id is not None:
        raw = rollup_reviews(repo, case_id=case_id)
        rows = raw.get("rollups") if isinstance(raw.get("rollups"), list) else []
        selected = [
            row
            for row in rows
            if isinstance(row, dict)
            and str(row.get("target_kind") or "") == "case_id"
            and str(row.get("target_id") or "") == case_id
        ]
        used_filter = {"case_id": case_id, "bundle_id": None}

    if not selected and bundle_id is not None:
        raw = rollup_reviews(repo, bundle_id=bundle_id)
        rows = raw.get("rollups") if isinstance(raw.get("rollups"), list) else []
        selected = [
            row
            for row in rows
            if isinstance(row, dict)
            and str(row.get("target_kind") or "") == "bundle_id"
            and str(row.get("target_id") or "") == bundle_id
        ]
        used_filter = {"case_id": None, "bundle_id": bundle_id}

    return {
        "authority": "advisory",
        "can_sole_promote_gold": False,
        "scores_are_accept_authority": False,
        "source_case_id": case_id,
        "source_bundle_id": bundle_id,
        "filters": used_filter,
        "rollup_count": len(selected),
        "rollups": selected,
    }


def _build_decision_row(
    *,
    accepted: bool,
    promotion_id: str,
    st: str,
    dest: str,
    owner: str,
    label: str,
    provenance: str,
    redaction_profile: str,
    split: str,
    source: dict[str, Any],
    source_path: Path,
    source_hash: str,
    source_trace: str,
    session_thread_id: str,
    review: dict[str, Any] | None,
    notes: str | None,
    dry_run: bool,
    denial_reason: str | None,
    candidate_class: str,
    human_rollup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured row/payload for the local operator store."""
    decision: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "promotion_id": promotion_id,
        "accepted": accepted,
        "from_stage": st,
        "via_stage": STAGE_SCRUBBED_CANDIDATE,
        "destination": dest,
        "owner": owner.strip(),
        "label": label.strip(),
        "provenance": provenance.strip(),
        "redaction_profile": redaction_profile,
        "split_group_id": split,
        "candidate_class": candidate_class,
        "source": {
            "path": str(source_path),
            "case_id": source.get("case_id"),
            "session_thread_id": session_thread_id or None,
            "trace_id": source_trace or None,
            "bundle_hash": source_hash,
            "artifact_class": source.get("artifact_class"),
            "provenance_label": source.get("provenance_label"),
        },
        "review_id": (
            (review.get("review_id") if isinstance(review, dict) else None)
            or (
                review.get("review", {}).get("review_id")
                if isinstance(review, dict) and isinstance(review.get("review"), dict)
                else None
            )
        ),
        "review_authority": (
            (review.get("review", {}) or {}).get("authority")
            if isinstance(review, dict) and isinstance(review.get("review"), dict)
            else (review.get("authority") if isinstance(review, dict) else None)
        ),
        "review_outcome_ref": (
            (review.get("adjudication") or {}).get("outcome_ref")
            if isinstance(review, dict) and isinstance(review.get("adjudication"), dict)
            else None
        ),
        "human_leg": _extract_human_leg(review),
        "human_rollup": human_rollup,
        "denial_reason": denial_reason,
        "notes": mask_optional_operator_text(notes),
        "created_at": _utc_now(),
        "dry_run": dry_run,
    }
    return {k: v for k, v in decision.items() if v is not None}


def _persist_decision(repo: Path, decision: dict[str, Any], *, dry_run: bool) -> str:
    """Persist a governed intermediate artifact for resume/audit."""
    decision_path = _promotions_dir(repo) / f"{decision['promotion_id']}.json"
    if not dry_run:
        _atomic_write(decision_path, decision)
    return str(decision_path)


def _raise_named_denial(
    repo: Path,
    *,
    reason: str,
    message: str,
    hint: str | None,
    dry_run: bool,
    st: str,
    dest: str,
    owner: str,
    label: str,
    provenance: str,
    redaction_profile: str,
    split: str,
    source: dict[str, Any],
    source_path: Path,
    source_hash: str,
    source_trace: str,
    session_thread_id: str,
    review: dict[str, Any] | None,
    notes: str | None,
    human_rollup: dict[str, Any] | None = None,
) -> None:
    """Record a candidate-class denial audit row, then fail closed.

    Denied candidates stay non-gold: no destination fixture/gold artifact is
    written. The audit row remains under ``.eval/index/promotions/`` with
    ``accepted=false`` + named ``denial_reason`` so operators can inspect the
    retained candidate decision without silent drops.
    """
    promotion_id = f"promo-{uuid.uuid4().hex[:12]}"
    # Denial retention class: quarantine-shaped candidate, never gold/fixture mint.
    candidate_class = "quarantine_candidate" if dest in {DEST_QUARANTINE, DEST_REJECT} else "scrubbed_candidate"
    decision = _build_decision_row(
        accepted=False,
        promotion_id=promotion_id,
        st=st,
        dest=dest,
        owner=owner,
        label=label,
        provenance=provenance,
        redaction_profile=redaction_profile,
        split=split,
        source=source,
        source_path=source_path,
        source_hash=source_hash,
        source_trace=source_trace,
        session_thread_id=session_thread_id,
        review=review,
        notes=notes,
        dry_run=dry_run,
        denial_reason=reason,
        candidate_class=candidate_class,
        human_rollup=human_rollup,
    )
    decision_path = _persist_decision(repo, decision, dry_run=dry_run)
    raise _deny(
        reason,
        message,
        hint=hint,
        decision=decision,
        decision_path=None if dry_run else decision_path,
    )


def promote(
    repo: Path,
    *,
    bundle: str,
    destination: str,
    owner: str,
    label: str,
    provenance: str,
    redaction_profile: str,
    stage: str = STAGE_SCRUBBED_CANDIDATE,
    split_group_id: str | None = None,
    review_id: str | None = None,
    notes: str | None = None,
    allow_golden: bool = False,
    popularity_signal: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run one promotion decision through the closed state machine.

    ``allow_golden`` is an explicit operator override that still cannot be
    satisfied by human review alone or popularity alone — both are denied.
    """
    dest = destination.strip()
    if dest not in TERMINAL_DESTINATIONS:
        raise _deny(
            DENY_INVALID_DESTINATION,
            f"invalid destination: {destination!r}",
            hint=f"Allowed: {sorted(TERMINAL_DESTINATIONS)}",
        )

    st = stage.strip() or STAGE_SCRUBBED_CANDIDATE
    if st not in {STAGE_FAILURE_OR_CAPTURE, STAGE_SCRUBBED_CANDIDATE}:
        raise _deny(
            DENY_INVALID_STAGE,
            f"invalid stage: {stage!r}",
            hint=f"Allowed sources: {STAGE_FAILURE_OR_CAPTURE}, {STAGE_SCRUBBED_CANDIDATE}",
        )

    # Required operator fields.
    missing: list[str] = []
    if not owner or not owner.strip():
        missing.append("owner")
    if not label or not label.strip():
        missing.append("label")
    if not provenance or not provenance.strip():
        missing.append("provenance")
    if not redaction_profile or not redaction_profile.strip():
        missing.append("redaction_profile")
    if missing:
        raise _deny(
            DENY_MISSING_FIELD,
            f"missing required promote fields: {', '.join(missing)}",
            hint="Pass --owner --label --provenance --redaction-profile.",
        )
    if redaction_profile not in REDACTION_PROFILES:
        raise _deny(
            DENY_MISSING_FIELD,
            f"invalid redaction_profile: {redaction_profile!r}",
            hint=f"Allowed: {sorted(REDACTION_PROFILES)}",
        )

    source, source_path = _resolve_source_bundle(repo, bundle)
    source_hash = _bundle_hash(source)
    source_trace = _extract_trace_id(source)
    session_thread_id = str(source.get("session_thread_id") or "").strip()

    # Best-effort split for audit rows even when later gates fail.
    try:
        split = _extract_split_group(source, split_group_id)
    except PromoteError as exc:
        if exc.denial_reason != DENY_MISSING_FIELD:
            raise
        split = ""

    # Advisory multi-rater evidence for accept + denial audit rows (never elevates).
    human_rollup = _build_human_rollup_evidence(repo, source)

    def _deny_after_source(reason: str, message: str, *, hint: str | None = None) -> None:
        # Once a candidate source exists, denials retain an audit row.
        """Internal helper: deny after source."""
        if not split:
            raise _deny(reason, message, hint=hint)
        _raise_named_denial(
            repo,
            reason=reason,
            message=message,
            hint=hint,
            dry_run=dry_run,
            st=st,
            dest=dest,
            owner=owner,
            label=label,
            provenance=provenance,
            redaction_profile=redaction_profile,
            split=split,
            source=source,
            source_path=source_path,
            source_hash=source_hash,
            source_trace=source_trace or "",
            session_thread_id=session_thread_id,
            review=None,
            notes=notes,
            human_rollup=human_rollup,
        )

    if not session_thread_id:
        _deny_after_source(
            DENY_MISSING_FIELD,
            "source bundle missing session_thread_id (required on promote)",
            hint="Replay/bind the bundle so session_thread_id is present, or pass a lineage-complete source.",
        )
    if not source_trace:
        _deny_after_source(
            DENY_MISSING_FIELD,
            "source bundle missing trace_id (required on promote)",
            hint="Ensure meta.binding.trace_id (or meta.trace_id) is present on the source bundle.",
        )
    if not split:
        # Re-raise with stable denial after source resolve (no lineage unit).
        raise _deny(
            DENY_MISSING_FIELD,
            "split_group_id required for contamination control",
            hint="Pass --split-group-id or ensure the source bundle carries one.",
        )

    # Schema gate (S6-E09): invalid bundles cannot mint destinations.
    try:
        _validate_source_bundle(source)
    except PromoteError as exc:
        if exc.denial_reason != DENY_SCHEMA:
            raise
        _deny_after_source(DENY_SCHEMA, str(exc), hint=exc.hint)

    review = _load_review(repo, review_id)
    label_l = label.strip().lower()
    wants_gold = label_l in _GOLD_LABELS or allow_golden

    def _deny_here(reason: str, message: str, *, hint: str | None = None) -> None:
        """Internal helper: deny here."""
        _raise_named_denial(
            repo,
            reason=reason,
            message=message,
            hint=hint,
            dry_run=dry_run,
            st=st,
            dest=dest,
            owner=owner,
            label=label,
            provenance=provenance,
            redaction_profile=redaction_profile,
            split=split,
            source=source,
            source_path=source_path,
            source_hash=source_hash,
            source_trace=source_trace or "",
            session_thread_id=session_thread_id,
            review=review,
            notes=notes,
            human_rollup=human_rollup,
        )

    # --- Forbidden paths (explicit denial taxonomy) ---
    if popularity_signal and wants_gold:
        _deny_here(
            DENY_POPULARITY_GOLD,
            "popularity/user_acceptance cannot promote golden",
            hint="Gold requires deterministic gate eligibility + owner provenance, not popularity.",
        )

    if wants_gold and dest not in {DEST_REJECT, DEST_QUARANTINE}:
        # Human review is advisory and can never be the sole golden promoter,
        # even when an adjudicated review_id is attached.
        if review is not None:
            _deny_here(
                DENY_HUMAN_SOLE_GOLD,
                "human review cannot sole-promote golden",
                hint="Adjudicated review is advisory. Golden needs gate eligibility + non-human authority.",
            )
        # Silent gold mint from production accept / popularity provenance.
        prov_l = provenance.strip().lower()
        if prov_l in {
            "user_acceptance",
            "popularity",
            "production_accept",
            "accept",
            "human_review",
            "human",
            "review",
        }:
            _deny_here(
                DENY_SILENT_GOLD,
                "silent gold mint from production acceptance/human provenance is forbidden",
                hint="Use observability_fixture / hard_negative / quarantine, not gold labels from accept/review.",
            )
        # Gold-final minting is not a Slice-6 automatic destination. fixture_lane_a
        # is a *candidate* lane only — refuse gold labels into non-quarantine paths
        # unless destination is explicitly reject/quarantine.
        if dest in {DEST_FIXTURE_LANE_A, DEST_PREFERENCE_PAIR, DEST_OBSERVABILITY_FIXTURE, DEST_HARD_NEGATIVE}:
            _deny_here(
                DENY_SILENT_GOLD,
                f"gold/golden labels cannot auto-mint via destination={dest!r}",
                hint="Gold-final requires the full gate eligibility path; use non-gold labels for candidate lanes.",
            )

    if _is_synthetic_expand(source, {}) and dest not in {
        DEST_QUARANTINE,
        DEST_REJECT,
    }:
        _deny_here(
            DENY_SYNTHETIC_UNQUARANTINED,
            "synthetic Expand-with-AI rows require quarantine before other destinations",
            hint="Promote to quarantine first; human/schema validate; then re-promote.",
        )

    if _is_antipattern(label.strip(), source) and (dest == DEST_FIXTURE_LANE_A or label_l in _POSITIVE_DEST_LABELS):
        _deny_here(
            DENY_ANTIPATTERN_POSITIVE,
            "antipattern rows cannot enter positive_train / fixture_lane_a gold paths",
            hint="Use hard_negative, quarantine, or antipattern_vault destinations.",
        )

    conflicts = _scan_split_contamination(
        repo,
        split_group_id=split,
        destination=dest,
        label=label.strip(),
    )
    if conflicts and dest not in {DEST_REJECT, DEST_QUARANTINE}:
        _deny_here(
            DENY_SPLIT_CONTAMINATION,
            f"split_group_id contamination: {split} already promoted as {conflicts}",
            hint="Keep preference/replay variants in one split_group; do not cross destinations.",
        )

    # Unresolved HITL dispute / open review lifecycle blocks non-park destinations.
    if review is not None and dest not in {DEST_REJECT, DEST_QUARANTINE}:
        dispute_msg = _unresolved_dispute_message(review)
        if dispute_msg is not None:
            _deny_here(
                DENY_UNRESOLVED_DISPUTE,
                dispute_msg,
                hint="Finish adjudication (or clear gold_dispute) before promoting out of candidate/park lanes.",
            )
        # Attached reviews must be adjudicated approve_promote (advisory only).
        human_leg = _extract_human_leg(review)
        leg_msg = _human_leg_block_message(review, human_leg)
        if leg_msg is not None:
            _deny_here(
                DENY_HUMAN_LEG,
                leg_msg,
                hint=(
                    "Adjudicate with outcome=approve_promote before attaching "
                    "--review-id on non-park destinations. Human review remains advisory."
                ),
            )

    # Stage transition: failure_or_capture must pass through scrubbed_candidate.
    effective_stage = STAGE_SCRUBBED_CANDIDATE if st == STAGE_FAILURE_OR_CAPTURE else st
    if effective_stage != STAGE_SCRUBBED_CANDIDATE:
        _deny_here(
            DENY_INVALID_STAGE,
            f"illegal stage for terminal promote: {effective_stage!r}",
        )

    promotion_id = f"promo-{uuid.uuid4().hex[:12]}"
    decision = _build_decision_row(
        accepted=True,
        promotion_id=promotion_id,
        st=st,
        dest=dest,
        owner=owner,
        label=label,
        provenance=provenance,
        redaction_profile=redaction_profile,
        split=split,
        source=source,
        source_path=source_path,
        source_hash=source_hash,
        source_trace=source_trace or "",
        session_thread_id=session_thread_id,
        review=review,
        notes=notes,
        dry_run=dry_run,
        denial_reason=None,
        candidate_class="scrubbed_candidate",
        human_rollup=human_rollup,
    )

    dest_dir = _destination_dir(repo, dest)
    dest_path = dest_dir / f"{promotion_id}.json"
    decision_path = _persist_decision(repo, decision, dry_run=dry_run)

    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "promotion_id": promotion_id,
        "destination": dest,
        "label": label.strip(),
        "split_group_id": split,
        "redaction_profile": redaction_profile,
        "source_bundle_hash": source_hash,
        "bundle_ref": {
            "case_id": source.get("case_id"),
            "session_thread_id": session_thread_id or None,
            "path": str(source_path),
        },
        "created_at": decision["created_at"],
    }

    if not dry_run and dest != DEST_REJECT:
        _atomic_write(dest_path, artifact)

    return {
        "decision": decision,
        "decision_path": decision_path,
        "artifact_path": str(dest_path) if dest != DEST_REJECT else None,
        "accepted": True,
        "denial_reason": None,
        "dry_run": dry_run,
    }


__all__ = [
    "DENIAL_REASONS",
    "DENY_ANTIPATTERN_POSITIVE",
    "DENY_HUMAN_LEG",
    "DENY_HUMAN_SOLE_GOLD",
    "DENY_INVALID_DESTINATION",
    "DENY_INVALID_STAGE",
    "DENY_MISSING_FIELD",
    "DENY_POPULARITY_GOLD",
    "DENY_PROVENANCE",
    "DENY_SCHEMA",
    "DENY_SILENT_GOLD",
    "DENY_SOURCE_MISSING",
    "DENY_SPLIT_CONTAMINATION",
    "DENY_SYNTHETIC_UNQUARANTINED",
    "DENY_UNRESOLVED_DISPUTE",
    "DEST_FIXTURE_LANE_A",
    "DEST_HARD_NEGATIVE",
    "DEST_OBSERVABILITY_FIXTURE",
    "DEST_PREFERENCE_PAIR",
    "DEST_QUARANTINE",
    "DEST_REJECT",
    "STAGE_FAILURE_OR_CAPTURE",
    "STAGE_SCRUBBED_CANDIDATE",
    "TERMINAL_DESTINATIONS",
    "PromoteError",
    "promote",
]
