"""Tests for Phase 1 code-review-graph sync adapter."""

from typing import Any, cast

from tenacity import wait_none

from git_cg import graph_context
from git_cg.graph_context import (
    GraphOperationResult,
    collect_graph_telemetry,
    detect_changes,
    graph_stats,
    impact_radius,
    query_graph_nodes,
    refresh_graph,
)


def _no_wait(fn: Any) -> Any:
    """Disable tenacity sleep for unit tests when decorator is present."""
    wrapped = cast(Any, fn)
    if hasattr(wrapped, "retry_with"):
        return wrapped.retry_with(wait=wait_none())
    return wrapped


def test_graph_stats_returns_structured_result():
    result = graph_stats(repo_root=".")
    assert isinstance(result, GraphOperationResult)
    assert result.operation == "graph_stats"
    assert result.latency_ms >= 0.0
    # In this repo the graph exists; still accept typed failure shape.
    if result.ok:
        assert isinstance(result.data, dict)
        assert "total_nodes" in result.data or "summary" in result.data
    else:
        assert result.error_type
        assert result.error


def test_refresh_graph_minimal_does_not_raise():
    # May be slower; still must return structured result without raising.
    result = refresh_graph(repo_root=".", full_rebuild=False, postprocess="minimal")
    assert result.operation == "refresh_graph"
    assert isinstance(result.to_dict(), dict)


def test_detect_changes_and_impact_radius_shapes(monkeypatch):
    def fake_detect(**kwargs):
        return {"risk_score": 0.1, "changed_functions": [], "test_gaps": []}

    def fake_impact(**kwargs):
        return {"total_impacted": 0, "impacted_files": []}

    monkeypatch.setattr(graph_context, "_detect_changes_raw", lambda **kwargs: fake_detect(**kwargs))
    monkeypatch.setattr(graph_context, "_impact_radius_raw", lambda **kwargs: fake_impact(**kwargs))

    d = detect_changes(repo_root=".", changed_files=["src/git_cg/main.py"])
    i = impact_radius(repo_root=".", changed_files=["src/git_cg/main.py"])
    assert d.ok is True
    assert d.data["risk_score"] == 0.1
    assert i.ok is True
    assert i.data["total_impacted"] == 0


def test_query_graph_nodes_failure_is_typed(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(graph_context, "_query_graph_raw", boom)
    result = query_graph_nodes("callers_of", "nope", repo_root=".")
    assert result.ok is False
    assert result.error_type == "RuntimeError"
    assert "unavailable" in (result.error or "")


def test_collect_graph_telemetry_aggregates_latencies():
    build = GraphOperationResult(ok=True, operation="refresh_graph", latency_ms=12.5, data={"status": "ok"})
    q1 = GraphOperationResult(ok=True, operation="graph_stats", latency_ms=3.0, data={})
    q2 = GraphOperationResult(ok=False, operation="detect_changes", latency_ms=4.5, error="x", error_type="ValueError")
    meta = collect_graph_telemetry(build_result=build, query_results=[q1, q2])
    assert meta["graph_build_latency_ms"] == 12.5
    assert meta["graph_query_latency_ms"] == 7.5
    assert meta["graph_operations_ok"] is False
    assert meta["graph_fallback_reasons"] == ["detect_changes:ValueError"]


def test_graph_retry_used_on_transient_errors(monkeypatch):
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            import sqlite3

            raise sqlite3.OperationalError("database is locked")
        return {"total_nodes": 1}

    # Patch the underlying tools import path used inside raw helper.
    import code_review_graph.tools as tools

    monkeypatch.setattr(tools, "list_graph_stats", flaky)
    # raw helper is decorated; disable wait
    graph_context._list_graph_stats_raw = _no_wait(graph_context._list_graph_stats_raw)
    result = graph_stats(repo_root=".")
    assert result.ok is True
    assert calls["n"] == 2
