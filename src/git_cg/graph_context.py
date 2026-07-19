"""
Sync adapter over ``code_review_graph.tools`` (ADR-0005 Phase 1).

Wraps graph build/query helpers with latency measurement and ``graph_retry``.
Does not force graph builds on the commit critical path when disabled.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from git_cg.retries import graph_retry


class GraphOutcome(StrEnum):
    """Deterministic graph adapter outcome."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class GraphOperationResult:
    """Structured result for a graph adapter call."""

    ok: bool
    operation: str
    outcome: GraphOutcome = GraphOutcome.OK
    latency_ms: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["outcome"] = str(self.outcome)
        return payload


def _timed_call(operation: str, fn, *args, **kwargs) -> GraphOperationResult:
    started = time.perf_counter()
    try:
        data = fn(*args, **kwargs)
        if not isinstance(data, dict):
            data = {"result": data}
        return GraphOperationResult(
            ok=True,
            operation=operation,
            outcome=GraphOutcome.OK,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            data=data,
        )
    except Exception as exc:
        return GraphOperationResult(
            ok=False,
            operation=operation,
            outcome=GraphOutcome.UNAVAILABLE,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 3),
            error=str(exc),
            error_type=type(exc).__name__,
        )


@graph_retry
def _build_or_update_graph_raw(
    *,
    repo_root: str | None,
    full_rebuild: bool,
    base: str,
    postprocess: str,
) -> dict[str, Any]:
    from code_review_graph.tools import build_or_update_graph

    return build_or_update_graph(
        full_rebuild=full_rebuild,
        repo_root=repo_root,
        base=base,
        postprocess=postprocess,
    )


@graph_retry
def _list_graph_stats_raw(*, repo_root: str | None) -> dict[str, Any]:
    from code_review_graph.tools import list_graph_stats

    return list_graph_stats(repo_root=repo_root)


@graph_retry
def _detect_changes_raw(
    *,
    repo_root: str | None,
    base: str,
    changed_files: list[str] | None,
    include_source: bool,
    max_depth: int,
    detail_level: str,
) -> dict[str, Any]:
    from code_review_graph.tools import detect_changes_func

    return detect_changes_func(
        base=base,
        changed_files=changed_files,
        include_source=include_source,
        max_depth=max_depth,
        repo_root=repo_root,
        detail_level=detail_level,
    )


@graph_retry
def _impact_radius_raw(
    *,
    repo_root: str | None,
    changed_files: list[str] | None,
    max_depth: int,
    max_results: int,
    base: str,
    detail_level: str,
) -> dict[str, Any]:
    from code_review_graph.tools import get_impact_radius

    return get_impact_radius(
        changed_files=changed_files,
        max_depth=max_depth,
        max_results=max_results,
        repo_root=repo_root,
        base=base,
        detail_level=detail_level,
    )


@graph_retry
def _affected_flows_raw(
    *,
    repo_root: str | None,
    changed_files: list[str] | None,
    base: str,
) -> dict[str, Any]:
    from code_review_graph.tools import get_affected_flows_func

    return get_affected_flows_func(
        changed_files=changed_files,
        base=base,
        repo_root=repo_root,
    )


@graph_retry
def _review_context_raw(
    *,
    repo_root: str | None,
    changed_files: list[str] | None,
    max_depth: int,
    include_source: bool,
    max_lines_per_file: int,
    base: str,
    detail_level: str,
) -> dict[str, Any]:
    from code_review_graph.tools import get_review_context

    return get_review_context(
        changed_files=changed_files,
        max_depth=max_depth,
        include_source=include_source,
        max_lines_per_file=max_lines_per_file,
        repo_root=repo_root,
        base=base,
        detail_level=detail_level,
    )


@graph_retry
def _query_graph_raw(
    *,
    pattern: str,
    target: str,
    repo_root: str | None,
    detail_level: str,
) -> dict[str, Any]:
    from code_review_graph.tools import query_graph

    return query_graph(
        pattern=pattern,
        target=target,
        repo_root=repo_root,
        detail_level=detail_level,
    )


def refresh_graph(
    repo_root: str | None = None,
    *,
    full_rebuild: bool = False,
    base: str = "HEAD",
    postprocess: str = "minimal",
) -> GraphOperationResult:
    """
    Build or incrementally update the per-repo code-review-graph.

    Default ``postprocess='minimal'`` keeps the commit path light (signatures+FTS).
    """
    return _timed_call(
        "refresh_graph",
        _build_or_update_graph_raw,
        repo_root=repo_root,
        full_rebuild=full_rebuild,
        base=base,
        postprocess=postprocess,
    )


def graph_stats(repo_root: str | None = None) -> GraphOperationResult:
    """Return aggregate graph statistics (or a typed failure)."""
    return _timed_call("graph_stats", _list_graph_stats_raw, repo_root=repo_root)


def detect_changes(
    repo_root: str | None = None,
    *,
    base: str = "HEAD",
    changed_files: list[str] | None = None,
    include_source: bool = False,
    max_depth: int = 2,
    detail_level: str = "standard",
) -> GraphOperationResult:
    """One-shot review payload: risk, changed functions, flows, test gaps."""
    return _timed_call(
        "detect_changes",
        _detect_changes_raw,
        repo_root=repo_root,
        base=base,
        changed_files=changed_files,
        include_source=include_source,
        max_depth=max_depth,
        detail_level=detail_level,
    )


def impact_radius(
    repo_root: str | None = None,
    *,
    changed_files: list[str] | None = None,
    max_depth: int = 2,
    max_results: int = 500,
    base: str = "HEAD",
    detail_level: str = "standard",
) -> GraphOperationResult:
    """Blast-radius query for ranking/evidence enrichment."""
    return _timed_call(
        "impact_radius",
        _impact_radius_raw,
        repo_root=repo_root,
        changed_files=changed_files,
        max_depth=max_depth,
        max_results=max_results,
        base=base,
        detail_level=detail_level,
    )


def affected_flows(
    repo_root: str | None = None,
    *,
    changed_files: list[str] | None = None,
    base: str = "HEAD",
) -> GraphOperationResult:
    """Flows touched by the given changed files."""
    return _timed_call(
        "affected_flows",
        _affected_flows_raw,
        repo_root=repo_root,
        changed_files=changed_files,
        base=base,
    )


def review_context_pack(
    repo_root: str | None = None,
    *,
    changed_files: list[str] | None = None,
    max_depth: int = 2,
    include_source: bool = True,
    max_lines_per_file: int = 200,
    base: str = "HEAD",
    detail_level: str = "standard",
) -> GraphOperationResult:
    """Pre-assembled review context pack for prompt enrichment (later phases)."""
    return _timed_call(
        "review_context_pack",
        _review_context_raw,
        repo_root=repo_root,
        changed_files=changed_files,
        max_depth=max_depth,
        include_source=include_source,
        max_lines_per_file=max_lines_per_file,
        base=base,
        detail_level=detail_level,
    )


def query_graph_nodes(
    pattern: str,
    target: str,
    *,
    repo_root: str | None = None,
    detail_level: str = "standard",
) -> GraphOperationResult:
    """Run a predefined graph query pattern (callers_of, tests_for, ...)."""
    return _timed_call(
        "query_graph",
        _query_graph_raw,
        pattern=pattern,
        target=target,
        repo_root=repo_root,
        detail_level=detail_level,
    )


def collect_graph_telemetry(
    *,
    build_result: GraphOperationResult | None = None,
    query_results: list[GraphOperationResult] | None = None,
) -> dict[str, Any]:
    """
    Collapse adapter results into Phase 1 graph telemetry fields.

    Returns only non-content metrics suitable for Opik/Sentry metadata.
    """
    query_results = query_results or []
    build_latency = build_result.latency_ms if build_result else 0.0
    query_latency = round(sum(r.latency_ms for r in query_results), 3)
    failures = []
    if build_result and not build_result.ok:
        failures.append(f"build:{build_result.error_type or 'error'}")
    for r in query_results:
        if not r.ok:
            failures.append(f"{r.operation}:{r.error_type or 'error'}")

    schema_version = "unknown"
    if build_result and build_result.ok:
        schema_version = str(
            build_result.data.get("schema_version")
            or build_result.data.get("stats", {}).get("schema_version")
            or "unknown"
        )

    return {
        "graph_build_latency_ms": build_latency,
        "graph_query_latency_ms": query_latency,
        "graph_operations_ok": (build_result.ok if build_result else True) and all(r.ok for r in query_results),
        "graph_fallback_reasons": failures,
        "graph_schema_version": schema_version,
    }
