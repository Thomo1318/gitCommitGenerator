"""Family D — gold bridge fan-out from runner-owned GoldSlot."""

from __future__ import annotations

from collections.abc import Callable

from git_cg.commit_gold import GoldReport
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.gold_slot import GoldSlot, build_gold_slot
from git_cg.eval.scoring.product_bridges import (
    GOLD_CODE_TO_D_METRIC,
    RANKED_DEPENDENT_GOLD_CODES,
)
from git_cg.eval.scoring.result_builder import make_score, metric_row
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan

FAMILY_D_S2A = (
    "d.gold_report_ok",
    "d.strict_fail_set",
    "d.skeleton_fallback_final",
    "d.process_meta_body",
)

FAMILY_D_MAPPED = tuple(GOLD_CODE_TO_D_METRIC.values())

GoldBridge = Callable[[CommitPlan, DiffSignals, str], tuple[GoldReport, frozenset[str], bool]]

_PA = "git_cg.commit_gold.check_commit_gold"


def _metric_exists(metric_id: str) -> bool:
    """True when ``metric_id`` exists in the frozen S0 catalog."""
    return metric_row(metric_id) is not None


def _unevaluable_core(reason: str, *, evidence: dict | None = None) -> list[ScoreResultV1]:
    """Emit core D rows as failed/unevaluable — never empty-input gold passes (D11/T3)."""
    ev = {"called": False, "unevaluable": True, **(evidence or {})}
    return [
        make_score(
            "d.gold_report_ok",
            False,
            reason=reason,
            evidence=ev,
            failure_ids=["EVAL_GOLD_SKIPPED"],
            product_authority=_PA,
        ),
        make_score(
            "d.strict_fail_set",
            0,
            passed=False,
            reason=reason,
            evidence={**ev, "strict_hits": [], "count": 0},
            failure_ids=["EVAL_GOLD_SKIPPED"],
            product_authority="git_cg.commit_gold.STRICT_FAIL_CODES",
        ),
        make_score(
            "d.skeleton_fallback_final",
            False,
            passed=False,
            reason=reason,
            evidence={**ev, "present": None},
            failure_ids=["EVAL_GOLD_SKIPPED"],
            product_authority=_PA,
        ),
        make_score(
            "d.process_meta_body",
            False,
            passed=False,
            reason=reason,
            evidence={**ev, "present": None},
            failure_ids=["EVAL_GOLD_SKIPPED"],
            product_authority=_PA,
        ),
    ]


def score_family_d(
    ctx: ScoreContext,
    *,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    plan: CommitPlan | None = None,
    signals: DiffSignals | None = None,
    gold_slot: GoldSlot | None = None,
) -> list[ScoreResultV1]:
    """Score Family D from a shared gold slot (or build one for standalone use).

    When ``gold_slot`` is supplied the family **must not** call gold (D40).
    On evaluable messages with a real report: emit every mapped catalog D row
    (present code ⇒ fail, absent ⇒ pass). Build errors fail closed. Empty /
    oversize / skipped slots never mint a genuine ``d.strict_fail_set`` pass.
    """
    slot = gold_slot
    if slot is None:
        # Standalone compatibility: build a one-shot slot (still one gold call).
        slot = build_gold_slot(
            ctx,
            gold_mode=gold_mode,
            gold_bridge=gold_bridge,
            plan=plan,
            signals=signals,
            short_circuit=False,
        )

    shared = slot.shared_evidence

    if slot.skipped or (slot.report is None and slot.error is None and not slot.call_count):
        return _unevaluable_core(slot.skip_reason or "gold_skipped", evidence=shared)

    if slot.error is not None or slot.report is None:
        # D41: fail closed — no pass-when-absent without a real report.
        scores = [
            make_score(
                "d.gold_report_ok",
                False,
                reason=slot.error or "gold_report_missing",
                evidence={**shared, "gold_mode": gold_mode},
                failure_ids=["EVAL_GOLD_BUILD_ERROR"],
                product_authority=_PA,
            ),
            make_score(
                "d.strict_fail_set",
                0,
                passed=False,
                reason="gold_evaluation_error",
                evidence={**shared, "strict_hits": [], "count": 0, "error": slot.error},
                failure_ids=["EVAL_GOLD_BUILD_ERROR"],
                product_authority="git_cg.commit_gold.STRICT_FAIL_CODES",
            ),
            make_score(
                "d.skeleton_fallback_final",
                False,
                passed=False,
                reason="gold_evaluation_error",
                evidence={**shared, "present": None},
                failure_ids=["EVAL_GOLD_BUILD_ERROR"],
                product_authority=_PA,
            ),
            make_score(
                "d.process_meta_body",
                False,
                passed=False,
                reason="gold_evaluation_error",
                evidence={**shared, "present": None},
                failure_ids=["EVAL_GOLD_BUILD_ERROR"],
                product_authority=_PA,
            ),
        ]
        # Mapped rows fail closed (not pass-when-absent) without a real report.
        for mid in FAMILY_D_MAPPED:
            if mid in {
                "d.skeleton_fallback_final",
                "d.process_meta_body",
            }:
                continue
            if _metric_exists(mid):
                scores.append(
                    make_score(
                        mid,
                        False,
                        passed=False,
                        reason="gold_evaluation_error",
                        evidence={**shared, "unevaluable": True},
                        failure_ids=["EVAL_GOLD_BUILD_ERROR"],
                        product_authority=_PA,
                    )
                )
        return scores

    report = slot.report
    codes = report.codes()
    strict_hits = slot.strict_hits
    gold_ok = slot.ok
    call_count = slot.call_count

    scores: list[ScoreResultV1] = []
    scores.append(
        make_score(
            "d.gold_report_ok",
            gold_ok,
            reason=None if gold_ok else "gold_strict_fail",
            evidence={
                **shared,
                "gold_mode": gold_mode,
                "call_count": call_count,
                "codes": sorted(codes),
            },
            failure_ids=None if gold_ok else ["GOLD_STRICT_FAIL"],
            product_authority=_PA,
        )
    )

    strict_count = len(strict_hits)
    strict_passed = strict_count == 0
    scores.append(
        make_score(
            "d.strict_fail_set",
            strict_count,
            passed=strict_passed,
            reason=None if strict_passed else "strict_codes_present",
            evidence={
                **shared,
                "strict_hits": sorted(strict_hits),
                "count": strict_count,
            },
            failure_ids=None if strict_passed else list(sorted(strict_hits)),
            product_authority="git_cg.commit_gold.STRICT_FAIL_CODES",
        )
    )

    # Core dual rows also covered by mapped emission below.
    skel_present = "GOLD_SKELETON_FALLBACK_FINAL" in codes
    scores.append(
        make_score(
            "d.skeleton_fallback_final",
            not skel_present,
            passed=not skel_present,
            reason=None if not skel_present else "GOLD_SKELETON_FALLBACK_FINAL",
            evidence={**shared, "present": skel_present},
            failure_ids=["GOLD_SKELETON_FALLBACK_FINAL"] if skel_present else None,
            product_authority=_PA,
        )
    )

    proc_present = "GOLD_PROCESS_META_BODY" in codes
    scores.append(
        make_score(
            "d.process_meta_body",
            not proc_present,
            passed=not proc_present,
            reason=None if not proc_present else "GOLD_PROCESS_META_BODY",
            evidence={**shared, "present": proc_present},
            failure_ids=["GOLD_PROCESS_META_BODY"] if proc_present else None,
            product_authority=_PA,
        )
    )

    emitted = {
        "d.gold_report_ok",
        "d.strict_fail_set",
        "d.skeleton_fallback_final",
        "d.process_meta_body",
    }

    # Walk GOLD_CODE_TO_D_METRIC (not strict_hits) — D42.
    for code, mid in sorted(GOLD_CODE_TO_D_METRIC.items(), key=lambda kv: kv[1]):
        if mid in emitted:
            continue
        if not _metric_exists(mid):
            continue

        # D43: ranked_intents=None skips coverage findings — not absent-code pass.
        if code in RANKED_DEPENDENT_GOLD_CODES and not slot.ranked_intents_provided:
            scores.append(
                make_score(
                    mid,
                    False,
                    passed=False,
                    reason="ranked_intents_not_provided_coverage_skipped",
                    evidence={
                        **shared,
                        "gold_code": code,
                        "unevaluable": True,
                        "skip_class": "ranked_intents_none",
                    },
                    failure_ids=["EVAL_GOLD_COVERAGE_SKIPPED"],
                    product_authority=_PA,
                )
            )
            emitted.add(mid)
            continue

        present = code in codes
        scores.append(
            make_score(
                mid,
                not present,
                passed=not present,
                reason=None if not present else code,
                evidence={**shared, "gold_code": code, "present": present, "call_count": call_count},
                failure_ids=[code] if present else None,
                product_authority=_PA,
            )
        )
        emitted.add(mid)

    return scores
