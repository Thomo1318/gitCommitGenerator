"""Family H — harness / offline / pin / envelope health."""

from __future__ import annotations

from typing import Any

from git_cg.eval.binding.trajectory import TrajectoryError, validate_observed_stages
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import SchemaPackError, validate_instance
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext, live_pin_refs
from git_cg.eval.scoring.preconditions import PreconditionResult
from git_cg.eval.scoring.result_builder import make_score

FAMILY_H_S2A = (
    "h.catalog_pinned",
    "h.suite_snapshot_pinned",
    "h.offline_complete",
    "h.score_envelope_valid",
    "h.evaluator_error_free",
    "h.eval_input_nonempty",
    "h.eval_input_size_ok",
    "h.eval_error_fanout_bounded",
    "h.pin_integrity",
    "h.online_scores_match_product_card",
)

# S3 (R7/N19.6): Family H owns the trajectory completeness/policy sink. These
# consume the two existing catalog metrics — no new catalog ids are invented.
FAMILY_H_S3 = (
    "h.trajectory_stages_declared",
    "h.trajectory_stages_observed",
)


def score_family_h(
    ctx: ScoreContext,
    *,
    pre: PreconditionResult,
    family_scores: list[ScoreResultV1],
    suite_snapshot_pin: str | None,
    offline: bool = True,
    evaluator_errors: list[str] | None = None,
    require_trajectory: bool = False,
) -> list[ScoreResultV1]:
    """
    Emit Family H metrics for pin integrity, offline execution, score validity, evaluation errors, input handling, product-card consistency, structured bundle compliance, and trajectory evidence.
    
    Parameters:
        ctx (ScoreContext): Evaluation context containing bundle metadata and product-card data.
        pre (PreconditionResult): Input precondition results used to report input validity.
        family_scores (list[ScoreResultV1]): Previously emitted family scores to validate.
        suite_snapshot_pin (str | None): Expected suite snapshot pin.
        offline (bool): Whether evaluation completed without online access.
        evaluator_errors (list[str] | None): Evaluator errors to report.
        require_trajectory (bool): Whether missing or incomplete trajectory evidence is an evaluation failure.
    
    Returns:
        list[ScoreResultV1]: Family H metric results.
    """
    errors = list(evaluator_errors or [])
    scores: list[ScoreResultV1] = []

    pack = schema_pack_pin()
    catalog = metric_catalog_pin()
    pin_ok = bool(pack and catalog)
    # Bundle pin match when present
    if ctx.schema_pack and ctx.schema_pack != pack:
        pin_ok = False
    if ctx.metric_catalog and ctx.metric_catalog != catalog:
        pin_ok = False

    scores.append(
        make_score(
            "h.catalog_pinned",
            bool(catalog),
            reason=None if catalog else "catalog_pin_missing",
            evidence={"metric_catalog": catalog},
            failure_ids=None if catalog else ["EVAL_CATALOG_PIN"],
            product_authority="git_cg.eval.pins.metric_catalog_pin",
        )
    )

    snap_ok = bool(suite_snapshot_pin and str(suite_snapshot_pin).strip())
    scores.append(
        make_score(
            "h.suite_snapshot_pinned",
            snap_ok,
            reason=None if snap_ok else "suite_snapshot_missing",
            evidence={"suite_snapshot_pin": suite_snapshot_pin},
            failure_ids=None if snap_ok else ["EVAL_SUITE_SNAPSHOT_PIN"],
        )
    )

    scores.append(
        make_score(
            "h.offline_complete",
            offline,
            reason=None if offline else "online_path_detected",
            evidence={"offline": offline, "network_forbidden": True},
            failure_ids=None if offline else ["EVAL_OFFLINE_INCOMPLETE"],
        )
    )

    env_bad: list[str] = []
    for s in family_scores:
        try:
            payload = s.model_dump(mode="json")
            ScoreResultV1.model_validate(payload)
        except Exception as exc:
            env_bad.append(f"{s.metric_id}: {exc}")
    env_ok = not env_bad
    scores.append(
        make_score(
            "h.score_envelope_valid",
            env_ok,
            reason=None if env_ok else "invalid_score_envelope",
            evidence={"invalid_count": len(env_bad), "samples": env_bad[:5]},
            failure_ids=None if env_ok else ["EVAL_SCORE_ENVELOPE"],
            product_authority="git_cg.eval.score_result.ScoreResultV1",
        )
    )

    err_free = len(errors) == 0
    scores.append(
        make_score(
            "h.evaluator_error_free",
            err_free,
            reason=None if err_free else "evaluator_exceptions",
            evidence={"errors": errors[:10], "count": len(errors)},
            failure_ids=None if err_free else ["EVAL_EVALUATOR_ERROR"],
        )
    )

    scores.append(
        make_score(
            "h.eval_input_nonempty",
            pre.input_nonempty,
            reason=None if pre.input_nonempty else (pre.reason or "empty_input"),
            evidence={
                "input_nonempty": pre.input_nonempty,
                "input_byte_len": ctx.input_size_bytes,
                "scored_target": ctx.scored_target,
            },
            failure_ids=["FIND-026", "EVAL_INPUT_EMPTY"] if not pre.input_nonempty else None,
        )
    )

    scores.append(
        make_score(
            "h.eval_input_size_ok",
            pre.input_size_ok,
            reason=None if pre.input_size_ok else (pre.reason or "oversize_input"),
            evidence={
                "input_size_ok": pre.input_size_ok,
                "input_byte_len": ctx.input_size_bytes,
                "max_eval_bytes": ctx.max_eval_bytes,
            },
            failure_ids=["FIND-026", "EVAL_INPUT_OVERSIZE"] if not pre.input_size_ok else None,
        )
    )

    # FIND-026: message-dependent families must not clone the input failure.
    input_fail_rows = [
        s
        for s in family_scores
        if s.failure_ids and any(str(fid).startswith("EVAL_INPUT") or str(fid) == "FIND-026" for fid in s.failure_ids)
    ]
    fanout_ok = len(input_fail_rows) == 0
    scores.append(
        make_score(
            "h.eval_error_fanout_bounded",
            fanout_ok,
            reason=None if fanout_ok else "input_failure_fanout",
            evidence={
                "short_circuit": pre.short_circuit,
                "leaked_input_fail_rows": len(input_fail_rows),
            },
            failure_ids=None if fanout_ok else ["FIND-026"],
        )
    )

    scores.append(
        make_score(
            "h.pin_integrity",
            pin_ok,
            reason=None if pin_ok else "pin_mismatch_or_missing",
            evidence={
                "schema_pack": pack,
                "metric_catalog": catalog,
                "bundle_schema_pack": ctx.schema_pack,
                "bundle_metric_catalog": ctx.metric_catalog,
                "pin_refs": live_pin_refs(),
            },
            failure_ids=None if pin_ok else ["EVAL_PIN_INTEGRITY"],
            product_authority="git_cg.eval.pins",
        )
    )

    card_match = True
    mismatches: list[dict[str, Any]] = []
    card = ctx.product_card if ctx.product_card else None
    if card and isinstance(card, dict):
        card_vals = card.get("metrics") or card.get("results") or card
        if isinstance(card_vals, dict):
            by_id = {s.metric_id: s for s in family_scores}
            for mid, cval in card_vals.items():
                if mid not in by_id:
                    continue
                s = by_id[mid]
                if isinstance(cval, bool) and s.passed is not None and bool(s.passed) != cval:
                    card_match = False
                    mismatches.append({"metric_id": mid, "card": cval, "score_passed": s.passed})
                elif isinstance(cval, dict) and "passed" in cval and s.passed is not None:
                    if bool(s.passed) != bool(cval["passed"]):
                        card_match = False
                        mismatches.append(
                            {
                                "metric_id": mid,
                                "card": cval["passed"],
                                "score_passed": s.passed,
                            }
                        )
    # FIND-002: structured bundle / score envelope compliance.
    # ctx.bundle may carry post-encode injection keys (score_card/files) that are
    # not schema fields; strip them for validation only — leave ctx.bundle intact.
    structured_ok = True
    structured_errors: list[str] = []
    try:
        bundle_for_schema = {k: v for k, v in dict(ctx.bundle or {}).items() if k not in {"score_card", "files"}}
        validate_instance("ape_bundle_v1", bundle_for_schema)
    except SchemaPackError as exc:
        structured_ok = False
        structured_errors.append(f"bundle:{exc}")
    except Exception as exc:
        structured_ok = False
        structured_errors.append(f"bundle:{type(exc).__name__}: {exc}")
    # Prior family score envelopes must already be ScoreResultV1-valid
    for s in family_scores:
        try:
            ScoreResultV1.model_validate(s.model_dump(mode="json"))
        except Exception as exc:
            structured_ok = False
            structured_errors.append(f"score:{s.metric_id}:{exc}")
            break
    scores.append(
        make_score(
            "h.structured_bundle_compliance",
            structured_ok,
            reason=None if structured_ok else "structured_bundle_noncompliant",
            evidence={"errors": structured_errors[:8], "finding": "FIND-002"},
            failure_ids=None if structured_ok else ["FIND-002", "EVAL_STRUCTURED_BUNDLE"],
            product_authority="git_cg.eval.schema_pack.validate_instance+ScoreResultV1",
        )
    )

    scores.append(
        make_score(
            "h.online_scores_match_product_card",
            card_match,
            reason=None if card_match else "product_card_mismatch",
            evidence={"mismatches": mismatches, "has_card": bool(card)},
            failure_ids=None if card_match else ["EVAL_PRODUCT_CARD_MISMATCH"],
        )
    )

    # S3 (R7/N19.6): trajectory completeness/policy sink. Trajectory evidence
    # is inlined at bundle.meta.trajectory (surfaced via ctx.meta["trajectory"]).
    # Family H owns this plane; Family I never consumes trajectory as topology.
    scores.extend(_score_trajectory(ctx, require_trajectory=require_trajectory))

    return scores


def _score_trajectory(ctx: ScoreContext, *, require_trajectory: bool) -> list[ScoreResultV1]:
    """Emit the two S3 trajectory metrics (existing catalog ids only).

    ``h.trajectory_stages_declared`` — declared stage list is present and
    non-empty. ``h.trajectory_stages_observed`` — observed stages are present
    and behaviourally complete (``meta.complete``). Both are eval-class signals:
    they fail only when ``require_trajectory`` is set (suite policy) and the
    evidence is missing/incomplete; otherwise they are advisory passes.
    """
    trajectory = (ctx.meta or {}).get("trajectory")
    declared: list[Any] = []
    observed: list[Any] = []
    meta_complete = False
    trajectory_valid = False
    present = isinstance(trajectory, dict)
    if present:
        raw_declared = trajectory.get("declared_stages")
        raw_observed = trajectory.get("observed_stages")
        traj_meta = trajectory.get("meta")
        if isinstance(raw_declared, list) and isinstance(raw_observed, list):
            try:
                declared = validate_observed_stages(raw_declared)
                observed = validate_observed_stages(raw_observed)
                trajectory_valid = True
            except TrajectoryError:
                declared = []
                observed = []
                trajectory_valid = False
        meta_complete = bool(traj_meta.get("complete")) if isinstance(traj_meta, dict) else False

    declared_ok = trajectory_valid and bool(declared)
    observed_ok = trajectory_valid and bool(observed) and meta_complete

    declared_pass = declared_ok or not require_trajectory
    observed_pass = observed_ok or not require_trajectory

    return [
        make_score(
            "h.trajectory_stages_declared",
            declared_pass,
            reason=None if declared_ok else "trajectory_declared_missing",
            evidence={
                "trajectory_present": present,
                "trajectory_valid": trajectory_valid,
                "declared_count": len(declared),
                "require_trajectory": require_trajectory,
            },
            failure_ids=None if declared_pass else ["EVAL_TRAJECTORY_DECLARED"],
        ),
        make_score(
            "h.trajectory_stages_observed",
            observed_pass,
            reason=None if observed_ok else "trajectory_observed_incomplete",
            evidence={
                "trajectory_present": present,
                "trajectory_valid": trajectory_valid,
                "observed_count": len(observed),
                "meta_complete": meta_complete,
                "require_trajectory": require_trajectory,
            },
            failure_ids=None if observed_pass else ["EVAL_TRAJECTORY_OBSERVED"],
        ),
    ]
