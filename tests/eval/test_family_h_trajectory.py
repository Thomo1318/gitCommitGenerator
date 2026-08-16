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
    """Project the valid fixture, optionally injecting ``meta.trajectory``."""
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    if trajectory is not None:
        bundle.setdefault("meta", {})["trajectory"] = trajectory
    return project_score_context(bundle)


def _score(ctx, *, require_trajectory: bool):
    """Run Family H after A/preconditions; return scores keyed by metric id."""
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
    # suite present but meta is non-mapping → fall through to False (81->85)
    assert resolve_require_trajectory(None, {"meta": "not-a-mapping"}) is False
    assert resolve_require_trajectory(None, {"meta": None}) is False
    assert resolve_require_trajectory(None, {}) is False


def test_trajectory_not_proven_by_topology() -> None:
    # Plane separation: require_topology must not imply require_trajectory.
    assert resolve_require_trajectory(None, {"meta": {"require_topology": True}}) is False


def test_unknown_stage_list_is_invalid_when_required() -> None:
    traj = {
        "schema_version": "trajectory_evidence_v1",
        "id": "ev-unknown",
        "declared_stages": ["diff_extraction", "not_a_real_stage"],
        "observed_stages": ["diff_extraction", "not_a_real_stage"],
        "meta": {"complete": True},
    }
    by = _score(_ctx_with_trajectory(traj), require_trajectory=True)
    assert by["h.trajectory_stages_declared"].passed is False
    assert by["h.trajectory_stages_observed"].passed is False
    assert by["h.trajectory_stages_declared"].evidence["trajectory_valid"] is False


def test_pin_mismatch_marks_pin_integrity_false() -> None:
    traj = build_trajectory_evidence("ev-pin", HAPPY_OBSERVED)
    ctx = _ctx_with_trajectory(traj)
    # Force bundle pin fields away from live pins.
    object.__setattr__(ctx, "schema_pack", "schema_pack_v1@deadbeef-not-live")
    object.__setattr__(ctx, "metric_catalog", "metric_catalog_v1@deadbeef-not-live")
    by = _score(ctx, require_trajectory=False)
    assert by["h.pin_integrity"].passed is False
    assert "EVAL_PIN_INTEGRITY" in (by["h.pin_integrity"].failure_ids or [])


def test_score_bundle_honours_require_trajectory_flag() -> None:
    """Runner must thread require_trajectory into Family H (R7/N19.6)."""
    import json

    from git_cg.eval.scoring.runner import score_bundle

    fx = json.loads(VALID.read_text(encoding="utf-8"))
    bundle = encode_fixture(fx)["bundle"]
    # No trajectory evidence in the fixture bundle.
    result = score_bundle(bundle, suite_snapshot_pin="snap@x", require_trajectory=True)
    by = result.by_id()
    assert by["h.trajectory_stages_declared"].passed is False
    assert by["h.trajectory_stages_observed"].passed is False


def test_family_h_structured_compliance_and_card_edges(monkeypatch) -> None:
    """Cover structured-bundle exception paths + product-card compare branches."""
    from git_cg.eval.schema_pack import SchemaPackError
    from git_cg.eval.score_result import ScoreResultV1
    from git_cg.eval.scoring.context import ScoreContext
    from git_cg.eval.scoring.result_builder import make_score

    traj = build_trajectory_evidence("ev-struct", HAPPY_OBSERVED)
    ctx = _ctx_with_trajectory(traj)
    pre = evaluate_preconditions(ctx)
    a_scores = score_family_a(ctx)

    # SchemaPackError path for structured bundle compliance.
    monkeypatch.setattr(
        "git_cg.eval.scoring.family_h.validate_instance",
        lambda *_a, **_k: (_ for _ in ()).throw(SchemaPackError("bad bundle")),
    )
    by = _score(ctx, require_trajectory=False)
    assert by["h.structured_bundle_compliance"].passed is False
    assert "FIND-002" in (by["h.structured_bundle_compliance"].failure_ids or [])

    # Generic exception path.
    monkeypatch.setattr(
        "git_cg.eval.scoring.family_h.validate_instance",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("explode")),
    )
    by2 = _score(ctx, require_trajectory=False)
    assert by2["h.structured_bundle_compliance"].passed is False
    assert any("RuntimeError" in e for e in (by2["h.structured_bundle_compliance"].evidence or {}).get("errors") or [])

    # Restore validator and force prior-score envelope failure in structured loop.
    monkeypatch.setattr(
        "git_cg.eval.scoring.family_h.validate_instance",
        lambda *_a, **_k: None,
    )

    class _BadScore:
        metric_id = "ghost.metric"
        failure_ids = None
        passed = True

        def model_dump(self, mode: str = "json"):
            raise ValueError("cannot dump score")

    h3 = score_family_h(
        ctx,
        pre=pre,
        family_scores=[_BadScore()],  # type: ignore[list-item]
        suite_snapshot_pin="snap@x",
        offline=True,
        require_trajectory=False,
    )
    by3 = {s.metric_id: s for s in h3}
    assert by3["h.score_envelope_valid"].passed is False
    assert by3["h.structured_bundle_compliance"].passed is False

    # Product-card bool + dict mismatch branches.
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
                "a.final_message_present": False,
                "a.artifact_class_known": {"passed": False},
                "missing.metric": True,
            }
        },
        scored_target=ctx.scored_target,
        meta=ctx.meta,
    )
    h4 = score_family_h(
        card_ctx,
        pre=pre,
        family_scores=a_scores,
        suite_snapshot_pin="snap@x",
        offline=True,
        require_trajectory=False,
    )
    by4 = {s.metric_id: s for s in h4}
    assert by4["h.online_scores_match_product_card"].passed is False
    assert len((by4["h.online_scores_match_product_card"].evidence or {}).get("mismatches") or []) >= 1

    # Envelope exception path via model_validate failure on a real ScoreResult dump.
    good = make_score("a.final_message_present", True, passed=True)
    real_validate = ScoreResultV1.model_validate

    def _validate_once(payload):
        if getattr(_validate_once, "n", 0) == 0:
            _validate_once.n = 1  # type: ignore[attr-defined]
            raise ValueError("envelope invalid")
        return real_validate(payload)

    monkeypatch.setattr(ScoreResultV1, "model_validate", staticmethod(_validate_once))
    h5 = score_family_h(
        ctx,
        pre=pre,
        family_scores=[good],
        suite_snapshot_pin="snap@x",
        offline=True,
        require_trajectory=False,
    )
    by5 = {s.metric_id: s for s in h5}
    assert by5["h.score_envelope_valid"].passed is False
