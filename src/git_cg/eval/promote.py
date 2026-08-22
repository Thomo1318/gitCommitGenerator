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

Import law: import-light. Path / schema helpers are lazy.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

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
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.hint = hint
        self.denial_reason = denial_reason


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _promotions_dir(repo: Path) -> Path:
    """Governed promotions store under ``.eval/index/promotions/`` (cache+audit)."""
    from git_cg.eval.binding.paths import LayerAPathError, index_dir

    try:
        return index_dir(repo) / "promotions"
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _acceptpath_dir(repo: Path) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, acceptpath_bundles_dir

    try:
        return acceptpath_bundles_dir(repo)
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _atomic_write(path: Path, payload: dict[str, Any]) -> Path:
    from git_cg.eval.binding.paths import LayerAPathError, atomic_write_json

    try:
        return atomic_write_json(path, payload)
    except LayerAPathError as exc:
        raise PromoteError(str(exc), code="EVAL_STORE_INTEGRITY", exit_code=4) from exc


def _load_json(path: Path, *, code: str = "EVAL_STORE_INTEGRITY", exit_code: int = 4) -> dict[str, Any]:
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
    from git_cg.eval.corpus.canonical import content_sha256

    return content_sha256(bundle)


def _extract_trace_id(bundle: dict[str, Any]) -> str:
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    binding = meta.get("binding") if isinstance(meta.get("binding"), dict) else {}
    for candidate in (binding.get("trace_id"), meta.get("trace_id"), bundle.get("trace_id")):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_split_group(bundle: dict[str, Any], explicit: str | None) -> str:
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
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    markers = [
        meta.get("synthetic"),
        meta.get("expand_with_ai"),
        meta.get("source_kind"),
        meta.get("producer"),
        meta_flags.get("synthetic"),
        meta_flags.get("expand_with_ai"),
        meta_flags.get("source_kind"),
        bundle.get("provenance_label"),
    ]
    # Explicit boolean flags win.
    for key in ("synthetic", "expand_with_ai"):
        if meta.get(key) is True or meta_flags.get(key) is True:
            return True
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
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    tokens = {
        label.lower(),
        str(meta.get("train_label") or "").lower(),
        str(meta.get("label") or "").lower(),
        str(bundle.get("provenance_label") or "").lower(),
    }
    return any("antipattern" in t for t in tokens if t)


def _destination_dir(repo: Path, destination: str) -> Path:
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
    for path in sorted(root.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("split_group_id") != split_group_id:
            continue
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
        for path in sorted(root.glob("*.json")):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("split_group_id") != split_group_id:
                continue
            if row.get("accepted") and row.get("destination") == DEST_HARD_NEGATIVE:
                conflicts.append(f"{row.get('promotion_id')}:hard_negative_vs_positive")
    return sorted(set(conflicts))


def _deny(reason: str, message: str, *, hint: str | None = None) -> PromoteError:
    return PromoteError(
        message,
        code="EVAL_USAGE",
        exit_code=2,
        denial_reason=reason,
        hint=hint,
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
    if not session_thread_id:
        raise _deny(
            DENY_MISSING_FIELD,
            "source bundle missing session_thread_id (required on promote)",
            hint="Replay/bind the bundle so session_thread_id is present, or pass a lineage-complete source.",
        )
    if not source_trace:
        raise _deny(
            DENY_MISSING_FIELD,
            "source bundle missing trace_id (required on promote)",
            hint="Ensure meta.binding.trace_id (or meta.trace_id) is present on the source bundle.",
        )
    split = _extract_split_group(source, split_group_id)

    review = _load_review(repo, review_id)
    label_l = label.strip().lower()
    wants_gold = label_l in _GOLD_LABELS or allow_golden

    # --- Forbidden paths (explicit denial taxonomy) ---
    if popularity_signal and wants_gold:
        raise _deny(
            DENY_POPULARITY_GOLD,
            "popularity/user_acceptance cannot promote golden",
            hint="Gold requires deterministic gate eligibility + owner provenance, not popularity.",
        )

    if wants_gold and dest not in {DEST_REJECT, DEST_QUARANTINE}:
        # Human review is advisory and can never be the sole golden promoter,
        # even when an adjudicated review_id is attached.
        if review is not None:
            raise _deny(
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
            raise _deny(
                DENY_SILENT_GOLD,
                "silent gold mint from production acceptance/human provenance is forbidden",
                hint="Use observability_fixture / hard_negative / quarantine, not gold labels from accept/review.",
            )
        # Gold-final minting is not a Slice-6 automatic destination. fixture_lane_a
        # is a *candidate* lane only — refuse gold labels into non-quarantine paths
        # unless destination is explicitly reject/quarantine.
        if dest in {DEST_FIXTURE_LANE_A, DEST_PREFERENCE_PAIR, DEST_OBSERVABILITY_FIXTURE, DEST_HARD_NEGATIVE}:
            raise _deny(
                DENY_SILENT_GOLD,
                f"gold/golden labels cannot auto-mint via destination={dest!r}",
                hint="Gold-final requires the full gate eligibility path; use non-gold labels for candidate lanes.",
            )

    if _is_synthetic_expand(source, {"synthetic": source.get("meta")}) and dest not in {
        DEST_QUARANTINE,
        DEST_REJECT,
    }:
        raise _deny(
            DENY_SYNTHETIC_UNQUARANTINED,
            "synthetic Expand-with-AI rows require quarantine before other destinations",
            hint="Promote to quarantine first; human/schema validate; then re-promote.",
        )

    if _is_antipattern(label.strip(), source) and (dest == DEST_FIXTURE_LANE_A or label_l in _POSITIVE_DEST_LABELS):
        raise _deny(
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
        raise _deny(
            DENY_SPLIT_CONTAMINATION,
            f"split_group_id contamination: {split} already promoted as {conflicts}",
            hint="Keep preference/replay variants in one split_group; do not cross destinations.",
        )

    # Stage transition: failure_or_capture must pass through scrubbed_candidate.
    effective_stage = STAGE_SCRUBBED_CANDIDATE if st == STAGE_FAILURE_OR_CAPTURE else st
    if effective_stage != STAGE_SCRUBBED_CANDIDATE:
        raise _deny(
            DENY_INVALID_STAGE,
            f"illegal stage for terminal promote: {effective_stage!r}",
        )

    promotion_id = f"promo-{uuid.uuid4().hex[:12]}"
    decision: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "promotion_id": promotion_id,
        "accepted": True,
        "from_stage": st,
        "via_stage": STAGE_SCRUBBED_CANDIDATE,
        "destination": dest,
        "owner": owner.strip(),
        "label": label.strip(),
        "provenance": provenance.strip(),
        "redaction_profile": redaction_profile,
        "split_group_id": split,
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
        "denial_reason": None,
        "notes": notes.strip() if notes and notes.strip() else None,
        "created_at": _utc_now(),
        "dry_run": dry_run,
    }

    # Drop null optional keys for cleaner audit rows.
    decision = {k: v for k, v in decision.items() if v is not None}

    dest_dir = _destination_dir(repo, dest)
    dest_path = dest_dir / f"{promotion_id}.json"
    decision_path = _promotions_dir(repo) / f"{promotion_id}.json"

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

    if not dry_run:
        _atomic_write(decision_path, decision)
        if dest != DEST_REJECT:
            _atomic_write(dest_path, artifact)

    return {
        "decision": decision,
        "decision_path": str(decision_path),
        "artifact_path": str(dest_path) if dest != DEST_REJECT else None,
        "accepted": True,
        "denial_reason": None,
        "dry_run": dry_run,
    }


__all__ = [
    "DENY_ANTIPATTERN_POSITIVE",
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
