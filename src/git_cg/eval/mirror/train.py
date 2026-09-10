"""S4 train-projection helpers (Q18 / D18 / D28 / P2-4 / S4-F).

Q18 decision (recorded): **one** owner train dataset with explicit
``label`` + ``split`` metadata — **not** separate positive/negative datasets.

Safeguards (must hold for every train projection):

* ``label`` is mandatory and closed: ``positive`` | ``negative``.
* Unlabeled / unknown rows are **excluded** from ``positive_gold``.
* Negative / antipattern rows **never** join ``positive_gold``.
* Each row carries ``split`` (or ``split_group_id``), ``redaction_profile``,
  and provenance/source markers.
* Train lake is dual-axis corpus retention only — **never** CI sole green /
  product accept authority.

Pure offline builders — no network, no Opik import.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final

from git_cg.eval.mirror.redaction import sanitize_export_tree

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


class TrainProjectionError(ValueError):
    """Train row failed dual-axis safeguards (export_validation class equivalent)."""


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


def project_train_row(
    bundle: Mapping[str, Any],
    *,
    dataset_id: str = TRAIN_DATASET_ID,
    default_split: str = "train",
) -> dict[str, Any] | None:
    """Project one redacted bundle into a train-lake row, or ``None`` if unlabeled.

    Expects R14 redaction to have already run. Does **not** invent labels
    from telemetry or user-acceptance popularity signals.
    """
    meta = dict(bundle.get("meta") or {})
    label = normalize_train_label(
        bundle.get("train_label") or meta.get("train_label") or meta.get("label") or bundle.get("label")
    )
    if label is None:
        return None

    split = (
        bundle.get("split")
        or meta.get("split")
        or meta.get("split_group_id")
        or bundle.get("split_group_id")
        or default_split
    )
    split_s = str(split).strip() or default_split
    profile = meta.get("redaction_profile") or bundle.get("redaction_profile")
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
        "redaction_profile": str(profile) if profile is not None else None,
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
    return cleaned if isinstance(cleaned, dict) else row


def filter_positive_gold(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return only labeled positive rows; reject negatives and unlabeled.

    Safeguard: antipattern / negative never silent-merge into ``positive_gold``.
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

    Returns labeled ``rows``, ``positive_gold``, ``negatives``, and
    ``excluded_unlabeled``. Fails closed on positive/negative bundle_id overlap.
    """
    rows: list[dict[str, Any]] = []
    excluded = 0
    for bundle in bundles:
        row = project_train_row(bundle, dataset_id=dataset_id, default_split=default_split)
        if row is None:
            excluded += 1
            continue
        rows.append(row)

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
        "excluded_unlabeled": excluded,
        "ci_sole_green": False,
        "product_accept_authority": False,
        "authority": "corpus_retention",
    }
    cleaned = sanitize_export_tree(projected)
    return cleaned if isinstance(cleaned, dict) else projected
