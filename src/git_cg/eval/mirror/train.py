"""Train projection helpers (Q18 / D18 / D28 / P2-4 / S4-F / S8c-D).

Q18 decision (recorded): **one** owner train dataset with explicit
``label`` + ``split`` metadata — **not** separate positive/negative datasets.

Safeguards (must hold for every train projection):

* ``label`` is mandatory and closed: ``positive`` | ``negative``.
* Unlabeled / unknown rows are **excluded** from ``positive_gold``.
* Negative / antipattern rows **never** join ``positive_gold``.
* Each row carries ``split`` (or ``split_group_id``), ``redaction_profile``,
  and provenance/source markers.
* **Fail-closed export profiles:** every emitted row carries a valid
  closed-vocabulary export ``redaction_profile`` (enum minus
  ``raw_dev_unsafe``). Rows with missing, conflicting (top-level vs meta),
  invalid, unknown, or ``raw_dev_unsafe`` profiles are **excluded** and
  counted under ``excluded_profile`` — never silently emitted, never
  invented, never ``None``.
* Train lake is dual-axis corpus retention only — **never** CI sole green /
  product accept authority.

Pure offline builders — no network, no Opik import.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final, NamedTuple

from git_cg.eval.enums import RedactionProfile
from git_cg.eval.mirror.redaction import _export_profile_or_none, sanitize_export_tree

__all__ = [
    "POSITIVE_GOLD",
    "TRAIN_DATASET_ID",
    "TRAIN_LABELS",
    "TrainProjectionError",
    "build_train_projection",
    "filter_positive_gold",
    "normalize_train_label",
    "project_train_row",
]

#: Single owner train dataset id (Q18 — metadata filter, not two datasets).
TRAIN_DATASET_ID: Final[str] = "cm-eval-owner-train"

#: Closed train label vocabulary.
TRAIN_LABELS: Final[frozenset[str]] = frozenset({"positive", "negative"})

#: Canonical positive projection name (never receives negatives / unlabeled).
POSITIVE_GOLD: Final[str] = "positive_gold"

#: Exclusion reasons carried by the private projection result.
_REASON_OK: Final[str] = "ok"
_REASON_UNLABELED: Final[str] = "excluded_unlabeled"
_REASON_PROFILE: Final[str] = "excluded_profile"


class TrainProjectionError(ValueError):
    """Train row failed dual-axis safeguards (export_validation class equivalent)."""


class _TrainRowResult(NamedTuple):
    """Private reason-carrying projection outcome.

    ``row`` is ``None`` unless ``reason == "ok"``.
    """

    row: dict[str, Any] | None
    reason: str


def normalize_train_label(raw: object) -> str | None:
    """Map common aliases to closed ``positive`` / ``negative`` labels.

    Returns ``None`` for missing/unknown labels (fail-closed for positive_gold).
    """
    if raw is None:
        return None
    token = str(raw).strip().lower().replace("-", "_")
    if not token or token in {"unlabeled", "unknown", "none", "null"}:
        return None
    if token in {"positive", "pos", "positive_gold", "train_positive", "preference_chosen"}:
        return "positive"
    if token in {
        "negative",
        "neg",
        "hard_negative",
        "train_negative",
        "preference_rejected",
        "antipattern",
        "antipattern_vault",
    }:
        return "negative"
    if token in TRAIN_LABELS:
        return token
    return None


def _profile_side(raw: object) -> tuple[bool, RedactionProfile | None]:
    """Classify one profile source as ``(present, export-valid profile)``.

    ``present`` is False only for missing / empty / whitespace-only tokens.
    Invalid, unknown, or ``raw_dev_unsafe`` tokens are present-but-invalid
    (fail closed).
    """
    if raw is None:
        return False, None
    token = str(raw).strip()
    if not token:
        return False, None
    return True, _export_profile_or_none(token)


def _resolve_train_profile(
    bundle: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> RedactionProfile | None:
    """Apply the fail-closed export-profile matrix to one bundle.

    Top-level and ``meta`` profiles are read independently (whitespace
    stripped; empty counts as missing):

    * both missing                    → excluded (no export vocabulary)
    * exactly one present and valid   → accepted
    * both present, valid, and equal  → accepted
    * both present but unequal        → excluded (conflict)
    * any present-but-invalid side    → excluded (unknown / raw_dev_unsafe)

    Returns the resolved export-capable profile, or ``None`` when the row
    must be excluded.
    """
    top_present, top_profile = _profile_side(bundle.get("redaction_profile"))
    meta_present, meta_profile = _profile_side(meta.get("redaction_profile"))
    if top_present and top_profile is None:
        return None
    if meta_present and meta_profile is None:
        return None
    if not top_present and not meta_present:
        return None
    if top_present and meta_present and top_profile is not meta_profile:
        return None
    return top_profile if top_present else meta_profile


def _resolve_train_label(
    bundle: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> object:
    """Return the first present label source by exact precedence.

    Order: ``bundle.train_label`` → ``meta.train_label`` → ``meta.label`` →
    ``bundle.label``. Presence means the value is not ``None``; an earlier
    source that is present but empty/falsey wins (fail-closed: no silent
    fallback to later sources).
    """
    for source in (
        bundle.get("train_label"),
        meta.get("train_label"),
        meta.get("label"),
        bundle.get("label"),
    ):
        if source is not None:
            return source
    return None


def _project_train_row_result(
    bundle: Mapping[str, Any],
    *,
    dataset_id: str = TRAIN_DATASET_ID,
    default_split: str = "train",
) -> _TrainRowResult:
    """Project one redacted bundle into a train-lake row, with exclusion reason.

    Reasons: ``ok`` (row emitted), ``excluded_unlabeled`` (missing/unknown
    label — the profile is never inspected for these rows), and
    ``excluded_profile`` (profile matrix rejected the row).

    Expects R14 redaction to have already run. Does **not** invent labels
    from telemetry or user-acceptance popularity signals.
    """
    meta = dict(bundle.get("meta") or {})
    label = normalize_train_label(_resolve_train_label(bundle, meta))
    if label is None:
        return _TrainRowResult(None, _REASON_UNLABELED)

    profile = _resolve_train_profile(bundle, meta)
    if profile is None:
        return _TrainRowResult(None, _REASON_PROFILE)

    split = (
        bundle.get("split")
        or meta.get("split")
        or meta.get("split_group_id")
        or bundle.get("split_group_id")
        or default_split
    )
    split_s = str(split).strip() or default_split
    provenance = (
        meta.get("provenance_label") or bundle.get("provenance_label") or meta.get("provenance") or "owner_train"
    )
    regime = meta.get("regime") or bundle.get("regime")
    artifact_class = bundle.get("artifact_class") or meta.get("artifact_class")

    row: dict[str, Any] = {
        "dataset_id": str(dataset_id or TRAIN_DATASET_ID),
        "label": label,
        "split": split_s,
        "split_group_id": str(meta.get("split_group_id") or bundle.get("split_group_id") or split_s),
        "redaction_profile": profile.value,
        "provenance_label": str(provenance),
        "source": "local_precompute",
        "bundle_id": bundle.get("id"),
        "artifact_class": artifact_class,
        "regime": regime,
        "gate": bundle.get("gate") or {},
        "score_card": bundle.get("score_card") or bundle.get("product_card") or {},
        # Dual-axis reminder on every row (docs/tests assert this).
        "authority": "corpus_retention",
        "ci_sole_green": False,
        "product_accept_authority": False,
    }
    cleaned = sanitize_export_tree(row)
    return _TrainRowResult(cleaned if isinstance(cleaned, dict) else row, _REASON_OK)


def project_train_row(
    bundle: Mapping[str, Any],
    *,
    dataset_id: str = TRAIN_DATASET_ID,
    default_split: str = "train",
) -> dict[str, Any] | None:
    """Project one redacted bundle into a train-lake row, or ``None``.

    Returns ``None`` when the row is unlabeled **or** failed the
    fail-closed export-profile matrix. Every emitted row carries a valid
    closed-vocabulary export ``redaction_profile`` (enum minus
    ``raw_dev_unsafe``) — never ``None``, never invented, never
    ``raw_dev_unsafe``.
    """
    return _project_train_row_result(bundle, dataset_id=dataset_id, default_split=default_split).row


def filter_positive_gold(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return only labeled positive rows; reject negatives and unlabeled.

    Safeguards: antipattern / negative rows never silent-merge into
    ``positive_gold`` (S6-G06), and directly supplied positive rows without
    a valid export profile (missing / empty / whitespace / invalid / unknown
    / ``raw_dev_unsafe``) are rejected fail-closed (S8c-D).
    """
    out: list[dict[str, Any]] = []
    for raw in rows:
        label = normalize_train_label(raw.get("label") or raw.get("train_label"))
        if label != "positive":
            continue
        # Belt-and-braces: refuse if explicit negative markers present.
        regime = str(raw.get("regime") or "").lower()
        if "antipattern" in regime:
            continue
        # Positive gold must carry a valid export profile (S8c-D).
        if _export_profile_or_none(raw.get("redaction_profile")) is None:
            continue
        row = dict(raw)
        row["label"] = "positive"
        row["projection"] = POSITIVE_GOLD
        cleaned = sanitize_export_tree(row)
        out.append(cleaned if isinstance(cleaned, dict) else row)
    return out


def build_train_projection(
    bundles: Iterable[Mapping[str, Any]],
    *,
    dataset_id: str = TRAIN_DATASET_ID,
    default_split: str = "train",
) -> dict[str, Any]:
    """Build Q18 single-dataset train projection with dual-axis safeguards.

    Returns labeled ``rows``, ``positive_gold``, ``negatives``, and the
    disjoint counters ``excluded_unlabeled`` / ``excluded_profile`` (S8c-D).
    Fails closed on positive/negative bundle_id overlap. Every emitted row
    carries a valid closed-vocabulary export profile.
    """
    rows: list[dict[str, Any]] = []
    excluded_unlabeled = 0
    excluded_profile = 0
    for bundle in bundles:
        result = _project_train_row_result(bundle, dataset_id=dataset_id, default_split=default_split)
        if result.reason == _REASON_UNLABELED:
            excluded_unlabeled += 1
            continue
        if result.reason == _REASON_PROFILE:
            excluded_profile += 1
            continue
        rows.append(result.row)

    positives = filter_positive_gold(rows)
    negatives = [r for r in rows if r.get("label") == "negative"]
    # Invariant: no overlap by bundle id between positive_gold and negatives.
    # Ignore missing/None ids — those are not a real collision signal and would
    # false-positive whenever two unlabeled-id rows land in opposite classes.
    pos_ids = {r.get("bundle_id") for r in positives if r.get("bundle_id") not in (None, "")}
    neg_ids = {r.get("bundle_id") for r in negatives if r.get("bundle_id") not in (None, "")}
    if pos_ids & neg_ids:
        raise TrainProjectionError("positive_gold/negative bundle_id overlap")

    projected = {
        "dataset_id": str(dataset_id or TRAIN_DATASET_ID),
        "q18": "single_dataset_label_split_metadata",
        "rows": rows,
        "positive_gold": positives,
        "negatives": negatives,
        "excluded_unlabeled": excluded_unlabeled,
        "excluded_profile": excluded_profile,
        "ci_sole_green": False,
        "product_accept_authority": False,
        "authority": "corpus_retention",
    }
    cleaned = sanitize_export_tree(projected)
    return cleaned if isinstance(cleaned, dict) else projected
