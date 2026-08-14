"""Family H — harness / pins / offline health."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_a import score_family_a
from git_cg.eval.scoring.family_h import score_family_h
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
