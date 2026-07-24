"""Unit tests for Phase 7 semantic context models and summary builder (#162)."""

from __future__ import annotations

from git_cg.intent import GraphEnrichmentFacts
from git_cg.semantic import (
    MAX_FALLBACK_REASONS,
    MAX_NOTABLE_CALLERS,
    SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION,
    RiskAssessment,
    SemanticDiffSummary,
    build_semantic_summary,
    empty_graph_product_fields,
    map_graph_product_results,
    semantic_analysis_metadata,
)


class _FakeResult:
    def __init__(self, ok: bool, data: dict, outcome: str = "ok", error_type: str | None = None):
        self.ok = ok
        self.data = data
        self.outcome = outcome
        self.error_type = error_type
        self.operation = "fake"
        self.latency_ms = 1.0
        self.error = None


def test_semantic_diff_summary_defaults_and_schema():
    summary = SemanticDiffSummary()
    assert summary.schema_version == SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION
    assert summary.test_coverage_gap is None
    assert summary.fallback_reasons == []


def test_summary_bounds_cap_lists_and_class_counts():
    summary = SemanticDiffSummary(
        fallback_reasons=[f"r{i}" for i in range(MAX_FALLBACK_REASONS + 5)],
        notable_callers=[f"c{i}" for i in range(MAX_NOTABLE_CALLERS + 5)],
        fingerprint_class_counts={f"k{i:02d}": i for i in range(40)},
    ).bounded()
    assert len(summary.fallback_reasons) == MAX_FALLBACK_REASONS
    assert len(summary.notable_callers) == MAX_NOTABLE_CALLERS
    assert summary.fingerprint_class_counts is not None
    assert len(summary.fingerprint_class_counts) <= 32


def test_build_semantic_summary_partial_without_producers():
    summary = build_semantic_summary({})
    assert isinstance(summary, SemanticDiffSummary)
    assert summary.blast_radius_size is None
    assert any("no_producer_success" in r for r in summary.fallback_reasons)


def test_build_semantic_summary_from_metrics_no_io():
    metrics = {
        "body_similarity_min": 0.91,
        "body_similarity_avg": 0.95,
        "fingerprint_class_counts": {"identifier_or_literal_only": 2},
        "blast_radius_size": 12,
        "affected_flows_count": 3,
        "test_coverage_gap": True,
        "test_gaps_count": 2,
        "semantic_parser_metrics": {
            "semantic_files_total": 4,
            "semantic_files_parsed": 3,
            "semantic_fallback_reasons": ["staged_skip:big.bin"],
        },
        "risk_assessment": RiskAssessment(risk_score=0.4, outcome="ok", priorities=["flow:main"]),
    }
    summary = build_semantic_summary(metrics)
    assert summary.body_similarity_min == 0.91
    assert summary.blast_radius_size == 12
    assert summary.affected_flows_count == 3
    assert summary.test_coverage_gap is True
    assert summary.test_gaps_count == 2
    assert summary.parser_coverage_ratio == 0.75
    assert summary.risk_score == 0.4
    assert summary.schema_version == SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION


def test_test_coverage_gap_bool_not_int():
    summary = build_semantic_summary({"test_coverage_gap": True, "blast_radius_size": 1})
    assert summary.test_coverage_gap is True
    assert isinstance(summary.test_coverage_gap, bool)


def test_semantic_analysis_metadata_redacts_and_allowlists(monkeypatch):
    monkeypatch.setattr(
        "git_cg.semantic.redact_payload",
        lambda payload: f"R:{payload}" if payload != "fail" else "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]",
    )
    summary = SemanticDiffSummary(
        blast_radius_size=9,
        affected_flows_count=2,
        test_coverage_gap=False,
        fallback_reasons=["path:/secret", "fail"],
    )
    meta = semantic_analysis_metadata(summary)
    assert meta["blast_radius_size"] == 9
    assert meta["affected_flows_count"] == 2
    assert meta["test_coverage_gap"] is False
    assert meta["semantic_context_schema_version"] == SEMANTIC_DIFF_SUMMARY_SCHEMA_VERSION
    assert meta["semantic_context_fallback_reasons"][0].startswith("R:")
    assert "[REDACTED]" in meta["semantic_context_fallback_reasons"]


def test_map_graph_product_results_success():
    detect = _FakeResult(
        True,
        {
            "risk_score": 0.7,
            "test_gaps": ["a", "b"],
            "priorities": [{"name": "hub"}],
            "nodes": [{"name": "foo", "is_test": False}, {"name": "test_foo", "is_test": True}],
        },
        outcome="ok",
    )
    impact = _FakeResult(True, {"total_impacted": 25}, outcome="ok")
    flows = _FakeResult(True, {"total": 4}, outcome="ok")
    product = map_graph_product_results(detect_result=detect, impact_result=impact, flows_result=flows)
    assert product["blast_radius_size"] == 25
    assert product["affected_flows_count"] == 4
    assert product["test_gaps_count"] == 2
    assert product["test_coverage_gap"] is True
    assert isinstance(product["graph_enrichment"], GraphEnrichmentFacts)
    assert product["graph_enrichment"].outcome == "ok"
    assert product["graph_enrichment"].total_impacted == 25
    assert product["risk_assessment"].risk_score == 0.7


def test_map_graph_product_results_unavailable_fallback():
    detect = _FakeResult(False, {}, outcome="unavailable", error_type="TimeoutError")
    product = map_graph_product_results(detect_result=detect, impact_result=None, flows_result=None)
    assert product["blast_radius_size"] is None
    assert any(r.startswith("detect_changes:") for r in product["graph_fallback_reasons"])
    assert product["graph_enrichment"].outcome in {"unavailable", "error"}


def test_empty_graph_product_fields_defaults():
    fields = empty_graph_product_fields()
    assert fields["blast_radius_size"] is None
    assert fields["test_coverage_gap"] is None
    assert fields["graph_fallback_reasons"] == []


def test_collect_graph_product_bundle_maps_monkeypatched_results(monkeypatch):
    from git_cg import graph_context as gc
    from git_cg.graph_context import GraphOperationResult, GraphOutcome, collect_graph_product_bundle

    def fake_detect(**kwargs):
        return GraphOperationResult(
            ok=True,
            operation="detect_changes",
            outcome=GraphOutcome.OK,
            latency_ms=1.0,
            data={"risk_score": 0.3, "test_gaps": ["x"], "total_impacted": 8},
        )

    def fake_impact(**kwargs):
        return GraphOperationResult(
            ok=True,
            operation="impact_radius",
            outcome=GraphOutcome.OK,
            latency_ms=2.0,
            data={"total_impacted": 14},
        )

    def fake_flows(**kwargs):
        return GraphOperationResult(
            ok=True,
            operation="affected_flows",
            outcome=GraphOutcome.OK,
            latency_ms=3.0,
            data={"total": 5},
        )

    monkeypatch.setattr(gc, "detect_changes", fake_detect)
    monkeypatch.setattr(gc, "impact_radius", fake_impact)
    monkeypatch.setattr(gc, "affected_flows", fake_flows)

    product, results = collect_graph_product_bundle(
        repo_root=".",
        changed_files=["src/git_cg/main.py"],
        max_depth=2,
        detail_level="minimal",
    )
    assert product["blast_radius_size"] == 14
    assert product["affected_flows_count"] == 5
    assert product["test_coverage_gap"] is True
    assert product["graph_enrichment"].total_impacted == 14
    assert len(results) == 3


def test_collect_semantic_producer_metrics_flag_off_skips_graph_product(monkeypatch):
    from git_cg.main import _collect_semantic_producer_metrics

    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("should not run when semantic disabled")

    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", boom)
    monkeypatch.setattr("git_cg.git_index.read_staged_sources", boom)
    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=False)
    assert out["semantic_enabled"] is False
    assert out["blast_radius_size"] is None
    assert out["test_coverage_gap"] is None
    assert called["n"] == 0
