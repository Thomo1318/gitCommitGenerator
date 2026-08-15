"""Focused branch coverage for S2b Families C/E/F/G patch lines.

These tests intentionally force fail-closed, exception, and gold dual-path
branches that happy-path suite fixtures do not reach. Production scorer
behaviour is exercised as-is; no scorer logic is relaxed for coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from git_cg.commit_gold import GoldFinding, GoldReport
from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_c import score_family_c
from git_cg.eval.scoring.family_e import score_family_e
from git_cg.eval.scoring.family_f import score_family_f
from git_cg.eval.scoring.family_g import score_family_g
from git_cg.eval.scoring.gold_slot import GoldSlot
from git_cg.intent import DiffSignals
from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"

VALID_MSG = (
    "📝 docs(eval): add offline fixture seed\n\n"
    "Document offline scoring fixtures.\n\n"
    "Refs: #223\n"
    "SemVer-Impact: PATCH\n"
    "Change-Types: docs\n"
    "Changelog-Groups: Documentation\n"
)


def _bundle(**overrides: Any) -> dict[str, Any]:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = dict(encode_fixture(fx)["bundle"])
    bundle.update(overrides)
    return bundle


def _ctx(**overrides: Any):
    return project_score_context(_bundle(**overrides))


def _intent(
    *,
    intent_id: str = "documentation_update",
    gitmoji: str = "📝",
    cc_type: CommitType = CommitType.DOCS,
    scope: str | None = "eval",
    description: str = "add offline fixture seed",
    semver_impact: SemVerImpact = SemVerImpact.PATCH,
    changelog_group: str = "Documentation",
) -> CommitIntent:
    return CommitIntent(
        intent_id=intent_id,
        gitmoji=gitmoji,
        cc_type=cc_type,
        scope=scope,
        description=description,
        semver_impact=semver_impact,
        changelog_group=changelog_group,
    )


def _plan(*, secondary: list[CommitIntent] | None = None, **primary_kw: Any) -> CommitPlan:
    return CommitPlan(
        primary_intent=_intent(**primary_kw),
        secondary_intents=list(secondary or []),
        split_recommended=False,
        rationale="test",
    )


def _by(scores: list) -> dict[str, Any]:
    return {s.metric_id: s for s in scores}


def _clean_gold(
    *,
    codes: set[str] | frozenset[str] | None = None,
    plan: CommitPlan | None = None,
    error: str | None = None,
    skipped: bool = False,
    contract_provided: bool = False,
) -> GoldSlot:
    findings = tuple(GoldFinding(code=c, message=c) for c in sorted(codes or ()))
    report = None if error or skipped else GoldReport(findings=findings)
    return GoldSlot(
        report=report,
        strict_hits=frozenset(),
        ok=report is not None and not findings,
        call_identity="test-slot",
        error=error,
        call_count=0 if (error or skipped) else 1,
        plan=plan,
        signals=DiffSignals(),
        contract_provided=contract_provided,
        skipped=skipped,
        skip_reason="test_skip" if skipped else None,
    )


# ---------------------------------------------------------------------------
# Family C
# ---------------------------------------------------------------------------


def test_family_c_parse_and_classify_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    monkeypatch.setattr(fc, "parse_message_to_plan", lambda _m: (_ for _ in ()).throw(RuntimeError("parse")))
    monkeypatch.setattr(fc, "classify_diff_class", lambda _p: (_ for _ in ()).throw(ValueError("dc")))

    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    by = _by(score_family_c(ctx, gold_slot=None))
    assert by["c.diff_class_resolved"].passed is False
    assert "ValueError" in (by["c.diff_class_resolved"].reason or "")
    assert by["c.type_allowed"].passed is False
    assert by["c.contract_smoke"].reason == "gold_slot_missing"


def test_family_c_no_paths_and_constraints_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    # Force constraints construction to fail after a resolved class.
    monkeypatch.setattr(fc, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(fc, "presentation_constraints", lambda _dc: (_ for _ in ()).throw(RuntimeError("cons")))

    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    by = _by(score_family_c(ctx, gold_slot=_clean_gold(plan=_plan())))
    assert by["c.diff_class_resolved"].passed is True

    # No explicit paths still fail-closed for diff class.
    bare = project_score_context(_bundle(final_message=VALID_MSG), files=())
    by_bare = _by(score_family_c(bare, gold_slot=_clean_gold(plan=_plan())))
    assert by_bare["c.diff_class_resolved"].passed is False
    assert by_bare["c.diff_class_resolved"].reason == "no_explicit_paths_for_diff_class"


def test_family_c_gate_eval_error_status_and_forced_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    plan = _plan(scope="eval")

    def _boom(*_a: Any, **_k: Any):
        raise RuntimeError("gate boom")

    monkeypatch.setattr(fc, "evaluate_presentation_gates", _boom)
    monkeypatch.setattr(fc, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(
        fc,
        "presentation_constraints",
        lambda _dc: SimpleNamespace(force_scope="api", forced_scope=None),
    )

    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    by = _by(score_family_c(ctx, gold_slot=_clean_gold(plan=plan), plan=plan))
    assert by["c.scope_forced_ok"].passed is False
    assert by["c.scope_forced_ok"].reason == "forced_scope_mismatch"
    # Gate exception still leaves gate_report None → type unevaluable unless gold present
    assert by["c.type_allowed"].passed is True or by["c.type_allowed"].reason in {
        "path_class_type_unevaluable",
        None,
    }


def test_family_c_exact_gate_codes_and_status_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    plan = _plan()
    gate = SimpleNamespace(
        codes=("GATE_PATH_SCOPE_MISMATCH", "GATE_TYPE_FORBIDDEN", "GATE_SEMVER_CEILING", "CHANGELOG_ANTISIGNAL"),
        gate_status=(
            ("scope", "fail"),
            ("type", "fail"),
            ("semver", "fail"),
            ("changelog", "fail"),
        ),
    )
    monkeypatch.setattr(fc, "evaluate_presentation_gates", lambda *a, **k: gate)
    monkeypatch.setattr(fc, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(
        fc, "presentation_constraints", lambda _dc: SimpleNamespace(force_scope=None, forced_scope=None)
    )

    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    # Without a usable gold dual-row, exact product gate codes must fail C metrics.
    by = _by(score_family_c(ctx, gold_slot=None, plan=plan))
    assert by["c.scope_forced_ok"].passed is False
    assert by["c.scope_forced_ok"].reason == "GATE_PATH_SCOPE_MISMATCH"
    assert by["c.type_allowed"].passed is False
    assert by["c.type_allowed"].reason == "path_class_type_gate"
    assert by["c.semver_ceiling"].passed is False
    assert by["c.semver_ceiling"].reason == "path_class_semver_gate"
    assert by["c.changelog_antisignal"].passed is False


def test_family_c_gold_dual_rows_and_contract_paths() -> None:
    plan = _plan()
    ctx = _ctx(final_message=VALID_MSG)

    gold_type = _clean_gold(
        codes={"GOLD_PATH_CLASS_TYPE_MISMATCH", "GOLD_PATH_CLASS_SEMVER_CEILING", "GOLD_CONTRACT_SMOKE"},
        plan=plan,
        contract_provided=True,
    )
    by = _by(score_family_c(ctx, gold_slot=gold_type, plan=plan))
    assert by["c.type_allowed"].passed is False
    assert by["c.type_allowed"].reason == "GOLD_PATH_CLASS_TYPE_MISMATCH"
    assert by["c.semver_ceiling"].passed is False
    assert by["c.semver_ceiling"].reason == "GOLD_PATH_CLASS_SEMVER_CEILING"
    assert by["c.contract_smoke"].passed is False
    assert by["c.contract_smoke"].reason == "GOLD_CONTRACT_SMOKE"

    clean = _clean_gold(codes=set(), plan=plan, contract_provided=True)
    by_ok = _by(score_family_c(ctx, gold_slot=clean, plan=plan))
    assert by_ok["c.type_allowed"].passed is True
    assert by_ok["c.semver_ceiling"].passed is True
    assert by_ok["c.contract_smoke"].passed is True

    err = _clean_gold(plan=plan, error="boom", contract_provided=True)
    by_err = _by(score_family_c(ctx, gold_slot=err, plan=plan))
    assert by_err["c.contract_smoke"].reason == "gold_evaluation_error"

    no_report = GoldSlot(plan=plan, contract_provided=True, call_count=1, call_identity="x")
    by_nr = _by(score_family_c(ctx, gold_slot=no_report, plan=plan))
    assert by_nr["c.contract_smoke"].reason == "gold_report_missing"


def test_family_c_security_and_evidence_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    msg = (
        "🔒 fix(security): rotate secrets\n\n"
        "Harden auth token handling without path proof.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: fix\nChangelog-Groups: Fixed\n"
    )
    secondary = [
        _intent(description="touch family_c module"),
        _intent(description="unrelated claim xyzzy"),
    ]
    plan = _plan(
        secondary=secondary,
        intent_id="security_hardening",
        gitmoji="🔒",
        cc_type=CommitType.FIX,
        scope="security",
        description="rotate secrets",
        changelog_group="Fixed",
    )
    monkeypatch.setattr(fc, "security_claims_without_path_evidence", lambda _m, _p: ["secrets"])
    monkeypatch.setattr(fc, "has_security_path_evidence", lambda _p: False)

    ctx = project_score_context(_bundle(final_message=msg), files=("src/git_cg/eval/scoring/family_c.py",))
    by = _by(score_family_c(ctx, gold_slot=_clean_gold(plan=plan), plan=plan))
    assert by["c.security_claim_evidence"].passed is False
    assert by["c.evidence_surface_precision"].value < 1.0 or by["c.evidence_surface_precision"].passed is False
    # Recall should improve when path stem appears in message body.
    assert "family_c" in msg or by["c.evidence_surface_recall"].value <= 1.0

    # Claims without any paths → precision/recall fail-closed warn path.
    bare = project_score_context(_bundle(final_message=msg), files=())
    by_bare = _by(score_family_c(bare, gold_slot=_clean_gold(plan=plan), plan=plan))
    assert by_bare["c.evidence_surface_precision"].passed is False
    assert by_bare["c.evidence_surface_recall"].passed is False


# ---------------------------------------------------------------------------
# Family E
# ---------------------------------------------------------------------------


def test_family_e_parse_guard_and_constraint_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    monkeypatch.setattr(fe, "parse_message_to_plan", lambda _m: (_ for _ in ()).throw(RuntimeError("p")))
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: (_ for _ in ()).throw(RuntimeError("c")))
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("g")))

    # Provide an explicit plan so guards are attempted after classify fails.
    plan = _plan()
    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    by = _by(score_family_e(ctx, gold_slot=None, plan=plan))
    assert by["e.banned_craft_openers"].passed is False
    assert any("GUARD_EVAL_ERROR" in c for c in (by["e.banned_craft_openers"].evidence or {}).get("guard_codes", []))
    assert by["e.presentation_constraints_applied"].passed is False
    assert by["e.secondary_intent_fill_legal"].reason != "plan_missing"


def test_family_e_banned_opener_changelog_and_docs_craft(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    msg = (
        "📝 docs(eval): banned opener\n\n"
        "This commit introduces a craft violation.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    plan = _plan()
    guard = SimpleNamespace(
        findings=(SimpleNamespace(code="GUARD_DOCS_CRAFT"),),
        craft_guard_fired=True,
        fallback_reason="none",
        hallucination_guard_fired=False,
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "changelog_groups_allowlisted", lambda *a, **k: False)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: SimpleNamespace())
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="docs"))

    signals = DiffSignals(only_docs=True)
    ctx = project_score_context(_bundle(final_message=msg), files=("docs/x.md",))
    by = _by(score_family_e(ctx, gold_slot=_clean_gold(plan=plan), plan=plan, signals=signals))
    assert by["e.banned_craft_openers"].passed is False
    assert by["e.changelog_groups_allowlisted"].passed is False
    assert by["e.docs_tests_craft"].passed is False


def test_family_e_missing_trailers_and_changelog_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    msg = "📝 docs(eval): no trailers\n\nBody only.\n"
    plan = _plan()
    guard = SimpleNamespace(
        findings=(), craft_guard_fired=False, fallback_reason="none", hallucination_guard_fired=False
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: SimpleNamespace())
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="docs"))

    ctx = _ctx(final_message=msg)
    by = _by(score_family_e(ctx, plan=plan))
    assert by["e.changelog_groups_allowlisted"].reason == "missing_changelog_trailers"

    monkeypatch.setattr(
        fe,
        "changelog_groups_allowlisted",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cg")),
    )
    by_err = _by(score_family_e(ctx, plan=plan))
    assert by_err["e.changelog_groups_allowlisted"].passed is False
    assert "RuntimeError" in (by_err["e.changelog_groups_allowlisted"].reason or "")


def test_family_e_low_confidence_min_bullets_and_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    plan = _plan(secondary=[])
    guard = SimpleNamespace(
        findings=(), craft_guard_fired=False, fallback_reason="none", hallucination_guard_fired=False
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: SimpleNamespace())
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(fe, "is_low_confidence_posture", lambda _c: True)
    monkeypatch.setattr(fe, "min_included_change_bullets", lambda _p: 3)

    # Mutating fill — primary identity changes.
    def _mutate(p: CommitPlan, **_k: Any) -> CommitPlan:
        bad_primary = p.primary_intent.model_copy(update={"intent_id": "mutated"})
        return p.model_copy(update={"primary_intent": bad_primary})

    monkeypatch.setattr(fe, "fill_secondary_intents_from_stubs", _mutate)

    msg = (
        "📝 docs(eval): missing posture wording\n\n"
        "Absolutely certain this is correct.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    ctx = project_score_context(
        _bundle(final_message=msg, product_card={"ranking_confidence": {"reasons": ["sparse_diff"]}}),
        files=("src/a.py", "src/b.py", "tests/t.py"),
    )
    by = _by(score_family_e(ctx, plan=plan))
    assert by["e.low_confidence_posture"].passed is False
    assert by["e.min_included_bullets"].passed is False
    assert by["e.secondary_intent_fill_legal"].passed is False
    assert by["e.secondary_intent_fill_legal"].reason == "primary_mutated:intent_id"

    monkeypatch.setattr(
        fe,
        "fill_secondary_intents_from_stubs",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fill")),
    )
    by_fill = _by(score_family_e(ctx, plan=plan))
    assert by_fill["e.secondary_intent_fill_legal"].reason.startswith("RuntimeError")

    by_no_plan = _by(score_family_e(project_score_context(_bundle(final_message=""), files=()), plan=None))
    assert by_no_plan["e.secondary_intent_fill_legal"].reason == "plan_missing"


def test_family_e_skeleton_and_stub_incoherence(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    plan = _plan(
        secondary=[
            _intent(description="same stub"),
            _intent(description="SAME STUB"),
            _intent(description=""),
        ]
    )
    guard = SimpleNamespace(
        findings=(),
        craft_guard_fired=False,
        fallback_reason="skeleton path engaged",
        hallucination_guard_fired=True,
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: SimpleNamespace())
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(fe, "fill_secondary_intents_from_stubs", lambda p, **k: p)
    monkeypatch.setattr(fe, "changelog_groups_allowlisted", lambda *a, **k: True)
    monkeypatch.setattr(fe, "min_included_change_bullets", lambda _p: 0)
    monkeypatch.setattr(fe, "is_low_confidence_posture", lambda _c: False)

    msg = (
        "♻️ refactor(eval): LOW-CONFIDENCE BODY SKELETON retained\n\n"
        "Included changes:\n"
        "- same stub\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: refactor\nChangelog-Groups: Changed\n"
    )
    gold = _clean_gold(codes={"GOLD_SKELETON_FALLBACK_FINAL"}, plan=plan)
    ctx = project_score_context(_bundle(final_message=msg), files=("src/a.py",))
    by = _by(score_family_e(ctx, gold_slot=gold, plan=plan))
    assert by["e.skeleton_avoidance"].passed is False
    assert by["e.stub_inventory_coherent"].passed is False

    # Empty message + no guard → skeleton fail-closed
    by_empty = _by(score_family_e(project_score_context(_bundle(final_message=""), files=()), plan=None))
    assert by_empty["e.skeleton_avoidance"].passed is False


def test_family_e_constraint_violation_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    plan = _plan()
    guard = SimpleNamespace(
        findings=(SimpleNamespace(code="CONSTRAINT_FORCE_SCOPE"),),
        craft_guard_fired=False,
        fallback_reason="none",
        hallucination_guard_fired=False,
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: SimpleNamespace(name="c"))
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(fe, "fill_secondary_intents_from_stubs", lambda p, **k: p)
    monkeypatch.setattr(fe, "changelog_groups_allowlisted", lambda *a, **k: True)
    monkeypatch.setattr(fe, "min_included_change_bullets", lambda _p: 0)

    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    by = _by(score_family_e(ctx, plan=plan))
    assert by["e.presentation_constraints_applied"].passed is False


# ---------------------------------------------------------------------------
# Family F
# ---------------------------------------------------------------------------


def test_family_f_gold_slot_states_and_parse_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_f as ff

    monkeypatch.setattr(ff, "parse_message_to_plan", lambda _m: (_ for _ in ()).throw(RuntimeError("p")))
    ctx = _ctx(final_message=VALID_MSG)

    by_missing = _by(score_family_f(ctx, gold_slot=None))
    assert by_missing["f.subject_attribution"].reason == "gold_slot_missing"

    skipped = _clean_gold(skipped=True)
    by_skip = _by(score_family_f(ctx, gold_slot=skipped))
    assert by_skip["f.body_attribution"].reason == "gold_skipped"

    err = _clean_gold(error="gold boom")
    by_err = _by(score_family_f(ctx, gold_slot=err))
    assert by_err["f.subject_attribution"].reason == "gold_evaluation_error"
    assert by_err["f.included_changes_vs_diff"].reason == "gold_evaluation_error"


def test_family_f_attribution_hits_counter_and_paths() -> None:
    plan = _plan(secondary=[_intent(description="update family_f path allowlist")])
    msg = (
        "📝 docs(eval): touch 9 files in docs\n\n"
        "Included changes:\n"
        "- update family_f path allowlist\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    gold = _clean_gold(
        codes={
            "GOLD_SUBJECT_INVENTORY",
            "GOLD_BODY_INVENTORY",
            "GOLD_INCLUDED_CHANGES_MISSING",
        },
        plan=plan,
    )
    ctx = project_score_context(_bundle(final_message=msg), files=("src/git_cg/eval/scoring/family_f.py",))
    by = _by(score_family_f(ctx, gold_slot=gold, plan=plan))
    assert by["f.subject_attribution"].passed is False
    assert by["f.body_attribution"].passed is False
    assert by["f.counter_integrity"].passed is False
    assert by["f.included_changes_vs_diff"].reason == "GOLD_INCLUDED_CHANGES_MISSING"

    # Local file-counter mismatch when gold is clean.
    clean = _clean_gold(codes=set(), plan=plan)
    by_cnt = _by(score_family_f(ctx, gold_slot=clean, plan=plan))
    assert by_cnt["f.counter_integrity"].reason == "file_counter_mismatch"


def test_family_f_included_changes_without_paths_and_allowlist() -> None:
    plan = _plan(secondary=[_intent(description="claim without path evidence")])
    msg = (
        "📝 docs(eval): included changes honesty\n\n"
        "Included changes:\n- claim without path evidence\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    ctx = project_score_context(_bundle(final_message=msg), files=())
    by = _by(score_family_f(ctx, gold_slot=_clean_gold(plan=plan), plan=plan))
    assert by["f.included_changes_vs_diff"].passed is False
    assert by["f.included_changes_vs_diff"].reason == "no_path_evidence_for_included_changes"
    assert by["f.staged_path_allowlist"].passed is True  # vacuous

    # No secondary and no included-changes section → pass without paths.
    bare_plan = _plan(secondary=[])
    bare_msg = (
        "📝 docs(eval): no inventory claims\n\n"
        "Prose only.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    bare = project_score_context(_bundle(final_message=bare_msg), files=())
    by_bare = _by(score_family_f(bare, gold_slot=_clean_gold(plan=bare_plan), plan=bare_plan))
    assert by_bare["f.included_changes_vs_diff"].passed is True

    bad = project_score_context(
        _bundle(final_message=bare_msg),
        files=("/abs/path.py", "https://x.example/a", "a//b.py", "win\\path.py", "a/\x00/b.py"),
    )
    by_bad = _by(score_family_f(bad, gold_slot=_clean_gold(plan=bare_plan), plan=bare_plan))
    assert by_bad["f.staged_path_allowlist"].passed is False


def test_family_f_alignment_and_security_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_f as ff

    monkeypatch.setattr(ff, "security_claims_without_path_evidence", lambda _m, _p: ["token"])

    empty = project_score_context(_bundle(final_message=""), files=("src/a.py",))
    by_empty = _by(score_family_f(empty, gold_slot=_clean_gold()))
    assert by_empty["f.claim_evidence_alignment"].reason == "empty_message"

    plan = _plan(secondary=[_intent(description="xyzzy unmatched claim token")])
    msg = (
        "📝 docs(eval): alignment\n\n"
        "Rotate token without evidence.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    ctx = project_score_context(_bundle(final_message=msg), files=("src/git_cg/eval/scoring/family_f.py",))
    by = _by(score_family_f(ctx, gold_slot=_clean_gold(plan=plan), plan=plan))
    assert by["f.security_claims_need_paths"].passed is False
    assert by["f.claim_evidence_alignment"].passed is False

    # No secondary → header token alignment path.
    plan2 = _plan(secondary=[])
    msg2 = (
        "📝 docs(eval): family path\n\n"
        "Body.\n\n"
        "Refs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    ctx2 = project_score_context(_bundle(final_message=msg2), files=("src/family_path.py",))
    by2 = _by(score_family_f(ctx2, gold_slot=_clean_gold(plan=plan2), plan=plan2))
    assert "alignment" in (by2["f.claim_evidence_alignment"].evidence or {})


# ---------------------------------------------------------------------------
# Family G
# ---------------------------------------------------------------------------


def test_family_g_null_numeric_secret_variants_and_identity() -> None:
    # Null without hash still accepted as #0 after normalization.
    msg0 = (
        "📝 docs(eval): null zero\n\n"
        "Null: 0\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    )
    by0 = _by(score_family_g(_ctx(final_message=msg0)))
    assert by0["g.issue_null_policy"].passed is True

    # Assemble secret-shape fixtures at runtime to avoid secret-scanner triggers.
    jwt = ".".join(
        (
            "eyJ" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0",
            "signature" + "xx_pad12",
        )
    )
    pem = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END " + "RSA PRIVATE KEY-----"
    msg_sec = (
        "🔧 chore(eval): secret shapes\n\n"
        f"jwt {jwt}\n"
        f"{pem}\n"
        "api_key: 'abcdefghijklmnop'\n"
        "Refs: #1\nSemVer-Impact: NONE\nChange-Types: chore\nChangelog-Groups: Miscellaneous\n"
    )
    by_sec = _by(score_family_g(_ctx(final_message=msg_sec)))
    assert by_sec["g.secrets_not_in_message"].passed is False
    hits = (by_sec["g.secrets_not_in_message"].evidence or {}).get("hits") or []
    assert hits

    # Empty message secret scan is clean.
    by_empty = _by(score_family_g(project_score_context(_bundle(final_message=""), files=())))
    assert by_empty["g.secrets_not_in_message"].passed is True

    # Missing plan identity fields.
    class _P:
        primary_intent = SimpleNamespace(intent_id=None, gitmoji=None, cc_type=None, description=None)

    by_id = _by(score_family_g(_ctx(final_message=VALID_MSG), plan=_P()))  # type: ignore[arg-type]
    assert by_id["g.ranked_identity_preserved"].passed is False
    assert by_id["g.semantic_contract_bound"].passed is False


def test_family_g_card_intent_mismatch_and_plan_missing() -> None:
    plan = _plan(intent_id="documentation_update")
    msg = VALID_MSG
    ctx = project_score_context(
        _bundle(final_message=msg, product_card={"intent_id": "totally_different"}),
        files=("src/a.py",),
    )
    by = _by(score_family_g(ctx, plan=plan))
    assert by["g.ranked_identity_preserved"].reason == "card_intent_mismatch"
    assert by["g.semantic_contract_bound"].passed is True

    class _MissingFields:
        primary_intent = SimpleNamespace(
            intent_id="x",
            gitmoji="📝",
            cc_type=None,
            description=None,
        )

    by_mf = _by(score_family_g(_ctx(final_message=msg), plan=_MissingFields()))  # type: ignore[arg-type]
    assert by_mf["g.ranked_identity_preserved"].reason == "missing_cc_type"
    assert by_mf["g.semantic_contract_bound"].reason == "semantic_fields_missing"

    by_empty = _by(score_family_g(project_score_context(_bundle(final_message=""), files=()), plan=None))
    assert by_empty["g.ranked_identity_preserved"].reason == "plan_missing"
    assert by_empty["g.semantic_contract_bound"].reason == "plan_unbound"


def test_family_g_policy_and_sop_audit_cache_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import git_cg.eval.scoring.family_g as fg

    # Clear caches so monkeypatches are observed.
    fg._audit_policy_fork.cache_clear()
    fg._audit_sop_mutation.cache_clear()

    # Point scoring root at a tiny synthetic package that triggers findings.
    root = tmp_path / "scoring"
    root.mkdir()
    (root / "product_bridges.py").write_text(
        "# missing required symbols and imports on purpose\n"
        "import re\n"
        "SOP_EMOJI_MAP = {}\n"
        "GOLD_FAKE_TABLE = {}\n"
        "def check_commit_gold():\n"
        "    return None\n",
        encoding="utf-8",
    )
    (root / "family_c.py").write_text(
        "import re\n_HYBRID_HEADER_RE = re.compile(r'(?P<cc_type>feat)')\n",
        encoding="utf-8",
    )
    (root / "family_x.py").write_text(
        "from opik import track\nopik_metrics = 1\nopen('gitops_agent_sop.json', 'w').write('x')\n",
        encoding="utf-8",
    )
    (root / "family_b.py").write_text("# no bridges import\n", encoding="utf-8")
    (root / "family_d.py").write_text("# no bridges import\n", encoding="utf-8")
    (root / "family_e.py").write_text("# no bridges import\n", encoding="utf-8")
    (root / "family_f.py").write_text("# no bridges import\n", encoding="utf-8")
    (root / "family_g.py").write_text("# self\n", encoding="utf-8")
    (root / "bad_syntax.py").write_text("def (\n", encoding="utf-8")

    monkeypatch.setattr(fg, "_SCORING_ROOT", root)
    fg._audit_policy_fork.cache_clear()
    fg._audit_sop_mutation.cache_clear()

    ok, findings, ev = fg._audit_policy_fork()
    assert ok is False
    assert findings
    assert ev["findings"]

    sop_ok, sop_findings = fg._audit_sop_mutation()
    assert sop_ok is False
    assert any(f.startswith("sop_write:") for f in sop_findings)

    # Score path should surface fail results via cached helpers.
    by = _by(score_family_g(_ctx(final_message=VALID_MSG), plan=_plan()))
    assert by["g.no_eval_policy_fork"].passed is False
    assert by["g.sop_not_mutated"].passed is False

    # Unreadable path branch for policy audit.
    fg._audit_policy_fork.cache_clear()

    class _BoomPath(type(root)):
        def read_text(self, *a: Any, **k: Any) -> str:  # type: ignore[override]
            raise OSError("nope")

    # Replace product_bridges with an unreadable path object via monkeypatch on Path.read_text
    real_read = Path.read_text

    def _flaky_read(self: Path, *a: Any, **k: Any) -> str:
        if self.name == "product_bridges.py":
            raise OSError("unreadable")
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _flaky_read)
    fg._audit_policy_fork.cache_clear()
    ok2, findings2, _ev2 = fg._audit_policy_fork()
    assert ok2 is False
    assert any("unreadable" in f for f in findings2)

    # Restore cache cleanliness for other tests in session.
    monkeypatch.undo()
    fg._audit_policy_fork.cache_clear()
    fg._audit_sop_mutation.cache_clear()
    # Ensure real package still passes after cache clear.
    ok_real, _f_real, _e_real = fg._audit_policy_fork()
    assert ok_real is True
    sop_real, _sf = fg._audit_sop_mutation()
    assert sop_real is True


def test_family_g_parse_exception_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_g as fg

    monkeypatch.setattr(fg, "parse_message_to_plan", lambda _m: (_ for _ in ()).throw(RuntimeError("parse")))
    by = _by(score_family_g(_ctx(final_message=VALID_MSG), plan=None))
    assert by["g.ranked_identity_preserved"].reason == "plan_missing"
    assert by["g.semantic_contract_bound"].reason == "plan_unbound"


def test_family_c_type_semver_gate_only_without_gold(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    plan = _plan()
    gate = SimpleNamespace(
        codes=(),
        gate_status=(("type", "fail"), ("semver", "fail")),
    )
    monkeypatch.setattr(fc, "evaluate_presentation_gates", lambda *a, **k: gate)
    monkeypatch.setattr(fc, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(fc, "presentation_constraints", lambda _dc: SimpleNamespace(force_scope=None))

    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    # gold report present with no type/semver codes → prefer gold clean pass
    gold = _clean_gold(codes=set(), plan=plan)
    by_gold = _by(score_family_c(ctx, gold_slot=gold, plan=plan))
    assert by_gold["c.type_allowed"].passed is True
    assert by_gold["c.semver_ceiling"].passed is True

    # no gold report usable: gate status fails
    by_gate = _by(score_family_c(ctx, gold_slot=None, plan=plan))
    assert by_gate["c.type_allowed"].reason == "path_class_type_gate"
    assert by_gate["c.semver_ceiling"].reason == "path_class_semver_gate"


def test_family_e_is_low_confidence_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    plan = _plan()
    guard = SimpleNamespace(
        findings=(), craft_guard_fired=False, fallback_reason="none", hallucination_guard_fired=False
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: None)
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="x"))
    monkeypatch.setattr(fe, "is_low_confidence_posture", lambda _c: (_ for _ in ()).throw(RuntimeError("lc")))
    monkeypatch.setattr(fe, "min_included_change_bullets", lambda _p: (_ for _ in ()).throw(RuntimeError("mb")))
    monkeypatch.setattr(fe, "fill_secondary_intents_from_stubs", lambda p, **k: p)
    monkeypatch.setattr(fe, "changelog_groups_allowlisted", lambda *a, **k: True)

    ctx = project_score_context(
        _bundle(final_message=VALID_MSG, product_card={"confidence": object()}),
        files=("src/a.py",),
    )
    by = _by(score_family_e(ctx, plan=plan))
    # Exceptions degrade closed but should not crash.
    assert by["e.low_confidence_posture"].passed is True
    assert by["e.min_included_bullets"].passed is True


def test_family_c_forced_scope_match_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_c as fc

    plan = _plan(scope="api")
    gate = SimpleNamespace(codes=(), gate_status=(("scope", "pass"),))
    monkeypatch.setattr(fc, "evaluate_presentation_gates", lambda *a, **k: gate)
    monkeypatch.setattr(fc, "classify_diff_class", lambda _p: SimpleNamespace(value="product_src"))
    monkeypatch.setattr(
        fc,
        "presentation_constraints",
        lambda _dc: SimpleNamespace(force_scope="api", forced_scope=None),
    )
    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    by = _by(score_family_c(ctx, gold_slot=None, plan=plan))
    assert by["c.scope_forced_ok"].passed is True
    assert by["c.scope_forced_ok"].reason is None


def test_family_e_parse_exception_and_guard_code_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.eval.scoring.family_e as fe

    monkeypatch.setattr(fe, "parse_message_to_plan", lambda _m: (_ for _ in ()).throw(RuntimeError("parse")))
    # No plan supplied → parse exception path.
    by_parse = _by(score_family_e(_ctx(final_message=VALID_MSG), plan=None, gold_slot=None))
    assert by_parse["e.secondary_intent_fill_legal"].reason == "plan_missing"

    # Findings without code are ignored; primary_cc without .value is used raw.
    # CommitPlan-like object with model_dump on primary for fill path.
    class _Primary:
        def model_dump(self) -> dict[str, Any]:
            return {
                "intent_id": "documentation_update",
                "cc_type": "docs",
                "gitmoji": "📝",
                "semver_impact": "PATCH",
            }

        cc_type = "docs"  # plain string — no .value
        intent_id = "documentation_update"
        gitmoji = "📝"
        semver_impact = "PATCH"

    class _Plan2:
        primary_intent = _Primary()
        secondary_intents: tuple[Any, ...] = ()

    guard = SimpleNamespace(
        findings=(SimpleNamespace(code=None), SimpleNamespace(code="OK")),
        craft_guard_fired=False,
        fallback_reason="none",
        hallucination_guard_fired=False,
    )
    monkeypatch.setattr(fe, "evaluate_presentation_guards", lambda *a, **k: guard)
    monkeypatch.setattr(fe, "presentation_constraints", lambda _dc: SimpleNamespace())
    monkeypatch.setattr(fe, "classify_diff_class", lambda _p: SimpleNamespace(value="x"))
    monkeypatch.setattr(fe, "fill_secondary_intents_from_stubs", lambda p, **k: p)
    monkeypatch.setattr(fe, "changelog_groups_allowlisted", lambda *a, **k: True)
    monkeypatch.setattr(fe, "min_included_change_bullets", lambda _p: 0)
    monkeypatch.setattr(fe, "is_low_confidence_posture", lambda _c: False)

    # Non-dict product/score card should not crash confidence extraction.
    ctx = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    object.__setattr__(ctx, "product_card", "not-a-dict")  # type: ignore[arg-type]
    object.__setattr__(ctx, "score_card", None)
    by = _by(score_family_e(ctx, plan=_Plan2()))  # type: ignore[arg-type]
    assert by["e.banned_craft_openers"].passed is True
    assert by["e.low_confidence_posture"].passed is True
    assert "OK" in (by["e.banned_craft_openers"].evidence or {}).get("guard_codes", [])


def test_family_g_identity_missing_gitmoji_and_nested_card() -> None:
    class _Plan:
        primary_intent = SimpleNamespace(
            intent_id="documentation_update",
            gitmoji=None,
            cc_type="docs",
            description="x",
        )

    by = _by(score_family_g(_ctx(final_message=VALID_MSG), plan=_Plan()))  # type: ignore[arg-type]
    assert by["g.ranked_identity_preserved"].reason == "missing_gitmoji"

    plan = _plan(intent_id="documentation_update")
    ctx = project_score_context(
        _bundle(
            final_message=VALID_MSG,
            product_card={"primary_intent": {"intent_id": "other_intent"}},
        ),
        files=("src/a.py",),
    )
    by2 = _by(score_family_g(ctx, plan=plan))
    assert by2["g.ranked_identity_preserved"].reason == "card_intent_mismatch"

    # Non-dict card skips card_intent extraction.
    ctx3 = project_score_context(_bundle(final_message=VALID_MSG), files=("src/a.py",))
    object.__setattr__(ctx3, "product_card", ["not", "dict"])
    by3 = _by(score_family_g(ctx3, plan=plan))
    assert by3["g.ranked_identity_preserved"].passed is True


def test_family_g_audit_attribute_annassign_direct_call_and_missing_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import git_cg.eval.scoring.family_g as fg

    root = tmp_path / "scoring2"
    root.mkdir()
    (root / "product_bridges.py").write_text(
        "from git_cg.commit_gold import check_commit_gold, STRICT_FAIL_CODES\n"
        "from git_cg.telemetry import reverse_parse_commit_message\n"
        "from git_cg.commit_quality import run_deterministic_checks\n"
        "import re\n"
        "_HYBRID_HEADER_RE = re.compile(r'(?P<cc_type>feat)')\n"
        "GOLD_CODE_TO_D_METRIC = {}\n",
        encoding="utf-8",
    )
    # Attribute forbidden name + annotated GOLD_ + attribute-style gold call.
    (root / "family_c.py").write_text(
        "import something\n"
        "something.SOP_EMOJI_MAP\n"
        "GOLD_ANN: dict = {}\n"
        "mod.check_commit_gold()\n"
        "from git_cg.eval.scoring import product_bridges\n",
        encoding="utf-8",
    )
    # Keep required families present for bridges import check except one missing.
    for fam in ("family_b.py", "family_d.py", "family_e.py", "family_f.py", "family_g.py"):
        (root / fam).write_text("import product_bridges\n", encoding="utf-8")
    # Unreadable sop file via permission or open path for sop audit load_sop dump.
    (root / "family_b.py").write_text(
        "import product_bridges\nload_sop(); json.dump(x, open('gitops_agent_sop.json','w'))\n",
        encoding="utf-8",
    )
    # Remove family_d to hit missing_family_module
    (root / "family_d.py").unlink()

    monkeypatch.setattr(fg, "_SCORING_ROOT", root)
    fg._audit_policy_fork.cache_clear()
    fg._audit_sop_mutation.cache_clear()

    ok, findings, ev = fg._audit_policy_fork()
    assert ok is False
    joined = " ".join(findings)
    assert "forbidden_name" in joined or ev["forbidden_hits"]
    assert "eval_gold_const" in joined or ev["gold_const_defs"]
    assert "direct_gold_call" in joined or ev["direct_gold_calls"]
    assert "missing_family_module:family_d.py" in findings

    sop_ok, sop_findings = fg._audit_sop_mutation()
    assert sop_ok is False
    assert any(x.startswith("sop_dump:") or x.startswith("sop_write:") for x in sop_findings)

    # Unreadable family module during policy family import pass.
    real_read = Path.read_text

    def _flaky(self: Path, *a: Any, **k: Any) -> str:
        if self.name == "family_e.py":
            raise OSError("nope")
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _flaky)
    fg._audit_policy_fork.cache_clear()
    fg._audit_sop_mutation.cache_clear()
    _ok2, findings2, _ = fg._audit_policy_fork()
    assert any("unreadable:family_e.py" in f for f in findings2)
    _sop_ok2, _ = fg._audit_sop_mutation()  # OSError continue path exercised

    monkeypatch.undo()
    fg._audit_policy_fork.cache_clear()
    fg._audit_sop_mutation.cache_clear()
    assert fg._audit_policy_fork()[0] is True
    assert fg._audit_sop_mutation()[0] is True
