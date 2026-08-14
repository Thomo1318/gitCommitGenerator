"""Family D — gold bridge: one product gold call, fan-out findings."""

from __future__ import annotations

from collections.abc import Callable

from git_cg.commit_gold import GoldReport
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.product_bridges import (
    GOLD_CODE_TO_D_METRIC,
    parse_message_to_plan,
    run_gold_once,
    signals_from_context,
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

GoldBridge = Callable[[CommitPlan, DiffSignals, str], tuple[GoldReport, frozenset[str], bool]]


def _default_bridge(plan: CommitPlan, signals: DiffSignals, mode: str) -> tuple[GoldReport, frozenset[str], bool]:
    return run_gold_once(plan, signals, gold_mode=mode)


def _metric_exists(metric_id: str) -> bool:
    return metric_row(metric_id) is not None


def score_family_d(
    ctx: ScoreContext,
    *,
    gold_mode: str = "strict",
    gold_bridge: GoldBridge | None = None,
    plan: CommitPlan | None = None,
    signals: DiffSignals | None = None,
) -> list[ScoreResultV1]:
    """Score Family D from one product gold call."""
    bridge = gold_bridge or _default_bridge
    scores: list[ScoreResultV1] = []

    msg = ctx.final_message or ""
    report: GoldReport | None = None
    strict_hits: frozenset[str] = frozenset()
    gold_ok = False
    build_err: str | None = None
    call_count = 0

    def _counting_bridge(p: CommitPlan, s: DiffSignals, mode: str) -> tuple[GoldReport, frozenset[str], bool]:
        nonlocal call_count
        call_count += 1
        return bridge(p, s, mode)

    if not msg.strip():
        scores.extend(
            [
                make_score(
                    "d.gold_report_ok",
                    False,
                    reason="no_final_message_for_gold",
                    evidence={"called": False},
                    failure_ids=["EVAL_GOLD_SKIPPED_EMPTY"],
                    product_authority="git_cg.commit_gold.check_commit_gold",
                ),
                make_score(
                    "d.strict_fail_set",
                    0,
                    passed=True,
                    reason="gold_not_invoked_empty_input",
                    evidence={"strict_hits": []},
                    product_authority="git_cg.commit_gold.STRICT_FAIL_CODES",
                ),
                make_score(
                    "d.skeleton_fallback_final",
                    False,  # value False = finding not present
                    passed=True,
                    reason="gold_not_invoked_empty_input",
                    evidence={"present": False},
                    product_authority="git_cg.commit_gold.check_commit_gold",
                ),
                make_score(
                    "d.process_meta_body",
                    False,
                    passed=True,
                    reason="gold_not_invoked_empty_input",
                    evidence={"present": False},
                    product_authority="git_cg.commit_gold.check_commit_gold",
                ),
            ]
        )
        return scores

    try:
        built_plan = plan or parse_message_to_plan(msg)
        built_signals = signals or signals_from_context(
            path_class_gate=ctx.path_class_gate,
            generation_task_input=ctx.generation_task_input,
        )
        report, strict_hits, gold_ok = _counting_bridge(built_plan, built_signals, gold_mode)
    except Exception as exc:
        build_err = f"{type(exc).__name__}: {exc}"
        gold_ok = False

    scores.append(
        make_score(
            "d.gold_report_ok",
            gold_ok,
            reason=None if gold_ok else (build_err or "gold_strict_fail"),
            evidence={
                "gold_mode": gold_mode,
                "call_count": call_count,
                "codes": sorted(report.codes()) if report is not None else [],
                "error": build_err,
            },
            failure_ids=None if gold_ok else (["EVAL_GOLD_BUILD_ERROR"] if build_err else ["GOLD_STRICT_FAIL"]),
            product_authority="git_cg.commit_gold.check_commit_gold",
        )
    )

    strict_count = len(strict_hits)
    strict_evaluated = build_err is None
    strict_passed = strict_evaluated and strict_count == 0
    scores.append(
        make_score(
            "d.strict_fail_set",
            strict_count,
            passed=strict_passed,
            reason=(None if strict_passed else ("gold_evaluation_error" if build_err else "strict_codes_present")),
            evidence={
                "strict_hits": sorted(strict_hits),
                "count": strict_count,
                "error": build_err,
            },
            failure_ids=(
                None if strict_passed else (["EVAL_GOLD_BUILD_ERROR"] if build_err else list(sorted(strict_hits)))
            ),
            product_authority="git_cg.commit_gold.STRICT_FAIL_CODES",
        )
    )

    codes = report.codes() if report is not None else frozenset()

    # Catalog polarity is pass_fail for skeleton/process_meta:
    # pass means the bad gold code is NOT present.
    skel_present = "GOLD_SKELETON_FALLBACK_FINAL" in codes
    scores.append(
        make_score(
            "d.skeleton_fallback_final",
            not skel_present,
            passed=not skel_present,
            reason=None if not skel_present else "GOLD_SKELETON_FALLBACK_FINAL",
            evidence={"present": skel_present},
            failure_ids=["GOLD_SKELETON_FALLBACK_FINAL"] if skel_present else None,
            product_authority="git_cg.commit_gold.check_commit_gold",
        )
    )

    proc_present = "GOLD_PROCESS_META_BODY" in codes
    scores.append(
        make_score(
            "d.process_meta_body",
            not proc_present,
            passed=not proc_present,
            reason=None if not proc_present else "GOLD_PROCESS_META_BODY",
            evidence={"present": proc_present},
            failure_ids=["GOLD_PROCESS_META_BODY"] if proc_present else None,
            product_authority="git_cg.commit_gold.check_commit_gold",
        )
    )

    emitted = {
        "d.gold_report_ok",
        "d.strict_fail_set",
        "d.skeleton_fallback_final",
        "d.process_meta_body",
    }
    for code in sorted(codes):
        mid = GOLD_CODE_TO_D_METRIC.get(code)
        if mid is None or mid in emitted:
            continue
        if _metric_exists(mid):
            # Presence of a gold finding ⇒ metric fails (pass_fail).
            scores.append(
                make_score(
                    mid,
                    False,
                    passed=False,
                    reason=code,
                    evidence={"gold_code": code, "call_count": call_count},
                    failure_ids=[code],
                    product_authority="git_cg.commit_gold.check_commit_gold",
                )
            )
            emitted.add(mid)

    return scores
