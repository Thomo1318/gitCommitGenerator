"""Tests for Phase 1 code-review-graph sync adapter."""

from typing import Any, cast

from tenacity import wait_none

from git_cg import graph_context
from git_cg.graph_context import (
    GraphOperationResult,
    GraphOutcome,
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


def test_graph_stats_returns_structured_result(monkeypatch):
    """Offline: structured GraphOperationResult shape without real CRG I/O."""

    def fake_stats(**kwargs):
        return {"total_nodes": 3, "summary": "ok"}

    monkeypatch.setattr(graph_context, "_list_graph_stats_raw", lambda **kwargs: fake_stats(**kwargs))
    result = graph_stats(repo_root=".")
    assert isinstance(result, GraphOperationResult)
    assert result.operation == "graph_stats"
    assert result.ok is True
    assert result.outcome == GraphOutcome.OK
    assert result.latency_ms >= 0.0
    assert result.data["total_nodes"] == 3


def test_refresh_graph_minimal_does_not_raise(monkeypatch):
    """Offline: refresh_graph returns structured result and never mutates real graph state."""
    calls: list[dict[str, Any]] = []

    def fake_build(**kwargs):
        calls.append(kwargs)
        return {"status": "ok", "schema_version": "test"}

    monkeypatch.setattr(graph_context, "_build_or_update_graph_raw", lambda **kwargs: fake_build(**kwargs))
    result = refresh_graph(repo_root=".", full_rebuild=False, postprocess="minimal")
    assert result.operation == "refresh_graph"
    assert result.ok is True
    assert isinstance(result.to_dict(), dict)
    assert calls and calls[0]["postprocess"] == "minimal"
    assert calls[0]["full_rebuild"] is False


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
    assert result.outcome == GraphOutcome.UNAVAILABLE
    assert result.error_type == "RuntimeError"
    assert "unavailable" in (result.error or "")


def test_timed_call_classifies_programming_errors_as_error(monkeypatch):
    def boom(**kwargs):
        raise TypeError("bad kwargs")

    monkeypatch.setattr(graph_context, "_list_graph_stats_raw", boom)
    result = graph_stats(repo_root=".")
    assert result.ok is False
    assert result.outcome == GraphOutcome.ERROR
    assert result.error_type == "TypeError"


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

    import code_review_graph.tools as tools

    monkeypatch.setattr(tools, "list_graph_stats", flaky)
    # Disable wait via monkeypatch so the original decorator is restored after the test.
    monkeypatch.setattr(graph_context, "_list_graph_stats_raw", _no_wait(graph_context._list_graph_stats_raw))
    result = graph_stats(repo_root=".")
    assert result.ok is True
    assert calls["n"] == 2


def test_graph_outcome_enum_and_result_payload():
    ok = GraphOperationResult(ok=True, operation="x", outcome=GraphOutcome.OK, data={"a": 1})
    bad = GraphOperationResult(
        ok=False, operation="y", outcome=GraphOutcome.UNAVAILABLE, error="e", error_type="RuntimeError"
    )
    assert ok.to_dict()["outcome"] == "ok"
    assert bad.to_dict()["outcome"] == "unavailable"
    assert set(GraphOutcome) == {GraphOutcome.OK, GraphOutcome.UNAVAILABLE, GraphOutcome.ERROR}


def test_review_context_pack_defaults_include_source_false(monkeypatch):
    seen: dict[str, Any] = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(graph_context, "_review_context_raw", lambda **kwargs: fake(**kwargs))
    from git_cg.graph_context import review_context_pack

    review_context_pack(repo_root=".", changed_files=["a.py"])
    assert seen.get("include_source") is False
