"""S2c Family I — topology / lifecycle validators + runner/gate plumbing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from git_cg.eval.catalog import load_metric_catalog
from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring import (
    FAMILY_I_METRIC_IDS,
    S2A_REQUIRE_BLOCK,
    S2B_REQUIRE_BLOCK,
    S2C_TOPOLOGY_BLOCK,
    build_session_thread_index,
    compose_gates,
    resolve_require_topology,
    score_bundle,
    score_case,
    score_family_i,
    synthesize_family_i_fail_closed,
)
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_i import project_topology_evidence
from git_cg.eval.scoring.gates import assert_s2c_block_len
from git_cg.eval.scoring.result_builder import make_score
from git_cg.eval.scoring.runner import score_suite

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"
TOPO_VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v-topology-complete.json"

_POL = {m["metric_id"]: m["polarity"] for m in load_metric_catalog()["metrics"]}


def _pass_row(metric_id: str) -> ScoreResultV1:
    pol = _POL[metric_id]
    if pol == "lower_is_better":
        return make_score(metric_id, 0, passed=True)
    if pol == "higher_is_better":
        return make_score(metric_id, 1.0, passed=True)
    return make_score(metric_id, True, passed=True)


def _fail_row(metric_id: str) -> ScoreResultV1:
    pol = _POL[metric_id]
    if pol == "lower_is_better":
        return make_score(metric_id, 2, passed=False)
    if pol == "higher_is_better":
        return make_score(metric_id, 0.0, passed=False)
    return make_score(metric_id, False, passed=False)


def _bundle_from_fixture(path: Path, **mut: Any) -> dict[str, Any]:
    fx = json.loads(path.read_text(encoding="utf-8"))
    fx.update(mut)
    return encode_fixture(fx)["bundle"]


def _by(rows: list[ScoreResultV1]) -> dict[str, ScoreResultV1]:
    return {r.metric_id: r for r in rows}


# ---------------------------------------------------------------------------
# Catalog / constant surface
# ---------------------------------------------------------------------------


def test_family_i_metric_ids_are_frozen_catalog_set() -> None:
    cat_ids = {m["metric_id"] for m in load_metric_catalog()["metrics"] if m["metric_id"].startswith("i.")}
    assert set(FAMILY_I_METRIC_IDS) == cat_ids
    assert len(FAMILY_I_METRIC_IDS) == 16
    assert list(FAMILY_I_METRIC_IDS) == sorted(FAMILY_I_METRIC_IDS)


def test_s2c_topology_block_is_exact_12_and_not_in_s2a_s2b() -> None:
    assert_s2c_block_len()
    assert len(S2C_TOPOLOGY_BLOCK) == 12
    assert set(S2C_TOPOLOGY_BLOCK).issubset(set(FAMILY_I_METRIC_IDS))
    for mid in S2C_TOPOLOGY_BLOCK:
        assert mid not in S2A_REQUIRE_BLOCK
        assert mid not in S2B_REQUIRE_BLOCK
    # S2A/S2B length frozen (S2c does not mutate those tuples)
    assert len(S2A_REQUIRE_BLOCK) == 30
    assert len(S2B_REQUIRE_BLOCK) == 68


def test_package_exports_s2c_surface() -> None:
    import git_cg.eval.scoring as s

    assert s.S2C_TOPOLOGY_BLOCK is S2C_TOPOLOGY_BLOCK
    assert callable(s.score_family_i)
    assert callable(s.build_session_thread_index)
    assert callable(s.resolve_require_topology)
    assert "i.trace_root_present" in s.FAMILY_I_METRIC_IDS


# ---------------------------------------------------------------------------
# Absent topology / always 16 rows
# ---------------------------------------------------------------------------


def test_score_family_i_always_emits_16_rows_without_topology() -> None:
    bundle = _bundle_from_fixture(VALID)
    ctx = project_score_context(bundle)
    rows = score_family_i(ctx, require_topology=False)
    assert [r.metric_id for r in rows] == list(FAMILY_I_METRIC_IDS)
    by = _by(rows)
    # Absent shell: correlation/replay/export unclaimed pass; most others fail honestly.
    assert by["i.correlation_envelope_valid"].passed is True
    assert by["i.replay_lineage_valid"].passed is True
    assert by["i.export_status_classified"].passed is True
    assert by["i.trace_root_present"].passed is False
    assert by["i.lifecycle_complete"].passed is False
    for r in rows:
        ScoreResultV1.model_validate(r.model_dump(mode="json"))
        assert bool(r.value) == bool(r.passed)


def test_runner_always_emits_family_i_even_when_not_required() -> None:
    result = score_case(VALID, suite_snapshot_pin="pin@1", require_topology=False)
    by = result.by_id()
    for mid in FAMILY_I_METRIC_IDS:
        assert mid in by
    # Topology failures must not veto S2A gates when require_topology=false.
    assert by["gate.deterministic_pass"].passed is True
    assert result.require_topology is False
    g = by["gate.deterministic_pass"]
    assert (g.evidence or {}).get("require_topology") is False
    assert (g.evidence or {}).get("s2c_topology_block") == []


def test_find026_short_circuit_still_emits_family_i() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    result = score_bundle(b, suite_snapshot_pin="pin@1")
    assert result.short_circuit is True
    by = result.by_id()
    assert "b.header_shape" not in by
    for mid in FAMILY_I_METRIC_IDS:
        assert mid in by
    assert by["h.eval_input_nonempty"].passed is False


# ---------------------------------------------------------------------------
# Canonical topology fixture behaviour
# ---------------------------------------------------------------------------


def test_valid_topology_fixture_aliases_and_lifecycle() -> None:
    bundle = _bundle_from_fixture(TOPO_VALID)
    # S1 shallow meta.topology preserved through encoder.
    assert bundle["meta"]["topology"]["terminal_state"] == "finalized"
    ctx = project_score_context(bundle)
    ev = project_topology_evidence(bundle, meta=ctx.meta)
    assert ev is not None
    assert ev.source == "meta.topology"
    # Aliases applied
    observed = {n.name for n in ev.nodes}
    assert "llm_generation" in observed
    assert "final_render" in observed
    assert "accept_path_finalization" in observed
    assert "generation" not in observed
    assert ev.terminal_state == "ok"

    rows = score_family_i(ctx, require_topology=False)
    by = _by(rows)
    assert by["i.lifecycle_complete"].passed is True
    assert by["i.required_spans_present"].passed is True
    assert by["i.span_tree_valid"].passed is True
    # No root_trace_id on shallow fixture → honest fail
    assert by["i.trace_root_present"].passed is False


def test_canonical_topology_precedence_bundle_root_wins() -> None:
    bundle = _bundle_from_fixture(TOPO_VALID)
    bundle["topology"] = {
        "root_trace_id": "tr-root-1",
        "session_thread_id": "th-1",
        "terminal_state": "ok",
        "required_spans": ["llm_generation", "accept_path_finalization", "final_render"],
        "observed_spans": [
            {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
            {"name": "accept_path_finalization", "span_id": "s2", "parent_span_id": "s1"},
            {"name": "final_render", "span_id": "s3", "parent_span_id": "s2"},
        ],
    }
    # Poison lower-precedence sources — must be ignored.
    bundle["meta"]["topology_canonical"] = {"status": "incomplete", "terminal_state": "open"}
    bundle["meta"]["trace_topology"] = {"status": "incomplete"}
    bundle["meta"]["topology"] = {"status": "incomplete", "terminal_state": "open"}

    ctx = project_score_context(bundle)
    ev = project_topology_evidence(bundle, meta=ctx.meta)
    assert ev is not None
    assert ev.source == "bundle.topology"
    assert ev.root_trace_id == "tr-root-1"
    assert ev.session_thread_id == "th-1"
    assert ev.terminal_state == "ok"

    by = _by(score_family_i(ctx, require_topology=True))
    assert by["i.trace_root_present"].passed is True
    assert by["i.lifecycle_complete"].passed is True
    assert by["i.thread_id_present"].passed is True
    assert by["i.span_tree_valid"].passed is True
    assert by["i.span_parentage_valid"].passed is True
    assert by["i.required_spans_present"].passed is True


def test_terminal_states_normalization() -> None:
    base = _bundle_from_fixture(TOPO_VALID)

    def _score(terminal: str) -> dict[str, ScoreResultV1]:
        b = json.loads(json.dumps(base))
        b["meta"]["topology"]["terminal_state"] = terminal
        ctx = project_score_context(b)
        return _by(score_family_i(ctx))

    assert _score("finalized")["i.lifecycle_complete"].passed is True
    assert _score("ok")["i.lifecycle_complete"].passed is True
    assert _score("product_error")["i.lifecycle_complete"].passed is True
    assert _score("export_error")["i.lifecycle_complete"].passed is True
    assert _score("cancelled")["i.lifecycle_complete"].passed is True
    assert _score("open")["i.lifecycle_complete"].passed is False
    assert _score("unknown")["i.lifecycle_complete"].passed is False
    assert _score("weird")["i.lifecycle_complete"].passed is False


# ---------------------------------------------------------------------------
# Gate composition topology coupling
# ---------------------------------------------------------------------------


def test_compose_gates_default_excludes_topology_block() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    # Topology failures present but not required.
    rows.extend(_fail_row(m) for m in S2C_TOPOLOGY_BLOCK)
    gates = compose_gates(rows, bound=True, require_topology=False)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    assert det.passed is True
    assert (det.evidence or {}).get("require_topology") is False
    promo = next(g for g in gates if g.metric_id == "gate.golden_promotion_eligible")
    # I metrics not consulted when require_topology=false.
    assert (promo.evidence or {}).get("require_topology") is False


def test_compose_gates_require_topology_unions_s2c_block() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.extend(_pass_row(m) for m in S2C_TOPOLOGY_BLOCK)
    gates = compose_gates(rows, bound=True, require_topology=True)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    assert det.passed is True
    req = (det.evidence or {}).get("require_block") or []
    for mid in S2C_TOPOLOGY_BLOCK:
        assert mid in req
    assert (det.evidence or {}).get("s2c_topology_block") == list(S2C_TOPOLOGY_BLOCK)


def test_compose_gates_require_topology_missing_i_fails() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    # No Family I rows at all.
    gates = compose_gates(rows, bound=True, require_topology=True)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    assert det.passed is False
    missing = (det.evidence or {}).get("missing") or []
    assert "i.lifecycle_complete" in missing


def test_golden_promotion_requires_lifecycle_and_required_spans_when_topo() -> None:
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.extend(_pass_row(m) for m in S2C_TOPOLOGY_BLOCK)
    # Force the two promotion-coupled I rows to fail while other I pass.
    rows = [r for r in rows if r.metric_id not in {"i.lifecycle_complete", "i.required_spans_present"}]
    rows.append(_fail_row("i.lifecycle_complete"))
    rows.append(_fail_row("i.required_spans_present"))

    gates = compose_gates(rows, bound=True, require_topology=True)
    det = next(g for g in gates if g.metric_id == "gate.deterministic_pass")
    promo = next(g for g in gates if g.metric_id == "gate.golden_promotion_eligible")
    assert det.passed is False  # S2C block is in det require_block
    assert promo.passed is False
    assert (promo.evidence or {}).get("lifecycle_complete") is False
    assert (promo.evidence or {}).get("required_spans_present") is False

    # When topology not required, failed I lifecycle does not block promo baseline.
    rows2 = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows2.append(_fail_row("i.lifecycle_complete"))
    rows2.append(_fail_row("i.required_spans_present"))
    gates2 = compose_gates(rows2, bound=True, require_topology=False)
    promo2 = next(g for g in gates2 if g.metric_id == "gate.golden_promotion_eligible")
    # det + gold + skeleton + bound — I not consulted
    assert promo2.passed is True


# ---------------------------------------------------------------------------
# Policy resolution + recovery
# ---------------------------------------------------------------------------


def test_resolve_require_topology_precedence() -> None:
    assert resolve_require_topology(True, {"meta": {"require_topology": False}}) is True
    assert resolve_require_topology(False, {"meta": {"require_topology": True}}) is False
    assert resolve_require_topology(None, {"meta": {"require_topology": True}}) is True
    assert resolve_require_topology(None, {"meta": {"require_topology": "yes"}}) is False
    assert resolve_require_topology(None, {"meta": {}}) is False
    assert resolve_require_topology(None, None) is False


def test_synthesize_family_i_fail_closed_emits_16_failed_rows() -> None:
    rows = synthesize_family_i_fail_closed(reason="boom", errors=["x"])
    assert [r.metric_id for r in rows] == list(FAMILY_I_METRIC_IDS)
    assert all(r.passed is False for r in rows)
    assert all(r.reason == "boom" for r in rows)


def test_runner_family_i_recovery_on_evaluator_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("family_i_exploded")

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_i", _boom)
    result = score_case(VALID, suite_snapshot_pin="pin@1")
    assert any("family_i" in e for e in result.evaluator_errors)
    by = result.by_id()
    for mid in FAMILY_I_METRIC_IDS:
        assert by[mid].passed is False
        assert by[mid].reason == "family_i_evaluator_error"
    assert by["h.evaluator_error_free"].passed is False


# ---------------------------------------------------------------------------
# Thread index / encoder session_thread_id
# ---------------------------------------------------------------------------


def test_encoder_copies_root_session_thread_id() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    fx["session_thread_id"] = "thread-encode-1"
    out = encode_fixture(fx)
    assert out["bundle"]["session_thread_id"] == "thread-encode-1"


def test_encoder_ignores_empty_session_thread_id() -> None:
    from git_cg.eval.corpus.encoder import CorpusEncodeError

    fx = json.loads(VALID.read_text(encoding="utf-8"))
    fx["session_thread_id"] = "   "
    with pytest.raises(CorpusEncodeError, match="session_thread_id"):
        encode_fixture(fx)


def test_build_session_thread_index_and_contamination() -> None:
    b1 = _bundle_from_fixture(VALID)
    b1["session_thread_id"] = "shared-thread"
    b2 = _bundle_from_fixture(VALID)
    b2["case_id"] = "other-case"
    b2["session_thread_id"] = "shared-thread"
    b3 = _bundle_from_fixture(VALID)
    b3["case_id"] = "solo-case"
    b3["session_thread_id"] = "solo-thread"

    index = build_session_thread_index(
        [
            ("seed-v1-valid-fixture", b1),
            ("other-case", b2),
            ("solo-case", b3),
        ]
    )
    assert index["shared-thread"] == ("other-case", "seed-v1-valid-fixture")
    assert index["solo-thread"] == ("solo-case",)

    ctx1 = project_score_context(b1, case_id="seed-v1-valid-fixture")
    by1 = _by(score_family_i(ctx1, session_thread_index=index))
    assert by1["i.no_cross_case_contamination"].passed is False
    assert "other-case" in ((by1["i.no_cross_case_contamination"].evidence or {}).get("foreign_case_ids") or [])

    ctx3 = project_score_context(b3, case_id="solo-case")
    by3 = _by(score_family_i(ctx3, session_thread_index=index))
    assert by3["i.no_cross_case_contamination"].passed is True


def test_score_suite_two_pass_builds_thread_index(tmp_path: Path) -> None:
    """suite scoring builds a read-only index before scoring cases."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    suites_dir = tmp_path / "suites"
    suites_dir.mkdir()

    def _write_case(cid: str, thread: str) -> None:
        fx = json.loads(VALID.read_text(encoding="utf-8"))
        fx["case_id"] = cid
        fx["session_thread_id"] = thread
        (cases_dir / f"{cid}.json").write_text(json.dumps(fx), encoding="utf-8")

    _write_case("case-a", "thread-x")
    _write_case("case-b", "thread-x")

    # Minimal suite matching the two synthetic cases. score_suite still pins
    # against the canonical suite snapshot for sid, so use a unique suite_id
    # and pass suite_path + fixture_root carefully.
    # For hermetic coverage of the index path, call score_bundle via encoded pairs.
    from git_cg.eval.scoring.runner import score_bundle as _score_bundle

    pairs = []
    for cid in ("case-a", "case-b"):
        fx = json.loads((cases_dir / f"{cid}.json").read_text(encoding="utf-8"))
        pairs.append((cid, encode_fixture(fx, case_id=cid)["bundle"]))
    index = build_session_thread_index(pairs)
    assert index["thread-x"] == ("case-a", "case-b")

    r_a = _score_bundle(pairs[0][1], case_id="case-a", session_thread_index=index, suite_snapshot_pin="p")
    r_b = _score_bundle(pairs[1][1], case_id="case-b", session_thread_index=index, suite_snapshot_pin="p")
    assert r_a.by_id()["i.no_cross_case_contamination"].passed is False
    assert r_b.by_id()["i.no_cross_case_contamination"].passed is False


def test_score_suite_respects_meta_require_topology_false() -> None:
    suite = score_suite("cm-eval-fixtures-core", fixture_root=FIXTURE_ROOT, require_topology=False)
    assert suite.require_topology is False
    assert isinstance(suite.session_thread_index, dict)
    # All cases still emit Family I rows.
    for case in suite.cases:
        by = case.by_id()
        for mid in FAMILY_I_METRIC_IDS:
            assert mid in by
        # Without topology required, core V1 still det-passes.
        if case.case_id == "seed-v1-valid-fixture":
            assert case.deterministic_pass is True


def test_score_bundle_require_topology_true_fails_missing_topo_gate() -> None:
    result = score_case(VALID, suite_snapshot_pin="pin@1", require_topology=True)
    assert result.require_topology is True
    by = result.by_id()
    assert by["gate.deterministic_pass"].passed is False
    failed_or_missing = set((by["gate.deterministic_pass"].evidence or {}).get("failed") or []) | set(
        (by["gate.deterministic_pass"].evidence or {}).get("missing") or []
    )
    assert "i.lifecycle_complete" in failed_or_missing or any(
        str(x).endswith("i.lifecycle_complete") or x == "i.lifecycle_complete"
        for x in (by["gate.deterministic_pass"].failure_ids or [])
    )


def test_parentage_name_only_vs_id_mode() -> None:
    b = _bundle_from_fixture(TOPO_VALID)
    # Name-only list → parentage inapplicable/pass
    ctx = project_score_context(b)
    by = _by(score_family_i(ctx))
    assert by["i.span_parentage_valid"].passed is True
    assert by["i.span_parentage_valid"].reason == "parentage_ids_not_provided"

    # ID mode with dangling parent → fail parentage
    b2 = json.loads(json.dumps(b))
    b2["topology"] = {
        "root_trace_id": "r1",
        "terminal_state": "ok",
        "required_spans": ["llm_generation"],
        "spans": [
            {"name": "llm_generation", "span_id": "s1", "parent_span_id": "missing-parent"},
        ],
    }
    ctx2 = project_score_context(b2)
    by2 = _by(score_family_i(ctx2))
    assert by2["i.span_parentage_valid"].passed is False
    assert by2["i.span_parentage_valid"].reason == "dangling_parent"


def test_counter_span_consistent_regen_mismatch() -> None:
    b = _bundle_from_fixture(TOPO_VALID)
    b["meta"]["evidence"]["counters"]["gold_regen_attempts"] = 2
    b["meta"]["evidence"]["span_counts"]["regeneration"] = 0
    # Drop encoder require flag so we can score the mismatched evidence directly.
    b["meta"]["evidence"]["require_counter_span_consistent"] = False
    ctx = project_score_context(b)
    by = _by(score_family_i(ctx))
    assert by["i.counter_span_consistent"].passed is False
