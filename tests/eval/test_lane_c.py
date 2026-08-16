"""S5a Lane C-prime — gated secondary semantic cohort skeleton.

Covers the plan §6.11 ``gate.semantic_cohort_eligible`` formula, fail-closed
credential handling (F4), advisory authority stamping (F3), and preservation of
the offline Lane A/B path (no verdict → gate stays False / deferred).
"""

from __future__ import annotations

import pytest

from git_cg.eval.enums import Authority, Source
from git_cg.eval.lane_c import (
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
    judge_pins_resolvable,
    resolve_allows_lane_c,
    resolve_lab_override,
)
from git_cg.eval.lane_c.judge import REASON_EMPTY_INPUT
from git_cg.eval.lane_c.runner import (
    REASON_COHORT_INELIGIBLE,
    run_lane_c,
)
from git_cg.eval.scoring import compose_gates

# ---------------------------------------------------------------------------
# Suite flag resolution (N19 order: explicit arg → suite.meta → False)
# ---------------------------------------------------------------------------


class TestResolveAllowsLaneC:
    def test_default_false_no_suite(self) -> None:
        assert resolve_allows_lane_c(None, None) is False

    def test_explicit_arg_wins(self) -> None:
        assert resolve_allows_lane_c(True, {"meta": {"allows_lane_c": False}}) is True
        assert resolve_allows_lane_c(False, {"meta": {"allows_lane_c": True}}) is False

    def test_suite_meta_bool(self) -> None:
        assert resolve_allows_lane_c(None, {"meta": {"allows_lane_c": True}}) is True
        assert resolve_allows_lane_c(None, {"meta": {"allows_lane_c": False}}) is False

    def test_suite_meta_non_bool_ignored(self) -> None:
        # N19: bool only; truthy strings/ints must not enable Lane C-prime.
        assert resolve_allows_lane_c(None, {"meta": {"allows_lane_c": "yes"}}) is False
        assert resolve_allows_lane_c(None, {"meta": {"allows_lane_c": 1}}) is False

    def test_never_inferred_from_bound(self) -> None:
        assert resolve_allows_lane_c(None, {"bound": True}) is False


class TestResolveLabOverride:
    def test_default_false(self) -> None:
        assert resolve_lab_override(None, None) is False

    def test_explicit_arg_wins(self) -> None:
        assert resolve_lab_override(True, {"meta": {"lab_override": False}}) is True

    def test_suite_meta_bool(self) -> None:
        assert resolve_lab_override(None, {"meta": {"lab_override": True}}) is True

    def test_non_bool_ignored(self) -> None:
        assert resolve_lab_override(None, {"meta": {"lab_override": 1}}) is False


# ---------------------------------------------------------------------------
# Judge pin resolvability (fail-closed, no network, no raise)
# ---------------------------------------------------------------------------


class TestJudgePinsResolvable:
    def test_both_present(self) -> None:
        env = {"GIT_CG_EVAL_JUDGE_MODEL": "gpt-4o-2024-08-06", "GIT_CG_EVAL_JUDGE_API_KEY": "k"}
        assert judge_pins_resolvable(environ=env) is True

    def test_missing_key(self) -> None:
        assert judge_pins_resolvable(environ={"GIT_CG_EVAL_JUDGE_MODEL": "m"}) is False

    def test_missing_model(self) -> None:
        assert judge_pins_resolvable(environ={"GIT_CG_EVAL_JUDGE_API_KEY": "k"}) is False

    def test_empty_env(self) -> None:
        assert judge_pins_resolvable(environ={}) is False

    def test_latest_model_rejected(self) -> None:
        # F5: floating "latest" judge forbidden.
        env = {"GIT_CG_EVAL_JUDGE_MODEL": "latest", "GIT_CG_EVAL_JUDGE_API_KEY": "k"}
        assert judge_pins_resolvable(environ=env) is False

    def test_blank_model_rejected(self) -> None:
        env = {"GIT_CG_EVAL_JUDGE_MODEL": "   ", "GIT_CG_EVAL_JUDGE_API_KEY": "k"}
        assert judge_pins_resolvable(environ=env) is False

    def test_explicit_overrides(self) -> None:
        assert judge_pins_resolvable(judge_model="m", judge_api_key="k", environ={}) is True
        assert judge_pins_resolvable(judge_model="", judge_api_key="k", environ={}) is False


# ---------------------------------------------------------------------------
# Eligibility formula (plan §6.11)
# ---------------------------------------------------------------------------


def _elig(**kw: object) -> LaneCEligibility:
    env = {"GIT_CG_EVAL_JUDGE_MODEL": "m", "GIT_CG_EVAL_JUDGE_API_KEY": "k"}
    kw.setdefault("environ", env)
    return evaluate_semantic_cohort_eligibility(**kw)  # type: ignore[arg-type]


class TestEligibilityFormula:
    def test_full_eligible(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=True)
        assert e.eligible is True
        assert e.reason == "eligible"

    def test_not_allowed_by_suite(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=False)
        assert e.eligible is False
        assert e.reason == "lane_c_not_allowed_by_suite"

    def test_det_fail_no_override(self) -> None:
        e = _elig(deterministic_pass=False, allows_lane_c=True, lab_override=False)
        assert e.eligible is False
        assert e.reason == "deterministic_pass_false_no_lab_override"

    def test_det_fail_with_lab_override(self) -> None:
        # lab_override permits the cohort despite deterministic fail (lab only).
        e = _elig(deterministic_pass=False, allows_lane_c=True, lab_override=True)
        assert e.eligible is True

    def test_pins_unresolvable(self) -> None:
        e = evaluate_semantic_cohort_eligibility(deterministic_pass=True, allows_lane_c=True, environ={})
        assert e.eligible is False
        assert e.reason == "judge_pins_unresolvable"

    def test_missing_credentials_fail_closed_not_raise(self) -> None:
        # AC: missing credentials → skip/lab-fail class, never an exception.
        e = evaluate_semantic_cohort_eligibility(deterministic_pass=True, allows_lane_c=True, environ={})
        assert e.judge_pins_resolvable is False
        assert e.eligible is False


# ---------------------------------------------------------------------------
# Runner — gating skeleton (no live judge in S5a)
# ---------------------------------------------------------------------------


class TestRunLaneC:
    def test_ineligible_emits_skip_rows_advisory(self) -> None:
        rows, elig = run_lane_c(
            ["cprime.geval_craft", "cprime.geval_relevance"],
            deterministic_pass=True,
            allows_lane_c=False,
            environ={},
        )
        assert elig.eligible is False
        assert len(rows) == 2
        for r in rows:
            assert r.authority is Authority.ADVISORY  # F3
            assert r.source is Source.LANE_C_JUDGE
            assert r.passed is None
            assert r.reason == REASON_COHORT_INELIGIBLE
            assert r.evidence and r.evidence["skipped"] is True

    def test_eligible_without_message_skips_gracefully(self) -> None:
        # S5c: an eligible cohort with no message to score degrades to an honest
        # empty-input skip (never a fabricated score, never a raise).
        env = {"GIT_CG_EVAL_JUDGE_MODEL": "m", "GIT_CG_EVAL_JUDGE_API_KEY": "k"}
        rows, elig = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=env,
            message="",
        )
        assert elig.eligible is True
        assert rows[0].reason == REASON_EMPTY_INPUT
        assert rows[0].passed is None
        assert rows[0].authority is Authority.ADVISORY

    def test_unknown_metric_id_fails_closed(self) -> None:
        with pytest.raises(KeyError):
            run_lane_c(["cprime.does_not_exist"], deterministic_pass=True, allows_lane_c=True, environ={})

    def test_empty_metric_list(self) -> None:
        rows, _elig = run_lane_c([], deterministic_pass=True, allows_lane_c=True, environ={})
        assert rows == []


# ---------------------------------------------------------------------------
# Gate composition — offline default unchanged; verdict threaded when supplied
# ---------------------------------------------------------------------------


class TestGateComposition:
    def _gate_row(self, rows: list, lane_c_eligibility: LaneCEligibility | None = None):
        gates = compose_gates(rows, require_block=(), lane_c_eligibility=lane_c_eligibility)
        return next(g for g in gates if g.metric_id == "gate.semantic_cohort_eligible")

    def test_offline_default_false_deferred(self) -> None:
        # No verdict → offline Lane A/B unchanged.
        row = self._gate_row([], lane_c_eligibility=None)
        assert row.passed is False
        assert row.reason == "semantic_cohort_deferred_offline_later_lane"
        assert row.failure_ids == ["GATE_SEMANTIC_COHORT_DEFERRED"]

    def test_verdict_eligible_true(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=True)
        row = self._gate_row([], lane_c_eligibility=e)
        assert row.passed is True
        assert row.reason is None
        assert row.failure_ids is None
        assert row.evidence and row.evidence["cprime_ran"] is True

    def test_verdict_ineligible_false(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=False)
        row = self._gate_row([], lane_c_eligibility=e)
        assert row.passed is False
        assert row.reason == "lane_c_not_allowed_by_suite"
        assert row.failure_ids == ["GATE_SEMANTIC_COHORT_INELIGIBLE"]

    def test_gate_row_is_law_authority(self) -> None:
        # The gate itself is law (entry gate), distinct from advisory C-prime scores.
        row = self._gate_row([], lane_c_eligibility=None)
        assert row.authority is Authority.LAW
