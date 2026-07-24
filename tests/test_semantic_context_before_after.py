"""Claim B deterministic before/after pack for Phase 7 semantic context (#162).

Mirrors characterisation discipline (corpus + goldens + SOP sha pin).
No live LLM, Opik workspace, or hub/callers fan-out.

Golden regeneration (explicit only; never on normal just test):
    GIT_CG_REGENERATE_SEMANTIC_CONTEXT_GOLDENS=1 uv run pytest \\
        tests/test_semantic_context_before_after.py -q
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from git_cg.graph_context import GraphOperationResult, GraphOutcome
from git_cg.intent import (
    DiffSignals,
    FingerprintEnrichmentFacts,
    GraphEnrichmentFacts,
    SemanticEnrichmentFacts,
    collect_active_markers,
    matrix_signal_vocabulary,
    rank_commit_intents,
)
from git_cg.semantic import build_semantic_summary, map_graph_product_results
from git_cg.sop import load_sop

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "semantic_context_before_after"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"
GOLDENS_PATH = FIXTURE_DIR / "goldens.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sop_matrix_sha256(matrix: list[dict]) -> str:
    payload = json.dumps(matrix, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _rank_top(ranked, n: int = 3) -> list[dict]:
    rows: list[dict] = []
    for item in ranked[:n]:
        rows.append(
            {
                "intent_id": item.intent_id,
                "score": item.score,
                "semver_impact": item.semver_impact,
                "priority": item.priority,
                "specificity": item.specificity,
            }
        )
    return rows


def _run_case(
    *,
    signals: dict,
    matrix: list[dict],
    vocab: frozenset[str],
    enable: bool,
    graph_spec: dict | None,
    fp_spec: dict | None,
) -> dict:
    diff_signals = DiffSignals(**signals)
    graph = GraphEnrichmentFacts(**graph_spec) if graph_spec else None
    fp = FingerprintEnrichmentFacts(**fp_spec) if fp_spec else None
    enrichment = None
    if enable and (graph is not None or fp is not None):
        enrichment = SemanticEnrichmentFacts(graph=graph, fingerprints=fp)

    markers = sorted(
        collect_active_markers(
            diff_signals,
            enrichment=enrichment if enable else None,
            enable_semantic=enable,
            matrix_vocab=vocab,
        )
    )
    ranked = rank_commit_intents(
        diff_signals,
        matrix,
        enrichment=enrichment if enable else None,
        enable_semantic=enable,
    )
    top = _rank_top(ranked, 3)
    primary = top[0] if top else None

    summary = None
    if enable:
        metrics: dict = {}
        # Exercise production graph-product mapping (not hand-built field copies).
        if graph is not None:
            detect_data: dict = {}
            if graph.outcome == "ok":
                if graph.total_impacted is not None:
                    detect_data["total_impacted"] = graph.total_impacted
                if graph.test_gaps_count is not None:
                    detect_data["test_gaps"] = [f"gap-{i}" for i in range(int(graph.test_gaps_count))]
                if graph.impacted_has_test_nodes is not None:
                    detect_data["impacted_has_test_nodes"] = graph.impacted_has_test_nodes
                if graph.impacted_has_production_nodes is not None:
                    detect_data["impacted_has_production_nodes"] = graph.impacted_has_production_nodes
            detect = GraphOperationResult(
                ok=graph.outcome == "ok",
                operation="detect_changes",
                outcome=GraphOutcome(graph.outcome),
                latency_ms=0.0,
                data=detect_data,
                error=None if graph.outcome == "ok" else graph.outcome,
                error_type=None if graph.outcome == "ok" else graph.outcome,
            )
            impact = GraphOperationResult(
                ok=graph.outcome == "ok",
                operation="impact_radius",
                outcome=GraphOutcome(graph.outcome),
                latency_ms=0.0,
                data={"total_impacted": graph.total_impacted} if graph.outcome == "ok" else {},
                error=None if graph.outcome == "ok" else graph.outcome,
                error_type=None if graph.outcome == "ok" else graph.outcome,
            )
            flows = GraphOperationResult(
                ok=graph.outcome == "ok",
                operation="affected_flows",
                outcome=GraphOutcome(graph.outcome),
                latency_ms=0.0,
                data={"total": 2 if (graph.total_impacted or 0) >= 10 else 0} if graph.outcome == "ok" else {},
                error=None if graph.outcome == "ok" else graph.outcome,
                error_type=None if graph.outcome == "ok" else graph.outcome,
            )
            product = map_graph_product_results(
                detect_result=detect,
                impact_result=impact,
                flows_result=flows,
            )
            metrics.update(product)
        if fp is not None:
            metrics.update(
                {
                    "body_similarity_min": fp.body_similarity_min,
                    "body_similarity_avg": fp.body_similarity_avg,
                    "fingerprint_class_counts": fp.class_counts,
                }
            )
        if not metrics:
            metrics = {"body_similarity_min": 0.1}
        summary = build_semantic_summary(metrics)

    return {
        "markers": markers,
        "top1": primary["intent_id"] if primary else None,
        "top3": [row["intent_id"] for row in top],
        "semver_impact": primary["semver_impact"] if primary else None,
        "blast_radius_size": summary.blast_radius_size if summary else None,
        "affected_flows_count": summary.affected_flows_count if summary else None,
        "test_coverage_gap": summary.test_coverage_gap if summary else None,
        "summary_present": summary is not None,
        "fallback_reasons": list(summary.fallback_reasons) if summary else [],
    }


@pytest.fixture(scope="module")
def sop_matrix() -> list[dict]:
    matrix = load_sop().get("gitmoji_reference_matrix", [])
    assert matrix, "production SOP matrix must load"
    return matrix


@pytest.fixture(scope="module")
def corpus() -> dict:
    assert CORPUS_PATH.is_file(), f"missing corpus: {CORPUS_PATH}"
    return _load_json(CORPUS_PATH)


@pytest.fixture(scope="module")
def goldens() -> dict:
    assert GOLDENS_PATH.is_file(), f"missing goldens: {GOLDENS_PATH}"
    return _load_json(GOLDENS_PATH)


def _case_ids() -> list[str]:
    data = _load_json(CORPUS_PATH)
    return [case["id"] for case in data["cases"]]


def test_claim_b_fixture_count_and_families(corpus: dict) -> None:
    cases = corpus["cases"]
    assert len(cases) >= 12
    families = {case["family"] for case in cases}
    required = {
        "docs_only",
        "tests_only",
        "formatting_ish",
        "public_api",
        "blast_internal",
        "blast_major",
        "blast_below",
        "graph_fallback",
        "empty_tiny",
        "mixed_intent",
        "security_path",
        "control_equal",
    }
    missing = required - families
    assert not missing, f"missing mandatory families: {sorted(missing)}"


def test_claim_b_pins_production_sop(sop_matrix: list[dict], corpus: dict, goldens: dict) -> None:
    live = _sop_matrix_sha256(sop_matrix)
    assert corpus["sop_matrix_sha256"] == live
    assert goldens["sop_matrix_sha256"] == live
    assert corpus["sop_matrix_row_count"] == len(sop_matrix)
    assert goldens["sop_matrix_row_count"] == len(sop_matrix)
    assert set(goldens["cases"]) == {case["id"] for case in corpus["cases"]}


@pytest.mark.parametrize("case_id", _case_ids())
def test_claim_b_case_matches_golden(
    case_id: str,
    sop_matrix: list[dict],
    corpus: dict,
    goldens: dict,
) -> None:
    case = next(item for item in corpus["cases"] if item["id"] == case_id)
    expected = goldens["cases"][case_id]
    vocab = matrix_signal_vocabulary(sop_matrix)

    actual_off = _run_case(
        signals=case.get("signals") or {},
        matrix=sop_matrix,
        vocab=vocab,
        enable=False,
        graph_spec=None,
        fp_spec=None,
    )
    actual_on = _run_case(
        signals=case.get("signals") or {},
        matrix=sop_matrix,
        vocab=vocab,
        enable=True,
        graph_spec=case.get("graph"),
        fp_spec=case.get("fingerprints"),
    )

    if os.environ.get("GIT_CG_REGENERATE_SEMANTIC_CONTEXT_GOLDENS") == "1":
        expected["flag_off"] = actual_off
        expected["flag_on"] = actual_on
        goldens["cases"][case_id] = expected
        GOLDENS_PATH.write_text(json.dumps(goldens, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert actual_off == expected["flag_off"], f"{case_id} flag-off drift"
    assert actual_on == expected["flag_on"], f"{case_id} flag-on drift"

    # Policy assertions beyond raw golden equality.
    if case.get("equal_to_flag_off"):
        assert actual_on["markers"] == actual_off["markers"]
        assert actual_on["top1"] == actual_off["top1"]
        assert actual_on["top3"] == actual_off["top3"]
        assert actual_on["semver_impact"] == actual_off["semver_impact"]

    if case.get("expects_rank_delta"):
        assert (
            actual_on["markers"] != actual_off["markers"]
            or actual_on["top1"] != actual_off["top1"]
            or actual_on["top3"] != actual_off["top3"]
        )

    if case.get("expects_phase7_fields"):
        assert actual_on["summary_present"] is True
        assert (
            actual_on["blast_radius_size"] is not None
            or actual_on["affected_flows_count"] is not None
            or actual_on["test_coverage_gap"] is not None
            or actual_on["markers"]  # fingerprint-only fill path
        )

    if case.get("expects_fallback"):
        assert actual_on["summary_present"] is True
        # Unavailable/error graph must not invent architecture markers.
        assert "major_subsystem_restructured" not in actual_on["markers"]
        assert "internal_restructure" not in actual_on["markers"]

    # Closed-vocab: every flag-on marker must exist in the live SOP matrix vocabulary.
    assert set(actual_on["markers"]) <= set(vocab)
