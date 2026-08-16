"""Lane C-prime runner — eligibility-gated, credential-gated, never blocking.

This is the **only** entrypoint that may emit ``cprime.*`` scores. It is a
separate, opt-in path from the offline :func:`score_bundle` plane: Lane A/B
never import it and never require judge credentials (F4).

S5a scope — **gating skeleton only**. No live LLM judge is called. The runner:

1. Evaluates ``gate.semantic_cohort_eligible`` (plan §6.11).
2. When the cohort is **ineligible**, emits a skip row per requested metric
   (``passed=None``, ``reason=...``) so dashboards record an honest non-run
   rather than a fabricated score.
3. When **eligible**, S5a still performs no network call — it emits a
   ``lab-fail``/not-implemented classification marking the runner as pending
   the S5b pinned-judge implementation.

Every emitted row carries ``authority=advisory`` (derived from the frozen
catalog row by :func:`make_score`) and ``source=lane_c_judge`` — judges are
never product law (F3). This function never raises on missing credentials,
missing pins, or ineligible cohorts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from git_cg.eval.lane_c.eligibility import (
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
)
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.result_builder import make_score

#: Reason stamped when a requested C-prime metric is skipped because the cohort is
#: not eligible (gate closed). Recorded, never a veto.
REASON_COHORT_INELIGIBLE = "lane_c_cohort_ineligible"

#: Reason stamped when the cohort is eligible but no pinned judge ran (S5a has
#: no live judge yet). A skip/lab-fail class, not a product failure.
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
) -> tuple[list[ScoreResultV1], LaneCEligibility]:
    """Run the Lane C-prime secondary semantic cohort for ``metric_ids``.

    Returns ``(rows, eligibility)``. ``rows`` has exactly one
    :class:`ScoreResultV1` per requested metric id, each stamped
    ``authority=advisory``. Unknown (non-catalog) metric ids raise
    :class:`KeyError` via :func:`make_score` — fail-closed on the metric
    vocabulary, never on credentials.

    This function performs **no** network I/O and never raises on missing
    judge credentials; an ineligible or un-pinned cohort yields skip rows.
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
    for mid in metric_ids:
        if not eligibility.eligible:
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
        else:
            # Eligible, but S5a ships no live judge. Record an honest
            # not-run classification rather than a fabricated score.
            row = make_score(
                mid,
                0.0,
                passed=None,
                reason=REASON_JUDGE_NOT_RUN,
                evidence={
                    "skipped": True,
                    "eligibility": eligibility.reason,
                    "judge_model": eligibility.evidence.get("judge_model_pinned"),
                    "pending": "S5b_pinned_judge",
                },
            )
        # ``passed=None`` is the honest "not evaluated" skip marker; make_score
        # would otherwise derive a boolean from the placeholder value. A skip is
        # neither a pass nor a fail and must never be read as either (F3/M11).
        rows.append(row.model_copy(update={"passed": None}))
    return rows, eligibility
