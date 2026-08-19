"""Gate composition — require_block only; C-prime ignored."""

from __future__ import annotations

from git_cg.eval.catalog import load_metric_catalog
from git_cg.eval.enums import Authority, Family, Polarity, Source
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.gates import (
    S2A_REQUIRE_BLOCK,
    S2B_REQUIRE_BLOCK,
    S2C_TOPOLOGY_BLOCK,
    assert_s2c_block_len,
    compose_gates,
)
from git_cg.eval.scoring.result_builder import make_score

_POL = {m["metric_id"]: m["polarity"] for m in load_metric_catalog()["metrics"]}


def _pass_row(metric_id: str) -> ScoreResultV1:
    """Catalog-aligned passing row for polarity-aware gate fixtures."""
    pol = _POL[metric_id]
    if pol == "lower_is_better":
        return make_score(metric_id, 0, passed=True)
    if pol == "higher_is_better":
        return make_score(metric_id, 1.0, passed=True)
    return make_score(metric_id, True, passed=True)


def _fail_row(metric_id: str) -> ScoreResultV1:
    """Catalog-aligned failing row for polarity-aware gate fixtures."""
    pol = _POL[metric_id]
    if pol == "lower_is_better":
        return make_score(metric_id, 2, passed=False)
    if pol == "higher_is_better":
        return make_score(metric_id, 0.0, passed=False)
    return make_score(metric_id, False, passed=False)


def test_deterministic_pass_all_required_ok() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows, bound=True)
    by = {g.metric_id: g for g in gates}
    assert by["gate.deterministic_pass"].passed is True


def test_missing_required_fails_closed() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK if m != "b.header_shape"]
    gates = compose_gates(rows)
    g = next(x for x in gates if x.metric_id == "gate.deterministic_pass")
    assert g.passed is False
    assert "missing:b.header_shape" in (g.failure_ids or [])


def test_failed_required_fails_gate() -> None:
    rows = [_fail_row(m) if m == "a.final_message_present" else _pass_row(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows)
    g = next(x for x in gates if x.metric_id == "gate.deterministic_pass")
    assert g.passed is False
    assert "a.final_message_present" in (g.failure_ids or [])


def test_cprime_failure_ignored() -> None:
    """True C-prime / lab advisory failures must not veto deterministic_pass."""
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.append(
        ScoreResultV1(
            metric_id="cprime.fake_advisory",
            polarity=Polarity.PASS_FAIL,
            authority=Authority.ADVISORY,
            source=Source.LANE_C_JUDGE,
            value=False,
            passed=False,
            family=Family.CPRIME,
        )
    )
    gates = compose_gates(rows, bound=True)
    g = next(x for x in gates if x.metric_id == "gate.deterministic_pass")
    assert g.passed is True
    ignored = (g.evidence or {}).get("ignored_advisory_failures") or []
    assert any(x.startswith("cprime") for x in ignored)


def test_unrequested_c_failure_not_labeled_advisory() -> None:
    """Unrequested Plane A c.* failures must not be ignored_advisory_failures."""
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.append(
        ScoreResultV1(
            metric_id="c.contract_smoke",
            polarity=Polarity.PASS_FAIL,
            authority=Authority.LAW,
            source=Source.LOCAL_WRAPPER,
            value=False,
            passed=False,
            family=Family.C,
        )
    )
    gates = compose_gates(rows, bound=True)
    g = next(x for x in gates if x.metric_id == "gate.deterministic_pass")
    assert g.passed is True  # not in S2A require block
    ignored = (g.evidence or {}).get("ignored_advisory_failures") or []
    assert "c.contract_smoke" not in ignored


def test_semantic_cohort_deferred_s2a() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows, bound=True)
    sc = next(x for x in gates if x.metric_id == "gate.semantic_cohort_eligible")
    assert sc.passed is False
    # Offline Lane A/B: deferred wording retained; D32 evidence vocabulary updated.
    assert sc.reason == "semantic_cohort_deferred_offline_later_lane"
    assert "deferred" in (sc.reason or "")
    assert sc.failure_ids == ["GATE_SEMANTIC_COHORT_DEFERRED"]
    assert sc.evidence is not None
    assert sc.evidence.get("cprime_ran") is False
    assert sc.evidence.get("invoked") is False
    assert sc.evidence.get("offline_lane_ab") is True
    assert "offline_s2b" not in sc.evidence


def test_promotion_requires_bound_and_gold() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows, bound=False)
    promo = next(x for x in gates if x.metric_id == "gate.golden_promotion_eligible")
    assert promo.passed is False


def test_promotion_requires_explicit_skeleton_row() -> None:
    """Custom require_block that omits skeleton must not promote as clean."""
    custom_block = tuple(m for m in S2A_REQUIRE_BLOCK if m != "d.skeleton_fallback_final")
    assert "d.gold_report_ok" in custom_block
    assert "d.skeleton_fallback_final" not in custom_block
    rows = [_pass_row(m) for m in custom_block]
    gates = compose_gates(rows, bound=True, require_block=custom_block)
    det = next(x for x in gates if x.metric_id == "gate.deterministic_pass")
    promo = next(x for x in gates if x.metric_id == "gate.golden_promotion_eligible")
    assert det.passed is True
    assert promo.passed is False
    assert (promo.evidence or {}).get("skeleton_clean") is False


def test_s2b_require_block_is_68_unique_catalog_ids() -> None:
    assert len(S2B_REQUIRE_BLOCK) == 68
    assert len(set(S2B_REQUIRE_BLOCK)) == 68
    assert set(S2A_REQUIRE_BLOCK).issubset(set(S2B_REQUIRE_BLOCK))
    assert "h.structured_bundle_compliance" in S2B_REQUIRE_BLOCK
    # warn rows stay out
    for mid in (
        "c.changelog_antisignal",
        "c.evidence_surface_precision",
        "c.evidence_surface_recall",
        "e.docs_tests_craft",
        "e.low_confidence_posture",
        "e.min_included_bullets",
        "e.stub_inventory_coherent",
        "f.claim_evidence_alignment",
        "h.eval_input_size_ok",
    ):
        assert mid not in S2B_REQUIRE_BLOCK


def test_compose_gates_rejects_duplicate_metric_ids() -> None:
    import pytest

    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.append(_pass_row("a.final_message_present"))
    with pytest.raises(ValueError, match="duplicate metric_id"):
        compose_gates(rows, bound=True)


def test_s2c_topology_block_constant() -> None:
    """S2C topology block is exactly 12 unique i.* ids and is opt-in only."""
    assert_s2c_block_len()
    assert len(S2C_TOPOLOGY_BLOCK) == 12
    assert len(set(S2C_TOPOLOGY_BLOCK)) == 12
    assert all(mid.startswith("i.") for mid in S2C_TOPOLOGY_BLOCK)
    for mid in S2C_TOPOLOGY_BLOCK:
        assert mid not in S2A_REQUIRE_BLOCK
        assert mid not in S2B_REQUIRE_BLOCK


def test_compose_gates_require_topology_false_default() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows, bound=True)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    assert det.passed is True
    assert (det.evidence or {}).get("require_topology") is False
    assert (det.evidence or {}).get("s2c_topology_block") == []
