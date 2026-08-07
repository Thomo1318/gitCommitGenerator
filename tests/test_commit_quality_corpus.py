"""Issue #204 Slice 3 + Slice 9 - pure presentation quality corpus.

Freezes path-class priors, constraints, ceilings, and apply_presentation_overlay
against pinned goldens (P9-G* + TIP-G* + S9-E/S9-H). Slice 9 adds the A-N
ordered gate characterisation harness (eval_an.json) with no live LLM and no
rank_commit_intents.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import conftest as _cq_factories
import pytest

from git_cg.commit_quality import (
    SLICE9_GATE_ORDER,
    apply_presentation_overlay,
    build_included_change_stubs,
    classify_diff_class,
    derive_trailer_priors,
    dominant_presentation_cc_type,
    evaluate_presentation_gates,
    is_high_risk_path_set,
    min_included_change_bullets,
    presentation_constraints,
    semver_presentation_ceiling,
    slice9_letter_map,
)
from git_cg.scope_canon import normalize_scope
from git_cg.sop import load_sop

# Shared D24 factories live in tests/conftest.py (pytest loads the module on the path).
make_commit_plan = _cq_factories.make_commit_plan
make_commit_intent = _cq_factories.make_commit_intent
make_diff_signals = _cq_factories.make_diff_signals

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "commit_quality"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"
GOLDENS_PATH = FIXTURE_DIR / "goldens.json"
EVAL_AN_PATH = FIXTURE_DIR / "eval_an.json"

EXPECTED_SOP_SHA256 = "7c746456c2da5f23d52d29f29538e6509580ac6cfdde9a92c991ffe044a454e7"
EXPECTED_SOP_ROW_COUNT = 75


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sop_matrix_sha256(matrix: list[dict]) -> str:
    payload = json.dumps(matrix, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _ser_enum(value: Any) -> Any:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def _case_map(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case["id"]: case for case in corpus["cases"]}


@pytest.fixture(scope="module")
def sop_matrix() -> list[dict]:
    data = load_sop()
    matrix = data.get("gitmoji_reference_matrix", [])
    assert matrix, "production SOP matrix must be loadable for commit_quality corpus"
    return matrix


@pytest.fixture(scope="module")
def corpus() -> dict[str, Any]:
    assert CORPUS_PATH.is_file(), f"missing corpus fixture: {CORPUS_PATH}"
    return _load_json(CORPUS_PATH)


@pytest.fixture(scope="module")
def goldens() -> dict[str, Any]:
    assert GOLDENS_PATH.is_file(), f"missing goldens fixture: {GOLDENS_PATH}"
    return _load_json(GOLDENS_PATH)


def _corpus_case_ids() -> list[str]:
    return [case["id"] for case in _load_json(CORPUS_PATH)["cases"]]


def test_sop_matrix_pin_matches_live(sop_matrix: list[dict], corpus: dict, goldens: dict) -> None:
    live_hash = _sop_matrix_sha256(sop_matrix)
    live_rows = len(sop_matrix)
    assert live_hash == EXPECTED_SOP_SHA256, f"live SOP SHA-256 drifted: {live_hash} != pinned {EXPECTED_SOP_SHA256}"
    assert live_rows == EXPECTED_SOP_ROW_COUNT
    assert corpus["sop_matrix_sha256"] == live_hash, (
        "corpus sop_matrix_sha256 does not match live matrix — refuse silent rebase"
    )
    assert goldens["sop_matrix_sha256"] == live_hash, (
        "goldens sop_matrix_sha256 does not match live matrix — refuse silent rebase"
    )
    assert corpus["sop_matrix_row_count"] == live_rows
    assert goldens["sop_matrix_row_count"] == live_rows


def test_corpus_and_golden_ids_match(corpus: dict, goldens: dict) -> None:
    corpus_ids = [case["id"] for case in corpus["cases"]]
    golden_ids = list(goldens["cases"].keys())
    assert corpus_ids, "corpus must define cases"
    assert corpus_ids == sorted(corpus_ids, key=corpus_ids.index)
    assert set(corpus_ids) == set(golden_ids)
    assert len(corpus_ids) == len(set(corpus_ids))
    # Exact ordered membership for P9 then TIP families
    assert corpus_ids == [
        "P9-G1",
        "P9-G2",
        "P9-G3",
        "P9-G4",
        "P9-G5",
        "P9-G6",
        "P9-G7",
        "TIP-G1",
        "TIP-G2",
        "TIP-G3",
        "TIP-G4",
        "TIP-G5",
        "TIP-G6",
        "TIP-G7",
        "TIP-G8",
        "TIP-G9",
        "TIP-G10",
        "TIP-G11",
        "TIP-G12",
        "TIP-G13",
        "TIP-G14",
        "TIP-G15",
        "TIP-G16",
        "TIP-G17",
        "S9-E",
        "S9-H",
    ]


def test_tip_g1_claim_tags_and_module_count(corpus: dict) -> None:
    case = _case_map(corpus)["TIP-G1"]
    assert case["claim_tags"] == ["P9-A05", "P9-B07", "P9-B10"]
    test_modules = [p for p in case["staged_paths"] if p.startswith("tests/test_")]
    assert len(test_modules) >= 4
    assert case["must_present"]["claim_tags"] == ["P9-A05", "P9-B07", "P9-B10"]
    assert case["must_present"]["test_module_count_gte"] >= 4


def _compute_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    paths = list(case["staged_paths"])
    tags = set(case.get("concern_tags") or [])
    signals = make_diff_signals(**case["diff_signals_kwargs"])
    dc = classify_diff_class(paths)
    cons = presentation_constraints(dc)
    priors = derive_trailer_priors(paths, signals=signals)
    ceiling = semver_presentation_ceiling(paths, signals, concern_tags=tags)
    dominant = dominant_presentation_cc_type(paths, signals=signals, concern_tags=tags, priors=priors)
    min_bullets = min_included_change_bullets(paths, concern_tags=tags)

    directives = None
    if case.get("preferred_scope"):
        directives = {"preferred_scope": case["preferred_scope"]}

    seed = make_commit_plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        scope=case.get("seed_scope"),
        description="add something big",
        semver_impact="MINOR",
        changelog_group="Added",
        rationale="corpus seed",
        body_summary="corpus seed",
    )
    ranked_intent_id = seed.primary_intent.intent_id
    ranked_gitmoji = seed.primary_intent.gitmoji
    out = apply_presentation_overlay(
        seed,
        paths=paths,
        signals=signals,
        priors=priors,
        constraints=cons,
        concern_tags=tags,
        active_directives=directives,
    )

    overlay_types = [
        out.primary_intent.cc_type.value,
        *(s.cc_type.value for s in out.secondary_intents),
    ]
    overlay_groups = [
        out.primary_intent.changelog_group,
        *(s.changelog_group for s in out.secondary_intents),
    ]
    overlay_scopes = [
        out.primary_intent.scope,
        *(s.scope for s in out.secondary_intents),
    ]

    high_risk = is_high_risk_path_set(paths)

    return {
        "diff_class": {
            "name": dc.name,
            "has_runtime_surface": dc.has_runtime_surface,
            "has_security_path_evidence": dc.has_security_path_evidence,
            "changelog_paths": list(dc.changelog_paths),
            "path_count": len(dc.paths),
        },
        "priors": {
            "cc_type": priors.cc_type.value,
            "semver_impact": priors.semver_impact.value,
            "changelog_group": priors.changelog_group,
            "scope_hint": priors.scope_hint,
            "role": priors.role,
        },
        "constraints": {
            "diff_class": cons.diff_class,
            "force_cc_type": _ser_enum(cons.force_cc_type),
            "force_semver": _ser_enum(cons.force_semver),
            "force_changelog_group": cons.force_changelog_group,
            "force_scope": cons.force_scope,
            "forbid_cc_types": sorted(cons.forbid_cc_types),
            "forbid_semver": sorted(cons.forbid_semver),
            "forbid_security_primary": cons.forbid_security_primary,
            "changelog_antisignal_applied": cons.changelog_antisignal_applied,
            "security_requires_path_evidence": cons.security_requires_path_evidence,
            "notes": list(cons.notes),
        },
        "semver_ceiling": ceiling.value,
        "dominant_cc_type": _ser_enum(dominant),
        "min_included_change_bullets": min_bullets,
        "scope_canon": {
            "scoped_history": normalize_scope("scoped_history"),
            "scoped_hist": normalize_scope("scoped_hist"),
            "main.py": normalize_scope("main.py"),
            "seed_scope": normalize_scope(case.get("seed_scope")),
            "preferred_scope": normalize_scope(case.get("preferred_scope")),
        },
        "overlay": {
            "intent_id": out.primary_intent.intent_id,
            "gitmoji": out.primary_intent.gitmoji,
            "cc_type": out.primary_intent.cc_type.value,
            "scope": out.primary_intent.scope,
            "semver_impact": out.primary_intent.semver_impact.value,
            "changelog_group": out.primary_intent.changelog_group,
            "secondary_intents": [
                {
                    "intent_id": s.intent_id,
                    "cc_type": s.cc_type.value,
                    "scope": s.scope,
                    "semver_impact": s.semver_impact.value,
                    "changelog_group": s.changelog_group,
                }
                for s in out.secondary_intents
            ],
            "types": overlay_types,
            "groups": overlay_groups,
            "scopes": overlay_scopes,
            "preserved_ranked_intent_id": ranked_intent_id,
            "preserved_ranked_gitmoji": ranked_gitmoji,
        },
        "high_risk_path": high_risk,
        "_plan": out,
    }


def _assert_must_present(case: dict[str, Any], snap: dict[str, Any]) -> None:
    mp = case.get("must_present") or {}
    overlay = snap["overlay"]
    priors = snap["priors"]
    constraints = snap["constraints"]

    if "diff_class" in mp:
        assert snap["diff_class"]["name"] == mp["diff_class"], case["id"]
    if "role" in mp:
        assert priors["role"] == mp["role"], case["id"]
    if "cc_type" in mp:
        assert overlay["cc_type"] == mp["cc_type"], case["id"]
    if "semver" in mp:
        assert overlay["semver_impact"] == mp["semver"], case["id"]
    if "semver_ceiling" in mp:
        assert snap["semver_ceiling"] == mp["semver_ceiling"], case["id"]
    if "changelog_group" in mp:
        assert overlay["changelog_group"] == mp["changelog_group"], case["id"]
    if "scope" in mp:
        assert overlay["scope"] == mp["scope"], case["id"]
    if "scope_canon" in mp:
        assert normalize_scope(overlay["scope"]) == mp["scope_canon"], case["id"]
    if "scope_canon_alias" in mp:
        assert normalize_scope(case.get("preferred_scope") or case.get("seed_scope")) == mp["scope_canon_alias"], case[
            "id"
        ]
        assert normalize_scope(overlay["scope"] or "") in {
            mp["scope_canon_alias"],
            normalize_scope(overlay["scope"] or ""),
        }
    if "high_risk_path" in mp:
        assert snap["high_risk_path"] is bool(mp["high_risk_path"]), case["id"]
    if "min_included_change_bullets_gte" in mp:
        assert snap["min_included_change_bullets"] >= int(mp["min_included_change_bullets_gte"]), case["id"]
    if "overlay_types_include" in mp:
        for t in mp["overlay_types_include"]:
            assert t in overlay["types"], (case["id"], t, overlay["types"])
    if "overlay_groups_include" in mp:
        for g in mp["overlay_groups_include"]:
            assert g in overlay["groups"], (case["id"], g, overlay["groups"])
    if "forbid_security_primary" in mp:
        assert constraints["forbid_security_primary"] is True, case["id"]
    if "changelog_antisignal_applied" in mp:
        assert constraints["changelog_antisignal_applied"] is bool(mp["changelog_antisignal_applied"]), case["id"]
    if "claim_tags" in mp:
        assert case.get("claim_tags") == mp["claim_tags"], case["id"]
    if "test_module_count_gte" in mp:
        modules = [p for p in case["staged_paths"] if Path(p).name.startswith("test_")]
        assert len(modules) >= int(mp["test_module_count_gte"]), case["id"]
    if "stub_note_tokens_any" in mp:
        stubs = build_included_change_stubs(
            list(case["staged_paths"]),
            make_diff_signals(**case["diff_signals_kwargs"]),
            concern_tags=set(case.get("concern_tags") or []),
            claim_tags=case.get("claim_tags") or [],
        )
        blob = " ".join(f"{s.note or ''} {s.surface or ''} {s.role or ''}" for s in stubs).lower()
        tokens = [str(t).lower() for t in mp["stub_note_tokens_any"]]
        assert any(tok in blob for tok in tokens), (case["id"], tokens, blob)


def _assert_must_not_present(case: dict[str, Any], snap: dict[str, Any]) -> None:
    mnp = case.get("must_not_present") or {}
    overlay = snap["overlay"]
    constraints = snap["constraints"]

    if "scope" in mnp:
        assert overlay["scope"] not in set(mnp["scope"]), case["id"]
    if "cc_type" in mnp:
        assert overlay["cc_type"] not in set(mnp["cc_type"]), case["id"]
    if "force_cc_type" in mnp:
        assert constraints["force_cc_type"] not in set(mnp["force_cc_type"]), case["id"]
        assert overlay["cc_type"] not in set(mnp["force_cc_type"]), case["id"]
    if "cc_type_forced" in mnp:
        assert overlay["cc_type"] not in set(mnp["cc_type_forced"]), case["id"]
    if "semver" in mnp:
        assert overlay["semver_impact"] not in set(mnp["semver"]), case["id"]
    if "changelog_group" in mnp:
        assert overlay["changelog_group"] not in set(mnp["changelog_group"]), case["id"]
    if "changelog_group_only" in mnp and len(overlay["groups"]) == 1:
        # groups must not be exactly the forbidden singleton set
        assert overlay["groups"][0] not in set(mnp["changelog_group_only"]), case["id"]
    if "diff_class" in mnp:
        assert snap["diff_class"]["name"] not in set(mnp["diff_class"]), case["id"]
    if mnp.get("security_primary"):
        assert constraints["forbid_security_primary"] is True, case["id"]
        assert overlay["changelog_group"].lower() != "security", case["id"]
    if "security_tokens" in mnp:
        blob = json.dumps(overlay).lower()
        for tok in mnp["security_tokens"]:
            assert tok.lower() not in blob, (case["id"], tok)
    if "gitmoji" in mnp:
        assert overlay["gitmoji"] not in set(mnp["gitmoji"]), case["id"]
    if "runtime_verbs" in mnp:
        blob = json.dumps(overlay).lower()
        for verb in mnp["runtime_verbs"]:
            assert verb.lower() not in blob, (case["id"], verb)

    # Session 6 residual markers (guard-level; not overlay snapshot fields).
    if mnp.get("mutation_verbs"):
        from git_cg.commit_quality import evaluate_presentation_guards

        plan = snap.get("_plan")
        if plan is not None:
            paths = list(case["staged_paths"])
            bad = plan.model_copy(
                update={
                    "body_summary": (
                        "Enforce the contract floor, lift the score boundary, and mutate plan fields in the evaluator."
                    )
                }
            )
            report = evaluate_presentation_guards(bad, paths=paths)
            assert "GUARD_EVALUATOR_MUTATION_VERB" in report.codes(), case["id"]
    if mnp.get("body_templates"):
        from git_cg.commit_quality import evaluate_presentation_guards

        plan = snap.get("_plan")
        if plan is not None:
            paths = list(case["staged_paths"])
            bad = plan.model_copy(update={"body_summary": "Context:\nEpic framing.\n\nChanges:\nWire everything."})
            report = evaluate_presentation_guards(bad, paths=paths)
            assert "GUARD_CONTEXT_CHANGES_TEMPLATE" in report.codes(), case["id"]
    if mnp.get("attribution_bleed"):
        from git_cg.commit_quality import evaluate_presentation_guards

        plan = snap.get("_plan")
        if plan is not None:
            paths = list(case["staged_paths"])
            bad = plan.model_copy(
                update={"body_summary": ("Implement the whole lifecycle feature and wire telemetry schema.")}
            )
            report = evaluate_presentation_guards(bad, paths=paths)
            assert "GUARD_ATTRIBUTION_BLEED" in report.codes(), case["id"]


@pytest.mark.parametrize("case_id", _corpus_case_ids())
def test_commit_quality_corpus_case(
    case_id: str,
    corpus: dict,
    goldens: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("rank_commit_intents must not be called from corpus tests")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)

    case = _case_map(corpus)[case_id]
    expected = goldens["cases"][case_id]
    snap = _compute_snapshot(case)
    plan = snap.pop("_plan")

    # Identity lock
    assert snap["overlay"]["intent_id"] == snap["overlay"]["preserved_ranked_intent_id"] == "feature_addition"
    assert snap["overlay"]["gitmoji"] == snap["overlay"]["preserved_ranked_gitmoji"] == "✨"
    assert plan.primary_intent.intent_id == "feature_addition"
    assert plan.primary_intent.gitmoji == "✨"

    # Full golden snapshot (presentation fields)
    comparable = {k: v for k, v in snap.items()}
    assert comparable["diff_class"] == expected["diff_class"], case_id
    assert comparable["priors"] == expected["priors"], case_id
    assert comparable["constraints"] == expected["constraints"], case_id
    assert comparable["semver_ceiling"] == expected["semver_ceiling"], case_id
    assert comparable["dominant_cc_type"] == expected["dominant_cc_type"], case_id
    assert comparable["min_included_change_bullets"] == expected["min_included_change_bullets"], case_id
    assert comparable["scope_canon"] == expected["scope_canon"], case_id
    assert comparable["overlay"] == expected["overlay"], case_id
    assert comparable["high_risk_path"] == expected["high_risk_path"], case_id

    _assert_must_present(case, snap)
    _assert_must_not_present(case, snap)


def test_corpus_helpers_never_call_ranker(monkeypatch: pytest.MonkeyPatch, corpus: dict) -> None:
    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("ranker invoked")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    case = corpus["cases"][0]
    _compute_snapshot(case)


# ---------------------------------------------------------------------------
# Slice 9 - A-N pure ordered-gate characterisation harness
# ---------------------------------------------------------------------------

_GITMOJI_FOR_TYPE = {
    "docs": "📝",
    "test": "✅",
    "fix": "🐛",
    "feat": "✨",
    "chore": "🔧",
    "refactor": "♻️",
    "perf": "⚡",
}
_INTENT_FOR_TYPE = {
    "docs": "documentation_update",
    "test": "tests_update",
    "fix": "bug_fix",
    "feat": "feature_addition",
    "chore": "chore_maintenance",
}


@pytest.fixture(scope="module")
def eval_an() -> dict[str, Any]:
    assert EVAL_AN_PATH.is_file(), f"missing Slice 9 eval fixture: {EVAL_AN_PATH}"
    return _load_json(EVAL_AN_PATH)


def _eval_candidate_ids() -> list[str]:
    return [c["id"] for c in _load_json(EVAL_AN_PATH)["candidates"]]


def _build_eval_plan(plan_fields: dict[str, Any]):
    """Build a deliberately matrix-bypassing candidate plan for pure gate eval."""
    fields = dict(plan_fields)
    included = fields.pop("included_changes", None)
    sec_types = list(fields.pop("secondary_types", None) or [])
    sec_groups = list(fields.pop("secondary_groups", None) or [])
    cc = str(fields.get("cc_type") or "feat")
    primary = make_commit_intent(
        intent_id=fields.get("intent_id") or _INTENT_FOR_TYPE.get(cc, "feature_addition"),
        gitmoji=fields.get("gitmoji") or _GITMOJI_FOR_TYPE.get(cc, "✨"),
        cc_type=cc,
        scope=fields.get("scope"),
        description=fields.get("description", "x"),
        semver_impact=fields.get("semver_impact", "NONE"),
        changelog_group=fields.get("changelog_group", "Miscellaneous"),
        construct=True,
    )
    secondaries = []
    for i, st in enumerate(sec_types):
        st = str(st)
        grp = (
            sec_groups[i]
            if i < len(sec_groups)
            else ("Documentation" if st == "docs" else "Tests" if st == "test" else "Miscellaneous")
        )
        secondaries.append(
            make_commit_intent(
                intent_id=_INTENT_FOR_TYPE.get(st, "feature_addition"),
                gitmoji=_GITMOJI_FOR_TYPE.get(st, "✨"),
                cc_type=st,
                scope=fields.get("scope"),
                description=f"secondary {st}",
                semver_impact=(
                    "NONE" if fields.get("semver_impact") == "NONE" else fields.get("semver_impact", "NONE")
                ),
                changelog_group=grp,
                construct=True,
            )
        )
    plan = make_commit_plan(
        primary=primary,
        secondary_intents=secondaries,
        body_summary=fields.get("body_summary", ""),
        construct=True,
    )
    return plan, included


def test_slice9_letter_map_covers_a_to_n(corpus: dict, eval_an: dict) -> None:
    harness = corpus.get("eval_harness") or {}
    letter_map = slice9_letter_map(harness)
    assert list(letter_map) == [chr(c) for c in range(ord("A"), ord("N") + 1)]
    assert harness.get("gate_order") == list(SLICE9_GATE_ORDER)
    assert eval_an.get("gate_order") == list(SLICE9_GATE_ORDER)
    assert eval_an.get("letter_map") == letter_map
    case_ids = {c["id"] for c in corpus["cases"]}
    for letter, case_id in letter_map.items():
        assert case_id in case_ids, (letter, case_id)
    # Every mapped corpus row carries the letter alias.
    by_id = _case_map(corpus)
    for letter, case_id in letter_map.items():
        letters = by_id[case_id].get("eval_letters") or []
        assert letter in letters, (case_id, letter, letters)


def test_slice9_gap_cases_exist(corpus: dict, goldens: dict) -> None:
    by_id = _case_map(corpus)
    assert "S9-E" in by_id and "S9-H" in by_id
    assert "S9-E" in goldens["cases"] and "S9-H" in goldens["cases"]
    e = by_id["S9-E"]
    h = by_id["S9-H"]
    assert e["must_present"]["cc_type"] == "docs"
    assert e["must_present"]["semver"] == "NONE"
    assert "fix" in (e.get("must_not_present") or {}).get("cc_type", [])
    assert h["must_present"]["cc_type"] == "test"
    assert h["must_present"]["stub_note_tokens_any"] == ["gpg", "signing"]
    # Deterministic stubs must surface signing inventory for H.
    stubs = build_included_change_stubs(list(h["staged_paths"]))
    blob = " ".join(f"{s.note or ''}" for s in stubs).lower()
    assert "gpg" in blob or "signing" in blob


@pytest.mark.parametrize("candidate_id", _eval_candidate_ids())
def test_slice9_eval_an_candidate(
    candidate_id: str,
    corpus: dict,
    eval_an: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("rank_commit_intents must not be called from Slice 9 eval")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)

    cand = next(c for c in eval_an["candidates"] if c["id"] == candidate_id)
    letter = cand["letter"]
    letter_map = slice9_letter_map(corpus.get("eval_harness"))
    case = _case_map(corpus)[letter_map[letter]]
    paths = list(case["staged_paths"])
    signals = make_diff_signals(**case["diff_signals_kwargs"])
    plan, included = _build_eval_plan(cand["plan"])

    req_tokens = None
    mp = case.get("must_present") or {}
    if mp.get("stub_note_tokens_any"):
        req_tokens = list(mp["stub_note_tokens_any"])
    if letter == "H":
        req_tokens = ["gpg", "signing"]

    report = evaluate_presentation_gates(
        plan,
        paths=paths,
        signals=signals,
        concern_tags=set(case.get("concern_tags") or []),
        claim_tags=case.get("claim_tags") or [],
        evidence_text=case.get("evidence_text") or "",
        included_changes=included,
        require_stub_note_tokens=req_tokens,
    )

    # Gate order identity
    assert [g for g, _ in report.gate_status] == list(SLICE9_GATE_ORDER)

    expect = cand["expect"]
    if expect == "pass":
        assert report.passed is True, (candidate_id, report.first_fail_gate, report.codes)
        assert report.first_fail_gate is None
        assert report.codes == ()
        assert all(status == "pass" for _, status in report.gate_status)
    else:
        assert report.passed is False, candidate_id
        assert report.first_fail_gate is not None
        exp_gate = cand.get("expect_fail_gate")
        if exp_gate:
            assert report.first_fail_gate == exp_gate, (
                candidate_id,
                report.first_fail_gate,
                report.codes,
            )
        exp_codes = set(cand.get("expect_fail_codes_any") or [])
        if exp_codes:
            assert exp_codes & set(report.codes), (candidate_id, report.codes, exp_codes)
        # First-fail semantics: earlier gates pass, fail gate is fail, later are skip.
        seen_fail = False
        for gate, status in report.gate_status:
            if not seen_fail:
                if gate == report.first_fail_gate:
                    assert status == "fail", (candidate_id, gate, status)
                    seen_fail = True
                else:
                    assert status == "pass", (candidate_id, gate, status)
            else:
                assert status == "skip", (candidate_id, gate, status)


def test_slice9_eval_helpers_never_call_ranker(
    monkeypatch: pytest.MonkeyPatch,
    corpus: dict,
    eval_an: dict,
) -> None:
    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("ranker invoked from slice9 helpers")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    cand = eval_an["candidates"][0]
    case = _case_map(corpus)[slice9_letter_map(corpus.get("eval_harness"))[cand["letter"]]]
    plan, included = _build_eval_plan(cand["plan"])
    evaluate_presentation_gates(
        plan,
        paths=list(case["staged_paths"]),
        signals=make_diff_signals(**case["diff_signals_kwargs"]),
        included_changes=included,
    )
