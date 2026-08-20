"""S5a Lane C' — eligibility, availability, taxonomy, runner skeleton, gate hook.

Covers issue #233 Slice 1 contracts:
C-ELIG / C-AVAIL / C-TAX / C-GATE / S5-A*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from git_cg.eval.enums import Authority, Source
from git_cg.eval.lane_c import (
    DEFAULT_LANE_C_METRICS,
    EXECUTION_CODES,
    GATE_DISPOSITION_CODES,
    GATE_TO_EXECUTION,
    LaneCEligibility,
    TaxonomyError,
    assert_execution_code,
    credentials_present,
    evaluate_judge_availability,
    evaluate_semantic_cohort_eligibility,
    failure_id_for,
    is_undated_model_alias,
    judge_identity_pins_resolvable,
    judge_pins_resolvable,
    map_gate_to_execution,
    resolve_allows_lane_c,
    resolve_lab_override,
    run_lane_c,
    validate_closed_reason,
)
from git_cg.eval.lane_c.taxonomy import (
    EXEC_COHORT_INELIGIBLE,
    EXEC_JUDGE_NOT_INVOKED,
    EXEC_LAB_OVERRIDE_DIAGNOSTIC,
    EXEC_UNAVAILABLE_CREDS,
    GATE_BUDGET_CAP_REACHED,
    GATE_DET_FAIL_EXCLUDED,
    GATE_JUDGE_UNAVAILABLE,
    GATE_LAB_OVERRIDE_DIAGNOSTIC,
    GATE_PROMPT_PACK_MISSING,
    GATE_SCOPE_GATE_REJECT,
)
from git_cg.eval.scoring import compose_gates
from git_cg.eval.scoring.gates import S2A_REQUIRE_BLOCK
from git_cg.eval.scoring.result_builder import make_score

PINNED_MODEL = "gpt-4o-2024-08-06"
PIN_ENV = {"GIT_CG_EVAL_JUDGE_MODEL": PINNED_MODEL}
PIN_ENV_WITH_KEY = {
    "GIT_CG_EVAL_JUDGE_MODEL": PINNED_MODEL,
    "GIT_CG_EVAL_JUDGE_API_KEY": "sk-test-not-real",
}


# ---------------------------------------------------------------------------
# Suite flag resolution (N19)
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
# Identity pins (NOT secrets)
# ---------------------------------------------------------------------------


class TestJudgeIdentityPins:
    def test_dated_model_ok_without_credentials(self) -> None:
        # D4': secrets must not be required for pin resolvability.
        assert judge_identity_pins_resolvable(environ=PIN_ENV) is True
        assert judge_pins_resolvable(environ=PIN_ENV) is True

    def test_missing_model_fails(self) -> None:
        assert judge_identity_pins_resolvable(environ={}) is False

    def test_latest_rejected(self) -> None:
        assert judge_identity_pins_resolvable(environ={"GIT_CG_EVAL_JUDGE_MODEL": "latest"}) is False
        assert judge_identity_pins_resolvable(environ={"GIT_CG_EVAL_JUDGE_MODEL": "gpt-4o-latest"}) is False

    def test_undated_alias_rejected(self) -> None:
        # D8 / F13: bare gpt-4o fails closed.
        assert is_undated_model_alias("gpt-4o") is True
        assert judge_identity_pins_resolvable(environ={"GIT_CG_EVAL_JUDGE_MODEL": "gpt-4o"}) is False

    def test_blank_model_rejected(self) -> None:
        assert judge_identity_pins_resolvable(environ={"GIT_CG_EVAL_JUDGE_MODEL": "   "}) is False

    def test_explicit_model_override(self) -> None:
        assert judge_identity_pins_resolvable(judge_model=PINNED_MODEL, environ={}) is True
        assert judge_identity_pins_resolvable(judge_model="", environ={}) is False

    def test_empty_pack_identity_fails(self) -> None:
        assert judge_identity_pins_resolvable(judge_model=PINNED_MODEL, pack_identity="  ", environ={}) is False

    def test_credentials_in_env_do_not_affect_pins(self) -> None:
        # Presence or absence of API key must not change identity pins.
        assert judge_identity_pins_resolvable(environ=PIN_ENV) is True
        assert judge_identity_pins_resolvable(environ=PIN_ENV_WITH_KEY) is True
        no_model = {"GIT_CG_EVAL_JUDGE_API_KEY": "sk-x"}
        assert judge_identity_pins_resolvable(environ=no_model) is False


# ---------------------------------------------------------------------------
# Eligibility formula (D4)
# ---------------------------------------------------------------------------


def _elig(**kw: Any) -> LaneCEligibility:
    kw.setdefault("environ", PIN_ENV)
    return evaluate_semantic_cohort_eligibility(**kw)


class TestEligibilityFormula:
    def test_full_eligible(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=True)
        assert e.eligible is True
        assert e.diagnostic_only is False
        assert e.reason == "eligible"
        assert e.pins_resolvable is True
        assert e.evidence["secrets_consulted"] is False

    def test_not_allowed_by_suite(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=False)
        assert e.eligible is False
        assert e.reason == "lane_c_not_allowed_by_suite"
        assert e.gate_disposition == GATE_SCOPE_GATE_REJECT
        assert EXEC_COHORT_INELIGIBLE in e.reasons

    def test_det_fail_no_override(self) -> None:
        e = _elig(deterministic_pass=False, allows_lane_c=True, lab_override=False)
        assert e.eligible is False
        assert e.reason == "deterministic_pass_false_no_lab_override"
        assert e.gate_disposition == GATE_DET_FAIL_EXCLUDED

    def test_det_fail_with_lab_override_is_diagnostic(self) -> None:
        e = _elig(deterministic_pass=False, allows_lane_c=True, lab_override=True)
        assert e.eligible is True
        assert e.diagnostic_only is True
        assert e.reason == GATE_LAB_OVERRIDE_DIAGNOSTIC
        assert e.gate_disposition == GATE_LAB_OVERRIDE_DIAGNOSTIC

    def test_pins_unresolvable_not_credential_reason(self) -> None:
        e = evaluate_semantic_cohort_eligibility(deterministic_pass=True, allows_lane_c=True, environ={})
        assert e.eligible is False
        assert e.pins_resolvable is False
        assert e.reason == "judge_identity_pins_unresolvable"
        assert "unavailable_creds" not in e.reasons
        assert "unauthorized" not in e.reason

    def test_missing_credentials_do_not_force_ineligible(self) -> None:
        # S5-A05 / D4': missing key leaves eligibility true when identity pins ok.
        e = evaluate_semantic_cohort_eligibility(
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV,  # model only — no API key
        )
        assert e.eligible is True
        assert e.pins_resolvable is True


# ---------------------------------------------------------------------------
# Availability (D4')
# ---------------------------------------------------------------------------


class TestAvailability:
    def test_missing_key_unavailable_but_eligible_unchanged(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=True)
        assert e.eligible is True
        av = evaluate_judge_availability(eligible=True, environ=PIN_ENV)
        assert av.available is False
        assert av.credentials_present is False
        assert av.reason == EXEC_UNAVAILABLE_CREDS
        assert av.execution_code == EXEC_UNAVAILABLE_CREDS
        assert av.gate_disposition == GATE_JUDGE_UNAVAILABLE
        assert av.evidence["raw_key_echoed"] is False

    def test_key_present_available(self) -> None:
        av = evaluate_judge_availability(eligible=True, environ=PIN_ENV_WITH_KEY)
        assert av.credentials_present is True
        assert av.client_constructible is True
        assert av.available is True
        assert av.reason is None

    def test_explicit_key_arg(self) -> None:
        av = evaluate_judge_availability(eligible=True, judge_api_key="sk-x", environ={})
        assert av.available is True

    def test_ineligible_short_circuits_available(self) -> None:
        av = evaluate_judge_availability(eligible=False, environ=PIN_ENV_WITH_KEY)
        assert av.available is False
        # reason left empty so runner stamps cohort_ineligible from eligibility
        assert av.reason is None

    def test_client_unconstructible(self) -> None:
        av = evaluate_judge_availability(
            eligible=True,
            environ=PIN_ENV_WITH_KEY,
            client_factory_ok=False,
        )
        assert av.available is False
        assert av.execution_code == "client_unconstructible"

    def test_credentials_present_helper_uses_environ(self) -> None:
        assert credentials_present(environ=PIN_ENV) is False
        assert credentials_present(environ=PIN_ENV_WITH_KEY) is True

    def test_secret_resolver_injection(self) -> None:
        calls: list[str] = []

        def resolver(k: str, d: str = "") -> str:
            """Test double: record key and return a fixed non-secret placeholder."""
            calls.append(k)
            return "sk-from-resolver"

        av = evaluate_judge_availability(
            eligible=True,
            environ=None,
            secret_resolver=resolver,
        )
        assert av.available is True
        assert calls == ["GIT_CG_EVAL_JUDGE_API_KEY"]
        # evidence must not contain the resolved secret
        dumped = repr(av.evidence)
        assert "sk-from-resolver" not in dumped


# ---------------------------------------------------------------------------
# Closed taxonomy (D42 / C-TAX)
# ---------------------------------------------------------------------------


class TestTaxonomy:
    def test_closed_sets_nonempty(self) -> None:
        assert EXEC_COHORT_INELIGIBLE in EXECUTION_CODES
        assert EXEC_UNAVAILABLE_CREDS in EXECUTION_CODES
        assert GATE_DET_FAIL_EXCLUDED in GATE_DISPOSITION_CODES
        assert GATE_JUDGE_UNAVAILABLE in GATE_DISPOSITION_CODES

    def test_mapping_covers_all_gate_codes(self) -> None:
        assert set(GATE_TO_EXECUTION) == set(GATE_DISPOSITION_CODES)

    def test_valid_mappings(self) -> None:
        map_gate_to_execution(GATE_DET_FAIL_EXCLUDED, EXEC_COHORT_INELIGIBLE)
        map_gate_to_execution(GATE_SCOPE_GATE_REJECT, EXEC_COHORT_INELIGIBLE)
        map_gate_to_execution(GATE_PROMPT_PACK_MISSING, "pack_unresolvable")
        map_gate_to_execution(GATE_JUDGE_UNAVAILABLE, EXEC_UNAVAILABLE_CREDS)
        map_gate_to_execution(GATE_LAB_OVERRIDE_DIAGNOSTIC, EXEC_LAB_OVERRIDE_DIAGNOSTIC)

    def test_budget_is_gate_only(self) -> None:
        with pytest.raises(TaxonomyError, match="gate-layer only"):
            map_gate_to_execution(GATE_BUDGET_CAP_REACHED, EXEC_COHORT_INELIGIBLE)

    def test_cross_layer_collision(self) -> None:
        with pytest.raises(TaxonomyError, match="not mapped"):
            map_gate_to_execution(GATE_DET_FAIL_EXCLUDED, EXEC_UNAVAILABLE_CREDS)

    def test_unknown_execution_code(self) -> None:
        with pytest.raises(TaxonomyError):
            assert_execution_code("free_form_reason")
        with pytest.raises(TaxonomyError):
            validate_closed_reason("because the model was weird")

    def test_failure_id_for_scored_is_none(self) -> None:
        assert failure_id_for("scored") is None
        assert failure_id_for(EXEC_COHORT_INELIGIBLE) == "CPRIME_COHORT_INELIGIBLE"


# ---------------------------------------------------------------------------
# Runner skeleton
# ---------------------------------------------------------------------------


class TestRunLaneC:
    def test_ineligible_emits_skip_rows_advisory(self) -> None:
        result = run_lane_c(
            ["cprime.geval_craft", "cprime.geval_relevance"],
            deterministic_pass=True,
            allows_lane_c=False,
            environ={},
        )
        assert result.eligibility.eligible is False
        assert result.invoked is False
        assert result.scored_count == 0
        assert result.cprime_ran is False
        assert len(result.rows) == 2
        for r in result.rows:
            assert r.authority is Authority.ADVISORY
            assert r.source is Source.LANE_C_JUDGE
            assert r.passed is None
            assert r.reason == EXEC_COHORT_INELIGIBLE
            assert r.evidence and r.evidence["skipped"] is True
            assert r.evidence["cprime_ran"] is False
            assert r.evidence["invoked"] is False
            assert "CPRIME_COHORT_INELIGIBLE" in (r.failure_ids or [])

    def test_missing_credentials_skip_not_ineligible(self) -> None:
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV,  # model only
        )
        assert result.eligibility.eligible is True
        assert result.availability.available is False
        assert result.invoked is False
        assert result.cprime_ran is False
        assert result.rows[0].reason == EXEC_UNAVAILABLE_CREDS
        assert result.rows[0].passed is None
        assert result.rows[0].authority is Authority.ADVISORY
        assert "CPRIME_UNAVAILABLE_CREDS" in (result.rows[0].failure_ids or [])

    def test_lab_override_diagnostic_zero_side_effects(self) -> None:
        # Even with credentials, lab_override on det-fail never invokes judges.
        side_effects = {"judge_calls": 0}

        def resolver(k: str, d: str = "") -> str:
            """Test double: count resolver calls; never return a live secret."""
            side_effects["judge_calls"] += 1
            return "sk-should-not-matter"

        result = run_lane_c(
            list(DEFAULT_LANE_C_METRICS),
            deterministic_pass=False,
            allows_lane_c=True,
            lab_override=True,
            environ=PIN_ENV_WITH_KEY,
            secret_resolver=resolver,
        )
        assert result.eligibility.eligible is True
        assert result.eligibility.diagnostic_only is True
        assert result.invoked is False
        assert result.cprime_ran is False
        assert result.scored_count == 0
        assert len(result.rows) == 2
        for r in result.rows:
            assert r.reason == EXEC_LAB_OVERRIDE_DIAGNOSTIC
            assert r.passed is None
        # Availability may still be probed for evidence; that is not judge invocation.
        assert result.evidence["invoked"] is False
        assert side_effects["judge_calls"] == 0

    def test_eligible_available_does_not_set_cprime_ran(self) -> None:
        # S5a: eligible+available still does not invoke judge (Slice 4).
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
        )
        assert result.eligibility.eligible is True
        assert result.availability.available is True
        assert result.invoked is False
        assert result.cprime_ran is False
        assert result.scored_count == 0
        assert result.rows[0].reason == EXEC_JUDGE_NOT_INVOKED
        assert result.rows[0].evidence["cprime_ran"] is False

    def test_unknown_metric_id_fails_closed(self) -> None:
        with pytest.raises(KeyError):
            run_lane_c(
                ["cprime.does_not_exist"],
                deterministic_pass=True,
                allows_lane_c=False,
                environ={},
            )

    def test_empty_metric_list(self) -> None:
        result = run_lane_c(
            [],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
        )
        assert result.rows == []
        assert result.invoked is False

    def test_default_metrics_opt_in(self) -> None:
        result = run_lane_c(
            None,
            deterministic_pass=True,
            allows_lane_c=False,
            environ={},
            use_default_metrics=True,
        )
        assert [r.metric_id for r in result.rows] == list(DEFAULT_LANE_C_METRICS)

    def test_skip_rows_never_auto_pass_on_value(self) -> None:
        # Guard D30 footgun on skip path: value 0 with higher_is_better must
        # still keep passed=None after model_copy.
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=False,
            environ={},
        )
        assert result.rows[0].passed is None
        # And a raw make_score footgun still exists on non-C' helper path:
        footgun = make_score("cprime.geval_craft", 5.0, passed=None)
        assert footgun.passed is True  # documents why make_advisory_score is required later


# ---------------------------------------------------------------------------
# Gate composition hook (C-GATE)
# ---------------------------------------------------------------------------


class TestGateComposition:
    def _sem_gate(self, **kw: Any):
        gates = compose_gates([], require_block=(), **kw)
        return next(g for g in gates if g.metric_id == "gate.semantic_cohort_eligible")

    def test_offline_default_deferred_honest_vocabulary(self) -> None:
        row = self._sem_gate(lane_c_eligibility=None)
        assert row.passed is False
        assert row.reason == "semantic_cohort_deferred_offline_later_lane"
        assert row.failure_ids == ["GATE_SEMANTIC_COHORT_DEFERRED"]
        assert row.evidence is not None
        assert row.evidence["cprime_ran"] is False
        assert row.evidence["invoked"] is False
        assert row.evidence["scored_count"] == 0
        assert row.evidence["offline_lane_ab"] is True
        assert "offline_s2b" not in row.evidence

    def test_verdict_eligible_true_does_not_imply_cprime_ran(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=True)
        row = self._sem_gate(
            lane_c_eligibility=e,
            lane_c_run_evidence={
                "available": False,
                "invoked": False,
                "scored_count": 0,
                "cprime_ran": False,
            },
        )
        assert row.passed is True
        assert row.authority is Authority.LAW
        assert row.evidence is not None
        assert row.evidence["eligible"] is True
        assert row.evidence["cprime_ran"] is False  # D32
        assert row.evidence["invoked"] is False
        assert row.evidence["scored_count"] == 0

    def test_verdict_ineligible_false(self) -> None:
        e = _elig(deterministic_pass=True, allows_lane_c=False)
        row = self._sem_gate(lane_c_eligibility=e)
        assert row.passed is False
        assert row.reason == "lane_c_not_allowed_by_suite"
        assert row.failure_ids == ["GATE_SEMANTIC_COHORT_INELIGIBLE"]
        assert row.evidence and row.evidence["cprime_ran"] is False

    def test_existing_gate_row_in_results_preferred(self) -> None:
        pre = make_score(
            "gate.semantic_cohort_eligible",
            True,
            passed=True,
            reason=None,
            evidence={"eligible": True, "cprime_ran": False, "from_row": True},
        )
        gates = compose_gates([pre], require_block=())
        row = next(g for g in gates if g.metric_id == "gate.semantic_cohort_eligible")
        assert row.evidence and row.evidence.get("from_row") is True

    def test_eligibility_true_does_not_pass_golden_or_det(self) -> None:
        # S5-A04: eligibility is entry only.
        e = _elig(deterministic_pass=True, allows_lane_c=True)
        # Empty require block → det passes; no gold/skeleton → promo fails.
        gates = compose_gates(
            [],
            require_block=(),
            bound=True,
            lane_c_eligibility=e,
            lane_c_run_evidence={"cprime_ran": False, "invoked": False, "scored_count": 0},
        )
        by = {g.metric_id: g for g in gates}
        assert by["gate.semantic_cohort_eligible"].passed is True
        assert by["gate.golden_promotion_eligible"].passed is False

    def test_compose_gates_has_no_lane_c_import(self) -> None:
        import git_cg.eval.scoring.gates as gates_mod

        src = Path(gates_mod.__file__).read_text(encoding="utf-8")
        # No runtime import of Lane C or secret resolvers inside gates.py (D34).
        assert "import git_cg.eval.lane_c" not in src
        assert "from git_cg.eval.lane_c" not in src
        assert "resolve_secret" not in src
        assert "GIT_CG_EVAL_JUDGE_API_KEY" not in src


# ---------------------------------------------------------------------------
# Import isolation (S5-E08 partial — no provider SDK on import)
# ---------------------------------------------------------------------------


class TestImportIsolation:
    def test_import_lane_c_does_not_import_openai(self) -> None:
        # Fresh subprocess: import surface must not pull provider/network SDKs.
        import subprocess
        import sys as _sys

        code = (
            "import sys\n"
            "banned = {'openai', 'anthropic', 'httpx', 'opik', 'requests'}\n"
            "before = {m for m in sys.modules if m.split('.', 1)[0] in banned}\n"
            "import git_cg.eval.lane_c as lane_c\n"
            "after = {m for m in sys.modules if m.split('.', 1)[0] in banned}\n"
            "leaked = sorted(after - before)\n"
            "assert not leaked, leaked\n"
            "assert hasattr(lane_c, 'run_lane_c')\n"
        )
        proc = subprocess.run(
            [_sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# Existing deferred test still green (updated evidence vocabulary allowed)
# ---------------------------------------------------------------------------


def test_semantic_cohort_deferred_s2a_compat() -> None:
    """Default offline path remains deferred (updated D32 evidence keys)."""
    from git_cg.eval.catalog import load_metric_catalog

    pol = {m["metric_id"]: m["polarity"] for m in load_metric_catalog()["metrics"]}

    def _pass(metric_id: str):
        """Minimal passing score row for gate composition fixtures."""
        p = pol[metric_id]
        if p == "lower_is_better":
            return make_score(metric_id, 0, passed=True)
        if p == "higher_is_better":
            return make_score(metric_id, 1.0, passed=True)
        return make_score(metric_id, True, passed=True)

    rows = [_pass(m) for m in S2A_REQUIRE_BLOCK]
    gates = compose_gates(rows, bound=True)
    sc = next(x for x in gates if x.metric_id == "gate.semantic_cohort_eligible")
    assert sc.passed is False
    assert sc.reason == "semantic_cohort_deferred_offline_later_lane"
    assert "deferred" in (sc.reason or "")


# ---------------------------------------------------------------------------
# Slice 4 — injectable judge wiring (C-RUN / C-ADV / C-JUDGE)
# ---------------------------------------------------------------------------


class TestSlice4JudgeWiring:
    def _projected(self):
        """Projected ordinary-path judge input for a representative accept artifact."""
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.judge_input import project_judge_input

        text = (
            "✨ feat(eval): lane c judge wiring\n\n"
            "Refs: #233\n"
            "SemVer-Impact: MINOR\n"
            "Change-Types: feat\n"
            "Changelog-Groups: Added\n"
        )
        return project_judge_input(
            {
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
            }
        )

    def test_eligible_with_judge_scores_advisory(self) -> None:
        from git_cg.eval.lane_c.taxonomy import EXEC_SCORED

        def fake(prompt, judge_input, *, model, timeout_s=15.0):
            assert prompt
            return {"score": 4, "rationale": "clear subject"}

        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=fake,
            judge_input=self._projected(),
        )
        assert result.invoked is True
        assert result.scored_count == 1
        assert result.cprime_ran is True
        row = result.rows[0]
        assert row.reason == EXEC_SCORED
        assert row.passed is None
        assert row.value == 4
        assert row.evidence["scale"] == "geval_1_5"
        assert row.evidence.get("rationale") == "clear subject"
        assert "api_key" not in row.evidence

    def test_judge_exception_isolated_per_metric(self) -> None:
        from git_cg.eval.lane_c.taxonomy import EXEC_TRANSPORT_ERROR

        def boom(*_a, **_k):
            raise RuntimeError("provider down")

        result = run_lane_c(
            ["cprime.geval_craft", "cprime.geval_relevance"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=boom,
            judge_input=self._projected(),
        )
        assert result.invoked is True
        assert result.scored_count == 0
        assert result.cprime_ran is False
        assert len(result.rows) == 2
        assert all(r.passed is None for r in result.rows)
        assert all(r.reason == EXEC_TRANSPORT_ERROR for r in result.rows)

    def test_empty_input_skips_without_invoke(self) -> None:
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.taxonomy import EXEC_EMPTY_INPUT

        calls = {"n": 0}

        def fake(*_a, **_k):
            calls["n"] += 1
            return {"score": 5}

        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=fake,
            judge_input={
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": "   ",
                "final_message_sha256": message_sha256_bytes("   "),
            },
        )
        assert calls["n"] == 0
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_EMPTY_INPUT
        assert result.rows[0].passed is None
        assert result.rows[0].evidence["invoked"] is False

    def test_without_judge_fn_remains_not_invoked(self) -> None:
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_input=self._projected(),
        )
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_JUDGE_NOT_INVOKED


class TestSlice4PromotionImmunity:
    def test_poisoned_cprime_passed_true_cannot_veto_or_promote(self) -> None:
        from git_cg.eval.enums import Authority, Family, Polarity, Severity, Source
        from git_cg.eval.score_result import ScoreResultV1

        poisoned = ScoreResultV1(
            metric_id="cprime.geval_craft",
            polarity=Polarity.HIGHER_IS_BETTER,
            authority=Authority.ADVISORY,
            source=Source.LANE_C_JUDGE,
            value=1,
            name="GEval craft",
            family=Family.CPRIME,
            threshold=None,
            passed=True,
            severity=Severity.WARN,
            reason="scored",
            evidence={"scale": "geval_1_5", "poison": True},
            failure_ids=None,
            product_authority=None,
            pin_refs=[],
            duration_ms=None,
        )
        gates = compose_gates([poisoned], require_block=S2A_REQUIRE_BLOCK, bound=True)
        by = {g.metric_id: g for g in gates}
        assert by["gate.deterministic_pass"].passed is False
        assert by["gate.golden_promotion_eligible"].passed is False

    def test_scored_cprime_does_not_flip_deferred_semantic_gate_alone(self) -> None:
        from git_cg.eval.lane_c.advisory import make_advisory_score

        row = make_advisory_score("cprime.geval_craft", 5)
        gates = compose_gates([row], require_block=(), bound=True)
        by = {g.metric_id: g for g in gates}
        assert by["gate.semantic_cohort_eligible"].passed is False
        assert by["gate.semantic_cohort_eligible"].evidence["cprime_ran"] is False


class TestRunnerCoverageEdges:
    def _projected(self):
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.judge_input import project_judge_input

        text = (
            "✨ feat(eval): runner coverage\n\n"
            "Refs: #233\n"
            "SemVer-Impact: MINOR\n"
            "Change-Types: feat\n"
            "Changelog-Groups: Added\n"
        )
        return project_judge_input(
            {
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
            }
        )

    def test_base_evidence_strips_secret_keys(self) -> None:
        from git_cg.eval.lane_c.availability import evaluate_judge_availability
        from git_cg.eval.lane_c.eligibility import evaluate_semantic_cohort_eligibility
        from git_cg.eval.lane_c.runner import _base_evidence

        elig = evaluate_semantic_cohort_eligibility(
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
        )
        avail = evaluate_judge_availability(eligible=elig.eligible, environ=PIN_ENV_WITH_KEY)
        ev = _base_evidence(
            eligibility=elig,
            availability=avail,
            extra={"api_key": "sk-x", "ok": 1, "authorization": "Bearer z", "token_hint": "nope"},
        )
        assert "api_key" not in ev
        assert "authorization" not in ev
        assert "token_hint" not in ev
        assert ev["ok"] == 1
        assert ev["available"] is True

    def test_aggregate_pack_evidence(self) -> None:
        from git_cg.eval.lane_c.advisory import make_advisory_score, make_advisory_skip
        from git_cg.eval.lane_c.runner import aggregate_pack_evidence
        from git_cg.eval.lane_c.taxonomy import EXEC_JUDGE_NOT_INVOKED

        rows = [
            make_advisory_score(
                "cprime.geval_craft",
                4,
                evidence={"pack_identity": "lane_c_craft@1", "content_sha256": "a" * 64},
            ),
            make_advisory_skip(
                "cprime.geval_relevance",
                reason=EXEC_JUDGE_NOT_INVOKED,
                evidence={"pack_identity": "lane_c_craft@1", "content_sha256": "b" * 64},
            ),
            make_advisory_score("cprime.geval_craft", 3, evidence={"not_pack": True}),
            object(),
        ]
        out = aggregate_pack_evidence(rows)
        assert out["pack_identity"] == "lane_c_craft@1"
        assert out["pack_identities"] == ["lane_c_craft@1"]
        assert out["content_sha256"] == "a" * 64
        assert out["content_hashes"] == ["a" * 64, "b" * 64]

    def test_resolve_projected_input_paths(self) -> None:
        from git_cg.eval.lane_c.runner import _resolve_projected_input
        from git_cg.eval.lane_c.taxonomy import EXEC_EMPTY_INPUT, EXEC_PARSE_ERROR

        none_proj, none_skip, none_note = _resolve_projected_input(
            judge_input=None,
            final_accept_evidence=None,
            lab_override=False,
            max_input_chars=None,
        )
        assert none_proj is None and none_skip is None and none_note is None

        projected = self._projected()
        same, skip, _note = _resolve_projected_input(
            judge_input=projected,
            final_accept_evidence=None,
            lab_override=False,
            max_input_chars=None,
        )
        assert same is projected and skip is None

        from git_cg.eval.binding.binder import message_sha256_bytes

        empty_text = "   "
        empty, code, err = _resolve_projected_input(
            judge_input={
                "artifact_class": "final_accept",
                "bound": True,
                "final_message": empty_text,
                "final_message_sha256": message_sha256_bytes(empty_text),
            },
            final_accept_evidence=None,
            lab_override=False,
            max_input_chars=None,
        )
        assert empty is None
        assert code == EXEC_EMPTY_INPUT
        assert err

        bad, code2, err2 = _resolve_projected_input(
            judge_input={"not": "valid"},
            final_accept_evidence=None,
            lab_override=False,
            max_input_chars=None,
        )
        assert bad is None
        assert code2 == EXEC_PARSE_ERROR
        assert err2

    def test_pack_dir_for_recorded_and_derived(self, tmp_path: Path) -> None:
        from git_cg.eval.lane_c.runner import _pack_dir_for

        recorded = tmp_path / "craft"
        recorded.mkdir()
        assert _pack_dir_for({"pack_dir": recorded}, None) == recorded
        assert _pack_dir_for({"pack_dir": str(recorded)}, None) == recorded
        derived = _pack_dir_for({"pack_id": "lane_c_craft"}, tmp_path)
        assert derived == tmp_path / "craft"

    def test_oversize_input_via_runner(self) -> None:
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.taxonomy import EXEC_OVERSIZE_INPUT

        huge = "x" * 40000
        calls = {"n": 0}

        def fake(*_a, **_k):
            calls["n"] += 1
            return {"score": 5}

        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=fake,
            judge_input={
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": huge,
                "final_message_sha256": message_sha256_bytes(huge),
            },
        )
        assert calls["n"] == 0
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_OVERSIZE_INPUT
        assert result.evidence.get("judge_input_isolated") is True

    def test_isolation_failure_via_runner(self) -> None:
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.taxonomy import EXEC_PARSE_ERROR

        text = (
            "✨ feat(eval): isolation\n\n"
            "Refs: #233\n"
            "SemVer-Impact: PATCH\n"
            "Change-Types: feat\n"
            "Changelog-Groups: Added\n"
        )
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=lambda *a, **k: {"score": 5},
            judge_input={
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
                "expected_output": "leak",
            },
        )
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_PARSE_ERROR
        assert result.evidence.get("judge_input_isolated") is False

    def test_timeout_maps_gate_disposition(self) -> None:
        from git_cg.eval.lane_c.taxonomy import EXEC_TIMEOUT, GATE_JUDGE_UNAVAILABLE

        def boom(*_a, **_k):
            raise TimeoutError("slow")

        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=boom,
            judge_input=self._projected(),
        )
        assert result.invoked is True
        row = result.rows[0]
        assert row.reason == EXEC_TIMEOUT
        assert row.evidence.get("gate_disposition") == GATE_JUDGE_UNAVAILABLE


class TestTaxonomyCoverageEdges:
    def test_assert_gate_and_pair_and_iters(self) -> None:
        from git_cg.eval.lane_c.taxonomy import (
            TaxonomyPair,
            assert_gate_disposition,
            iter_execution_codes,
            iter_gate_disposition_codes,
            mapping_table,
            validate_closed_reason,
        )

        assert assert_gate_disposition(GATE_SCOPE_GATE_REJECT) == GATE_SCOPE_GATE_REJECT
        with pytest.raises(TaxonomyError):
            assert_gate_disposition("not-a-gate")

        pair = TaxonomyPair(
            gate_disposition=GATE_SCOPE_GATE_REJECT,
            execution_code=EXEC_COHORT_INELIGIBLE,
        ).validate()
        assert pair.execution_code == EXEC_COHORT_INELIGIBLE

        with pytest.raises(TaxonomyError):
            TaxonomyPair(
                gate_disposition=GATE_BUDGET_CAP_REACHED,
                execution_code=EXEC_COHORT_INELIGIBLE,
            ).validate()

        assert "scored" in set(iter_execution_codes())
        assert GATE_SCOPE_GATE_REJECT in set(iter_gate_disposition_codes())
        table = mapping_table()
        assert GATE_SCOPE_GATE_REJECT in table
        assert validate_closed_reason("scored") == "scored"
        with pytest.raises(TaxonomyError):
            validate_closed_reason("scored", allow_scored=False)


class TestRunnerPackErrorPaths:
    def _projected(self):
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.judge_input import project_judge_input

        text = (
            "✨ feat(eval): pack errors\n\n"
            "Refs: #233\n"
            "SemVer-Impact: PATCH\n"
            "Change-Types: feat\n"
            "Changelog-Groups: Added\n"
        )
        return project_judge_input(
            {
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
            }
        )

    def test_resolve_pack_error_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.lane_c import runner as runner_mod
        from git_cg.eval.lane_c.prompt_pack import PromptPackError
        from git_cg.eval.lane_c.taxonomy import EXEC_PACK_UNRESOLVABLE

        def boom(*_a, **_k):
            raise PromptPackError("missing pack", code=EXEC_PACK_UNRESOLVABLE)

        monkeypatch.setattr(runner_mod, "resolve_judge_pack", boom)
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=lambda *a, **k: {"score": 5},
            judge_input=self._projected(),
        )
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_PACK_UNRESOLVABLE
        assert result.rows[0].evidence.get("gate_disposition") == GATE_PROMPT_PACK_MISSING

    def test_load_pack_prompt_error_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.lane_c import runner as runner_mod
        from git_cg.eval.lane_c.prompt_pack import PromptPackError
        from git_cg.eval.lane_c.taxonomy import EXEC_PACK_DECODE_ERROR

        def bad_load(_pack_dir):
            raise PromptPackError("bad utf8", code=EXEC_PACK_DECODE_ERROR)

        monkeypatch.setattr(runner_mod, "load_pack_prompt_text", bad_load)
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=lambda *a, **k: {"score": 5},
            judge_input=self._projected(),
        )
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_PACK_DECODE_ERROR

    def test_load_pack_unexpected_exception_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.lane_c import runner as runner_mod
        from git_cg.eval.lane_c.taxonomy import EXEC_PACK_DECODE_ERROR

        def bad_load(_pack_dir):
            raise RuntimeError("disk exploded")

        monkeypatch.setattr(runner_mod, "load_pack_prompt_text", bad_load)
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=lambda *a, **k: {"score": 5},
            judge_input=self._projected(),
        )
        assert result.invoked is False
        assert result.rows[0].reason == EXEC_PACK_DECODE_ERROR
        assert "RuntimeError" in str(result.rows[0].evidence.get("pack_error", ""))

    def test_run_pinned_judge_exception_marks_invoked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.lane_c import runner as runner_mod
        from git_cg.eval.lane_c.taxonomy import EXEC_TRANSPORT_ERROR

        def boom(*_a, **_k):
            raise RuntimeError("escaped")

        monkeypatch.setattr(runner_mod, "run_pinned_judge", boom)
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=lambda *a, **k: {"score": 5},
            judge_input=self._projected(),
        )
        assert result.invoked is True
        assert result.rows[0].reason == EXEC_TRANSPORT_ERROR
        assert result.rows[0].evidence.get("invoked") is True


class TestRunnerProjectionAndFailCodes:
    def test_resolve_projected_from_final_accept_and_max_chars(self) -> None:
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c.runner import _resolve_projected_input
        from git_cg.eval.lane_c.taxonomy import EXEC_OVERSIZE_INPUT

        text = (
            "✨ feat(eval): final accept path\n\n"
            "Refs: #233\n"
            "SemVer-Impact: PATCH\n"
            "Change-Types: feat\n"
            "Changelog-Groups: Added\n"
        )
        projected, code, err = _resolve_projected_input(
            judge_input=None,
            final_accept_evidence={
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
            },
            lab_override=False,
            max_input_chars=None,
        )
        assert projected is not None
        assert code is None
        assert err is None

        _, code2, err2 = _resolve_projected_input(
            judge_input=None,
            final_accept_evidence={
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
            },
            lab_override=False,
            max_input_chars=1,
        )
        assert code2 == EXEC_OVERSIZE_INPUT
        assert err2

    def test_resolve_projected_unexpected_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.lane_c import runner as runner_mod
        from git_cg.eval.lane_c.taxonomy import EXEC_PARSE_ERROR

        def boom(*_a, **_k):
            raise RuntimeError("projection exploded")

        monkeypatch.setattr(runner_mod, "project_judge_input", boom)
        projected, code, err = runner_mod._resolve_projected_input(
            judge_input={
                "artifact_class": "final_accept",
                "bound": True,
                "final_message": "x",
                "final_message_sha256": "a" * 64,
            },
            final_accept_evidence=None,
            lab_override=False,
            max_input_chars=None,
        )
        assert projected is None
        assert code == EXEC_PARSE_ERROR
        assert "RuntimeError" in (err or "")

    def test_unknown_execution_code_maps_to_parse_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.binding.binder import message_sha256_bytes
        from git_cg.eval.enums import ArtifactClass
        from git_cg.eval.lane_c import runner as runner_mod
        from git_cg.eval.lane_c.judge import JudgeOutcome
        from git_cg.eval.lane_c.judge_input import project_judge_input
        from git_cg.eval.lane_c.taxonomy import EXEC_PARSE_ERROR

        text = (
            "✨ feat(eval): unknown code\n\n"
            "Refs: #233\n"
            "SemVer-Impact: PATCH\n"
            "Change-Types: feat\n"
            "Changelog-Groups: Added\n"
        )
        projected = project_judge_input(
            {
                "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
                "bound": True,
                "final_message": text,
                "final_message_sha256": message_sha256_bytes(text),
            }
        )

        def weird(*_a, **_k):
            return JudgeOutcome(
                ok=False,
                execution_code="not_a_real_code",
                score=None,
                rationale=None,
                text=None,
                usage=None,
                latency_ms=1.0,
                finish_reason=None,
                retry_count=0,
                error_type="weird",
                raw_discarded=True,
                duration_ms=1.0,
            )

        monkeypatch.setattr(runner_mod, "run_pinned_judge", weird)
        result = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=PIN_ENV_WITH_KEY,
            judge_fn=lambda *a, **k: {"score": 5},
            judge_input=projected,
        )
        assert result.invoked is True
        assert result.rows[0].reason == EXEC_PARSE_ERROR
