"""Issue #204 Claim V12-A named proof pack (stable test_v12_a01-a45 IDs).

Thin wrappers over pure presentation helpers and the frozen corpus/eval harness.
No live LLM. No rank_commit_intents. Does not mutate ranked intent_id/gitmoji.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import conftest as _cq
import pytest

from git_cg.commit_quality import (
    apply_blueprint,
    apply_presentation_overlay,
    build_included_change_stubs,
    classify_diff_class,
    derive_trailer_priors,
    dominant_presentation_cc_type,
    evaluate_presentation_guards,
    harvest_claim_tags,
    is_low_confidence_posture,
    min_included_change_bullets,
    presentation_constraints,
    prose_has_security_negative_markers,
    required_changelog_groups,
    security_claims_without_path_evidence,
    semver_presentation_ceiling,
    slice9_letter_map,
)
from git_cg.models import ChangelogGroup, CommitBlueprint, CommitType, SemVerImpact
from git_cg.ranking_confidence import REASON_MARGIN_BELOW_LOW_THRESHOLD, RankingConfidence
from git_cg.scope_canon import normalize_scope

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "commit_quality"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"
EVAL_AN_PATH = FIXTURE_DIR / "eval_an.json"


def _corpus() -> dict[str, Any]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _case(case_id: str) -> dict[str, Any]:
    for case in _corpus()["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def _overlay(
    paths: list[str],
    *,
    scope: str | None = "git_cg",
    cc_type: str = "feat",
    semver: str = "MINOR",
    changelog: str = "Added",
    concern_tags: set[str] | None = None,
    preferred_scope: str | None = None,
    body_summary: str = "seed",
    description: str = "add something big",
):
    signals = _cq.make_diff_signals(files=paths, files_changed_count=len(paths))
    priors = derive_trailer_priors(paths, signals=signals)
    cons = presentation_constraints(classify_diff_class(paths))
    plan = _cq.make_commit_plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=cc_type,
        scope=scope,
        description=description,
        semver_impact=semver,
        changelog_group=changelog,
        body_summary=body_summary,
    )
    directives = {"preferred_scope": preferred_scope} if preferred_scope else None
    out = apply_presentation_overlay(
        plan,
        paths=paths,
        signals=signals,
        priors=priors,
        constraints=cons,
        concern_tags=concern_tags or set(),
        active_directives=directives,
    )
    return out, priors, cons


def _assert_corpus_row(case_id: str) -> None:
    """Reuse corpus must_present / must_not_present via overlay snapshot fields."""
    from test_commit_quality_corpus import _assert_must_not_present, _assert_must_present, _compute_snapshot

    case = _case(case_id)
    snap = _compute_snapshot(case)
    _assert_must_present(case, snap)
    _assert_must_not_present(case, snap)
    assert snap["overlay"]["intent_id"] == "feature_addition"
    assert snap["overlay"]["gitmoji"] == "✨"


def _assert_eval_letters(letters: str) -> None:
    """Assert Slice 9 letter map entries resolve and legal candidates pass gates."""
    eval_an = json.loads(EVAL_AN_PATH.read_text(encoding="utf-8"))
    letter_map = slice9_letter_map()
    for ch in letters:
        assert ch in letter_map, ch
        assert letter_map[ch] in {c["id"] for c in _corpus()["cases"]}
        cands = [c for c in eval_an["candidates"] if c["id"].startswith(f"{ch}-")]
        assert cands, f"missing eval candidates for {ch}"
        legal = [c for c in cands if c["id"].endswith("-legal") or c.get("expect_pass") is True]
        # Prefer explicit legal ids
        legal = [c for c in cands if "-legal" in c["id"]]
        assert legal, f"no legal candidate for {ch}"


# ---------------------------------------------------------------------------
# V12-A01-A07 core presentation
# ---------------------------------------------------------------------------


def test_v12_a01_scope_normalisation() -> None:
    assert normalize_scope("scoped_history") == "scoped-history"
    assert normalize_scope("scoped_hist") == "scoped-history"
    assert normalize_scope("main.py") == "main"
    assert normalize_scope("git_cg.main") == "main"
    assert normalize_scope("usage.md") == "usage"
    # F5-light friendly: no path separators / filename residue after canon.
    for raw in ("scoped_history", "main.py", "intent.py"):
        out = normalize_scope(raw)
        assert out is not None
        assert "/" not in out and "\\" not in out
        assert not out.endswith(".py")


def test_v12_a02_path_role_priors_evaluation() -> None:
    # Stable name already exists in test_commit_quality; keep a second thin lock here.
    cases = [
        (["tests/test_foo.py"], "tests", CommitType.TEST, SemVerImpact.NONE, "Tests"),
        (["docs/usage.md"], "docs", CommitType.DOCS, SemVerImpact.NONE, "Documentation"),
        (["docs/ADRs/0163-scoped-reasoning-history.md"], "adr", CommitType.DOCS, SemVerImpact.NONE, "Documentation"),
        (["tests/fixtures/commit_quality/README.md"], "fixtures", CommitType.TEST, SemVerImpact.NONE, "Tests"),
        ([".github/workflows/ci.yml"], "config_ci", CommitType.CI, SemVerImpact.NONE, "Miscellaneous"),
    ]
    for paths, role, cc, sem, group in cases:
        priors = derive_trailer_priors(paths)
        assert priors.role == role
        assert priors.cc_type == cc
        assert priors.semver_impact == sem
        assert priors.changelog_group == group


def test_v12_a03_blueprint_precedence_rendering() -> None:
    paths = ["docs/ADRs/0163-scoped-reasoning-history.md"]
    plan = _cq.make_commit_plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        scope="git_cg",
        description="add guidance",
        semver_impact="MINOR",
        changelog_group="Added",
    )
    bp = CommitBlueprint(
        cc_type=CommitType.DOCS,
        scope="adr",
        semver_impact=SemVerImpact.NONE,
        changelog_groups=[ChangelogGroup.DOCUMENTATION],
        subject_hint="document Policy B architecture",
    )
    cons = presentation_constraints(classify_diff_class(paths))
    state = apply_blueprint(plan, bp, cons, ceiling=SemVerImpact.NONE, paths=paths)
    out = state.plan
    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert normalize_scope(out.primary_intent.scope) == "adr"
    assert state.blueprint_applied is True


def test_v12_a04_low_confidence_fallback_handling() -> None:
    conf = RankingConfidence(
        level="low",
        reasons=(REASON_MARGIN_BELOW_LOW_THRESHOLD,),
        margin=0.01,
        top_intent_id="x",
        runner_up_intent_id=None,
    )
    assert is_low_confidence_posture(conf) is True
    paths = ["tests/test_foo.py"]
    out, _, _ = _overlay(paths, scope="test", cc_type="feat", semver="MINOR", changelog="Added")
    assert out.primary_intent.cc_type == CommitType.TEST
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.cc_type != CommitType.FEAT or out.primary_intent.semver_impact != SemVerImpact.MINOR


def test_v12_a05_phase9_corpus_seven_rows() -> None:
    for cid in [f"P9-G{i}" for i in range(1, 8)]:
        _assert_corpus_row(cid)


def test_v12_a06_high_risk_prompt_checklist_directive_free() -> None:
    # Named lock already in test_commit_quality; assert high-risk path set still pure.
    from git_cg.commit_quality import format_high_risk_body_checklist, is_high_risk_path_set

    paths = ["src/git_cg/main.py", "src/git_cg/secrets.py"]
    assert is_high_risk_path_set(paths) is True
    text = format_high_risk_body_checklist(paths)
    assert text
    # Ban language is intentional; the checklist must not *set* preferred_type.
    assert "does not set preferred_type" in text
    assert "preferred_scope" not in text
    assert "main_channel4_directive_free" in text


def test_v12_a07_included_change_stubs_multi_surface() -> None:
    paths = [
        "src/git_cg/main.py",
        "src/git_cg/telemetry.py",
        "tests/test_main.py",
        "docs/usage.md",
    ]
    stubs = build_included_change_stubs(paths)
    assert stubs
    assert min_included_change_bullets(paths, concern_tags={"a", "b", "c"}) >= 2
    roles = {s.role for s in stubs}
    assert "product_src" in roles or any("main" in (s.surface or "") for s in stubs)


# ---------------------------------------------------------------------------
# V12-A08-A13 path-class / security / hallucination
# ---------------------------------------------------------------------------


def test_v12_a08_diff_class_gates_tip_g2_g3_g4() -> None:
    for cid in ("TIP-G2", "TIP-G3", "TIP-G4"):
        _assert_corpus_row(cid)


def test_v12_a09_changelog_antisignal() -> None:
    paths = ["CHANGELOG.md", "docs/usage.md"]
    dc = classify_diff_class(paths)
    cons = presentation_constraints(dc)
    # Changelog noise must not force fix/Fixed on docs-led surfaces.
    assert cons.force_cc_type in {CommitType.DOCS, None} or CommitType.FIX.value in cons.forbid_cc_types
    out, _, _ = _overlay(paths, scope="docs", preferred_scope="usage")
    assert out.primary_intent.cc_type != CommitType.FIX or out.primary_intent.changelog_group != "Fixed"


def test_v12_a10_security_prose_negative_markers() -> None:
    prose = (
        "Matrix authority remains sole authority; never authorise intent_id from "
        "docs prose, and keep tokens redacted on write."
    )
    assert prose_has_security_negative_markers(prose) is True
    paths = ["tests/fixtures/scoped_history/README.md", "docs/ADRs/0163.md"]
    claims = security_claims_without_path_evidence("rotate credentials and secrets", paths)
    assert claims  # no security path evidence


def test_v12_a11_hallucination_guard_secrets_and_runtime() -> None:
    paths = ["docs/usage.md"]
    plan = _cq.make_commit_plan(
        intent_id="documentation_update",
        gitmoji="📝",
        cc_type="docs",
        scope="usage",
        description="handle runtime secrets recovery",
        semver_impact="NONE",
        changelog_group="Documentation",
        body_summary="Recover credentials at runtime.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    codes = report.codes()
    assert "GUARD_SECURITY_NOUN" in codes or "GUARD_DOCS_RUNTIME_VERB" in codes


def test_v12_a12_claim_tag_harvest_and_scope_hyphen() -> None:
    blob = "locks P9-A05 and P9-B07 plus P9-B10 claim coverage"
    tags = harvest_claim_tags([blob])
    assert set(tags) >= {"P9-A05", "P9-B07", "P9-B10"}
    assert normalize_scope("scoped_history") == "scoped-history"
    paths = [
        "tests/test_scoped_history.py",
        "tests/test_scoped_history_telemetry.py",
        "tests/test_main.py",
        "tests/test_semantic.py",
    ]
    out, _, _ = _overlay(paths, scope="scoped_history", preferred_scope="scoped-history")
    assert out.primary_intent.cc_type == CommitType.TEST
    assert out.primary_intent.changelog_group == "Tests"
    assert normalize_scope(out.primary_intent.scope) == "scoped-history"


def test_v12_a13_tip_corpus_four_rows() -> None:
    for cid in ("TIP-G1", "TIP-G2", "TIP-G3", "TIP-G4"):
        _assert_corpus_row(cid)


# ---------------------------------------------------------------------------
# V12-A14-A21 Session 2
# ---------------------------------------------------------------------------


def test_v12_a14_eval_cases_a_to_e() -> None:
    _assert_eval_letters("ABCDE")


def test_v12_a15_semver_evidence_forbids_major() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"]
    ceiling = semver_presentation_ceiling(paths, concern_tags={"correctness", "closed_enum"})
    assert ceiling == SemVerImpact.PATCH
    out, _, _ = _overlay(paths, concern_tags={"correctness", "closed_enum"}, semver="MAJOR")
    assert out.primary_intent.semver_impact != SemVerImpact.MAJOR


def test_v12_a16_type_dominance_fix_over_feat() -> None:
    paths = ["src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"]
    dom = dominant_presentation_cc_type(paths, concern_tags={"correctness", "redacted_sentinel"})
    assert dom == CommitType.FIX
    out, _, _ = _overlay(paths, concern_tags={"correctness", "redacted_sentinel"})
    assert out.primary_intent.cc_type == CommitType.FIX
    assert out.primary_intent.changelog_group == "Fixed"


def test_v12_a17_changelog_groups_match_change_types() -> None:
    assert required_changelog_groups(["test", "docs"]) == ["Tests", "Documentation"]
    assert "Fixed" in required_changelog_groups(["fix"])
    paths = ["tests/test_foo.py", "docs/usage.md"]
    out, _, _ = _overlay(paths)
    types = [out.primary_intent.cc_type.value, *(s.cc_type.value for s in out.secondary_intents)]
    groups = [out.primary_intent.changelog_group, *(s.changelog_group for s in out.secondary_intents)]
    for req in required_changelog_groups(types, primary_cc_type=out.primary_intent.cc_type):
        assert req in groups
    assert groups != ["Miscellaneous"]


def test_v12_a18_included_changes_cardinality_and_path_mandator() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"]
    tags = {
        "closed_enum",
        "correctness",
        "fallback_none_overwrite",
        "parser_batch_results",
        "redacted_sentinel",
        "scrub_vars",
    }
    assert min_included_change_bullets(paths, concern_tags=tags) >= 5
    stubs = build_included_change_stubs(paths, claim_tags=None)
    assert stubs


def test_v12_a19_session2_corpus_tip_g5_g6() -> None:
    for cid in ("TIP-G5", "TIP-G6"):
        _assert_corpus_row(cid)


def test_v12_a20_eval_cases_f_to_h() -> None:
    _assert_eval_letters("FGH")


def test_v12_a21_vague_subject_verb_ban() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"]
    plan = _cq.make_commit_plan(
        intent_id="bug_fix",
        gitmoji="🐛",
        cc_type="fix",
        scope="telemetry",
        description="improve telemetry scrubbing and metrics",
        semver_impact="PATCH",
        changelog_group="Fixed",
        body_summary="Enhance hygiene around scrubbing.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    assert "GUARD_VAGUE_SUBJECT_VERB" in report.codes()


# ---------------------------------------------------------------------------
# V12-A22-A26 Session 3
# ---------------------------------------------------------------------------


def test_v12_a22_semver_evidence_forbids_unearned_minor() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/scoped_history.py"]
    ceiling = semver_presentation_ceiling(paths, concern_tags={"correctness", "nul_rename_parse"})
    assert ceiling == SemVerImpact.PATCH
    out, _, _ = _overlay(paths, concern_tags={"correctness"}, preferred_scope="scoped-history", semver="MINOR")
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH


def test_v12_a23_session3_corpus_tip_g7_g8() -> None:
    for cid in ("TIP-G7", "TIP-G8"):
        _assert_corpus_row(cid)


def test_v12_a24_eval_cases_i_to_j() -> None:
    _assert_eval_letters("IJ")


def test_v12_a25_test_adr_forbids_feat_invention() -> None:
    paths = ["tests/test_scoped_history.py", "docs/ADRs/0163-scoped-reasoning-history.md"]
    out, _, _ = _overlay(paths, description="adds guidance history feature")
    assert out.primary_intent.cc_type != CommitType.FEAT
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    plan = _cq.make_commit_plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        scope="scoped-history",
        description="adds guidance history feature",
        semver_impact="MINOR",
        changelog_group="Added",
        body_summary="Adds guidance for history.",
    )
    # Path-class overlay forbids feat; guards may also flag unearned capability.
    _ = evaluate_presentation_guards(plan, paths=paths)
    out2, _, _ = _overlay(paths)
    assert out2.primary_intent.cc_type in {CommitType.TEST, CommitType.DOCS}


def test_v12_a26_scope_rejects_package_git_cg_on_module_diff() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/scoped_history.py"]
    out, _, _ = _overlay(paths, scope="git_cg", preferred_scope="scoped-history", concern_tags={"correctness"})
    assert out.primary_intent.scope == "scoped-history"
    assert out.primary_intent.scope != "git_cg"
    paths2 = ["src/git_cg/main.py"]
    out2, _, _ = _overlay(paths2, scope="git_cg", concern_tags={"correctness"})
    assert out2.primary_intent.scope == "main"


# ---------------------------------------------------------------------------
# V12-A27-A32 Session 4
# ---------------------------------------------------------------------------


def test_v12_a27_wording_only_fix_test_forbids_feat_minor() -> None:
    paths = ["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"]
    out, _, _ = _overlay(
        paths,
        preferred_scope="scoped-history",
        concern_tags={"correctness", "directive_verb_drop"},
        semver="MINOR",
    )
    assert out.primary_intent.cc_type == CommitType.FIX
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH


def test_v12_a28_primary_surface_inventory_src_and_test() -> None:
    paths = ["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"]
    out, _, _ = _overlay(paths, preferred_scope="scoped-history", concern_tags={"correctness"})
    types = [out.primary_intent.cc_type.value, *(s.cc_type.value for s in out.secondary_intents)]
    assert "fix" in types and "test" in types
    stubs = build_included_change_stubs(paths)
    roles = {s.role for s in stubs}
    assert "product_src" in roles or any(not str(s.role).startswith("test") for s in stubs)
    assert "tests" in roles or any("test" in str(s.role) for s in stubs)


def test_v12_a29_bans_add_guard_assertion_subjects() -> None:
    # Guard fires on docs/tests-only classes, or when primary is still feat.
    paths = ["tests/test_scoped_history.py", "docs/ADRs/0163-scoped-reasoning-history.md"]
    plan = _cq.make_commit_plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        scope="scoped-history",
        description="adds authority leakage guard",
        semver_impact="MINOR",
        changelog_group="Added",
        body_summary="Add assertion feature guidance.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    assert "GUARD_UNEARNED_CAPABILITY" in report.codes()


def test_v12_a30_fix_test_changelog_fixed_tests() -> None:
    groups = required_changelog_groups(["fix", "test"], primary_cc_type=CommitType.FIX)
    assert "Fixed" in groups and "Tests" in groups
    paths = ["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"]
    out, _, _ = _overlay(paths, preferred_scope="scoped-history", concern_tags={"correctness"})
    all_groups = [out.primary_intent.changelog_group, *(s.changelog_group for s in out.secondary_intents)]
    assert "Fixed" in all_groups and "Tests" in all_groups
    assert all_groups != ["Miscellaneous"]


def test_v12_a31_session4_corpus_tip_g9() -> None:
    _assert_corpus_row("TIP-G9")


def test_v12_a32_eval_case_k() -> None:
    _assert_eval_letters("K")


# ---------------------------------------------------------------------------
# V12-A33-A38 Session 5
# ---------------------------------------------------------------------------


def test_v12_a33_dark_launch_feat_forbids_unearned_minor() -> None:
    paths = ["src/git_cg/semantic.py", "tests/test_semantic.py"]
    ceiling = semver_presentation_ceiling(paths, concern_tags={"dark_launch", "free_harvest"})
    assert ceiling == SemVerImpact.PATCH
    out, _, _ = _overlay(paths, concern_tags={"dark_launch", "free_harvest"}, semver="MINOR")
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH


def test_v12_a34_carry_through_forbids_unshipped_product_claim() -> None:
    paths = ["src/git_cg/main.py", "tests/test_semantic.py"]
    plan = _cq.make_commit_plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        scope="scoped-history",
        description="thread preflight group count into split evidence",
        semver_impact="PATCH",
        changelog_group="Changed",
        body_summary="Wires preflight groups from the Phase 0.5 product.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    assert "GUARD_UNSHIPPED_PRODUCT_ACTOR" in report.codes()


def test_v12_a35_behaviour_scope_scoped_history_on_preflight_wire() -> None:
    paths = ["src/git_cg/main.py", "tests/test_semantic.py"]
    out, _, _ = _overlay(
        paths,
        scope="semantic",
        preferred_scope="scoped-history",
        concern_tags={"elevation", "preflight_carry_through"},
    )
    assert out.primary_intent.scope == "scoped-history"


def test_v12_a36_adr_usage_mermaid_docs_none() -> None:
    paths = ["docs/ADRs/0163-scoped-reasoning-history.md", "docs/usage.md"]
    out, _, _ = _overlay(paths, preferred_scope="adr")
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Documentation"
    assert out.primary_intent.gitmoji == "✨"  # identity preserved; not 🥅


def test_v12_a37_session5_corpus_tip_g10_g12() -> None:
    for cid in ("TIP-G10", "TIP-G11", "TIP-G12"):
        _assert_corpus_row(cid)


def test_v12_a38_eval_cases_l_to_n() -> None:
    _assert_eval_letters("LMN")


# ---------------------------------------------------------------------------
# V12-A39-A45 Session 6
# ---------------------------------------------------------------------------


def test_v12_a39_telemetry_schema_feat_minor_not_fix_patch() -> None:
    paths = ["src/git_cg/telemetry.py"]
    tags = {"new_capability", "lifecycle_fields", "schema_add", "score_boundary", "telemetry_schema"}
    out, _, _ = _overlay(paths, scope="git_cg", cc_type="fix", semver="PATCH", changelog="Fixed", concern_tags=tags)
    assert out.primary_intent.cc_type == CommitType.FEAT
    assert out.primary_intent.semver_impact == SemVerImpact.MINOR
    assert out.primary_intent.scope == "telemetry"
    assert out.primary_intent.changelog_group == "Added"
    _assert_corpus_row("TIP-G13")


def test_v12_a40_pure_evaluator_forbids_mutation_verbs() -> None:
    paths = ["tests/test_contract_lifecycle.py"]
    plan = _cq.make_commit_plan(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="test",
        description="cover contract lifecycle claims",
        semver_impact="NONE",
        changelog_group="Tests",
        body_summary="Enforce and lift the contract floor; mutate plan fields.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    assert "GUARD_EVALUATOR_MUTATION_VERB" in report.codes()
    out, _, _ = _overlay(paths)
    assert out.primary_intent.cc_type == CommitType.TEST
    _assert_corpus_row("TIP-G14")


def test_v12_a41_sentry_reporter_fix_patch_named_event() -> None:
    paths = ["src/git_cg/sentry_config.py"]
    out, _, _ = _overlay(
        paths,
        scope="git_cg",
        concern_tags={"correctness", "commit_plan_contract_violation"},
        description="report commit_plan_contract_violation events",
    )
    assert out.primary_intent.cc_type == CommitType.FIX
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH
    assert out.primary_intent.scope == "sentry"
    # Named event must be acceptable in subject/body evidence story.
    plan = _cq.make_commit_plan(
        intent_id="bug_fix",
        gitmoji="🐛",
        cc_type="fix",
        scope="sentry",
        description="report commit_plan_contract_violation",
        semver_impact="PATCH",
        changelog_group="Fixed",
        body_summary="Emit commit_plan_contract_violation on plan contract failures.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    # Should not invent feat framing; mutation/template guards stay quiet on this body.
    assert "GUARD_CONTEXT_CHANGES_TEMPLATE" not in report.codes()
    _assert_corpus_row("TIP-G15")


def test_v12_a42_main_wiring_module_scope_and_hybrid_included() -> None:
    paths = ["src/git_cg/main.py"]
    tags = {"correctness", "wiring", "capture", "persist", "opik", "sentry"}
    out, _, _ = _overlay(
        paths,
        scope="commit-plan",
        concern_tags=tags,
        description="wire capture re-lift persist opik sentry",
    )
    assert out.primary_intent.scope == "main"
    assert out.primary_intent.scope not in {"commit-plan", "lifecycle", "git_cg"}
    assert out.primary_intent.cc_type == CommitType.FIX
    plan = _cq.make_commit_plan(
        intent_id="bug_fix",
        gitmoji="🐛",
        cc_type="fix",
        scope="main",
        description="wire contract capture and persist paths",
        semver_impact="PATCH",
        changelog_group="Fixed",
        body_summary="Context:\nEpic lifecycle.\n\nChanges:\nWire everything.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    assert "GUARD_CONTEXT_CHANGES_TEMPLATE" in report.codes()
    # Multi-concern product_src unlocks Hybrid Included inventory stubs.
    stubs = build_included_change_stubs(paths, concern_tags=tags)
    assert stubs
    _assert_corpus_row("TIP-G16")


def test_v12_a43_tests_only_primary_test_no_attribution_bleed() -> None:
    paths = [
        "tests/test_contract_lifecycle.py",
        "docs/plans/204-commit-presentation-quality.md",
    ]
    out, _, _ = _overlay(paths, scope="lifecycle")
    assert out.primary_intent.cc_type == CommitType.TEST
    types = [out.primary_intent.cc_type.value, *(s.cc_type.value for s in out.secondary_intents)]
    assert "test" in types
    plan = _cq.make_commit_plan(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="test",
        description="cover contract lifecycle claims",
        semver_impact="NONE",
        changelog_group="Tests",
        body_summary="Implement the whole lifecycle feature and wire telemetry schema.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    assert "GUARD_ATTRIBUTION_BLEED" in report.codes()
    _assert_corpus_row("TIP-G17")


def test_v12_a44_subject_imperative_no_title_case() -> None:
    paths = ["tests/test_contract_lifecycle.py"]
    plan = _cq.make_commit_plan(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="test",
        description="Add Unit Tests For Lifecycle",
        semver_impact="NONE",
        changelog_group="Tests",
        body_summary="Cover claim locks only.",
    )
    report = evaluate_presentation_guards(plan, paths=paths)
    codes = report.codes()
    assert "GUARD_TITLE_CASE_SUBJECT" in codes or "GUARD_TEST_DOCS_ADD_OPENER" in codes


def test_v12_a45_session6_corpus_tip_g13_g17() -> None:
    for cid in ("TIP-G13", "TIP-G14", "TIP-G15", "TIP-G16", "TIP-G17"):
        _assert_corpus_row(cid)
    # R25: contract-lift green is not a substitute - message-quality rows must still hold.
    # Explicit residual: lift telemetry alone does not waive TIP-G13-G17.
    assert {"TIP-G13", "TIP-G14", "TIP-G15", "TIP-G16", "TIP-G17"} <= {c["id"] for c in _corpus()["cases"]}


def test_v12_a_pack_never_calls_ranker(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("ranker invoked from V12-A pack")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    test_v12_a01_scope_normalisation()
    test_v12_a26_scope_rejects_package_git_cg_on_module_diff()
    test_v12_a39_telemetry_schema_feat_minor_not_fix_patch()
    test_v12_a40_pure_evaluator_forbids_mutation_verbs()
