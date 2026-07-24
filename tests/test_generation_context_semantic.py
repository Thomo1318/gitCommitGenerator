"""Direct tests for Phase 7 GenerationContext wiring (#162)."""

from __future__ import annotations

from git_cg.intent import (
    DiffSignals,
    GraphEnrichmentFacts,
    SemanticEnrichmentFacts,
    collect_active_markers,
    matrix_signal_vocabulary,
)
from git_cg.main import _build_generation_context, _build_semantic_enrichment_facts
from git_cg.regeneration import GenerationContext, RegenerationState, resolve_semantic_contract
from git_cg.semantic import RiskAssessment, SemanticDiffSummary, build_semantic_summary
from git_cg.sop import load_sop


def test_build_generation_context_flag_off_omits_summary(monkeypatch):
    monkeypatch.delenv("GIT_CG_ENABLE_SEMANTIC", raising=False)
    summary = SemanticDiffSummary(blast_radius_size=3)
    risk = RiskAssessment(risk_score=0.2, outcome="ok")
    ctx = _build_generation_context(
        "diff --git a/x b/x\n",
        enable_semantic=False,
        semantic_summary=summary,
        risk_assessment=risk,
    )
    assert isinstance(ctx, GenerationContext)
    assert ctx.semantic_summary is None
    assert ctx.risk_assessment is None


def test_build_generation_context_flag_on_keeps_summary(monkeypatch):
    monkeypatch.setenv("GIT_CG_ENABLE_SEMANTIC", "1")
    summary = SemanticDiffSummary(blast_radius_size=12, affected_flows_count=2, test_coverage_gap=True)
    risk = RiskAssessment(risk_score=0.5, outcome="ok", priorities=["p1"])
    facts = _build_semantic_enrichment_facts(
        semantic_enabled=True,
        fingerprint_class_counts={"identifier_or_literal_only": 1},
        body_similarity_min=0.95,
        body_similarity_avg=0.96,
        fingerprint_markers=["formatting_only"],
        graph_enrichment=GraphEnrichmentFacts(total_impacted=12, outcome="ok"),
    )
    assert facts is not None
    assert facts.graph is not None
    ctx = _build_generation_context(
        "diff --git a/README.md b/README.md\n",
        enable_semantic=True,
        enrichment_facts=facts,
        semantic_summary=summary,
        risk_assessment=risk,
    )
    assert ctx.semantic_summary is summary
    assert ctx.risk_assessment is risk
    assert ctx.ranked_intents is not None


def test_enrichment_facts_graph_only():
    facts = _build_semantic_enrichment_facts(
        semantic_enabled=True,
        fingerprint_class_counts=None,
        body_similarity_min=None,
        body_similarity_avg=None,
        fingerprint_markers=None,
        graph_enrichment=GraphEnrichmentFacts(total_impacted=30, outcome="ok"),
    )
    assert facts is not None
    assert facts.graph is not None
    assert facts.fingerprints is None


def test_contract_ignores_semantic_summary_fields():
    ctx = GenerationContext(
        diff_signals=DiffSignals(only_docs=True, touches_docs=True),
        ranked_intents=[],
        constraints=__import__("git_cg.intent", fromlist=["IntentSelectionConstraints"]).IntentSelectionConstraints(),
        semantic_summary=SemanticDiffSummary(blast_radius_size=99),
        risk_assessment=RiskAssessment(risk_score=1.0, outcome="ok"),
    )
    # Empty ranked list uses fallback contract path; must not throw on extra fields.
    contract = resolve_semantic_contract(ctx, RegenerationState())
    assert contract.primary_intent_id
    assert contract.semver_impact


def test_closed_vocab_graph_markers_via_enrichment():
    sop = load_sop()
    matrix = sop.get("gitmoji_reference_matrix", [])
    vocab = matrix_signal_vocabulary(matrix)
    facts = SemanticEnrichmentFacts(graph=GraphEnrichmentFacts(total_impacted=25, outcome="ok"))
    markers = collect_active_markers(DiffSignals(), enrichment=facts, enable_semantic=True, matrix_vocab=vocab)
    assert "major_subsystem_restructured" in markers or "core_architecture_changed" in markers


def test_build_semantic_summary_helper_no_producer_io():
    summary = build_semantic_summary(
        {
            "blast_radius_size": 10,
            "affected_flows_count": 1,
            "test_coverage_gap": False,
            "body_similarity_min": 0.5,
        }
    )
    assert summary.blast_radius_size == 10
    assert summary.test_coverage_gap is False
