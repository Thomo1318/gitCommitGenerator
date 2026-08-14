"""Family A — artifact / binding (offline-honest S2a minimum)."""

from __future__ import annotations

from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.enums import ARTIFACT_CLASS
from git_cg.eval.schema_pack import SchemaPackError, validate_instance
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.result_builder import make_score

FAMILY_A_S2A = (
    "a.bundle_schema_valid",
    "a.artifact_class_known",
    "a.final_message_present",
    "a.binding_unbound_explicit",
    "a.binding_complete",
    "a.final_bytes_stable",
    "a.scored_target_order_ok",
)


def score_family_a(ctx: ScoreContext) -> list[ScoreResultV1]:
    """
    Evaluate Family A artifact and binding conditions for a scoring context.
    
    Parameters:
    	ctx (ScoreContext): Context containing the bundle, artifact classification, binding state, final message, and scoring metadata.
    
    Returns:
    	list[ScoreResultV1]: Results for schema validity, artifact classification, final-message presence, binding status and completeness, byte stability, and scoring-target order.
    """
    scores: list[ScoreResultV1] = []

    schema_ok = False
    schema_errors: list[str] = []
    try:
        validate_instance("ape_bundle_v1", ctx.bundle)
        schema_ok = True
    except SchemaPackError as exc:
        schema_errors.append(str(exc))
    except Exception as exc:
        schema_errors.append(f"{type(exc).__name__}: {exc}")
    scores.append(
        make_score(
            "a.bundle_schema_valid",
            schema_ok,
            reason=None if schema_ok else "bundle_schema_invalid",
            evidence={"errors": schema_errors} if schema_errors else {"schema": "ape_bundle_v1"},
            failure_ids=None if schema_ok else ["EVAL_BUNDLE_SCHEMA"],
            product_authority="git_cg.eval.schema_pack.validate_instance",
        )
    )

    ac = ctx.artifact_class
    ac_ok = isinstance(ac, str) and ac in ARTIFACT_CLASS
    scores.append(
        make_score(
            "a.artifact_class_known",
            ac_ok,
            reason=None if ac_ok else "unknown_artifact_class",
            evidence={"artifact_class": ac},
            failure_ids=None if ac_ok else ["EVAL_ARTIFACT_CLASS_UNKNOWN"],
        )
    )

    fm_ok = bool(ctx.final_message and ctx.final_message.strip())
    scores.append(
        make_score(
            "a.final_message_present",
            fm_ok,
            reason=None if fm_ok else "final_message_absent",
            evidence={
                "byte_len": len(ctx.final_message.encode("utf-8")) if ctx.final_message else 0,
                "content_sha256": ctx.final_message_sha256,
            },
            failure_ids=None if fm_ok else ["EVAL_FINAL_ABSENT"],
        )
    )

    # a.binding_unbound_explicit
    fake_bound = False
    reasons: list[str] = []
    if ctx.bound is False:
        if ctx.artifact_class == "final_accept":
            fake_bound = True
            reasons.append("unbound_final_accept")
        prov = None
        if isinstance(ctx.bundle, dict):
            prov = ctx.bundle.get("provenance_label")
        if prov is None:
            prov = ctx.meta.get("provenance_label")
        if prov == "final_accept":
            fake_bound = True
            reasons.append("unbound_final_accept_provenance")
        if not ctx.unbound_reason:
            fake_bound = True
            reasons.append("missing_unbound_reason")
    unbound_ok = not fake_bound
    scores.append(
        make_score(
            "a.binding_unbound_explicit",
            unbound_ok,
            reason=None if unbound_ok else ",".join(reasons) or "fake_bound",
            evidence={
                "bound": ctx.bound,
                "unbound_reason": ctx.unbound_reason,
                "artifact_class": ctx.artifact_class,
            },
            failure_ids=None if unbound_ok else ["EVAL_FAKE_BOUND"],
        )
    )

    if ctx.bound:
        missing: list[str] = []
        if not ctx.final_message:
            missing.append("final_message")
        if ctx.artifact_class != "final_accept":
            missing.append("artifact_class!=final_accept")
        bind_ok = not missing
        scores.append(
            make_score(
                "a.binding_complete",
                bind_ok,
                reason=None if bind_ok else "binding_incomplete",
                evidence={"missing_fields": missing},
                failure_ids=None if bind_ok else ["EVAL_BINDING_INCOMPLETE"],
            )
        )
    else:
        bind_ok = bool(ctx.unbound_reason) and unbound_ok
        scores.append(
            make_score(
                "a.binding_complete",
                bind_ok,
                reason=None if bind_ok else "unbound_incomplete",
                evidence={"bound": False, "unbound_reason": ctx.unbound_reason},
                failure_ids=None if bind_ok else ["EVAL_BINDING_INCOMPLETE"],
            )
        )

    stable = True
    if ctx.final_message and ctx.final_message_sha256:
        stable = message_sha256(ctx.final_message) == ctx.final_message_sha256
    elif not ctx.final_message:
        stable = False
    scores.append(
        make_score(
            "a.final_bytes_stable",
            stable,
            reason=None if stable else "final_bytes_mismatch_or_absent",
            evidence={"final_message_sha256": ctx.final_message_sha256},
            failure_ids=None if stable else ["EVAL_FINAL_BYTES_MISMATCH"],
        )
    )

    # FIND-027 order: final_message primary; product_card only as explicit fallback
    order_ok = ctx.scored_target in {"final_message", "missing"} or (
        ctx.scored_target == "product_card" and not (ctx.final_message and str(ctx.final_message).strip())
    )
    scores.append(
        make_score(
            "a.scored_target_order_ok",
            order_ok,
            reason=None if order_ok else "wrong_score_target_order",
            evidence={"scored_target": ctx.scored_target, "warnings": list(ctx.warnings)},
            failure_ids=None if order_ok else ["EVAL_SCORE_TARGET_ORDER"],
        )
    )

    return scores
