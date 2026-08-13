"""metric_catalog_v0 loader."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from git_cg.eval.paths import CATALOG_PATH


class CatalogError(ValueError):
    """Catalog load/integrity failure."""


@lru_cache(maxsize=1)
def load_metric_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.is_file():
        raise CatalogError(f"missing catalog: {CATALOG_PATH}")
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if data.get("catalog_id") != "metric_catalog_v0":
        raise CatalogError("catalog_id must be metric_catalog_v0")
    metrics = data.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise CatalogError("catalog metrics must be a non-empty list")
    for row in metrics:
        for key in ("metric_id", "polarity", "authority"):
            if key not in row:
                raise CatalogError(f"catalog row missing {key}: {row!r}")
    laws = {law.get("law_id") for law in data.get("laws", [])}
    for required in ("M10", "M11"):
        if required not in laws:
            raise CatalogError(f"catalog laws must include {required}")
    return data


def metric_ids() -> set[str]:
    return {row["metric_id"] for row in load_metric_catalog()["metrics"]}
