"""metric_catalog_v0 loader."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from typing import Any

from git_cg.eval.enums import AUTHORITY, FAMILY, POLARITY, SEVERITY, SOURCE
from git_cg.eval.paths import CATALOG_PATH

_ROW_ENUMS: dict[str, tuple[str, ...]] = {
    "polarity": POLARITY,
    "authority": AUTHORITY,
    "family": FAMILY,
    "severity": SEVERITY,
    "source_default": SOURCE,
}


class CatalogError(ValueError):
    """Catalog load/integrity failure."""


@lru_cache(maxsize=1)
def _load_metric_catalog_cached() -> dict[str, Any]:
    """Load a governed artifact from the Layer-A store (fail closed)."""
    if not CATALOG_PATH.is_file():
        raise CatalogError(f"missing catalog: {CATALOG_PATH}")
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if data.get("catalog_id") != "metric_catalog_v0":
        raise CatalogError("catalog_id must be metric_catalog_v0")
    metrics = data.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise CatalogError("catalog metrics must be a non-empty list")
    seen: set[str] = set()
    for row in metrics:
        if not isinstance(row, dict):
            raise CatalogError(f"catalog row must be an object: {row!r}")
        for key in ("metric_id", "polarity", "authority"):
            if key not in row:
                raise CatalogError(f"catalog row missing {key}: {row!r}")
        metric_id = row["metric_id"]
        if not isinstance(metric_id, str) or not metric_id:
            raise CatalogError(f"invalid metric_id: {metric_id!r}")
        if metric_id in seen:
            raise CatalogError(f"duplicate metric_id: {metric_id}")
        seen.add(metric_id)
        for key, allowed in _ROW_ENUMS.items():
            if key in row and row[key] not in allowed:
                raise CatalogError(f"{metric_id}: invalid {key}={row[key]!r}")
    laws = {law.get("law_id") for law in data.get("laws", []) if isinstance(law, dict)}
    for required in ("M10", "M11"):
        if required not in laws:
            raise CatalogError(f"catalog laws must include {required}")
    return data


def load_metric_catalog() -> dict[str, Any]:
    """Return a private deep copy of the validated catalog."""
    return copy.deepcopy(_load_metric_catalog_cached())


def metric_ids() -> set[str]:
    """Return the closed set of metric ids from the pinned catalog."""
    return {row["metric_id"] for row in load_metric_catalog()["metrics"]}


def clear_catalog_cache() -> None:
    """Test helper: drop the cached catalog object."""
    _load_metric_catalog_cached.cache_clear()
