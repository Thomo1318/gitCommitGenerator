"""Dataset ID alias map (§7.3.2).

Stable plan ids are authoritative. Historical #217 body aliases resolve into them.
"""

from __future__ import annotations

from typing import Final

# stable_id -> self and accepted aliases
DATASET_ID_ALIASES: Final[dict[str, frozenset[str]]] = {
    "cm-eval-fixtures-core": frozenset({"cm-eval-fixtures-core"}),
    "204-archive": frozenset({"204-archive", "cm-eval-204-archive"}),
    "acceptpath-live": frozenset({"acceptpath-live", "cm-eval-acceptpath-live"}),
    "gold-counter-integrity": frozenset({"gold-counter-integrity", "cm-eval-gold-counter-integrity"}),
    "semantic-cohort": frozenset({"semantic-cohort", "cm-eval-semantic-cohort"}),
    "regression-queue": frozenset({"regression-queue", "cm-eval-regression-queue"}),
    "dogfood-rolling": frozenset({"dogfood-rolling"}),
    "train-positive": frozenset({"train-positive"}),
    "train-negative": frozenset({"train-negative"}),
    "judge-meta-hm": frozenset({"judge-meta-hm"}),
}

_ALIAS_TO_STABLE: Final[dict[str, str]] = {
    alias: stable for stable, aliases in DATASET_ID_ALIASES.items() for alias in aliases
}


class DatasetAliasError(ValueError):
    """Unknown or ambiguous dataset id / alias."""


def resolve_dataset_id(dataset_id: str) -> str:
    """Resolve an alias or stable id to the stable dataset_id.

    Raises:
        DatasetAliasError: when the id is empty or unknown.
    """
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise DatasetAliasError("dataset_id must be a non-empty string")
    key = dataset_id.strip()
    try:
        return _ALIAS_TO_STABLE[key]
    except KeyError as exc:
        known = ", ".join(sorted(_ALIAS_TO_STABLE))
        raise DatasetAliasError(f"unknown dataset id or alias: {dataset_id!r}; known: {known}") from exc


def canonicalize_dataset_id(dataset_id: str) -> str:
    """Alias of :func:`resolve_dataset_id` for call-site clarity."""
    return resolve_dataset_id(dataset_id)
