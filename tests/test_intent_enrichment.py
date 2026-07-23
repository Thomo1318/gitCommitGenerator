"""Slice 1 gated marker enrichment tests for Issue #161."""

from __future__ import annotations

import pytest

from git_cg.intent import (
    CLOSED_ENRICHMENT_MARKERS,
    DiffSignals,
    FingerprintEnrichmentFacts,
    GraphEnrichmentFacts,
    SemanticEnrichmentFacts,
    _generate_signal_markers,
    collect_active_markers,
    enrich_markers_from_facts,
    matrix_signal_vocabulary,
    rank_commit_intents,
)
from git_cg.sop import load_sop


@pytest.fixture
def sop_matrix() -> list[dict]:
    """
    Load the Gitmoji reference matrix from the SOP data.
    
    Returns:
    	list[dict]: The Gitmoji reference matrix, or an empty list when it is absent.
    """
    data = load_sop()
    return data.get("gitmoji_reference_matrix", [])


@pytest.fixture
def matrix_vocab(sop_matrix: list[dict]) -> frozenset[str]:
    """Return the set of signal markers defined in the SOP matrix.
    
    Parameters:
    	sop_matrix (list[dict]): SOP matrix entries from which to derive the marker vocabulary.
    
    Returns:
    	frozenset[str]: The SOP-defined signal marker vocabulary.
    """
    return matrix_signal_vocabulary(sop_matrix)


def test_closed_enrichment_markers_subset_of_live_sop(matrix_vocab: frozenset[str]) -> None:
    """Every closed enrichment marker must exist on the production matrix."""
    missing = sorted(CLOSED_ENRICHMENT_MARKERS - matrix_vocab)
    assert missing == [], f"closed markers missing from SOP vocabulary: {missing}"


def test_generate_signal_markers_additive_breaking_and_tests() -> None:
    markers = _generate_signal_markers(DiffSignals(has_breaking_change=True, touches_tests=True, adds_public_api=True))
    assert "breaking_change_declared" in markers
    assert "tests_added" in markers
    assert "new_api" in markers


def test_enrichment_ignored_when_semantic_disabled(sop_matrix: list[dict]) -> None:
    signals = DiffSignals(adds_public_api=True, files=["src/api.py"])
    facts = SemanticEnrichmentFacts(
        graph=GraphEnrichmentFacts(total_impacted=40, outcome="ok"),
    )
    baseline = rank_commit_intents(signals, sop_matrix, enable_semantic=False)
    enriched_off = rank_commit_intents(
        signals,
        sop_matrix,
        enrichment=facts,
        enable_semantic=False,
    )
    assert [(r.intent_id, r.score, r.semver_impact) for r in enriched_off] == [
        (r.intent_id, r.score, r.semver_impact) for r in baseline
    ]
    assert collect_active_markers(signals, enrichment=facts, enable_semantic=False) == set(
        _generate_signal_markers(signals)
    )


def test_graph_enrichment_adds_architecture_markers_when_semantic_on(
    sop_matrix: list[dict], matrix_vocab: frozenset[str]
) -> None:
    signals = DiffSignals(files=["src/core/engine.py"])
    facts = SemanticEnrichmentFacts(
        graph=GraphEnrichmentFacts(total_impacted=30, outcome="ok"),
    )
    markers = collect_active_markers(
        signals,
        enrichment=facts,
        enable_semantic=True,
        matrix_vocab=matrix_vocab,
    )
    assert "major_subsystem_restructured" in markers
    assert "core_architecture_changed" in markers

    ranked = rank_commit_intents(
        signals,
        sop_matrix,
        enrichment=facts,
        enable_semantic=True,
    )
    baseline = rank_commit_intents(signals, sop_matrix, enable_semantic=False)
    # Enrichment may change scores but never invents semver outside matrix rows.
    by_id_base = {r.intent_id: r for r in baseline}
    for row in ranked:
        assert row.semver_impact == by_id_base[row.intent_id].semver_impact


def test_graph_enrichment_medium_blast_uses_internal_restructure(
    matrix_vocab: frozenset[str],
) -> None:
    facts = SemanticEnrichmentFacts(
        graph=GraphEnrichmentFacts(total_impacted=12, outcome="ok"),
    )
    markers = enrich_markers_from_facts(facts, matrix_vocab=matrix_vocab)
    assert markers == {"internal_restructure"}


def test_graph_unavailable_or_error_emits_no_markers(matrix_vocab: frozenset[str]) -> None:
    for outcome in ("unavailable", "error"):
        facts = SemanticEnrichmentFacts(
            graph=GraphEnrichmentFacts(total_impacted=99, outcome=outcome),  # type: ignore[arg-type]
        )
        assert enrich_markers_from_facts(facts, matrix_vocab=matrix_vocab) == set()


def test_fingerprint_enrichment_formatting_and_comments(
    matrix_vocab: frozenset[str],
) -> None:
    facts = SemanticEnrichmentFacts(
        fingerprints=FingerprintEnrichmentFacts(
            class_counts={"comments_only": 2, "formatting_only": 1},
            body_similarity_min=0.95,
            markers=["inline_comment_changed", "not_a_real_marker", "test_coverage_gap"],
        )
    )
    markers = enrich_markers_from_facts(facts, matrix_vocab=matrix_vocab)
    assert "comments_only" in markers
    assert "formatting_only" in markers
    assert "inline_comment_changed" in markers
    assert "not_a_real_marker" not in markers
    assert "test_coverage_gap" not in markers


def test_unknown_enrichment_marker_strings_filtered(matrix_vocab: frozenset[str]) -> None:
    facts = SemanticEnrichmentFacts(
        fingerprints=FingerprintEnrichmentFacts(markers=["totally_invented_marker"]),
    )
    assert enrich_markers_from_facts(facts, matrix_vocab=matrix_vocab) == set()


def test_enrichment_does_not_mutate_diff_signals() -> None:
    signals = DiffSignals(only_docs=True, touches_docs=True)
    before = signals.model_dump()
    facts = SemanticEnrichmentFacts(
        graph=GraphEnrichmentFacts(total_impacted=50, outcome="ok"),
    )
    collect_active_markers(signals, enrichment=facts, enable_semantic=True)
    assert signals.model_dump() == before
    assert signals.only_docs is True


def test_named_semantic_fixture_changes_only_when_enabled(sop_matrix: list[dict]) -> None:
    """Named enriched-lane fixture: architecture facts only affect semantic-on ranks."""
    signals = DiffSignals(files=["src/hub.py"])
    facts = SemanticEnrichmentFacts(
        graph=GraphEnrichmentFacts(total_impacted=40, outcome="ok"),
    )
    off = [(r.intent_id, r.score) for r in rank_commit_intents(signals, sop_matrix, enable_semantic=False)]
    on = [
        (r.intent_id, r.score) for r in rank_commit_intents(signals, sop_matrix, enrichment=facts, enable_semantic=True)
    ]
    assert off != on
    # Without facts, semantic-on matches semantic-off for this baseline signal set.
    on_no_facts = [(r.intent_id, r.score) for r in rank_commit_intents(signals, sop_matrix, enable_semantic=True)]
    assert on_no_facts == off
