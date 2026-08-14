"""Gate composition — require_block only; C-prime ignored."""

from __future__ import annotations

from git_cg.eval.catalog import load_metric_catalog
from git_cg.eval.enums import Authority, Family, Polarity, Source
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.gates import S2A_REQUIRE_BLOCK, compose_gates
from git_cg.eval.scoring.result_builder import make_score

_POL = {m["metric_id"]: m["polarity"] for m in load_metric_catalog()["metrics"]}


def _pass_row(metric_id: str) -> ScoreResultV1:
    """
    Create a passing score result for a metric using its configured polarity.
    
    Parameters:
    	metric_id (str): Identifier of the metric for which to create the score.
    
    Returns:
    	ScoreResultV1: A passing score result with a polarity-appropriate value.
    """
    pol = _POL[metric_id]
    if pol == "lower_is_better":
        return make_score(metric_id, 0, passed=True)
    if pol == "higher_is_better":
        return make_score(metric_id, 1.0, passed=True)
    return make_score(metric_id, True, passed=True)


def _fail_row(metric_id: str) -> ScoreResultV1:
    """Create a failed score result using a polarity-appropriate failing value for the specified metric."""
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
    """C-prime / advisory failures must not veto deterministic_pass."""
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.append(
        ScoreResultV1(
            metric_id="c.fake_advisory",
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
    assert any(x.startswith("c.") for x in ignored)


def test_semantic_cohort_deferred_s2a() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows, bound=True)
    sc = next(x for x in gates if x.metric_id == "gate.semantic_cohort_eligible")
    assert sc.passed is False
    assert sc.reason == "cprime_deferred_s2a"


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
