"""Helpers to emit catalog-aligned ScoreResultV1 rows."""

from __future__ import annotations

from typing import Any

from git_cg.eval.catalog import load_metric_catalog
from git_cg.eval.enums import Authority, Family, Polarity, Severity, Source
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import live_pin_refs

_CATALOG_INDEX: dict[str, dict[str, Any]] | None = None


def _catalog_index() -> dict[str, dict[str, Any]]:
    """Build and cache an index of metric catalogue rows by metric ID.
    
    Returns:
        dict[str, dict[str, Any]]: The cached metric catalogue index.
    """
    global _CATALOG_INDEX
    if _CATALOG_INDEX is None:
        cat = load_metric_catalog()
        _CATALOG_INDEX = {row["metric_id"]: row for row in cat["metrics"]}
    return _CATALOG_INDEX


def clear_catalog_index() -> None:
    """
    Clear the cached metric catalog index.
    
    Primarily used to reset catalog state between tests.
    """
    global _CATALOG_INDEX
    _CATALOG_INDEX = None


def metric_row(metric_id: str) -> dict[str, Any] | None:
    """Return the catalog entry for a metric identifier.
    
    Parameters:
    	metric_id (str): Identifier of the metric to look up.
    
    Returns:
    	dict[str, Any] | None: The catalog row for the metric, or `None` when no matching entry exists.
    """
    return _catalog_index().get(metric_id)


def make_score(
    metric_id: str,
    value: bool | int | float,
    *,
    passed: bool | None = None,
    reason: str | None = None,
    evidence: dict[str, Any] | None = None,
    failure_ids: list[str] | None = None,
    product_authority: str | None = None,
    pin_refs: list[str] | None = None,
    severity: Severity | str | None = None,
    name: str | None = None,
) -> ScoreResultV1:
    """
    Build a catalog-aligned score result for a metric.
    
    Parameters:
    	metric_id (str): Identifier of a metric defined in the catalog.
    	value (bool | int | float): Observed metric value.
    	passed (bool | None): Explicit pass status; inferred from the metric polarity when omitted.
    	severity (Severity | str | None): Severity override for the result.
    
    Returns:
    	ScoreResultV1: A populated score result using catalog metadata and supplied overrides.
    
    Raises:
    	KeyError: If `metric_id` is not defined in the catalog.
    """
    row = metric_row(metric_id)
    if row is None:
        raise KeyError(f"unknown metric_id not in catalog: {metric_id}")

    polarity = Polarity(row["polarity"])
    authority = Authority(row["authority"])
    source = Source(row.get("source_default") or "local_wrapper")
    family = Family(row["family"]) if row.get("family") else None
    sev_raw = severity if severity is not None else row.get("severity")
    sev = Severity(sev_raw) if sev_raw is not None else None

    if passed is None:
        if polarity is Polarity.PASS_FAIL:
            passed = bool(value)
        elif polarity is Polarity.LOWER_IS_BETTER:
            passed = float(value) <= 0.0
        else:
            passed = float(value) >= 1.0

    return ScoreResultV1(
        metric_id=metric_id,
        polarity=polarity,
        authority=authority,
        source=source,
        value=value,
        name=name or row.get("name"),
        family=family,
        passed=passed,
        severity=sev,
        reason=reason,
        evidence=evidence,
        failure_ids=failure_ids,
        product_authority=product_authority,
        pin_refs=pin_refs if pin_refs is not None else live_pin_refs(),
    )
