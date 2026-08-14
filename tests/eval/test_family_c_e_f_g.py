"""S2b Families C/E/F/G — product authority metrics + shared gold."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.commit_gold import STRICT_FAIL_CODES, GoldFinding, GoldReport
from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring import score_bundle
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_c import FAMILY_C_S2B, score_family_c
from git_cg.eval.scoring.family_d import score_family_d
from git_cg.eval.scoring.family_e import FAMILY_E_S2B, score_family_e
from git_cg.eval.scoring.family_f import FAMILY_F_S2B, score_family_f
from git_cg.eval.scoring.family_g import FAMILY_G_S2B, score_family_g
from git_cg.eval.scoring.gold_slot import build_gold_slot
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def _bundle(**overrides):
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b.update(overrides)
    return b


def _ctx(**overrides):
    return project_score_context(_bundle(**overrides))


def test_family_c_emits_all_catalog_rows() -> None:
    ctx = _ctx()
    slot = build_gold_slot(ctx)
    scores = score_family_c(ctx, gold_slot=slot)
    ids = {s.metric_id for s in scores}
    assert ids == set(FAMILY_C_S2B)


def test_family_e_emits_all_catalog_rows() -> None:
    ctx = _ctx()
    slot = build_gold_slot(ctx)
    scores = score_family_e(ctx, gold_slot=slot)
    assert {s.metric_id for s in scores} == set(FAMILY_E_S2B)


def test_family_f_emits_all_and_never_calls_gold() -> None:
    calls = {"n": 0}

    def bridge(plan: CommitPlan, signals: DiffSignals, mode: str):
        calls["n"] += 1
        report = GoldReport()
        return report, frozenset(), True

    ctx = _ctx()
    slot = build_gold_slot(ctx, gold_bridge=bridge)
    assert calls["n"] == 1
    scores = score_family_f(ctx, gold_slot=slot)
    assert calls["n"] == 1  # F must not call again
    assert {s.metric_id for s in scores} == set(FAMILY_F_S2B)


def test_family_g_emits_all_and_policy_fork_non_vacuous() -> None:
    ctx = _ctx()
    scores = score_family_g(ctx)
    by = {s.metric_id: s for s in scores}
    assert set(by) == set(FAMILY_G_S2B)
    fork = by["g.no_eval_policy_fork"]
    assert fork.passed is True
    assert (fork.evidence or {}).get("scoring_root")
    # secrets clean on valid fixture
    assert by["g.secrets_not_in_message"].passed is True


def test_family_g_detects_secret_shape() -> None:
    msg = (
        "🔧 chore(eval): touch secrets\n\n"
        "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789\n\n"
        "Refs: #1\nSemVer-Impact: NONE\nChange-Types: chore\nChangelog-Groups: Miscellaneous\n"
    )
    ctx = _ctx(final_message=msg)
    by = {s.metric_id: s for s in score_family_g(ctx)}
    assert by["g.secrets_not_in_message"].passed is False


def test_family_g_null_policy() -> None:
    msg = (
        "📝 docs(eval): null policy\n\n"
        "Null: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    ctx = _ctx(final_message=msg)
    by = {s.metric_id: s for s in score_family_g(ctx)}
    assert by["g.issue_null_policy"].passed is False

    msg0 = msg.replace("Null: #1", "Null: #0")
    ctx0 = _ctx(final_message=msg0)
    by0 = {s.metric_id: s for s in score_family_g(ctx0)}
    assert by0["g.issue_null_policy"].passed is True


def test_shared_gold_object_identity_across_d_f_c() -> None:
    report = GoldReport(findings=(GoldFinding(code="GOLD_SUBJECT_TITLE_CASE", message="t"),))
    calls = {"n": 0}

    def bridge(plan, signals, mode):
        calls["n"] += 1
        strict = report.codes() & STRICT_FAIL_CODES
        return report, strict, report.ok_for_mode(mode)

    ctx = _ctx()
    slot = build_gold_slot(ctx, gold_bridge=bridge)
    assert calls["n"] == 1
    assert slot.report is report

    d_scores = score_family_d(ctx, gold_slot=slot)
    f_scores = score_family_f(ctx, gold_slot=slot)
    c_scores = score_family_c(ctx, gold_slot=slot)
    assert calls["n"] == 1

    d_by = {s.metric_id: s for s in d_scores}
    f_by = {s.metric_id: s for s in f_scores}
    c_by = {s.metric_id: s for s in c_scores}

    # Shared evidence identity
    assert d_by["d.gold_report_ok"].evidence["report_is"] == id(report)
    assert f_by["f.subject_attribution"].evidence["report_is"] == id(report)
    assert c_by["c.contract_smoke"].evidence["report_is"] == id(report)
    assert d_by["d.subject_title_case"].passed is False


def test_runner_one_gold_call_and_emits_new_families() -> None:
    calls = {"n": 0}

    def bridge(plan, signals, mode):
        calls["n"] += 1
        r = GoldReport()
        return r, frozenset(), True

    result = score_bundle(_bundle(), suite_snapshot_pin="pin@1", gold_bridge=bridge)
    assert result.short_circuit is False
    assert calls["n"] == 1
    assert result.gold_call_count == 1
    by = result.by_id()
    for mid in (
        "c.diff_class_resolved",
        "e.banned_craft_openers",
        "f.staged_path_allowlist",
        "g.no_eval_policy_fork",
        "h.structured_bundle_compliance",
    ):
        assert mid in by
    assert by["h.structured_bundle_compliance"].passed is True


def test_empty_short_circuit_skips_c_d_e_f_g() -> None:
    b = _bundle()
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    b.pop("product_card", None)
    b.pop("score_card", None)
    result = score_bundle(b, suite_snapshot_pin="pin@1")
    assert result.short_circuit is True
    assert result.gold_call_count == 0
    by = result.by_id()
    for prefix in ("b.", "c.", "d.", "e.", "f.", "g."):
        assert not any(k.startswith(prefix) for k in by), prefix
    assert "h.eval_input_nonempty" in by


def test_security_path_honesty_no_placeholder_pass() -> None:
    """Security metrics must not pass via gold path-class placeholders."""
    msg = (
        "🔒 fix(security): harden auth token handling\n\n"
        "Rotate API secrets and fix auth bypass.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: fix\nChangelog-Groups: Fixed\n"
    )
    # No explicit files — placeholders may exist for gold but C/F must not treat as evidence
    ctx = project_score_context(_bundle(final_message=msg), files=())
    assert ctx.path_evidence == ()
    slot = build_gold_slot(ctx)
    c_by = {s.metric_id: s for s in score_family_c(ctx, gold_slot=slot)}
    f_by = {s.metric_id: s for s in score_family_f(ctx, gold_slot=slot)}
    # Claims without explicit paths → fail
    assert c_by["c.security_claim_evidence"].passed is False or not (
        c_by["c.security_claim_evidence"].evidence or {}
    ).get("claims")
    # If claims detected, must fail without paths
    claims = (f_by["f.security_claims_need_paths"].evidence or {}).get("claims") or []
    if claims:
        assert f_by["f.security_claims_need_paths"].passed is False


def test_contract_smoke_fail_closed_without_contract() -> None:
    ctx = _ctx()
    slot = build_gold_slot(ctx)  # contract_provided False
    assert slot.contract_provided is False
    by = {s.metric_id: s for s in score_family_c(ctx, gold_slot=slot)}
    assert by["c.contract_smoke"].passed is False
    assert "contract_not_provided" in (by["c.contract_smoke"].reason or "")


def test_family_d_emits_all_mapped_rows_on_clean_report() -> None:
    from git_cg.eval.scoring.product_bridges import GOLD_CODE_TO_D_METRIC

    report = GoldReport()

    def bridge(plan, signals, mode):
        return report, frozenset(), True

    ctx = _ctx()
    slot = build_gold_slot(ctx, gold_bridge=bridge)
    # ranked not provided → included_changes_coverage unevaluable fail
    scores = score_family_d(ctx, gold_slot=slot)
    by = {s.metric_id: s for s in scores}
    for mid in GOLD_CODE_TO_D_METRIC.values():
        assert mid in by, mid
    assert by["d.included_changes_coverage"].passed is False
    assert by["d.subject_title_case"].passed is True


def test_suite_empty_all_pass_false() -> None:
    from git_cg.eval.scoring.runner import ScoreSuiteResult

    assert ScoreSuiteResult(suite_id="x", cases=[]).all_pass is False
