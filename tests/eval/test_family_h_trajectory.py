"""Family H trajectory policy sink (R7 / N19.6).

Family H owns the two existing catalog metrics ``h.trajectory_stages_declared``
and ``h.trajectory_stages_observed``. Trajectory evidence is inlined at
``bundle.meta.trajectory``. Missing/incomplete trajectory is an eval-class fail
only under ``require_trajectory`` (suite policy); otherwise advisory. Family I
topology is never used to prove trajectory requirements (plane separation).
"""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.binding.trajectory import build_trajectory_evidence
from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_a import score_family_a
from git_cg.eval.scoring.family_h import score_family_h
from git_cg.eval.scoring.preconditions import evaluate_preconditions
from git_cg.eval.scoring.runner import resolve_require_trajectory

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"

HAPPY_OBSERVED = (
    "diff_extraction",
    "path_classification",
    "intent_ranking",
    "contract_resolution",
    "gold_evaluation",
    "presentation_guard",
    "final_render",
    "accept_path_finalization",
)


def _ctx_with_trajectory(trajectory: dict | None):
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    if trajectory is not None:
        bundle.setdefault("meta", {})["trajectory"] = trajectory
    return project_score_context(bundle)


def _score(ctx, *, require_trajectory: bool):
    pre = evaluate_preconditions(ctx)
    a_scores = score_family_a(ctx)
    h = score_family_h(
        ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="snap@deadbeef",
        offline=True,
        evaluator_errors=[],
        require_trajectory=require_trajectory,
    )
    return {s.metric_id: s for s in h}


def test_complete_trajectory_passes_when_required() -> None:
    traj = build_trajectory_evidence("ev-h1", HAPPY_OBSERVED)
    by = _score(_ctx_with_trajectory(traj), require_trajectory=True)
    assert by["h.trajectory_stages_declared"].passed is True
    assert by["h.trajectory_stages_observed"].passed is True


def test_missing_trajectory_fails_when_required() -> None:
    by = _score(_ctx_with_trajectory(None), require_trajectory=True)
    assert by["h.trajectory_stages_declared"].passed is False
    assert by["h.trajectory_stages_observed"].passed is False
    assert "EVAL_TRAJECTORY_DECLARED" in (by["h.trajectory_stages_declared"].failure_ids or [])
    assert "EVAL_TRAJECTORY_OBSERVED" in (by["h.trajectory_stages_observed"].failure_ids or [])


def test_missing_trajectory_advisory_when_not_required() -> None:
    by = _score(_ctx_with_trajectory(None), require_trajectory=False)
    # Advisory: not required, so absence does not fail the eval-class metric.
    assert by["h.trajectory_stages_declared"].passed is True
    assert by["h.trajectory_stages_observed"].passed is True
    assert by["h.trajectory_stages_declared"].evidence["trajectory_present"] is False


def test_incomplete_trajectory_fails_observed_when_required() -> None:
    # final_render present but accept_path_finalization absent → incomplete.
    traj = build_trajectory_evidence(
        "ev-h2",
        tuple(s for s in HAPPY_OBSERVED if s != "accept_path_finalization"),
    )
    by = _score(_ctx_with_trajectory(traj), require_trajectory=True)
    assert by["h.trajectory_stages_declared"].passed is True
    assert by["h.trajectory_stages_observed"].passed is False
    assert by["h.trajectory_stages_observed"].evidence["meta_complete"] is False


def test_invalid_trajectory_shape_fails_when_required() -> None:
    """Non-list / invalid stage values must not count as present evidence."""
    traj = {
        "schema_version": "trajectory_evidence_v1",
        "id": "ev-bad",
        "declared_stages": "x",
        "observed_stages": "x",
        "meta": {"complete": True},
    }
    by = _score(_ctx_with_trajectory(traj), require_trajectory=True)
    assert by["h.trajectory_stages_declared"].passed is False
    assert by["h.trajectory_stages_observed"].passed is False
    assert by["h.trajectory_stages_declared"].evidence["trajectory_valid"] is False


def test_resolve_require_trajectory_precedence() -> None:
    assert resolve_require_trajectory(True, None) is True
    assert resolve_require_trajectory(False, {"meta": {"require_trajectory": True}}) is False
    assert resolve_require_trajectory(None, {"meta": {"require_trajectory": True}}) is True
    assert resolve_require_trajectory(None, {"meta": {"require_trajectory": "yes"}}) is False
    assert resolve_require_trajectory(None, None) is False


def test_trajectory_not_proven_by_topology() -> None:
    # Plane separation: require_topology must not imply require_trajectory.
    assert resolve_require_trajectory(None, {"meta": {"require_topology": True}}) is False
