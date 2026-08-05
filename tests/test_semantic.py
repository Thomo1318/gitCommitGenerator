"""Unit tests for Phase 7 semantic context models and summary builder (#162)."""

from __future__ import annotations

from typing import ClassVar

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


def test_collect_semantic_producer_metrics_flag_off_does_not_import_semantic(monkeypatch):
    """Flag-off must not import git_cg.semantic (keeps zero-safe path isolated)."""
    import builtins
    import sys

    from git_cg.main import _collect_semantic_producer_metrics

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "git_cg.semantic" or (name == "git_cg" and fromlist and "semantic" in fromlist):
            raise ImportError("semantic import blocked in flag-off test")
        return real_import(name, globals, locals, fromlist, level)

    # Drop cached module so import would be attempted if code path touches it.
    sys.modules.pop("git_cg.semantic", None)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=False)
    assert out["semantic_enabled"] is False
    assert out["blast_radius_size"] is None
    assert out["graph_fallback_reasons"] == []


def test_collect_graph_product_bundle_fail_open_on_mapper_error(monkeypatch):
    from git_cg import graph_context as gc
    from git_cg.graph_context import collect_graph_product_bundle

    def boom(**kwargs):
        raise RuntimeError("mapper exploded")

    # Force an unexpected exception inside the bundle body (docstring: never raises).
    monkeypatch.setattr(gc, "detect_changes", boom)
    product, results = collect_graph_product_bundle(repo_root=".")
    assert product["blast_radius_size"] is None
    assert product.get("graph_fallback_reasons")
    assert results and results[0].ok is False
    assert results[0].operation == "graph_product_bundle"
    assert results[0].error_type == "RuntimeError"


def test_bound_str_and_list_helpers():
    from git_cg.semantic import MAX_REASON_STRING_LENGTH, _bound_str, _bound_str_list

    assert _bound_str("short") == "short"
    long = "x" * (MAX_REASON_STRING_LENGTH + 20)
    clipped = _bound_str(long)
    assert clipped.endswith("...")
    assert len(clipped) == MAX_REASON_STRING_LENGTH
    assert _bound_str_list(None, max_items=3) == []
    assert _bound_str_list(["a", 1, "b", "c", "d"], max_items=3) == ["a", "b", "c"]


def test_outcome_from_graph_result_branches():
    from git_cg.semantic import _outcome_from_graph_result

    class Outcome:
        def __init__(self, value: str):
            self.value = value

    class R:
        def __init__(self, ok, outcome, value_attr=False):
            self.ok = ok
            self.outcome = Outcome(outcome) if value_attr else outcome

    assert _outcome_from_graph_result(None) == "unavailable"
    assert _outcome_from_graph_result(R(True, "ok")) == "ok"
    assert _outcome_from_graph_result(R(True, "")) == "ok"
    assert _outcome_from_graph_result(R(False, "error")) == "error"
    assert _outcome_from_graph_result(R(False, "unavailable")) == "unavailable"
    assert _outcome_from_graph_result(R(True, "ok", value_attr=True)) == "ok"
    assert _outcome_from_graph_result(R(False, "weird")) == "unavailable"
    assert _outcome_from_graph_result(R(True, "weird")) == "ok"


def test_count_from_payload_shapes():
    from git_cg.semantic import _count_from_payload

    assert _count_from_payload({}, "total") is None
    assert _count_from_payload({"total": None}, "total") is None
    assert _count_from_payload({"total": True}, "total") is None
    assert _count_from_payload({"total": 7}, "total") == 7
    assert _count_from_payload({"items": [1, 2, 3]}, "items") == 3
    assert _count_from_payload({"wrap": {"total": 4}}, "wrap") == 4
    assert _count_from_payload({"wrap": {"flows": ["a", "b"]}}, "wrap") == 2
    assert _count_from_payload({"wrap": {"nope": 1}}, "wrap") is None


def test_test_gaps_count_shapes():
    from git_cg.semantic import _test_gaps_count

    assert _test_gaps_count({}) is None
    assert _test_gaps_count({"test_gaps": ["a", "b"]}) == 2
    assert _test_gaps_count({"test_coverage_gaps": 3}) == 3
    assert _test_gaps_count({"knowledge_gaps": {"items": [1]}}) == 1
    assert _test_gaps_count({"untested_hotspots": {"count": 5}}) == 5
    assert _test_gaps_count({"gaps": {"test_gaps": ["x"]}}) == 1
    assert _test_gaps_count({"coverage": {"test_gaps": []}}) == 0


def test_risk_score_and_priority_labels():
    from git_cg.semantic import _priority_labels, _risk_score

    assert _risk_score({"risk_score": 0.4}) == 0.4
    assert _risk_score({"risk": {"score": 0.2}}) == 0.2
    assert _risk_score({"summary": {"risk_score": 0.9}}) == 0.9
    assert _risk_score({}) is None
    labels = _priority_labels(
        {
            "priorities": [
                "plain",
                {"name": "n1"},
                {"title": "t1"},
                {"id": "i1"},
                {"path": "p1"},
                {"kind": "k1"},
                {"other": "skip"},
                12,
            ]
        }
    )
    assert "plain" in labels
    assert "n1" in labels
    assert "t1" in labels


def test_impact_flags_from_nodes_and_explicit():
    from git_cg.semantic import _impact_flags

    has_test, has_prod = _impact_flags(
        {
            "nodes": [
                {"name": "test_foo", "is_test": True},
                {"name": "svc", "file_path": "src/a.py"},
                "skip",
                {"kind": "Test", "name": "Suite"},
            ]
        }
    )
    assert has_test is True
    assert has_prod is True
    has_test2, has_prod2 = _impact_flags({"impacted_has_test_nodes": False, "impacted_has_production_nodes": True})
    assert has_test2 is False
    assert has_prod2 is True


def test_map_graph_product_non_dict_payloads_and_impact_only_risk():
    from git_cg.semantic import RiskAssessment, map_graph_product_results

    class R:
        def __init__(self, ok, outcome, data, error_type=None):
            self.ok = ok
            self.outcome = outcome
            self.data = data
            self.error_type = error_type

    product = map_graph_product_results(
        detect_result=R(True, "ok", "not-a-dict"),
        impact_result=R(True, "ok", {"total_impacted": 9, "risk_score": 0.55}),
        flows_result=R(True, "ok", {"flows": [1, 2]}),
    )
    assert product["blast_radius_size"] == 9
    assert product["affected_flows_count"] == 2
    assert isinstance(product["risk_assessment"], RiskAssessment)
    assert product["risk_assessment"].risk_score == 0.55


def test_map_graph_product_detect_none_uses_impact_outcome():
    from git_cg.semantic import map_graph_product_results

    class R:
        def __init__(self, ok, outcome, data):
            self.ok = ok
            self.outcome = outcome
            self.data = data
            self.error_type = None

    product = map_graph_product_results(
        detect_result=None,
        impact_result=R(False, "error", {}),
        flows_result=None,
    )
    assert product["risk_assessment"].outcome == "error"
    assert any("impact_radius" in r for r in product["graph_fallback_reasons"])


def test_parser_coverage_ratio_edges():
    from git_cg.semantic import _parser_coverage_ratio

    assert _parser_coverage_ratio(None) is None
    assert _parser_coverage_ratio({"semantic_files_total": "x", "semantic_files_parsed": 1}) is None
    assert _parser_coverage_ratio({"semantic_files_total": 0, "semantic_files_parsed": 0}) == 0.0
    assert _parser_coverage_ratio({"semantic_files_total": 4, "semantic_files_parsed": 5}) == 1.0
    assert _parser_coverage_ratio({"semantic_files_total": 4, "semantic_files_parsed": 2}) == 0.5


def test_build_semantic_summary_invalid_risk_and_fp_counts(monkeypatch):
    from git_cg.semantic import build_semantic_summary

    summary = build_semantic_summary(
        {
            "blast_radius_size": 1,
            "risk_assessment": {"risk_score": "bad", "outcome": "nope"},
            "fingerprint_class_counts": ["not", "a", "dict"],
            "notable_callers": "not-a-list",
            "graph_fallback_reasons": [1, "ok"],
        }
    )
    assert any("risk_assessment:invalid" in r for r in summary.fallback_reasons)
    assert any("fingerprints:invalid_class_counts" in r for r in summary.fallback_reasons)
    assert summary.notable_callers == []


def test_build_semantic_summary_gap_from_count_only():
    from git_cg.semantic import build_semantic_summary

    summary = build_semantic_summary({"test_gaps_count": 2, "body_similarity_min": 0.2})
    assert summary.test_coverage_gap is True
    assert summary.test_gaps_count == 2


def test_build_semantic_summary_opik_context_failure_is_swallowed(monkeypatch):
    import builtins

    from git_cg.semantic import build_semantic_summary

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "opik" or name.startswith("opik."):
            raise ImportError("opik unavailable in test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    summary = build_semantic_summary({"blast_radius_size": 4, "body_similarity_min": 0.1})
    assert summary.blast_radius_size == 4


def test_semantic_analysis_metadata_none():
    from git_cg.semantic import semantic_analysis_metadata

    meta = semantic_analysis_metadata(None)
    assert meta["blast_radius_size"] is None
    assert meta["semantic_context_schema_version"] == ""
    assert meta["semantic_context_fallback_reasons"] is None


def test_map_graph_product_non_dict_impact_and_flows():
    from git_cg.semantic import map_graph_product_results

    class R:
        def __init__(self, ok, outcome, data):
            self.ok = ok
            self.outcome = outcome
            self.data = data
            self.error_type = None

    product = map_graph_product_results(
        detect_result=R(True, "ok", {"total_impacted": 2, "test_gaps": []}),
        impact_result=R(True, "ok", ["not", "dict"]),
        flows_result=R(True, "ok", "nope"),
    )
    # detect supplies blast when impact payload is unusable
    assert product["blast_radius_size"] == 2
    assert product["affected_flows_count"] is None
    assert product["test_coverage_gap"] is False


def test_build_semantic_summary_accepts_risk_assessment_model():
    from git_cg.semantic import RiskAssessment, build_semantic_summary

    risk = RiskAssessment(risk_score=0.33, outcome="ok", priorities=["a"])
    summary = build_semantic_summary(
        {"body_similarity_min": 0.4},
        risk_assessment=risk,
        graph_product={"blast_radius_size": 6},
    )
    assert summary.risk_score == 0.33
    assert summary.blast_radius_size == 6


def test_collect_semantic_producer_metrics_outer_graph_stage_records_fallback(monkeypatch):
    """Outer graph-stage failures append bounded graph_stage:<Type> without wiping product fields."""
    from types import SimpleNamespace

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.semantic import empty_graph_product_fields

    staged = SimpleNamespace(files={"a.py": "x = 1\n"}, errors=[], skipped=[])
    head = SimpleNamespace(files={}, errors=[], skipped=[])

    class Parsed:
        results: ClassVar[list] = []

        def to_metrics_dict(self):
            return {"semantic_files_total": 1, "semantic_files_parsed": 1}

    monkeypatch.setattr("git_cg.git_index.read_staged_sources", lambda *a, **k: staged)
    monkeypatch.setattr("git_cg.ast_parser.parse_files", lambda files: Parsed())
    monkeypatch.setattr("git_cg.git_index.read_head_sources", lambda *a, **k: head)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: False)

    product = empty_graph_product_fields()
    product["blast_radius_size"] = 9
    product["affected_flows_count"] = 2
    product["test_coverage_gap"] = True
    product["graph_fallback_reasons"] = ["detect_changes:ok"]

    def fake_bundle(**kwargs):
        return product, [
            GraphOperationResult(
                ok=True,
                operation="detect_changes",
                outcome=GraphOutcome.OK,
                data={},
                latency_ms=1.0,
            )
        ]

    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", fake_bundle)

    def fake_stats(*, repo_root=None, **kwargs):
        return GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "s"},
            latency_ms=0.5,
        )

    monkeypatch.setattr("git_cg.graph_context.graph_stats", fake_stats)

    def boom_meta(**kwargs):
        raise RuntimeError("telemetry aggregation failed")

    monkeypatch.setattr("git_cg.graph_context.collect_graph_telemetry", boom_meta)

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["semantic_enabled"] is True
    # Product fields preserved (outer except must not wipe them).
    assert out["blast_radius_size"] == 9
    assert out["affected_flows_count"] == 2
    assert out["test_coverage_gap"] is True
    # Latency/schema reset + bounded graph_stage reason appended.
    assert out["graph_build_latency_ms"] == 0.0
    assert out["graph_query_latency_ms"] == 0.0
    assert out["crg_schema_version"] is None
    reasons = out.get("graph_fallback_reasons") or []
    assert "detect_changes:ok" in reasons
    assert any(r == "graph_stage:RuntimeError" for r in reasons)


# ---------------------------------------------------------------------------
# Phase 7.5 (#180): generate-path shadow isolation matrix (4 / 5 / 7 / 7b)
# ---------------------------------------------------------------------------


def _phase75_base_monkeypatches(monkeypatch):
    """Stub parser/fingerprint/product boundaries so only the shadow/refresh path is under test."""
    from types import SimpleNamespace

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.semantic import empty_graph_product_fields

    staged = SimpleNamespace(files={"a.py": "x = 1\n"}, errors=[], skipped=[])
    head = SimpleNamespace(files={}, errors=[], skipped=[])

    class _Metrics:
        def to_dict(self):
            return {
                "semantic_files_total": 1,
                "semantic_files_parsed": 1,
                "parser_latency_ms": 0.1,
                "semantic_fallback_reasons": [],
            }

    class Parsed:
        metrics = _Metrics()
        results: ClassVar[list] = []

    monkeypatch.setattr("git_cg.git_index.read_staged_sources", lambda *a, **k: staged)
    monkeypatch.setattr("git_cg.ast_parser.parse_files", lambda files: Parsed())
    monkeypatch.setattr("git_cg.git_index.read_head_sources", lambda *a, **k: head)
    monkeypatch.setattr(
        "git_cg.fingerprints.compare_fingerprint_sets",
        lambda **kwargs: SimpleNamespace(
            metrics=SimpleNamespace(
                to_dict=lambda: {
                    "body_similarity_min": 1.0,
                    "body_similarity_avg": 1.0,
                    "fingerprint_files_compared": 1,
                    "fingerprint_latency_ms": 0.0,
                    "class_counts": {},
                    "grammar_version": "test",
                    "markers": [],
                    "reasons": [],
                }
            )
        ),
    )

    product = empty_graph_product_fields()
    product["blast_radius_size"] = 1
    product["affected_flows_count"] = 0
    product["test_coverage_gap"] = False
    product["graph_fallback_reasons"] = []

    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_product_bundle",
        lambda **kwargs: (
            product,
            [
                GraphOperationResult(
                    ok=True,
                    operation="detect_changes",
                    outcome=GraphOutcome.OK,
                    data={},
                    latency_ms=0.5,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "git_cg.graph_context.graph_stats",
        lambda **kwargs: GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "s"},
            latency_ms=0.2,
        ),
    )
    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_telemetry",
        lambda **kwargs: {"graph_build_latency_ms": 0.0, "graph_query_latency_ms": 0.7},
    )


def test_phase75_refresh_off_zero_shadow_invocations(monkeypatch):
    """Matrix 4 + 7: refresh flag off → zero shadow construction; shadow_workspace_used False."""
    from git_cg.main import _collect_semantic_producer_metrics

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: False)

    shadow_calls: list[tuple] = []

    class _BoomShadow:
        def __init__(self, *a, **k):
            shadow_calls.append((a, k))
            raise AssertionError("shadow_workspace must not be constructed when refresh is off")

        def __enter__(self):
            raise AssertionError("unreachable")

        def __exit__(self, *a):
            return False

    def boom_shadow(*a, **k):
        shadow_calls.append((a, k))
        raise AssertionError("shadow_workspace must not be invoked when refresh is off")

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", boom_shadow)
    # Also guard the class path if imported differently.
    monkeypatch.setattr("git_cg.shadow_workspace.ShadowWorkspace", _BoomShadow)

    refresh_calls: list[dict] = []

    def track_refresh(**kwargs):
        refresh_calls.append(kwargs)
        raise AssertionError("refresh_graph must not run when refresh is off")

    monkeypatch.setattr("git_cg.graph_context.refresh_graph", track_refresh)

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["semantic_enabled"] is True
    assert out.get("shadow_workspace_used") is False
    assert out.get("semantic_refresh_graph") == "skipped"
    assert out.get("shadow_fail_open_reason") == "none"
    assert shadow_calls == []
    assert refresh_calls == []


def test_phase75_flag_on_refresh_uses_shadow_path(monkeypatch):
    """Matrix 7b: flag on → refresh_graph(repo_root=shadow.path); used=True; semantic_refresh_graph=ran."""
    from contextlib import contextmanager

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    shadow_path = "/tmp/git-cg-shadow-test-repo"
    enter_kwargs: list[dict] = []

    @contextmanager
    def fake_shadow(source_dir=".", include_unstaged=True):
        enter_kwargs.append({"source_dir": source_dir, "include_unstaged": include_unstaged})
        yield type("Shadow", (), {"path": shadow_path})()

    refresh_kwargs: list[dict] = []

    def fake_refresh(**kwargs):
        refresh_kwargs.append(kwargs)
        return GraphOperationResult(
            ok=True,
            operation="refresh_graph",
            outcome=GraphOutcome.OK,
            data={},
            latency_ms=3.0,
        )

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", fake_shadow)
    monkeypatch.setattr("git_cg.graph_context.refresh_graph", fake_refresh)

    out = _collect_semantic_producer_metrics("/live/repo", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["semantic_refresh_graph"] == "ran"
    assert out["shadow_fail_open_reason"] == "none"
    assert enter_kwargs == [{"source_dir": "/live/repo", "include_unstaged": False}]
    assert len(refresh_kwargs) == 1
    assert refresh_kwargs[0]["repo_root"] == shadow_path
    assert refresh_kwargs[0].get("full_rebuild") is False
    assert refresh_kwargs[0].get("postprocess") == "minimal"


def test_phase75_shadow_enter_failure_fail_open(monkeypatch):
    """Matrix 5: shadow __enter__/clone failure → fail-open + both vocabularies."""
    from contextlib import contextmanager

    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def boom_shadow(*a, **k):
        raise OSError("clone failed")
        yield  # pragma: no cover

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", boom_shadow)

    refresh_calls: list[dict] = []
    monkeypatch.setattr(
        "git_cg.graph_context.refresh_graph",
        lambda **kwargs: refresh_calls.append(kwargs) or (_ for _ in ()).throw(AssertionError("no refresh")),
    )

    tags: dict[str, str] = {}
    monkeypatch.setattr("sentry_sdk.set_tag", lambda k, v: tags.__setitem__(k, v))

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is False
    # requested stays requested on failure (ran only on success)
    assert out["semantic_refresh_graph"] == "requested"
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.SHADOW_CREATE_FAILED.value
    reasons = out.get("graph_fallback_reasons") or []
    assert "shadow_workspace:OSError" in reasons
    assert tags.get("shadow_fail_open_reason") == ShadowFailOpenReason.SHADOW_CREATE_FAILED.value
    assert refresh_calls == []
    # Product fields still populated (fail-open must not wipe graph product stage).
    assert out["blast_radius_size"] == 1


def test_phase75_shadow_sync_staged_fail_open(monkeypatch):
    """Staged sync CalledProcessError maps to SHADOW_SYNC_STAGED + shadow_sync:staged."""
    import subprocess
    from contextlib import contextmanager

    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def boom_sync(*a, **k):
        raise subprocess.CalledProcessError(1, ["git", "apply", "--index"])
        yield  # pragma: no cover

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", boom_sync)

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is False
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.SHADOW_SYNC_STAGED.value
    reasons = out.get("graph_fallback_reasons") or []
    assert "shadow_sync:staged" in reasons
    assert out["semantic_refresh_graph"] == "requested"


def test_phase75_refresh_raise_fail_open_marks_shadow_used(monkeypatch):
    """Refresh raise after successful enter → REFRESH_FAILED + refresh_graph:<Type>; shadow used."""
    from contextlib import contextmanager

    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def ok_shadow(*a, **k):
        yield type("Shadow", (), {"path": "/tmp/shadow-ok"})()

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", ok_shadow)
    monkeypatch.setattr(
        "git_cg.graph_context.refresh_graph",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("refresh boom")),
    )

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.REFRESH_FAILED.value
    reasons = out.get("graph_fallback_reasons") or []
    assert "refresh_graph:RuntimeError" in reasons
    assert out["semantic_refresh_graph"] == "requested"


def test_phase75_refresh_timeout_fail_open(monkeypatch):
    """TimeoutError during refresh → REFRESH_TIMEOUT."""
    from contextlib import contextmanager

    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def ok_shadow(*a, **k):
        yield type("Shadow", (), {"path": "/tmp/shadow-ok"})()

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", ok_shadow)
    monkeypatch.setattr(
        "git_cg.graph_context.refresh_graph",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("deadline")),
    )

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.REFRESH_TIMEOUT.value
    assert "refresh_graph:TimeoutError" in (out.get("graph_fallback_reasons") or [])


def test_phase75_refresh_result_not_ok_fail_open(monkeypatch):
    """refresh_graph returns GraphOperationResult(ok=False) without raising → REFRESH_FAILED."""
    from contextlib import contextmanager

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def ok_shadow(*a, **k):
        yield type("Shadow", (), {"path": "/tmp/shadow-ok"})()

    def failed_refresh(**kwargs):
        return GraphOperationResult(
            ok=False,
            operation="refresh_graph",
            outcome=GraphOutcome.ERROR,
            error_type="CalledProcessError",
            error="refresh returned not ok",
        )

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", ok_shadow)
    monkeypatch.setattr("git_cg.graph_context.refresh_graph", failed_refresh)

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.REFRESH_FAILED.value
    assert out["semantic_refresh_graph"] == "requested"
    reasons = out.get("graph_fallback_reasons") or []
    assert "refresh_graph:CalledProcessError" in reasons


def test_phase75_product_bundle_exception_preserves_shadow_fallback_reasons(monkeypatch):
    """Product-bundle exception must not wipe Vocab1 shadow/refresh fail-open reasons."""
    from contextlib import contextmanager

    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def ok_shadow(*a, **k):
        yield type("Shadow", (), {"path": "/tmp/shadow-ok"})()

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", ok_shadow)
    monkeypatch.setattr(
        "git_cg.graph_context.refresh_graph",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("refresh boom")),
    )

    def boom_bundle(**kwargs):
        raise RuntimeError("product boom")

    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", boom_bundle)

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.REFRESH_FAILED.value
    reasons = out.get("graph_fallback_reasons") or []
    assert "refresh_graph:RuntimeError" in reasons
    # Product fields fail open to empty defaults, but shadow reason survives.
    assert out.get("blast_radius_size") is None


def test_phase75_shadow_clone_sync_latency_accumulates_into_graph_build(monkeypatch):
    """Nice-to-have: shadow clone/sync ms folds into existing graph_build_latency_ms."""
    from contextlib import contextmanager

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    @contextmanager
    def timed_shadow(*a, **k):
        yield type(
            "Shadow",
            (),
            {"path": "/tmp/shadow-latency", "clone_sync_latency_ms": 12.5},
        )()

    def fake_refresh(**kwargs):
        return GraphOperationResult(
            ok=True,
            operation="refresh_graph",
            outcome=GraphOutcome.OK,
            data={},
            latency_ms=3.0,
        )

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", timed_shadow)
    monkeypatch.setattr("git_cg.graph_context.refresh_graph", fake_refresh)
    # Override base collect_graph_telemetry so build latency is known (3.0 from refresh
    # is not used when collect_graph_telemetry is stubbed — stub returns build=4.0).
    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_telemetry",
        lambda **kwargs: {"graph_build_latency_ms": 4.0, "graph_query_latency_ms": 0.7},
    )

    out = _collect_semantic_producer_metrics("/live/repo", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["semantic_refresh_graph"] == "ran"
    # 4.0 (refresh/build) + 12.5 (clone/sync) — no new telemetry keys.
    assert out["graph_build_latency_ms"] == 16.5
    assert "clone_sync_latency_ms" not in out
    assert "shadow_clone_sync_latency_ms" not in out


def test_phase75_refresh_off_graph_build_latency_excludes_shadow(monkeypatch):
    """Refresh off: graph_build_latency_ms stays at collect_graph_telemetry value only."""
    from git_cg.main import _collect_semantic_producer_metrics

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: False)
    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_telemetry",
        lambda **kwargs: {"graph_build_latency_ms": 1.25, "graph_query_latency_ms": 0.7},
    )

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=True, verbose=False)
    assert out.get("shadow_workspace_used") is False
    assert out["graph_build_latency_ms"] == 1.25


# ---------------------------------------------------------------------------
# Phase 9 (#163): Policy B claim tests (P9-A) + scoped-history flag-off (P9-A06)
# ---------------------------------------------------------------------------


def test_p9_a01_a02_a07_policy_b_stats_and_product_use_live_shadow(monkeypatch):
    """P9-A01/A02/A07: refresh-on + ran → stats+product called with shadow.path inside with."""
    from contextlib import contextmanager

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.semantic import empty_graph_product_fields

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    shadow_path = "/tmp/git-cg-shadow-policy-b"
    active = {"inside": False}
    stats_roots: list[str] = []
    product_roots: list[str] = []
    stats_inside: list[bool] = []
    product_inside: list[bool] = []

    @contextmanager
    def fake_shadow(source_dir=".", include_unstaged=True):
        active["inside"] = True
        try:
            yield type("Shadow", (), {"path": shadow_path, "clone_sync_latency_ms": 1.5})()
        finally:
            active["inside"] = False

    def fake_refresh(**kwargs):
        assert active["inside"] is True
        assert kwargs.get("repo_root") == shadow_path
        return GraphOperationResult(
            ok=True,
            operation="refresh_graph",
            outcome=GraphOutcome.OK,
            data={},
            latency_ms=2.0,
        )

    def fake_stats(*, repo_root=None, **kwargs):
        stats_roots.append(repo_root)
        stats_inside.append(active["inside"])
        return GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "s"},
            latency_ms=0.2,
        )

    def fake_bundle(**kwargs):
        product_roots.append(kwargs.get("repo_root"))
        product_inside.append(active["inside"])
        product = empty_graph_product_fields()
        product["blast_radius_size"] = 2
        product["affected_flows_count"] = 2
        product["graph_fallback_reasons"] = []
        return (
            product,
            [
                GraphOperationResult(
                    ok=True,
                    operation="affected_flows",
                    outcome=GraphOutcome.OK,
                    data={
                        "flows": [
                            {"id": "flow_a", "files": ["a.py"]},
                            {"id": "flow_b", "files": ["b.py"]},
                        ]
                    },
                    latency_ms=0.4,
                )
            ],
        )

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", fake_shadow)
    monkeypatch.setattr("git_cg.graph_context.refresh_graph", fake_refresh)
    monkeypatch.setattr("git_cg.graph_context.graph_stats", fake_stats)
    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", fake_bundle)
    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_telemetry",
        lambda **kwargs: {"graph_build_latency_ms": 2.0, "graph_query_latency_ms": 0.6},
    )

    out = _collect_semantic_producer_metrics("/live/repo", enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["semantic_refresh_graph"] == "ran"
    assert stats_roots == [shadow_path]
    assert product_roots == [shadow_path]
    # P9-A07: queries ran while shadow context was active (not after exit).
    assert stats_inside == [True]
    assert product_inside == [True]
    assert out.get("scoped_history_fallback_reason", "none") == "none"


def test_p9_a03_refresh_off_uses_live_repo_root(monkeypatch):
    """P9-A03: refresh-off → live repo_root queries (baseline parity)."""
    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.semantic import empty_graph_product_fields

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: False)

    live = "/live/repo-off"
    stats_roots: list[str] = []
    product_roots: list[str] = []

    def fake_stats(*, repo_root=None, **kwargs):
        stats_roots.append(repo_root)
        return GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "s"},
            latency_ms=0.1,
        )

    def fake_bundle(**kwargs):
        product_roots.append(kwargs.get("repo_root"))
        product = empty_graph_product_fields()
        product["blast_radius_size"] = 1
        return (
            product,
            [
                GraphOperationResult(
                    ok=True,
                    operation="detect_changes",
                    outcome=GraphOutcome.OK,
                    data={},
                    latency_ms=0.2,
                )
            ],
        )

    monkeypatch.setattr("git_cg.graph_context.graph_stats", fake_stats)
    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", fake_bundle)

    out = _collect_semantic_producer_metrics(live, enable_semantic=True, verbose=False)
    assert out.get("shadow_workspace_used") is False
    assert out.get("semantic_refresh_graph") == "skipped"
    assert stats_roots == [live]
    assert product_roots == [live]


def test_p9_a04_refresh_fail_open_does_not_claim_staged_truth(monkeypatch):
    """P9-A04: refresh fail-open → live queries; scoped fallback set; no hard-fail."""
    from contextlib import contextmanager

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.semantic import empty_graph_product_fields
    from git_cg.telemetry import ShadowFailOpenReason

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    live = "/live/repo-fail"
    stats_roots: list[str] = []

    @contextmanager
    def ok_shadow(*a, **k):
        yield type("Shadow", (), {"path": "/tmp/shadow-dead", "clone_sync_latency_ms": 1.0})()

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", ok_shadow)
    monkeypatch.setattr(
        "git_cg.graph_context.refresh_graph",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("refresh boom")),
    )

    def fake_stats(*, repo_root=None, **kwargs):
        stats_roots.append(repo_root)
        return GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "s"},
            latency_ms=0.1,
        )

    def fake_bundle(**kwargs):
        product = empty_graph_product_fields()
        product["blast_radius_size"] = 1
        return (
            product,
            [
                GraphOperationResult(
                    ok=True,
                    operation="detect_changes",
                    outcome=GraphOutcome.OK,
                    data={},
                    latency_ms=0.1,
                )
            ],
        )

    monkeypatch.setattr("git_cg.graph_context.graph_stats", fake_stats)
    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", fake_bundle)

    out = _collect_semantic_producer_metrics(live, enable_semantic=True, verbose=False)
    assert out["shadow_workspace_used"] is True
    assert out["shadow_fail_open_reason"] == ShadowFailOpenReason.REFRESH_FAILED.value
    # Must not query destroyed shadow path after fail-open.
    assert stats_roots == [live]
    assert out.get("scoped_history_fallback_reason") == "graph_unavailable"


def test_p9_a06_semantic_off_no_scoped_history_side_effects(monkeypatch):
    """P9-A06: semantic-off → no new producer side effects vs baseline snapshot."""
    from git_cg.main import _collect_semantic_producer_metrics

    monkeypatch.setattr(
        "git_cg.shadow_workspace.shadow_workspace",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no shadow on flag-off")),
    )
    monkeypatch.setattr(
        "git_cg.graph_context.refresh_graph",
        lambda **k: (_ for _ in ()).throw(AssertionError("no refresh on flag-off")),
    )
    monkeypatch.setattr(
        "git_cg.git_index.read_staged_sources",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no staged read on flag-off")),
    )

    out = _collect_semantic_producer_metrics("/tmp", enable_semantic=False, verbose=False)
    assert out["semantic_enabled"] is False
    assert out.get("scoped_history_fallback_reason", "none") == "none"
    assert out.get("rename_confidence", "none") == "none"
    assert out.get("split_recommended", False) is False
    assert out.get("structural_error_handling", False) is False
    assert out.get("structural_public_api", False) is False
    assert out.get("structural_new_command", False) is False
    assert out.get("scoped_history_guidance") in (None, "")


def test_p9_b07_policy_b_producers_do_not_contaminate_worktree_or_index(monkeypatch, tmp_path):
    """P9-B07: Policy B / scoped-history path must not dirty worktree or index.

    Captures `git status --porcelain` before and after
    `_collect_semantic_producer_metrics` and asserts equality. Producers may
    only touch an ephemeral shadow workspace, never the live repo index/worktree.
    """
    import subprocess
    from contextlib import contextmanager

    from git_cg.graph_context import GraphOperationResult, GraphOutcome
    from git_cg.main import _collect_semantic_producer_metrics
    from git_cg.semantic import empty_graph_product_fields

    repo = tmp_path / "live-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True)
    tracked = repo / "tracked.py"
    tracked.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    # Staged change present (index dirty relative to HEAD is OK and stable).
    tracked.write_text("x = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=repo, check=True, capture_output=True)

    def porcelain() -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"],
            text=True,
        )

    before = porcelain()

    _phase75_base_monkeypatches(monkeypatch)
    monkeypatch.setattr("git_cg.git_index.should_refresh_graph", lambda: True)

    shadow_path = str(tmp_path / "shadow-policy-b")

    @contextmanager
    def fake_shadow(source_dir=".", include_unstaged=True):
        # Ephemeral shadow only — must not touch live repo paths.
        yield type("Shadow", (), {"path": shadow_path, "clone_sync_latency_ms": 0.5})()

    def fake_refresh(**kwargs):
        assert kwargs.get("repo_root") == shadow_path
        return GraphOperationResult(
            ok=True,
            operation="refresh_graph",
            outcome=GraphOutcome.OK,
            data={},
            latency_ms=1.0,
        )

    def fake_stats(*, repo_root=None, **kwargs):
        assert repo_root == shadow_path
        return GraphOperationResult(
            ok=True,
            operation="stats",
            outcome=GraphOutcome.OK,
            data={"schema_version": "s"},
            latency_ms=0.1,
        )

    def fake_bundle(**kwargs):
        assert kwargs.get("repo_root") == shadow_path
        product = empty_graph_product_fields()
        product["blast_radius_size"] = 1
        product["affected_flows_count"] = 2
        product["graph_fallback_reasons"] = []
        return (
            product,
            [
                GraphOperationResult(
                    ok=True,
                    operation="affected_flows",
                    outcome=GraphOutcome.OK,
                    data={
                        "flows": [
                            {"id": "flow_a", "files": ["tracked.py"]},
                            {"id": "flow_b", "files": ["other.py"]},
                        ]
                    },
                    latency_ms=0.2,
                )
            ],
        )

    monkeypatch.setattr("git_cg.shadow_workspace.shadow_workspace", fake_shadow)
    monkeypatch.setattr("git_cg.graph_context.refresh_graph", fake_refresh)
    monkeypatch.setattr("git_cg.graph_context.graph_stats", fake_stats)
    monkeypatch.setattr("git_cg.graph_context.collect_graph_product_bundle", fake_bundle)
    monkeypatch.setattr(
        "git_cg.graph_context.collect_graph_telemetry",
        lambda **kwargs: {"graph_build_latency_ms": 1.0, "graph_query_latency_ms": 0.3},
    )
    # Avoid real staged-source IO side effects beyond git status snapshot.
    monkeypatch.setattr(
        "git_cg.git_index.read_staged_sources",
        lambda *a, **k: type("Staged", (), {"files": {"tracked.py": b"x = 2\n"}, "changed_files": ["tracked.py"]})(),
    )
    monkeypatch.setattr(
        "git_cg.git_index.read_head_sources",
        lambda *a, **k: type("Head", (), {"files": {}})(),
    )

    out = _collect_semantic_producer_metrics(str(repo), enable_semantic=True, verbose=False)
    after = porcelain()

    assert before == after, f"live worktree/index contaminated:\nBEFORE:\n{before!r}\nAFTER:\n{after!r}"
    assert out.get("shadow_workspace_used") is True
    assert out.get("semantic_refresh_graph") == "ran"
