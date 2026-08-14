"""Edge-path coverage for git_cg.eval.scoring (S2a offline package).

Targets previously uncovered branches across product bridges, families A/H,
runner recovery paths, result builder polarity, and context projection.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.enums import Authority, Family, Polarity, Source
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring import score_bundle, score_case, score_suite
from git_cg.eval.scoring.context import (
    ScoreContext,
    ScoreContextError,
    project_score_context,
)
from git_cg.eval.scoring.family_a import score_family_a
from git_cg.eval.scoring.family_b import score_family_b
from git_cg.eval.scoring.family_h import score_family_h
from git_cg.eval.scoring.gates import S2A_REQUIRE_BLOCK, compose_gates
from git_cg.eval.scoring.preconditions import evaluate_preconditions
from git_cg.eval.scoring.product_bridges import (
    deterministic_card_from_plan,
    extract_trailers,
    issue_ref_ok,
    known_cc_type,
    known_semver,
    parse_hybrid_header,
    parse_message_to_plan,
    signals_from_context,
)
from git_cg.eval.scoring.result_builder import (
    clear_catalog_index,
    make_score,
    metric_row,
)
from git_cg.eval.scoring.runner import ScoreCaseResult, ScoreSuiteResult
from git_cg.models import CommitPlan

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"

VALID_MSG = (
    "📝 docs(eval): add offline fixture seed\n\n"
    "Refs: #223\n"
    "SemVer-Impact: PATCH\n"
    "Change-Types: docs\n"
    "Changelog-Groups: Documentation\n"
)


def _encoded_bundle(**overrides: Any) -> dict[str, Any]:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = dict(encode_fixture(fx)["bundle"])
    bundle.update(overrides)
    return bundle


def _ctx(**overrides: Any) -> ScoreContext:
    return project_score_context(_encoded_bundle(**overrides))


# ---------------------------------------------------------------------------
# product_bridges
# ---------------------------------------------------------------------------


def test_parse_hybrid_header_empty_and_soft_and_breaking() -> None:
    assert parse_hybrid_header("")["reason"] == "empty_message"
    assert parse_hybrid_header("   \n")["reason"] == "empty_message"

    soft = parse_hybrid_header("feat(eval): missing gitmoji subject\n\nRefs: #1\n")
    assert soft["ok"] is False
    assert soft["soft_parse"] is True
    assert soft["reason"] == "header_shape_mismatch"
    assert soft["cc_type"] == "feat"

    br = parse_hybrid_header("✨ feat(eval)!: break the API\n\nBREAKING CHANGE: gone\n")
    assert br["ok"] is True
    assert br["breaking"] is True
    assert br["soft_parse"] is False


def test_extract_trailers_and_issue_ref_matrix() -> None:
    assert extract_trailers("") == {}
    trailers = extract_trailers("📝 docs(x): s\n\nRefs: #1\nCo-authored-by: A <a@b.c>\nSemVer-Impact: PATCH\n")
    assert trailers["Refs"] == "#1"
    assert trailers["Co-authored-by"] == "A <a@b.c>"

    assert issue_ref_ok({}) == (False, "missing_issue_ref")
    assert issue_ref_ok({"Refs": "225"}) == (True, None)
    assert issue_ref_ok({"Refs": "#225"}) == (True, None)
    assert issue_ref_ok({"Resolves": "nope"})[0] is False
    assert issue_ref_ok({"Null": "#0"}) == (True, None)
    assert issue_ref_ok({"Null": "#1"}) == (False, "null_must_be_zero")
    assert issue_ref_ok({"Fixes": "abc"})[1] == "malformed_issue_ref:Fixes"


def test_known_cc_and_semver() -> None:
    assert known_cc_type("feat") is True
    assert known_cc_type("NOPE") is False
    assert known_cc_type(None) is False
    assert known_cc_type("") is False
    assert known_semver("patch") is True
    assert known_semver("MINOR") is True
    assert known_semver("x") is False
    assert known_semver(None) is False


def test_parse_message_to_plan_normalizes_and_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = parse_message_to_plan(VALID_MSG, rationale="unit")
    assert isinstance(plan, CommitPlan)
    assert plan.rationale == "unit"
    assert plan.primary_intent.cc_type.value == "docs"

    # Empty reverse-parse must fail closed.
    monkeypatch.setattr(
        "git_cg.eval.scoring.product_bridges.reverse_parse_commit_message",
        lambda _msg: {},
    )
    with pytest.raises(ValueError, match="empty plan"):
        parse_message_to_plan("anything")

    # Sparse primary + messy secondary intents.
    monkeypatch.setattr(
        "git_cg.eval.scoring.product_bridges.reverse_parse_commit_message",
        lambda _msg: {
            "primary_intent": {
                "cc_type": "not-a-type",
                "semver_impact": "bogus",
                "description": "",
                "gitmoji": "",
                "changelog_group": "",
                "intent_id": "",
            },
            "secondary_intents": [
                "skip-me",
                {
                    "cc_type": "also-bad",
                    "semver_impact": "??? ",
                    "description": "",
                    "gitmoji": None,
                    "changelog_group": None,
                    "intent_id": None,
                },
            ],
            "split_recommended": True,
            "breaking_change": False,
        },
    )
    sparse = parse_message_to_plan("x")
    assert sparse.primary_intent.cc_type.value == "chore"
    assert sparse.primary_intent.semver_impact.value == "NONE"
    assert sparse.primary_intent.description == "unparsed subject"
    assert sparse.primary_intent.gitmoji == "🔧"
    assert sparse.primary_intent.changelog_group == "Miscellaneous"
    assert sparse.primary_intent.intent_id  # filled by bridge defaults and/or model
    assert len(sparse.secondary_intents) == 1
    sec = sparse.secondary_intents[0]
    assert sec.cc_type.value == "chore"
    assert sec.semver_impact.value == "NONE"
    assert sec.description == "secondary"
    assert sec.gitmoji == "🔧"
    assert sec.intent_id
    assert sparse.split_recommended is True


def test_signals_from_context_gates_summary_and_files() -> None:
    docs = signals_from_context(path_class_gate="docs_only", generation_task_input=None)
    assert docs.only_docs is True
    assert docs.files == ["docs/eval/README.md"]

    tests = signals_from_context(path_class_gate="tests_only", generation_task_input=None)
    assert tests.only_tests is True
    assert tests.files[0].startswith("tests/")

    fixtures = signals_from_context(path_class_gate="fixtures_only", generation_task_input=None)
    assert fixtures.only_fixtures is True
    assert fixtures.touches_tests is True

    product = signals_from_context(path_class_gate="product_src", generation_task_input=None)
    assert product.files == ["src/git_cg/commit_quality.py"]

    # Explicit files must not be replaced by gate defaults.
    custom = signals_from_context(
        path_class_gate="docs_only",
        generation_task_input=None,
        files=["docs/custom.md"],
    )
    assert custom.files == ["docs/custom.md"]

    # Summary-derived flags when gate empty.
    summary = signals_from_context(
        path_class_gate=None,
        generation_task_input={"diff_summary": "update docs and test fixtures"},
    )
    assert summary.touches_docs is True
    assert summary.touches_tests is True

    # Gate from GTI when path_class_gate omitted.
    via_gti = signals_from_context(
        path_class_gate=None,
        generation_task_input={"path_class_gate": "docs"},
    )
    assert via_gti.only_docs is True


def test_deterministic_card_from_plan_dict_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = parse_message_to_plan(VALID_MSG)

    class DumpCard:
        def model_dump(self) -> dict[str, Any]:
            """Stub card via ``model_dump`` path."""
            return {"header_length_ok": True, "via": "model_dump"}

    monkeypatch.setattr(
        "git_cg.eval.scoring.product_bridges.run_deterministic_checks",
        lambda _plan: DumpCard(),
    )
    assert deterministic_card_from_plan(plan)["via"] == "model_dump"

    ns = SimpleNamespace(
        header_length_ok=True,
        description_length_ok=False,
        type_valid=True,
        _private=1,
    )
    monkeypatch.setattr(
        "git_cg.eval.scoring.product_bridges.run_deterministic_checks",
        lambda _plan: ns,
    )
    dumped = deterministic_card_from_plan(plan)
    assert dumped["header_length_ok"] is True
    assert "_private" not in dumped

    class AttrOnly:
        header_length_ok = True
        description_length_ok = True
        type_valid = False

        # no __dict__ at instance level for getattr path — use object without __dict__
        __slots__ = ()

    monkeypatch.setattr(
        "git_cg.eval.scoring.product_bridges.run_deterministic_checks",
        lambda _plan: AttrOnly(),
    )
    fb = deterministic_card_from_plan(plan)
    assert fb == {
        "header_length_ok": True,
        "description_length_ok": True,
        "type_valid": False,
    }


# ---------------------------------------------------------------------------
# family_a
# ---------------------------------------------------------------------------


def test_family_a_schema_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx()

    def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("schema exploded")

    monkeypatch.setattr("git_cg.eval.scoring.family_a.validate_instance", _boom)
    by = {s.metric_id: s for s in score_family_a(ctx)}
    assert by["a.bundle_schema_valid"].passed is False
    assert "RuntimeError" in str((by["a.bundle_schema_valid"].evidence or {}).get("errors"))


def test_family_a_binding_and_bytes_and_order_edges() -> None:
    # unbound final_accept artifact is fake-bound
    ctx = _ctx(
        bound=False,
        unbound_reason="synthetic",
        artifact_class="final_accept",
        provenance_label="fixture",
    )
    by = {s.metric_id: s for s in score_family_a(ctx)}
    assert by["a.binding_unbound_explicit"].passed is False
    assert "unbound_final_accept" in (by["a.binding_unbound_explicit"].reason or "")

    # provenance_label final_accept also fake-bound
    ctx2 = _ctx(
        bound=False,
        unbound_reason="synthetic",
        artifact_class="fixture_expected",
        provenance_label="final_accept",
    )
    # provenance is read from bundle; ensure override lands on bundle
    b = dict(ctx2.bundle)
    b["bound"] = False
    b["unbound_reason"] = "synthetic"
    b["artifact_class"] = "fixture_expected"
    b["provenance_label"] = "final_accept"
    ctx2 = project_score_context(b)
    by2 = {s.metric_id: s for s in score_family_a(ctx2)}
    assert by2["a.binding_unbound_explicit"].passed is False
    assert "unbound_final_accept_provenance" in (by2["a.binding_unbound_explicit"].reason or "")

    # bound incomplete: wrong artifact + empty final
    b3 = _encoded_bundle()
    b3["bound"] = True
    b3["unbound_reason"] = None
    b3.pop("unbound_reason", None)
    b3["artifact_class"] = "fixture_expected"
    b3["final_message"] = ""
    b3.pop("final_message_sha256", None)
    ctx3 = project_score_context(b3)
    by3 = {s.metric_id: s for s in score_family_a(ctx3)}
    assert by3["a.binding_complete"].passed is False
    missing = (by3["a.binding_complete"].evidence or {}).get("missing_fields") or []
    assert "final_message" in missing
    assert "artifact_class!=final_accept" in missing

    # bound complete path
    b4 = _encoded_bundle()
    b4["bound"] = True
    b4["unbound_reason"] = None
    b4.pop("unbound_reason", None)
    b4["artifact_class"] = "final_accept"
    ctx4 = project_score_context(b4)
    by4 = {s.metric_id: s for s in score_family_a(ctx4)}
    assert by4["a.binding_complete"].passed is True

    # hash mismatch → unstable bytes
    b5 = _encoded_bundle()
    b5["final_message_sha256"] = "0" * 64
    ctx5 = project_score_context(b5)
    # project_score_context recomputes sha; force mismatch on context via replace
    ctx5_bad = ScoreContext(
        case_id=ctx5.case_id,
        bundle=ctx5.bundle,
        suite=ctx5.suite,
        final_message=ctx5.final_message,
        final_message_sha256="deadbeef",
        artifact_class=ctx5.artifact_class,
        bound=ctx5.bound,
        unbound_reason=ctx5.unbound_reason,
        schema_pack=ctx5.schema_pack,
        metric_catalog=ctx5.metric_catalog,
        expected_final_message=ctx5.expected_final_message,
        expected_gold_codes=ctx5.expected_gold_codes,
        failure_ids=ctx5.failure_ids,
        path_class_gate=ctx5.path_class_gate,
        generation_task_input=ctx5.generation_task_input,
        product_card=ctx5.product_card,
        scored_target=ctx5.scored_target,
        meta=ctx5.meta,
        warnings=ctx5.warnings,
    )
    by5 = {s.metric_id: s for s in score_family_a(ctx5_bad)}
    assert by5["a.final_bytes_stable"].passed is False

    # wrong score target order: product_card while final_message present
    ctx6 = ScoreContext(
        case_id=ctx5.case_id,
        bundle=ctx5.bundle,
        suite=None,
        final_message=ctx5.final_message,
        final_message_sha256=ctx5.final_message_sha256,
        artifact_class=ctx5.artifact_class,
        bound=False,
        unbound_reason="x",
        schema_pack=ctx5.schema_pack,
        metric_catalog=ctx5.metric_catalog,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={"k": 1},
        scored_target="product_card",
    )
    by6 = {s.metric_id: s for s in score_family_a(ctx6)}
    assert by6["a.scored_target_order_ok"].passed is False


# ---------------------------------------------------------------------------
# family_h
# ---------------------------------------------------------------------------


def test_family_h_pin_envelope_fanout_and_card_match() -> None:
    ctx = _ctx()
    pre = evaluate_preconditions(ctx)
    base_scores = score_family_a(ctx)

    # pin mismatch on bundle fields
    bad_pin_ctx = ScoreContext(
        case_id=ctx.case_id,
        bundle=ctx.bundle,
        suite=None,
        final_message=ctx.final_message,
        final_message_sha256=ctx.final_message_sha256,
        artifact_class=ctx.artifact_class,
        bound=ctx.bound,
        unbound_reason=ctx.unbound_reason,
        schema_pack="schema@not-real",
        metric_catalog="catalog@not-real",
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=ctx.path_class_gate,
        generation_task_input=ctx.generation_task_input,
        product_card={},
        scored_target=ctx.scored_target,
    )
    h = score_family_h(
        bad_pin_ctx,
        pre=pre,
        family_scores=base_scores,
        suite_snapshot_pin="snap@1",
        offline=True,
        evaluator_errors=["boom"],
    )
    by = {s.metric_id: s for s in h}
    assert by["h.pin_integrity"].passed is False
    assert by["h.evaluator_error_free"].passed is False
    assert by["h.catalog_pinned"].passed is True

    # invalid envelope among family scores
    bad_row = ScoreResultV1(
        metric_id="a.final_message_present",
        polarity=Polarity.PASS_FAIL,
        authority=Authority.LAW,
        source=Source.LOCAL_WRAPPER,
        value=True,
        passed=True,
        family=Family.A,
    )

    # Force invalidation via monkeypatched validate by injecting a mock with bad dump
    class _Bad:
        metric_id = "totally.invalid.metric"
        failure_ids = None
        passed = True

        def model_dump(self, mode: str = "json") -> dict[str, Any]:
            """Stub invalid ScoreResult shape for envelope fail path."""
            return {"metric_id": "not-valid-shape"}

    h2 = score_family_h(
        ctx,
        pre=pre,
        family_scores=[bad_row, _Bad()],  # type: ignore[list-item]
        suite_snapshot_pin="  ",
        offline=True,
    )
    by2 = {s.metric_id: s for s in h2}
    assert by2["h.score_envelope_valid"].passed is False
    assert by2["h.suite_snapshot_pinned"].passed is False

    # fanout when prior rows carry FIND-026
    leak = make_score(
        "b.header_shape",
        False,
        passed=False,
        failure_ids=["FIND-026", "EVAL_INPUT_EMPTY"],
    )
    h3 = score_family_h(
        ctx,
        pre=pre,
        family_scores=[leak],
        suite_snapshot_pin="p",
        offline=True,
    )
    by3 = {s.metric_id: s for s in h3}
    assert by3["h.eval_error_fanout_bounded"].passed is False

    # product card bool + dict mismatch / match
    card_ctx = ScoreContext(
        case_id=ctx.case_id,
        bundle=ctx.bundle,
        suite=None,
        final_message=ctx.final_message,
        final_message_sha256=ctx.final_message_sha256,
        artifact_class=ctx.artifact_class,
        bound=ctx.bound,
        unbound_reason=ctx.unbound_reason,
        schema_pack=ctx.schema_pack,
        metric_catalog=ctx.metric_catalog,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={
            "metrics": {
                "a.final_message_present": False,  # bool mismatch
                "a.artifact_class_known": {"passed": False},  # dict mismatch
                "not.in.scores": True,
            }
        },
        scored_target=ctx.scored_target,
    )
    a_scores = score_family_a(ctx)
    # ensure the two metrics exist and currently pass so mismatch fires
    assert {s.metric_id: s for s in a_scores}["a.final_message_present"].passed is True
    h4 = score_family_h(
        card_ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="p",
        offline=True,
    )
    by4 = {s.metric_id: s for s in h4}
    assert by4["h.online_scores_match_product_card"].passed is False
    assert len((by4["h.online_scores_match_product_card"].evidence or {}).get("mismatches") or []) >= 1

    # matching card
    match_ctx = ScoreContext(
        case_id=ctx.case_id,
        bundle=ctx.bundle,
        suite=None,
        final_message=ctx.final_message,
        final_message_sha256=ctx.final_message_sha256,
        artifact_class=ctx.artifact_class,
        bound=ctx.bound,
        unbound_reason=ctx.unbound_reason,
        schema_pack=ctx.schema_pack,
        metric_catalog=ctx.metric_catalog,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={"results": {"a.final_message_present": True}},
        scored_target=ctx.scored_target,
    )
    h5 = score_family_h(
        match_ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="p",
        offline=True,
    )
    assert {s.metric_id: s for s in h5}["h.online_scores_match_product_card"].passed is True


# ---------------------------------------------------------------------------
# result_builder + gates polarity edges
# ---------------------------------------------------------------------------


def test_result_builder_clear_unknown_and_polarity() -> None:
    clear_catalog_index()
    assert metric_row("a.final_message_present") is not None

    with pytest.raises(KeyError, match="unknown metric_id"):
        make_score("not.a.metric", True)

    # lower_is_better auto passed
    low_ok = make_score("d.strict_fail_set", 0)
    assert low_ok.passed is True
    low_bad = make_score("d.strict_fail_set", 3)
    assert low_bad.passed is False

    # higher_is_better auto passed (catalog C-prime metrics exist)
    hib = "c.evidence_surface_precision"
    assert metric_row(hib) is not None
    hi_ok = make_score(hib, 1.0, name="custom-name", pin_refs=["pin@x"], severity="info")
    assert hi_ok.passed is True
    assert hi_ok.name == "custom-name"
    assert hi_ok.pin_refs == ["pin@x"]
    hi_bad = make_score(hib, 0.0)
    assert hi_bad.passed is False

    # pass_fail default
    pf = make_score("a.final_message_present", True)
    assert pf.passed is True
    pf2 = make_score("a.final_message_present", False)
    assert pf2.passed is False

    clear_catalog_index()


def test_compose_gates_pass_fail_none_treated_failed() -> None:
    rows = []
    for mid in S2A_REQUIRE_BLOCK:
        if mid == "b.header_shape":
            row = make_score(mid, True, passed=None)
            # force None passed after construction via model_copy if available
            row = row.model_copy(update={"passed": None})
            rows.append(row)
        else:
            pol = metric_row(mid) or {}
            if pol.get("polarity") == "lower_is_better":
                rows.append(make_score(mid, 0, passed=True))
            else:
                rows.append(make_score(mid, True, passed=True))
    gates = compose_gates(rows, bound=True)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    assert det.passed is False
    assert "b.header_shape" in (det.evidence or {}).get("failed", [])


# ---------------------------------------------------------------------------
# context projection edges
# ---------------------------------------------------------------------------


def test_project_score_context_validation_and_fallbacks() -> None:
    with pytest.raises(ScoreContextError, match="object"):
        project_score_context("nope")  # type: ignore[arg-type]

    with pytest.raises(ScoreContextError, match="case_id"):
        project_score_context({"final_message": "x"})

    with pytest.raises(ScoreContextError, match="final_message must be a string"):
        project_score_context({"case_id": "c1", "final_message": 123})  # type: ignore[dict-item]

    with pytest.raises(ScoreContextError, match="artifact_class must be a string"):
        project_score_context({"case_id": "c1", "final_message": "x", "artifact_class": 1})

    with pytest.raises(ScoreContextError, match="bound must be a boolean"):
        project_score_context({"case_id": "c1", "final_message": "x", "bound": "yes"})

    with pytest.raises(ScoreContextError, match="unbound_reason must be a string"):
        project_score_context({"case_id": "c1", "final_message": "x", "bound": False, "unbound_reason": 9})

    # sha mismatch warning + score_card alias + non-str path_class
    ctx = project_score_context(
        {
            "case_id": "c1",
            "final_message": "hi",
            "final_message_sha256": "0" * 64,
            "bound": False,
            "score_card": {"a": 1},
            "path_class_gate": 12,
            "generation_task_input": {"diff_summary": "x", "skip": 1},
            "expected_gold_codes": ["G1", 2, "G2"],
            "failure_ids": None,
            "meta": {"k": "v"},
        }
    )
    assert "final_message_sha256_mismatch" in ctx.warnings
    assert ctx.final_message_sha256 is not None
    assert ctx.final_message_sha256 != "0" * 64
    assert ctx.product_card == {"a": 1}
    assert ctx.path_class_gate == "12"
    assert ctx.generation_task_input == {"diff_summary": "x"}
    assert ctx.expected_gold_codes == ("G1", "G2")
    assert ctx.meta == {"k": "v"}

    # input size properties
    assert ctx.input_nonempty is True
    assert ctx.input_size_bytes == len(b"hi")
    assert ctx.input_size_ok is True

    missing = project_score_context({"case_id": "c2", "final_message": "", "bound": False})
    assert missing.scored_target == "missing"
    assert missing.input_nonempty is False
    assert missing.input_size_bytes == 0

    card_only = project_score_context(
        {"case_id": "c3", "final_message": "  ", "bound": False, "product_card": {"z": True}}
    )
    assert card_only.scored_target == "product_card"
    assert card_only.input_nonempty is True
    assert card_only.input_size_bytes > 0


# ---------------------------------------------------------------------------
# runner recovery / aggregation edges
# ---------------------------------------------------------------------------


def test_score_bundle_context_error_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a: Any, **_k: Any) -> None:
        """Force ``ScoreContextError`` from context projection."""
        raise ScoreContextError("projected poorly")

    monkeypatch.setattr("git_cg.eval.scoring.runner.project_score_context", _raise)
    result = score_bundle({"case_id": "reco"}, suite_snapshot_pin="p@1", case_id="reco")
    assert result.case_id == "reco"
    assert result.short_circuit is True
    assert any(e.startswith("context:") for e in result.evaluator_errors)
    assert result.context is not None
    assert result.context.scored_target == "missing"
    assert result.by_id()["h.eval_input_nonempty"].passed is False


def test_score_bundle_generic_context_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a: Any, **_k: Any) -> None:
        """Force generic exception from context projection."""
        raise RuntimeError("unexpected")

    monkeypatch.setattr("git_cg.eval.scoring.runner.project_score_context", _raise)
    result = score_bundle({"case_id": "g"}, suite_snapshot_pin="p", case_id="g")
    assert any("RuntimeError" in e for e in result.evaluator_errors)
    assert result.context is not None
    assert result.context.unbound_reason == "context_projection_failed"


def test_score_bundle_family_exceptions_and_gate_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _encoded_bundle()

    def _boom_a(_ctx: ScoreContext) -> list[ScoreResultV1]:
        raise RuntimeError("a-fail")

    def _boom_b(_ctx: ScoreContext) -> list[ScoreResultV1]:
        raise RuntimeError("b-fail")

    def _boom_d(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("d-fail")

    def _boom_h(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("h-fail")

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_a", _boom_a)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_b", _boom_b)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_d", _boom_d)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_h", _boom_h)

    def _boom_gates(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("gate-fail")

    monkeypatch.setattr("git_cg.eval.scoring.runner.compose_gates", _boom_gates)

    result = score_bundle(b, suite_snapshot_pin="p")
    joined = " ".join(result.evaluator_errors)
    assert "family_a" in joined
    assert "family_b" in joined
    assert "family_d" in joined
    assert "family_h" in joined
    assert "gates" in joined
    # H fallback metric still emitted
    assert "h.eval_input_nonempty" in result.by_id()
    assert result.gates == []


def test_score_bundle_short_circuit_family_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _encoded_bundle()
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    b.pop("product_card", None)
    b.pop("score_card", None)

    def _boom_a(_ctx: ScoreContext) -> list[ScoreResultV1]:
        raise RuntimeError("a-sc")

    def _boom_h(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("h-sc")

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_a", _boom_a)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_h", _boom_h)
    result = score_bundle(b, suite_snapshot_pin="p")
    assert result.short_circuit is True
    assert any("family_a" in e for e in result.evaluator_errors)
    assert any("family_h" in e for e in result.evaluator_errors)
    assert result.by_id()["h.eval_input_nonempty"].passed is False


def test_score_bundle_rewrites_evaluator_error_free_and_drops_bad_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    b = _encoded_bundle()

    good = make_score("h.evaluator_error_free", True, passed=True)

    class _BadEnv:
        metric_id = "ghost.metric"

        def model_dump(self, mode: str = "json") -> dict[str, Any]:
            """Fail envelope dump to exercise evaluator-error rewrite."""
            raise ValueError("cannot dump")

    def _fake_a(_ctx: ScoreContext) -> list[Any]:
        return [good, _BadEnv()]

    def _empty_rest(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        """No-op family stub (empty scores)."""
        return []

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_a", _fake_a)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_b", _empty_rest)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_d", _empty_rest)
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_h", _empty_rest)

    result = score_bundle(b, suite_snapshot_pin="p")
    assert any(e.startswith("envelope:") for e in result.evaluator_errors)
    # evaluator_error_free must be rewritten false because envelope errors exist
    eef = result.by_id().get("h.evaluator_error_free")
    assert eef is not None
    assert eef.passed is False


def test_score_case_result_helpers_and_suite_all_pass() -> None:
    empty = ScoreCaseResult(case_id="x", scores=[], gates=[])
    assert empty.deterministic_pass is None
    assert empty.by_id() == {}

    gate = make_score("gate.deterministic_pass", True, passed=True)
    ok = ScoreCaseResult(case_id="y", gates=[gate])
    bad = ScoreCaseResult(case_id="z", gates=[make_score("gate.deterministic_pass", False, passed=False)])
    suite = ScoreSuiteResult(suite_id="s", cases=[ok, bad])
    assert suite.all_pass is False
    suite_ok = ScoreSuiteResult(suite_id="s", cases=[ok])
    assert suite_ok.all_pass is True


def test_score_case_and_suite_require_block_override(tmp_path: Path) -> None:
    # score_case smoke with offline + require_block subset still runs
    mini_req = (
        "a.final_message_present",
        "h.eval_input_nonempty",
        "h.offline_complete",
        "h.catalog_pinned",
        "h.suite_snapshot_pinned",
        "h.score_envelope_valid",
        "h.evaluator_error_free",
        "h.eval_error_fanout_bounded",
        "h.pin_integrity",
    )
    case = score_case(
        VALID,
        suite_snapshot_pin="case-pin",
        require_block=mini_req,
        offline=True,
        suite_id="cm-eval-fixtures-core",
    )
    assert case.case_id == "seed-v1-valid-fixture"
    assert case.suite_snapshot_pin == "case-pin"
    assert case.by_id()["a.final_message_present"].passed is True

    # suite metrics.require_block path via identical suite_path membership
    core_path = FIXTURE_ROOT / "suites" / "cm-eval-fixtures-core.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    overridden = dict(core)
    overridden["metrics"] = {"require_block": list(mini_req)}
    # Keep case_ids identical so snapshot pin guard accepts suite_path
    path = tmp_path / "core-req.json"
    path.write_text(json.dumps(overridden, indent=2) + "\n", encoding="utf-8")
    suite = score_suite(
        "cm-eval-fixtures-core",
        fixture_root=FIXTURE_ROOT,
        suite_path=path,
    )
    assert suite.require_block == tuple(mini_req)
    assert suite.suite_snapshot_pin
    assert len(suite.cases) == 3
    # explicit require_block arg wins over suite metrics
    suite2 = score_suite(
        "cm-eval-fixtures-core",
        fixture_root=FIXTURE_ROOT,
        require_block=("a.final_message_present",),
    )
    assert suite2.require_block == ("a.final_message_present",)


def test_family_b_scope_illegal_and_empty_message() -> None:
    # scope with illegal characters via soft path still exercises scope_shape fail
    # Direct header with bad scope that still matches hybrid regex is hard; force via monkeypatch
    msg = VALID_MSG
    b = _encoded_bundle(final_message=msg)
    b.pop("final_message_sha256", None)
    ctx = project_score_context(b)

    real_parse = parse_hybrid_header

    def _bad_scope(message: str) -> dict[str, Any]:
        """Hybrid header stub with illegal scope token."""
        h = real_parse(message)
        h["scope"] = "bad scope!!"
        h["ok"] = True
        return h

    import git_cg.eval.scoring.family_b as fb

    original = fb.parse_hybrid_header
    fb.parse_hybrid_header = _bad_scope  # type: ignore[assignment]
    try:
        by = {s.metric_id: s for s in score_family_b(ctx)}
        assert by["b.scope_shape"].passed is False
    finally:
        fb.parse_hybrid_header = original  # type: ignore[assignment]

    # empty message structured envelope false
    b2 = _encoded_bundle(final_message="")
    b2.pop("final_message_sha256", None)
    # avoid short-circuit by giving product card so families can be called directly
    ctx2 = project_score_context({**b2, "final_message": "   "})
    # force empty for family_b only
    ctx_empty = ScoreContext(
        case_id=ctx2.case_id,
        bundle=ctx2.bundle,
        suite=None,
        final_message="",
        final_message_sha256=None,
        artifact_class=ctx2.artifact_class,
        bound=False,
        unbound_reason="x",
        schema_pack=None,
        metric_catalog=None,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={},
        scored_target="missing",
    )
    by2 = {s.metric_id: s for s in score_family_b(ctx_empty)}
    assert by2["b.header_shape"].passed is False
    assert by2["b.structured_envelope"].passed is False


# ---------------------------------------------------------------------------
# Residual branch polish (Codecov patch misses)
# ---------------------------------------------------------------------------


def test_family_b_structured_envelope_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx()

    def _boom(_msg: str, **_k: Any) -> CommitPlan:
        raise RuntimeError("plan-build-failed")

    monkeypatch.setattr("git_cg.eval.scoring.family_b.parse_message_to_plan", _boom)
    by = {s.metric_id: s for s in score_family_b(ctx)}
    assert by["b.structured_envelope"].passed is False
    assert "RuntimeError" in (by["b.structured_envelope"].reason or "")


def test_context_product_card_empty_size_and_helpers() -> None:
    # scored_target product_card with empty card → size 0
    ctx = ScoreContext(
        case_id="c",
        bundle={},
        suite=None,
        final_message=None,
        final_message_sha256=None,
        artifact_class=None,
        bound=False,
        unbound_reason="x",
        schema_pack=None,
        metric_catalog=None,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={},
        scored_target="product_card",
    )
    assert ctx.input_nonempty is False
    assert ctx.input_size_bytes == 0
    assert ctx.input_size_ok is True

    # _as_dict / _str_tuple residual branches via projection inputs
    from git_cg.eval.scoring import context as ctxmod

    assert ctxmod._as_dict(None) is None
    assert ctxmod._as_dict({"a": 1}) == {"a": 1}
    assert ctxmod._as_dict(["not", "mapping"]) is None
    assert ctxmod._str_tuple(None) == ()
    assert ctxmod._str_tuple(["a", "b"]) == ("a", "b")
    assert ctxmod._str_tuple("solo") == ()
    assert ctxmod._str_tuple(b"x") == ()

    # final_message empty keeps provided non-str sha as None path via non-str final_sha
    c2 = project_score_context(
        {
            "case_id": "sha-none",
            "final_message": "",
            "final_message_sha256": 123,
            "bound": False,
            "product_card": {"ok": True},
        }
    )
    assert c2.scored_target == "product_card"
    assert c2.final_message_sha256 is None

    # allow_wrong_artifact skips warning loop path difference
    c3 = project_score_context(
        {
            "case_id": "allow",
            "final_message": "",
            "raw_model_output": "RAW",
            "bound": False,
        },
        allow_wrong_artifact=True,
    )
    assert not any(w.startswith("ignored_wrong_artifact_key:") for w in c3.warnings)


def test_gates_skips_existing_gate_rows() -> None:
    rows = []
    for m in S2A_REQUIRE_BLOCK:
        row_meta = metric_row(m) or {}
        if row_meta.get("polarity") == "lower_is_better":
            rows.append(make_score(m, 0, passed=True))
        elif row_meta.get("polarity") == "higher_is_better":
            rows.append(make_score(m, 1.0, passed=True))
        else:
            rows.append(make_score(m, True, passed=True))
    # Inject a pre-existing gate row and an advisory failure prefix covered by startswith
    rows.append(make_score("gate.deterministic_pass", True, passed=True))
    rows.append(
        ScoreResultV1(
            metric_id="lab.noise",
            polarity=Polarity.PASS_FAIL,
            authority=Authority.ADVISORY,
            source=Source.LANE_C_JUDGE,
            value=False,
            passed=False,
            family=Family.LAB,
        )
    )
    gates = compose_gates(rows, bound=True)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    # deterministic_pass recomputed; true advisory lab.* ignored (S2b: e.* is gate-capable)
    assert det.passed is True
    ignored = (det.evidence or {}).get("ignored_advisory_failures") or []
    assert "lab.noise" in ignored


def test_family_h_card_vals_non_dict_and_dict_match() -> None:
    ctx = _ctx()
    pre = evaluate_preconditions(ctx)
    a_scores = score_family_a(ctx)

    # metrics payload is a list → skip compare loop body
    non_dict_ctx = ScoreContext(
        case_id=ctx.case_id,
        bundle=ctx.bundle,
        suite=None,
        final_message=ctx.final_message,
        final_message_sha256=ctx.final_message_sha256,
        artifact_class=ctx.artifact_class,
        bound=ctx.bound,
        unbound_reason=ctx.unbound_reason,
        schema_pack=ctx.schema_pack,
        metric_catalog=ctx.metric_catalog,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={"metrics": ["not", "a", "dict"]},
        scored_target=ctx.scored_target,
    )
    h = score_family_h(
        non_dict_ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="p",
        offline=True,
    )
    assert {s.metric_id: s for s in h}["h.online_scores_match_product_card"].passed is True

    # dict form with matching passed
    match_ctx = ScoreContext(
        case_id=ctx.case_id,
        bundle=ctx.bundle,
        suite=None,
        final_message=ctx.final_message,
        final_message_sha256=ctx.final_message_sha256,
        artifact_class=ctx.artifact_class,
        bound=ctx.bound,
        unbound_reason=ctx.unbound_reason,
        schema_pack=ctx.schema_pack,
        metric_catalog=ctx.metric_catalog,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={"metrics": {"a.final_message_present": {"passed": True}}},
        scored_target=ctx.scored_target,
    )
    h2 = score_family_h(
        match_ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="p",
        offline=True,
    )
    assert {s.metric_id: s for s in h2}["h.online_scores_match_product_card"].passed is True


def test_family_a_provenance_from_meta_and_stable_without_sha() -> None:
    # provenance via meta when bundle lacks provenance_label
    b = _encoded_bundle()
    b.pop("provenance_label", None)
    b["bound"] = False
    b["unbound_reason"] = "synthetic"
    b["meta"] = {"provenance_label": "final_accept"}
    ctx = project_score_context(b)
    by = {s.metric_id: s for s in score_family_a(ctx)}
    assert by["a.binding_unbound_explicit"].passed is False
    assert "unbound_final_accept_provenance" in (by["a.binding_unbound_explicit"].reason or "")

    # final message present but sha absent → stable remains True (no compare)
    ctx2 = ScoreContext(
        case_id=ctx.case_id,
        bundle=ctx.bundle,
        suite=None,
        final_message="hello",
        final_message_sha256=None,
        artifact_class="fixture_expected",
        bound=False,
        unbound_reason="x",
        schema_pack=None,
        metric_catalog=None,
        expected_final_message=None,
        expected_gold_codes=(),
        failure_ids=(),
        path_class_gate=None,
        generation_task_input=None,
        product_card={},
        scored_target="final_message",
    )
    by2 = {s.metric_id: s for s in score_family_a(ctx2)}
    assert by2["a.final_bytes_stable"].passed is True


def test_runner_h_fallback_make_score_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _encoded_bundle()

    def _boom_h(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("h-down")

    real_make = make_score

    def _flaky_make(metric_id: str, *a: Any, **k: Any):
        """Break ``h.eval_input_nonempty`` emission to cover H fallback error path."""
        if metric_id == "h.eval_input_nonempty":
            raise RuntimeError("cannot emit fallback")
        return real_make(metric_id, *a, **k)

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_h", _boom_h)
    monkeypatch.setattr("git_cg.eval.scoring.runner.make_score", _flaky_make)
    # keep other families minimal
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_a", lambda _c: [])
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_b", lambda _c: [])
    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_d", lambda _c, **_k: [])
    monkeypatch.setattr("git_cg.eval.scoring.runner.compose_gates", lambda *_a, **_k: [])
    result = score_bundle(b, suite_snapshot_pin="p")
    assert any("h_fallback" in e for e in result.evaluator_errors)


def test_parse_message_secondary_already_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Secondary intent fields that are already valid skip normalization branches."""
    monkeypatch.setattr(
        "git_cg.eval.scoring.product_bridges.reverse_parse_commit_message",
        lambda _msg: {
            "primary_intent": {
                "cc_type": "feat",
                "semver_impact": "MINOR",
                "description": "primary",
                "gitmoji": "✨",
                "changelog_group": "Added",
                "intent_id": "feature_addition",
                "scope": "eval",
            },
            "secondary_intents": [
                {
                    "cc_type": "docs",
                    "semver_impact": "PATCH",
                    "description": "secondary docs",
                    "gitmoji": "📝",
                    "changelog_group": "Documentation",
                    "intent_id": "documentation_update",
                    "scope": "eval",
                }
            ],
        },
    )
    plan = parse_message_to_plan("x")
    assert plan.secondary_intents[0].cc_type.value == "docs"
    # CommitIntent may normalize secondary semver; ensure valid enum and non-empty description path hit
    assert plan.secondary_intents[0].semver_impact.value in {"PATCH", "NONE", "MINOR", "MAJOR"}
    assert plan.secondary_intents[0].description == "secondary docs"
    assert plan.secondary_intents[0].gitmoji == "📝"


def test_score_case_result_deterministic_pass_none_when_other_gates_only() -> None:
    # gate list without deterministic_pass → property returns None (loop exhaust)
    g = make_score("gate.golden_promotion_eligible", False, passed=False)
    res = ScoreCaseResult(case_id="n", gates=[g])
    assert res.deterministic_pass is None
