"""Lane C-prime runner — eligibility-gated, credential-gated, never blocking.

This is the **only** entrypoint that may emit ``cprime.*`` scores. It is a
separate, opt-in path from the offline :func:`score_bundle` plane: Lane A/B
never import it and never require judge credentials (F4).

S5c scope — **pinned GEval judge wired behind the eligibility gate**:

1. Evaluates ``gate.semantic_cohort_eligible`` (plan §6.11).
2. When the cohort is **ineligible**, emits a skip row per requested metric
   (``passed=None``, ``reason=...``) so dashboards record an honest non-run
   rather than a fabricated score.
3. When **eligible**, resolves the repo-owned prompt pack (INT-26) and runs the
   pinned GEval judge via :func:`run_pinned_judge`. A parseable in-range score
   becomes a real advisory row; any judge/pack/parse failure degrades to a
   skip row — never an exception, never a fabricated score.

Every emitted row carries ``authority=advisory`` (derived from the frozen
catalog row by :func:`make_score`) and ``source=lane_c_judge`` — judges are
never product law (F3). This function never raises on missing credentials,
missing pins, ineligible cohorts, or judge failure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from git_cg.eval.lane_c.eligibility import (
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
)
from git_cg.eval.lane_c.judge import (
    JudgeFn,
    resolve_judge_credentials,
    run_pinned_judge,
)
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.result_builder import make_score

#: Reason stamped when a requested C-prime metric is skipped because the cohort is
#: not eligible (gate closed). Recorded, never a veto.
REASON_COHORT_INELIGIBLE = "lane_c_cohort_ineligible"

#: Reason stamped when the cohort is eligible but no pinned judge ran. Retained
#: for back-compat with S5a callers; S5c no longer emits it on the live path.
REASON_JUDGE_NOT_RUN = "lane_c_judge_not_implemented"


def run_lane_c(
    metric_ids: Sequence[str],
    *,
    deterministic_pass: bool,
    allows_lane_c: bool | None = None,
    lab_override: bool | None = None,
    suite: Mapping[str, Any] | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
    message: str = "",
    diff_summary: str | None = None,
    prompt_root: Path | None = None,
    judge_fn: JudgeFn | None = None,
) -> tuple[list[ScoreResultV1], LaneCEligibility]:
    """Run the Lane C-prime secondary semantic cohort for ``metric_ids``.

    Returns ``(rows, eligibility)``. ``rows`` has exactly one
    :class:`ScoreResultV1` per requested metric id, each stamped
    ``authority=advisory``. Unknown (non-catalog) metric ids raise
    :class:`KeyError` via :func:`make_score` — fail-closed on the metric
    vocabulary, never on credentials.

    When the cohort is eligible, the pinned judge runs against ``message``
    (the accepted COMMIT_EDITMSG text) plus an optional gold-blind
    ``diff_summary``. Judge/pack/parse failures and empty/oversize input all
    degrade to ``passed=None`` skip rows; this function never raises on them.
    """
    eligibility = evaluate_semantic_cohort_eligibility(
        deterministic_pass=deterministic_pass,
        allows_lane_c=allows_lane_c,
        lab_override=lab_override,
        suite=suite,
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        environ=environ,
    )

    rows: list[ScoreResultV1] = []
    if not eligibility.eligible:
        for mid in metric_ids:
            row = make_score(
                mid,
                0.0,
                passed=None,
                reason=REASON_COHORT_INELIGIBLE,
                evidence={
                    "skipped": True,
                    "eligibility": eligibility.reason,
                    "allows_lane_c": eligibility.allows_lane_c,
                    "deterministic_pass": eligibility.deterministic_pass,
                    "lab_override": eligibility.lab_override,
                    "judge_pins_resolvable": eligibility.judge_pins_resolvable,
                },
            )
            # ``passed=None`` is the honest "not evaluated" skip marker. A skip is
            # neither a pass nor a fail and must never be read as either (F3/M11).
            rows.append(row.model_copy(update={"passed": None}))
        return rows, eligibility

    # Eligible: resolve the pinned judge credentials and run each metric.
    model, key = resolve_judge_credentials(
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        environ=environ,
    )
    for mid in metric_ids:
        outcome = run_pinned_judge(
            mid,
            message=message,
            diff_summary=diff_summary,
            judge_model=model,
            judge_api_key=key,
            prompt_root=prompt_root,
            judge_fn=judge_fn,
        )
        if outcome.scored and outcome.score is not None:
            row = make_score(
                mid,
                outcome.score,
                passed=None,  # advisory: no product pass/fail threshold
                reason=outcome.rationale or None,
                evidence={"skipped": False, **outcome.evidence},
            )
            # Advisory GEval scores carry no boolean verdict (F3/M11).
            rows.append(row.model_copy(update={"passed": None}))
        else:
            row = make_score(
                mid,
                0.0,
                passed=None,
                reason=outcome.reason or "lane_c_judge_not_run",
                evidence={"skipped": True, "eligibility": eligibility.reason, **outcome.evidence},
            )
            rows.append(row.model_copy(update={"passed": None}))
    return rows, eligibility
