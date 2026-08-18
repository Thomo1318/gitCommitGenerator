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


def test_runner_family_i_recovers_missing_row(monkeypatch: pytest.MonkeyPatch) -> None:
    def _drop_one(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        rows = score_family_i(project_score_context(_bundle_from_fixture(VALID)))
        # Drop one catalog id so the N18 missing-row path fills it.
        return [r for r in rows if r.metric_id != "i.thread_id_present"]

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_i", _drop_one)
    result = score_case(VALID, suite_snapshot_pin="pin@1")
    by = result.by_id()
    assert by["i.thread_id_present"].passed is False
    assert by["i.thread_id_present"].reason == "family_i_row_missing_recovered"
    assert any("family_i_missing:i.thread_id_present" in e for e in result.evaluator_errors)
    for mid in FAMILY_I_METRIC_IDS:
        assert mid in by


def test_runner_family_i_recovers_value_passed_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _mismatch(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        rows = score_family_i(project_score_context(_bundle_from_fixture(VALID)))
        out: list[ScoreResultV1] = []
        for r in rows:
            if r.metric_id == "i.lifecycle_complete":
                payload = r.model_dump(mode="json")
                payload["value"] = True
                payload["passed"] = False
                out.append(ScoreResultV1.model_validate(payload))
            else:
                out.append(r)
        return out

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_i", _mismatch)
    result = score_case(VALID, suite_snapshot_pin="pin@1")
    by = result.by_id()
    assert by["i.lifecycle_complete"].passed is False
    assert by["i.lifecycle_complete"].reason == "family_i_envelope_invalid"
    assert any("family_i_envelope:i.lifecycle_complete" in e for e in result.evaluator_errors)
    # Other I rows still present and not wholesale-replaced.
    assert by["i.trace_root_present"].reason != "family_i_envelope_invalid"


# ---------------------------------------------------------------------------
# Thread index / encoder session_thread_id
# ---------------------------------------------------------------------------


def test_encoder_copies_root_session_thread_id() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    fx["session_thread_id"] = "thread-encode-1"
    out = encode_fixture(fx)
    assert out["bundle"]["session_thread_id"] == "thread-encode-1"


def test_encoder_strips_session_thread_id_whitespace() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    fx["session_thread_id"] = "  thread-encode-pad  "
    out = encode_fixture(fx)
    assert out["bundle"]["session_thread_id"] == "thread-encode-pad"


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


def test_build_session_thread_index_and_score_bundle_contamination(tmp_path: Path) -> None:
    """Hermetic index + score_bundle path for cross-case contamination evidence."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()

    def _write_case(cid: str, thread: str) -> None:
        fx = json.loads(VALID.read_text(encoding="utf-8"))
        fx["case_id"] = cid
        fx["session_thread_id"] = thread
        (cases_dir / f"{cid}.json").write_text(json.dumps(fx), encoding="utf-8")

    _write_case("case-a", "thread-x")
    _write_case("case-b", "thread-x")

    # score_suite still pins against the canonical suite snapshot for sid; keep
    # this hermetic by exercising build_session_thread_index + score_bundle.
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


# ---------------------------------------------------------------------------
# N12 fixture matrix via direct injection + split-oracle assertions
# ---------------------------------------------------------------------------

INVALID = FIXTURE_ROOT / "cases" / "invalid"
N_INCOMPLETE = INVALID / "seed-n-topology-incomplete.json"
N_COUNTER = INVALID / "seed-n-counter-mismatch.json"
N_REPLAY = INVALID / "seed-n-replay-lineage-missing.json"


def _bundle_from_negative_fixture(path: Path, **mut: Any) -> dict[str, Any]:
    """Project encoder-negative fixtures into a scoreable bundle without weakening S1 floors.

    S1 still fail-closes these probes under encode_fixture (even validate=False) because
    topology/counter/replay guards are encoder law. N12 therefore scores via direct
    injection: encode a valid carrier fixture, then overlay the negative fixture's
    case_id / meta evidence for Family I only.
    """
    fx = json.loads(path.read_text(encoding="utf-8"))
    carrier = _bundle_from_fixture(VALID)
    carrier["case_id"] = fx.get("case_id", carrier.get("case_id"))
    # Preserve carrier message/schema; overlay topology-class evidence from the probe.
    meta = dict(carrier.get("meta") or {})
    fx_meta = dict(fx.get("meta") or {})
    meta.update(fx_meta)
    carrier["meta"] = meta
    if "session_thread_id" in fx and isinstance(fx.get("session_thread_id"), str):
        carrier["session_thread_id"] = fx["session_thread_id"]
    if "bound" in fx:
        carrier["bound"] = fx["bound"]
    if "artifact_class" in fx:
        carrier["artifact_class"] = fx["artifact_class"]
    carrier.update(mut)
    return carrier


def test_n12_seed_v_topology_complete_is_split_oracle_not_all_green() -> None:
    """N12 / S2C-B: complete shallow control is a split oracle, not all-green."""
    bundle = _bundle_from_fixture(TOPO_VALID)
    ctx = project_score_context(bundle)
    by = _by(score_family_i(ctx, require_topology=False))

    # Must-pass after alias/terminal/counter projection
    assert by["i.lifecycle_complete"].passed is True
    assert by["i.required_spans_present"].passed is True
    assert by["i.counter_span_consistent"].passed is True
    # Name-only parentage is inapplicable-pass, not invented IDs
    assert by["i.span_parentage_valid"].passed is True
    assert by["i.span_parentage_valid"].reason == "parentage_ids_not_provided"
    # Unclaimed surfaces stay honest inapplicable passes
    assert by["i.correlation_envelope_valid"].reason == "correlation_not_claimed"
    assert by["i.replay_lineage_valid"].reason == "replay_not_claimed"
    assert by["i.export_status_classified"].reason == "export_not_claimed"
    # Missing root evidence remains honest failure
    assert by["i.trace_root_present"].passed is False
    assert by["i.trace_root_present"].reason == "root_trace_missing"


def test_n12_seed_n_topology_incomplete_scores_via_direct_injection() -> None:
    """N12: incomplete topology fails required-spans + open lifecycle under Family I."""
    bundle = _bundle_from_negative_fixture(N_INCOMPLETE)
    # Overlay preserves shallow topology evidence for Family I scoring.
    assert bundle["meta"]["topology"]["status"] == "incomplete"
    ctx = project_score_context(bundle)
    by = _by(score_family_i(ctx, require_topology=True))
    assert by["i.lifecycle_complete"].passed is False
    assert by["i.lifecycle_complete"].reason == "terminal_missing_or_open"
    assert by["i.required_spans_present"].passed is False
    missing = (by["i.required_spans_present"].evidence or {}).get("missing_required_spans") or []
    assert "regeneration" in missing
    assert "accept_path_finalization" in missing
    assert "final_render" in missing  # score_emit aliased
    # Finalization claimed via required_spans → fail when absent
    assert by["i.finalization_observed"].passed is False


def test_n12_seed_n_counter_mismatch_scores_via_direct_injection() -> None:
    """N12 / Session-12: counter claims regen but observed regeneration spans are 0."""
    bundle = _bundle_from_negative_fixture(N_COUNTER)
    ctx = project_score_context(bundle)
    by = _by(score_family_i(ctx))
    row = by["i.counter_span_consistent"]
    assert row.passed is False
    assert row.reason == "counter_span_mismatch_regen"
    assert (row.evidence or {}).get("blame_span") == "regeneration"


def test_n12_seed_n_replay_lineage_missing_scores_via_direct_injection() -> None:
    """N12: is_replay + missing parent_trace_id fails replay lineage under Family I."""
    bundle = _bundle_from_negative_fixture(N_REPLAY)
    ctx = project_score_context(bundle)
    by = _by(score_family_i(ctx))
    row = by["i.replay_lineage_valid"]
    assert row.passed is False
    assert row.reason == "replay_lineage_incomplete"
    assert "parent_trace_id" in ((row.evidence or {}).get("missing_fields") or [])


# ---------------------------------------------------------------------------
# Named claims S2C-A … S2C-H
# ---------------------------------------------------------------------------


def test_s2c_a_family_i_emits_16_schema_valid_rows_normal_and_find026_and_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S2C-A: 16 schema-valid I rows on normal, FIND-026, and N18 recovery paths."""
    # Normal path
    normal = score_case(VALID, suite_snapshot_pin="pin@1")
    nby = normal.by_id()
    for mid in FAMILY_I_METRIC_IDS:
        row = nby[mid]
        ScoreResultV1.model_validate(row.model_dump(mode="json"))
        assert bool(row.value) == bool(row.passed)

    # FIND-026 short-circuit still emits I
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    short = score_bundle(b, suite_snapshot_pin="pin@1")
    assert short.short_circuit is True
    sby = short.by_id()
    for mid in FAMILY_I_METRIC_IDS:
        ScoreResultV1.model_validate(sby[mid].model_dump(mode="json"))

    # N18 recovery
    def _boom(*_a: Any, **_k: Any) -> list[ScoreResultV1]:
        raise RuntimeError("s2c_a_recovery")

    monkeypatch.setattr("git_cg.eval.scoring.runner.score_family_i", _boom)
    recovered = score_case(VALID, suite_snapshot_pin="pin@1")
    rby = recovered.by_id()
    for mid in FAMILY_I_METRIC_IDS:
        assert rby[mid].passed is False
        ScoreResultV1.model_validate(rby[mid].model_dump(mode="json"))
        assert bool(rby[mid].value) is False
    assert rby["h.evaluator_error_free"].passed is False


def test_s2c_b_adapter_aliases_and_declared_required_set() -> None:
    """S2C-B: N3 aliases + declared required_spans win offline required-set checks."""
    bundle = _bundle_from_fixture(TOPO_VALID)
    ctx = project_score_context(bundle)
    ev = project_topology_evidence(bundle, meta=ctx.meta)
    assert ev is not None
    names = {n.name for n in ev.nodes}
    assert names == {"llm_generation", "accept_path_finalization", "final_render"}
    assert "generation" not in names
    assert "score_emit" not in names
    assert set(ev.required_spans) == names
    by = _by(score_family_i(ctx))
    assert by["i.required_spans_present"].passed is True
    # Incomplete declared set fails after aliasing score_emit → final_render
    bad = _bundle_from_negative_fixture(N_INCOMPLETE)
    by2 = _by(score_family_i(project_score_context(bad)))
    assert by2["i.required_spans_present"].passed is False


def test_s2c_c_negative_validators_fail_closed() -> None:
    """S2C-C: lifecycle/parentage/counter/replay/contamination/correlation fail-closed."""
    # lifecycle + required (N12 incomplete)
    inc = _by(score_family_i(project_score_context(_bundle_from_negative_fixture(N_INCOMPLETE))))
    assert inc["i.lifecycle_complete"].passed is False
    assert inc["i.required_spans_present"].passed is False

    # counters
    ctr = _by(score_family_i(project_score_context(_bundle_from_negative_fixture(N_COUNTER))))
    assert ctr["i.counter_span_consistent"].passed is False

    # replay
    rep = _by(score_family_i(project_score_context(_bundle_from_negative_fixture(N_REPLAY))))
    assert rep["i.replay_lineage_valid"].passed is False

    # parentage dangling
    b = _bundle_from_fixture(TOPO_VALID)
    b["topology"] = {
        "root_trace_id": "r1",
        "terminal_state": "ok",
        "required_spans": ["llm_generation"],
        "spans": [{"name": "llm_generation", "span_id": "s1", "parent_span_id": "missing"}],
    }
    par = _by(score_family_i(project_score_context(b)))
    assert par["i.span_parentage_valid"].passed is False
    assert par["i.span_parentage_valid"].reason == "dangling_parent"

    # cross-case contamination (N14)
    b1 = _bundle_from_fixture(VALID)
    b1["session_thread_id"] = "shared-s2c-c"
    b2 = _bundle_from_fixture(VALID)
    b2["case_id"] = "peer-case"
    b2["session_thread_id"] = "shared-s2c-c"
    index = build_session_thread_index([("seed-v1-valid-fixture", b1), ("peer-case", b2)])
    x = _by(
        score_family_i(
            project_score_context(b1, case_id="seed-v1-valid-fixture"),
            session_thread_index=index,
        )
    )
    assert x["i.no_cross_case_contamination"].passed is False

    # correlation claimed but missing id
    b3 = _bundle_from_fixture(TOPO_VALID)
    b3["meta"]["correlation"] = {"multi_process": True, "hook_phase": "post-commit"}
    corr = _by(score_family_i(project_score_context(b3)))
    assert corr["i.correlation_envelope_valid"].passed is False
    assert corr["i.correlation_envelope_valid"].reason == "correlation_id_missing"


def test_s2c_d_require_topology_joins_s2c_block_only_when_true() -> None:
    """S2C-D: require_topology true unions S2C block; default false; no bound inference."""
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.extend(_fail_row(m) for m in S2C_TOPOLOGY_BLOCK)
    off = compose_gates(rows, bound=True, require_topology=False)
    det_off = next(g for g in off if g.metric_id == "gate.deterministic_pass")
    assert det_off.passed is True

    on = compose_gates(rows, bound=True, require_topology=True)
    det_on = next(g for g in on if g.metric_id == "gate.deterministic_pass")
    assert det_on.passed is False
    req = (det_on.evidence or {}).get("require_block") or []
    for mid in S2C_TOPOLOGY_BLOCK:
        assert mid in req

    # Explicit false beats suite meta true (N19)
    assert resolve_require_topology(False, {"meta": {"require_topology": True}}) is False
    # Bound inference banned
    assert resolve_require_topology(None, {"meta": {}, "bound": True}) is False


def test_s2c_e_golden_couples_lifecycle_and_required_only_when_topology_required() -> None:
    """S2C-E: golden couples to lifecycle+required spans iff require_topology=true."""
    rows = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows.extend(_pass_row(m) for m in S2C_TOPOLOGY_BLOCK)
    rows = [r for r in rows if r.metric_id not in {"i.lifecycle_complete", "i.required_spans_present"}]
    rows.append(_fail_row("i.lifecycle_complete"))
    rows.append(_fail_row("i.required_spans_present"))

    gates_on = compose_gates(rows, bound=True, require_topology=True)
    promo_on = next(g for g in gates_on if g.metric_id == "gate.golden_promotion_eligible")
    assert promo_on.passed is False

    rows_off = [_pass_row(m) for m in S2A_REQUIRE_BLOCK]
    rows_off.append(_fail_row("i.lifecycle_complete"))
    rows_off.append(_fail_row("i.required_spans_present"))
    gates_off = compose_gates(rows_off, bound=True, require_topology=False)
    promo_off = next(g for g in gates_off if g.metric_id == "gate.golden_promotion_eligible")
    assert promo_off.passed is True


def test_s2c_f_honest_degrade_no_fake_topology_greens_when_required() -> None:
    """S2C-F: missing topology evidence fails closed under require_topology=true."""
    result = score_case(VALID, suite_snapshot_pin="pin@1", require_topology=True)
    by = result.by_id()
    assert by["i.lifecycle_complete"].passed is False
    assert by["i.lifecycle_complete"].reason == "topology_evidence_absent"
    assert by["i.required_spans_present"].passed is False
    assert by["gate.deterministic_pass"].passed is False
    # No invented root/tree green
    assert by["i.trace_root_present"].passed is False
    assert by["i.span_tree_valid"].passed is False


def test_s2c_g_rca_evidence_fields_attached_when_computable() -> None:
    """S2C-G: N11 RCA evidence fields attach on relevant I failures (no S6 CLI)."""
    b = _bundle_from_fixture(TOPO_VALID)
    b["topology"] = {
        "root_trace_id": "tr-rca",
        "terminal_state": "ok",
        "required_spans": ["llm_generation", "accept_path_finalization", "final_render"],
        "observed_spans": [
            {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
            {"name": "mystery_probe_span", "span_id": "s2", "parent_span_id": "s1"},
        ],
    }
    by = _by(score_family_i(project_score_context(b)))
    req = by["i.required_spans_present"]
    assert req.passed is False
    ev = req.evidence or {}
    assert "accept_path_finalization" in (ev.get("missing_required_spans") or [])
    assert "final_render" in (ev.get("missing_required_spans") or [])
    assert "mystery_probe_span" in (ev.get("unexpected_spans") or [])
    assert ev.get("blame_span") in {"accept_path_finalization", "final_render"}
    assert ev.get("first_divergent_span") == ev.get("blame_span")
    fp = ev.get("diag_fingerprint_inputs") or {}
    assert "metric_ids" in fp
    assert "missing_required_spans" in fp
    assert "unexpected_spans" in fp
    # Unknown producer names are digest-sanitized in fingerprint inputs (N11).
    assert "mystery_probe_span" not in json.dumps(fp.get("unexpected_spans") or [])
    assert any(str(x).startswith("unknown:") for x in (fp.get("unexpected_spans") or []))
    # Canonical missing names may remain in fingerprint.
    assert "accept_path_finalization" in (fp.get("missing_required_spans") or [])
    # N11 exclusions — no raw message / absolute paths / trace ids in fingerprint inputs
    blob = json.dumps(fp)
    assert "tr-rca" not in blob
    assert "/Users/" not in blob
    assert "docs(eval)" not in blob
    assert "mystery_probe_span" not in blob


def test_s2c_h_no_s3_s4_thread_star_or_pin_drift() -> None:
    """S2C-H: isolation invariants — no thread.* rows; pins unchanged; no Opik imports."""
    import re

    import git_cg.eval.scoring as scoring_pkg
    from git_cg.eval import metric_catalog_pin, schema_pack_pin

    # No thread.* metric emission on a scored case
    result = score_case(VALID, suite_snapshot_pin="pin@1")
    for mid in result.by_id():
        assert not mid.startswith("thread."), mid
    # Public S2c surface present; S2A/S2B lengths frozen
    assert callable(scoring_pkg.score_family_i)
    assert len(scoring_pkg.S2C_TOPOLOGY_BLOCK) == 12
    assert len(scoring_pkg.S2A_REQUIRE_BLOCK) == 30
    assert len(scoring_pkg.S2B_REQUIRE_BLOCK) == 68
    # Pin identity unchanged
    assert schema_pack_pin().endswith("6647b3a3c45e5b22743ccc686eb662f70d8d65858c06fb5f19dafe849e27a5d6")
    assert metric_catalog_pin().endswith("430a62c1d7971e1145cfffd41e608a5f6bd39d284a3d050f991b8537f817eb75")
    # No S3 accept-path emitter / S4 Opik client surface under scoring package.
    repo_root = Path(__file__).resolve().parents[2]
    scoring_root = repo_root / "src" / "git_cg" / "eval" / "scoring"
    import_re = re.compile(r"^\s*(import\s+opik\b|from\s+opik\b)", re.M)
    for py in scoring_root.glob("*.py"):
        src = py.read_text(encoding="utf-8")
        assert import_re.search(src) is None, f"unexpected opik import in {py.name}"
    assert not (scoring_root / "emitters.py").exists()
    assert not (scoring_root / "accept_path.py").exists()


def test_s2c_docs_boundary_anchors() -> None:
    """Docs anchors for S2c / deferred S3+ (separate from isolation pin checks)."""
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "docs" / "eval" / "README.md").read_text(encoding="utf-8")
    dev = (repo_root / "DEVELOPMENT.md").read_text(encoding="utf-8")
    assert "## S2c — Family I topology / lifecycle validators" in readme
    assert "require_topology" in readme
    assert "S2C_TOPOLOGY_BLOCK" in readme
    assert "envelope validate → gates" in readme
    assert "Family I is harness/eval law only" in dev
    assert "S2b/S2c family expansion" not in dev
    assert "remain deferred on #217" in dev


# ---------------------------------------------------------------------------
# N15-N17 edge coverage (synthetic canonical objects)
# ---------------------------------------------------------------------------


def _score_topo(topology: dict[str, Any], **bundle_mut: Any) -> dict[str, ScoreResultV1]:
    b = _bundle_from_fixture(TOPO_VALID)
    b.update(bundle_mut)
    b["topology"] = topology
    # Neutralise lower-precedence shallow topology so synthetic object wins.
    if isinstance(b.get("meta"), dict):
        b["meta"] = dict(b["meta"])
        b["meta"].pop("topology", None)
    return _by(score_family_i(project_score_context(b)))


def test_n15_duplicate_singleton_name_fails_tree() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation", "llm_generation"],
        }
    )
    assert by["i.span_tree_valid"].passed is False
    assert by["i.span_tree_valid"].reason == "duplicate_singleton_span_names"


def test_n15_repeatable_regeneration_duplicates_allowed() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "regeneration", "final_render"],
            "observed_spans": ["llm_generation", "regeneration", "regeneration", "final_render"],
        }
    )
    assert by["i.span_tree_valid"].passed is True


def test_n15_duplicate_span_ids_self_parent_orphan_cycle_multiple_roots() -> None:
    # duplicate ids
    dups = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
                {"name": "final_render", "span_id": "s1", "parent_span_id": None},
            ],
        }
    )
    assert dups["i.span_tree_valid"].passed is False
    assert dups["i.span_tree_valid"].reason == "duplicate_span_ids"

    # self-parent
    self_p = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "spans": [{"name": "llm_generation", "span_id": "s1", "parent_span_id": "s1"}],
        }
    )
    assert self_p["i.span_tree_valid"].passed is False
    assert self_p["i.span_tree_valid"].reason == "self_parent"
    assert self_p["i.span_parentage_valid"].passed is False

    # dangling / orphan parent
    orphan = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "spans": [{"name": "llm_generation", "span_id": "s1", "parent_span_id": "nope"}],
        }
    )
    assert orphan["i.span_parentage_valid"].passed is False
    assert orphan["i.span_parentage_valid"].reason == "dangling_parent"

    # cycle
    cycle = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": "s2"},
                {"name": "final_render", "span_id": "s2", "parent_span_id": "s1"},
            ],
        }
    )
    assert cycle["i.span_tree_valid"].passed is False
    assert cycle["i.span_tree_valid"].reason == "cycle_detected"

    # multiple roots
    multi = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
                {"name": "final_render", "span_id": "s2", "parent_span_id": None},
            ],
        }
    )
    assert multi["i.span_tree_valid"].passed is False
    assert multi["i.span_tree_valid"].reason == "multiple_roots"


def test_n16_correlation_unclaimed_vs_claimed() -> None:
    # unclaimed
    bare = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
        }
    )
    assert bare["i.correlation_envelope_valid"].passed is True
    assert bare["i.correlation_envelope_valid"].reason == "correlation_not_claimed"

    # claimed valid
    ok = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
            "correlation": {
                "correlation_id": "corr-1",
                "hook_phase": "pre-commit",
                "process_id_token": "p1",
            },
        }
    )
    assert ok["i.correlation_envelope_valid"].passed is True

    # claimed invalid (no id)
    bad = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
            "correlation": {"multi_process": True},
        }
    )
    assert bad["i.correlation_envelope_valid"].passed is False


def test_n17_declared_graph_pin_only_match_and_mismatch() -> None:
    # pin-only → inapplicable pass
    pin = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "observed_spans": ["llm_generation", "final_render"],
            "declared_graph": "git_cg_pipeline_graph_v1@deadbeef",
        }
    )
    assert pin["i.graph_observed_matches_declared"].passed is True
    assert pin["i.graph_observed_matches_declared"].reason == "declared_graph_object_unavailable"

    # matching inline graph (name-only consecutive edges)
    match = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "observed_spans": ["llm_generation", "final_render"],
            "declared_graph": {
                "nodes": ["llm_generation", "final_render"],
                "edges": [["llm_generation", "final_render"]],
            },
        }
    )
    assert match["i.graph_observed_matches_declared"].passed is True

    # mismatch missing node
    mismatch = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
            "declared_graph": {
                "nodes": ["llm_generation", "accept_path_finalization"],
                "edges": [["llm_generation", "accept_path_finalization"]],
            },
        }
    )
    g = mismatch["i.graph_observed_matches_declared"]
    assert g.passed is False
    assert g.reason == "graph_observed_mismatch"
    # warn-only: not in S2C block
    assert "i.graph_observed_matches_declared" not in S2C_TOPOLOGY_BLOCK


def test_declared_order_index_detects_non_monotonic_span_order() -> None:
    """Producer-declared order_index must drive i.span_order_valid (not list position)."""
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None, "order_index": 2},
                {"name": "final_render", "span_id": "s2", "parent_span_id": "s1", "order_index": 1},
            ],
        }
    )
    assert by["i.span_order_valid"].passed is False
    assert by["i.span_order_valid"].reason == "span_order_non_monotonic"
    assert by["i.span_order_valid"].evidence is not None
    assert by["i.span_order_valid"].evidence.get("indices") == [2, 1]


def test_declared_order_index_detects_parent_before_child_violation() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None, "order_index": 5},
                {"name": "final_render", "span_id": "s2", "parent_span_id": "s1", "order_index": 1},
            ],
            "declared_graph": {
                "nodes": ["llm_generation", "final_render"],
                "edges": [["llm_generation", "final_render"]],
            },
        }
    )
    assert by["i.span_order_valid"].passed is False
    assert by["i.span_order_valid"].reason == "span_order_violation"


def test_dangling_parent_fails_with_multiple_roots() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
                {"name": "final_render", "span_id": "s2", "parent_span_id": "nope"},
            ],
        }
    )
    assert by["i.span_tree_valid"].passed is False
    assert by["i.span_tree_valid"].reason == "multiple_roots"
    assert by["i.span_parentage_valid"].passed is False
    assert by["i.span_parentage_valid"].reason == "dangling_parent"
    assert "nope" in ((by["i.span_parentage_valid"].evidence or {}).get("dangling_parents") or [])


def test_deep_parent_chain_does_not_raise_or_fail_closed() -> None:
    """Iterative cycle detection must tolerate deep valid ID chains."""
    n = 2500
    # regeneration is a legal repeatable span name; avoids singleton-name failures.
    spans = []
    for i in range(n):
        spans.append(
            {
                "name": "llm_generation" if i == 0 else "regeneration",
                "span_id": f"s{i}",
                "parent_span_id": None if i == 0 else f"s{i - 1}",
            }
        )
    by = _score_topo(
        {
            "root_trace_id": "r-deep",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "spans": spans,
        }
    )
    assert by["i.span_tree_valid"].passed is True
    assert by["i.span_parentage_valid"].passed is True
    assert by["i.span_tree_valid"].reason != "family_i_evaluator_error"


def test_optional_declared_graph_nodes_are_excluded_from_required_match() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "observed_spans": ["llm_generation", "final_render"],
            "declared_graph": {
                "nodes": [
                    {"name": "llm_generation"},
                    {"name": "final_render"},
                    {"name": "opik_export", "optional": True},
                ],
                "edges": [["llm_generation", "final_render"]],
            },
        }
    )
    assert by["i.graph_observed_matches_declared"].passed is True


def test_attempt_order_non_decreasing_allows_duplicates_and_flags_regressions() -> None:
    ok = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
            "multi_attempt": True,
            "attempt_indices": [1, 1, 2, 2],
            "session_thread_id": "th-attempts",
        }
    )
    assert ok["i.attempt_order_valid"].passed is True

    bad = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
            "multi_attempt": True,
            "attempt_indices": [2, 1],
            "session_thread_id": "th-attempts-bad",
        }
    )
    assert bad["i.attempt_order_valid"].passed is False
    assert bad["i.attempt_order_valid"].reason == "attempt_order_non_monotonic"


def test_fingerprint_sanitizes_pathlike_unexpected_span_names() -> None:
    # Force a required-span failure so diag_fingerprint_inputs attaches.
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "accept_path_finalization"],
            "observed_spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
                {
                    "name": "/Users/secret/proj/span https://evil.example/x?id=9",
                    "span_id": "s2",
                    "parent_span_id": "s1",
                },
            ],
        }
    )
    req = by["i.required_spans_present"]
    assert req.passed is False
    # Row evidence may retain raw unexpected names for RCA; fingerprint must not.
    assert any("Users/secret" in x for x in ((req.evidence or {}).get("unexpected_spans") or []))
    fp = (req.evidence or {}).get("diag_fingerprint_inputs") or {}
    blob = json.dumps(fp)
    assert "/Users/secret" not in blob
    assert "evil.example" not in blob
    assert any(str(x).startswith("unknown:") for x in (fp.get("unexpected_spans") or []))


def test_normalize_node_supports_index_alias_and_string_nodes() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None, "index": 0},
                {"name": "final_render", "span_id": "s2", "parent_span_id": "s1", "index": 1},
            ],
        }
    )
    assert by["i.span_order_valid"].passed is True

    # string node path still accepted via observed_spans / nodes
    by2 = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "nodes": ["llm_generation", "  "],
        }
    )
    assert by2["i.span_tree_valid"].passed is True


def test_graph_sets_mapping_edges_and_id_aliases() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation", "final_render"],
            "spans": [
                {"span_name": "llm_generation", "id": "s1", "parent_id": None, "order_index": 0},
                {"span_name": "final_render", "id": "s2", "parent_id": "s1", "order_index": 1},
            ],
            "declared_graph": {
                "nodes": [
                    {"id": "llm_generation"},
                    {"name": "final_render"},
                    "opik_export",
                ],
                "edges": [
                    {"from": "llm_generation", "to": "final_render"},
                    {"source": "final_render", "target": "opik_export"},
                ],
            },
        }
    )
    # missing observed opik_export edge/node should mismatch
    g = by["i.graph_observed_matches_declared"]
    assert g.passed is False
    assert g.reason == "graph_observed_mismatch"


def test_id_mode_duplicate_singleton_names_fail_tree() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "spans": [
                {"name": "llm_generation", "span_id": "s1", "parent_span_id": None},
                {"name": "llm_generation", "span_id": "s2", "parent_span_id": "s1"},
            ],
        }
    )
    assert by["i.span_tree_valid"].passed is False
    assert by["i.span_tree_valid"].reason == "duplicate_singleton_span_names"


def test_multi_attempt_without_thread_id_continuity() -> None:
    by = _score_topo(
        {
            "root_trace_id": "r",
            "terminal_state": "ok",
            "required_spans": ["llm_generation"],
            "observed_spans": ["llm_generation"],
            "multi_attempt": True,
            "attempt_indices": [1, 2],
        },
    )
    # no session_thread_id on topology → continuity unresolved / soft when require_topology false
    assert by["i.thread_continuity"].reason in {
        "thread_continuity_unresolved",
        "thread_id_missing",
        "single_attempt_no_continuity_claim",
    }

    # hard fail under require_topology
    b = _bundle_from_fixture(VALID)
    b["topology"] = {
        "root_trace_id": "r",
        "terminal_state": "ok",
        "required_spans": ["llm_generation"],
        "observed_spans": ["llm_generation"],
        "multi_attempt": True,
        "attempt_indices": [1, 2],
    }
    hard = _by(score_family_i(project_score_context(b), require_topology=True))
    assert hard["i.thread_continuity"].passed is False
    assert hard["i.thread_id_present"].passed is False


def test_cross_case_index_present_without_thread_id() -> None:
    b = _bundle_from_fixture(VALID)
    b["topology"] = {
        "root_trace_id": "r",
        "terminal_state": "ok",
        "required_spans": ["llm_generation"],
        "observed_spans": ["llm_generation"],
    }
    index = {"some-thread": ("other",)}
    by = _by(score_family_i(project_score_context(b), session_thread_index=index))
    assert by["i.no_cross_case_contamination"].passed is True
    assert by["i.no_cross_case_contamination"].reason == "cross_case_evidence_unavailable"


def test_build_session_thread_index_skips_blank_case_ids() -> None:
    b = _bundle_from_fixture(VALID)
    b["session_thread_id"] = "t1"
    index = build_session_thread_index(
        [
            ("", b),
            ("   ", b),
            ("case-ok", b),
            ("case-ok", b),  # de-dupe
        ]
    )
    assert index == {"t1": ("case-ok",)}
