"""Gate composition for S2a (required-block only; C-prime ignored)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.result_builder import make_score

# S2a required metric block — catalog has no require_block field; suite may override.
S2A_REQUIRE_BLOCK: tuple[str, ...] = (
    # Family A
    "a.bundle_schema_valid",
    "a.artifact_class_known",
    "a.final_message_present",
    "a.binding_unbound_explicit",
    "a.binding_complete",
    "a.final_bytes_stable",
    "a.scored_target_order_ok",
    # Family B
    "b.header_shape",
    "b.gitmoji_present",
    "b.cc_type_known",
    "b.scope_shape",
    "b.subject_length",
    "b.trailers_parse",
    "b.trailers_issue_ref",
    "b.trailers_semver",
    "b.trailers_change_types",
    "b.trailers_changelog_groups",
    "b.structured_envelope",
    # Family D core
    "d.gold_report_ok",
    "d.strict_fail_set",
    "d.skeleton_fallback_final",
    "d.process_meta_body",
    # Family H core
    "h.catalog_pinned",
    "h.suite_snapshot_pinned",
    "h.offline_complete",
    "h.score_envelope_valid",
    "h.evaluator_error_free",
    "h.eval_input_nonempty",
    "h.eval_error_fanout_bounded",
    "h.pin_integrity",
)

_IGNORE_FAMILY_PREFIXES = (
    "c.",
    "e.",
    "f.",
    "g.",
    "lab.",
    "human.",
    "nlp.",
    "export.",
)


def _is_advisory(metric_id: str) -> bool:
    """True for C-prime / lab / human / NLP / export metrics (never gate veto)."""
    return metric_id.startswith(_IGNORE_FAMILY_PREFIXES) or metric_id.startswith("cprime")


def compose_gates(
    results: Sequence[ScoreResultV1],
    *,
    require_block: Iterable[str] | None = None,
    bound: bool | None = None,
    require_topology: bool = False,
    gold_mode: str = "strict",
) -> list[ScoreResultV1]:
    """Compose ``gate.*`` metrics from score rows.

    ``gate.deterministic_pass`` uses only metrics in ``require_block``
    (default ``S2A_REQUIRE_BLOCK``). C-prime / lab / human / NLP / export never
    veto. Missing required metrics fail closed. Golden promotion additionally
    requires an explicit passing skeleton row (not merely require_block absence).
    Semantic cohort stays false while C-prime is deferred (S2b).
    """
    req = tuple(require_block) if require_block is not None else S2A_REQUIRE_BLOCK
    by_id: dict[str, ScoreResultV1] = {r.metric_id: r for r in results}

    missing: list[str] = []
    failed: list[str] = []
    ignored_failures: list[str] = []

    for mid, row in by_id.items():
        if mid.startswith("gate."):
            continue
        if _is_advisory(mid) and mid not in req and row.passed is False:
            ignored_failures.append(mid)

    for mid in req:
        row = by_id.get(mid)
        if row is None:
            missing.append(mid)
            continue
        if row.passed is False or (
            row.passed is None and getattr(row.polarity, "value", str(row.polarity)) == "pass_fail"
        ):
            failed.append(mid)

    det_ok = not missing and not failed

    gates: list[ScoreResultV1] = [
        make_score(
            "gate.deterministic_pass",
            det_ok,
            reason=None if det_ok else "require_block_failed",
            evidence={
                "require_block": list(req),
                "missing": missing,
                "failed": failed,
                "ignored_advisory_failures": ignored_failures,
                "bound": bound,
                "require_topology": require_topology,
                "gold_mode": gold_mode,
            },
            failure_ids=None if det_ok else (["GATE_REQUIRE_BLOCK"] + failed + [f"missing:{m}" for m in missing]),
        )
    ]

    gold_row = by_id.get("d.gold_report_ok")
    skel_row = by_id.get("d.skeleton_fallback_final")
    gold_pass = bool(gold_row and gold_row.passed)
    # Fail-closed: missing skeleton row must block promotion even if a custom
    # require_block omitted ``d.skeleton_fallback_final``.
    skel_clean = bool(skel_row and skel_row.passed)
    promo_ok = det_ok and gold_pass and skel_clean and (bound is not False)
    gates.append(
        make_score(
            "gate.golden_promotion_eligible",
            promo_ok,
            reason=None if promo_ok else "promotion_blocked",
            evidence={
                "deterministic_pass": det_ok,
                "gold_ok": gold_pass,
                "skeleton_clean": skel_clean,
                "bound": bound,
            },
            failure_ids=None if promo_ok else ["GATE_PROMOTION_BLOCKED"],
        )
    )

    # S2a does not run C-prime — offline-honest False
    gates.append(
        make_score(
            "gate.semantic_cohort_eligible",
            False,
            passed=False,
            reason="cprime_deferred_s2a",
            evidence={"cprime_ran": False},
            failure_ids=["GATE_CPRIME_DEFERRED"],
        )
    )

    return gates
