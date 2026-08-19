"""Family H — harness / pins / offline health."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_a import score_family_a
from git_cg.eval.scoring.family_h import (
    FAMILY_H_CPRIME,
    score_family_h,
    score_family_h_cprime,
)
from git_cg.eval.scoring.preconditions import evaluate_preconditions

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def test_family_h_core_metrics_on_valid() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    ctx = project_score_context(bundle)
    pre = evaluate_preconditions(ctx)
    a_scores = score_family_a(ctx)
    h = score_family_h(
        ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="snap@deadbeef",
        offline=True,
        evaluator_errors=[],
    )
    by = {s.metric_id: s for s in h}
    assert by["h.catalog_pinned"].passed is True
    assert by["h.suite_snapshot_pinned"].passed is True
    assert by["h.offline_complete"].passed is True
    assert by["h.score_envelope_valid"].passed is True
    assert by["h.evaluator_error_free"].passed is True
    assert by["h.eval_input_nonempty"].passed is True
    assert by["h.eval_input_size_ok"].passed is True
    assert by["h.eval_error_fanout_bounded"].passed is True
    assert by["h.pin_integrity"].passed is True


def test_family_h_missing_snapshot_pin_fails() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    ctx = project_score_context(bundle)
    pre = evaluate_preconditions(ctx)
    h = score_family_h(
        ctx,
        pre=pre,
        family_scores=[],
        suite_snapshot_pin=None,
        offline=True,
    )
    by = {s.metric_id: s for s in h}
    assert by["h.suite_snapshot_pinned"].passed is False


def test_family_h_online_flag_fails_offline_complete() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    ctx = project_score_context(bundle)
    pre = evaluate_preconditions(ctx)
    h = score_family_h(
        ctx,
        pre=pre,
        family_scores=[],
        suite_snapshot_pin="x",
        offline=False,
    )
    by = {s.metric_id: s for s in h}
    assert by["h.offline_complete"].passed is False


def _by_id(scores):
    return {s.metric_id: s for s in scores}


def test_family_h_does_not_emit_cprime_metrics_without_lane_c_args() -> None:
    """Pre-Lane-C Family H must not emit S5 honesty metrics by default."""
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    ctx = project_score_context(bundle)
    pre = evaluate_preconditions(ctx)
    h = score_family_h(
        ctx,
        pre=pre,
        family_scores=[],
        suite_snapshot_pin="snap@1",
        offline=True,
    )
    ids = {s.metric_id for s in h}
    assert ids.isdisjoint(set(FAMILY_H_CPRIME))


def test_family_h_cprime_not_run_is_honest_fail() -> None:
    """Disabled / absent Lane C must never green-by-absence (D39)."""
    scores = score_family_h_cprime(
        suite_snapshot_pin="snap@1",
        lane_c_run_evidence={"lane_c_enabled": False},
        lane_c_rows=[],
    )
    assert [s.metric_id for s in scores] == list(FAMILY_H_CPRIME)
    for s in scores:
        assert s.passed is False
        assert s.reason == "lane_c_not_run"
        assert s.failure_ids == ["EVAL_LANE_C_NOT_RUN"]
        assert s.evidence.get("honest_not_run") is True


def test_family_h_cprime_not_run_when_evidence_absent() -> None:
    scores = score_family_h_cprime(suite_snapshot_pin=None)
    by = _by_id(scores)
    assert by["h.judge_input_isolated"].passed is False
    assert by["h.prompt_pack_pinned"].reason == "lane_c_not_run"


def test_family_h_cprime_happy_path_all_pass() -> None:
    digest = "a" * 64
    pin = f"prompt_pack_v1@{digest}"
    scores = score_family_h_cprime(
        suite_snapshot_pin="suite@abc123",
        lane_c_run_evidence={
            "lane_c_enabled": True,
            "cprime_attempted": True,
            "invoked": True,
            "scored_count": 1,
            "cprime_ran": True,
            "judge_input_isolated": True,
            "judge_input_projected": True,
            "judge_input_present": True,
            "pack_identity": pin,
            "content_sha256": digest,
            "universe_fingerprint": {
                "status": "pinned",
                "root_present": True,
                "pinned": True,
            },
        },
        lane_c_rows=[],
    )
    by = _by_id(scores)
    assert by["h.judge_input_isolated"].passed is True
    assert by["h.prompt_pack_pinned"].passed is True
    assert by["h.prompt_pack_hash_known"].passed is True
    assert by["h.prompt_pack_suite_fresh"].passed is True


def test_family_h_cprime_missing_pack_pin_fails() -> None:
    scores = score_family_h_cprime(
        suite_snapshot_pin="suite@1",
        lane_c_run_evidence={
            "lane_c_enabled": True,
            "cprime_attempted": True,
            "judge_input_isolated": True,
            "judge_input_projected": True,
        },
    )
    by = _by_id(scores)
    assert by["h.prompt_pack_pinned"].passed is False
    assert by["h.prompt_pack_pinned"].reason == "prompt_pack_pin_missing"
    assert by["h.prompt_pack_hash_known"].passed is False
    assert by["h.prompt_pack_hash_known"].reason == "prompt_pack_hash_missing"
    assert by["h.prompt_pack_suite_fresh"].passed is False
    assert by["h.prompt_pack_suite_fresh"].reason == "prompt_pack_pin_missing"


def test_family_h_cprime_missing_suite_snapshot_fails_freshness() -> None:
    digest = "b" * 64
    pin = f"prompt_pack_v1@{digest}"
    scores = score_family_h_cprime(
        suite_snapshot_pin=None,
        lane_c_run_evidence={
            "lane_c_enabled": True,
            "cprime_attempted": True,
            "judge_input_isolated": True,
            "pack_identity": pin,
            "content_sha256": digest,
        },
    )
    by = _by_id(scores)
    assert by["h.prompt_pack_pinned"].passed is True
    assert by["h.prompt_pack_hash_known"].passed is True
    assert by["h.prompt_pack_suite_fresh"].passed is False
    assert by["h.prompt_pack_suite_fresh"].reason == "suite_snapshot_missing_for_pack"


def test_family_h_cprime_isolation_failure() -> None:
    scores = score_family_h_cprime(
        suite_snapshot_pin="suite@1",
        lane_c_run_evidence={
            "lane_c_enabled": True,
            "cprime_attempted": True,
            "judge_input_isolated": False,
            "judge_input_projected": False,
            "judge_input_skip_code": "parse_error",
            "judge_input_error": "isolation: gold field leaked into judge input",
            "pack_identity": f"prompt_pack_v1@{'c' * 64}",
            "content_sha256": "c" * 64,
        },
    )
    by = _by_id(scores)
    assert by["h.judge_input_isolated"].passed is False
    assert by["h.judge_input_isolated"].reason == "judge_input_isolation_failed"
    assert by["h.judge_input_isolated"].failure_ids == ["EVAL_JUDGE_INPUT_ISOLATION"]


def test_family_h_cprime_host_guard_empty_input_keeps_isolation() -> None:
    """empty_input / oversize_input are host guards, not isolation leaks."""
    scores = score_family_h_cprime(
        suite_snapshot_pin="suite@1",
        lane_c_run_evidence={
            "lane_c_enabled": True,
            "cprime_attempted": True,
            "judge_input_skip_code": "empty_input",
            "judge_input_projected": False,
            "pack_identity": f"prompt_pack_v1@{'d' * 64}",
            "content_sha256": "d" * 64,
        },
    )
    by = _by_id(scores)
    assert by["h.judge_input_isolated"].passed is True


def test_family_h_cprime_unpinned_universe_fails_pin_metric() -> None:
    digest = "e" * 64
    scores = score_family_h_cprime(
        suite_snapshot_pin="suite@1",
        lane_c_run_evidence={
            "lane_c_enabled": True,
            "cprime_attempted": True,
            "judge_input_isolated": True,
            "pack_identity": f"prompt_pack_v1@{digest}",
            "content_sha256": digest,
            "universe_fingerprint": {
                "status": "unpinned",
                "root_present": True,
                "pinned": False,
            },
        },
    )
    by = _by_id(scores)
    assert by["h.prompt_pack_pinned"].passed is False
    assert by["h.prompt_pack_pinned"].reason == "universe_fingerprint_unpinned"


def test_family_h_cprime_via_score_family_h_optional_args() -> None:
    """Direct score_family_h path can emit C' honesty when evidence is supplied."""
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    ctx = project_score_context(bundle)
    pre = evaluate_preconditions(ctx)
    h = score_family_h(
        ctx,
        pre=pre,
        family_scores=[],
        suite_snapshot_pin="snap@1",
        offline=True,
        lane_c_run_evidence={"lane_c_enabled": False},
        lane_c_rows=[],
    )
    by = _by_id(h)
    for mid in FAMILY_H_CPRIME:
        assert mid in by
        assert by[mid].passed is False
        assert by[mid].reason == "lane_c_not_run"
