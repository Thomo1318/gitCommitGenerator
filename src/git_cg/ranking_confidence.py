"""Pure deterministic confidence policy for ranked commit intents.

This module is the sole owner of ranking-confidence *policy* (thresholds,
closed reason codes, and level rules). It must stay free of git/LLM/TUI I/O
and must never mutate ranker weights, signals, or SemVer selection.

Preconditions for ``compute_ranking_confidence``:
    * ``ranked`` is the authoritative, pre-sorted output of
      ``rank_commit_intents`` (descending score / ranker order).
    * The pure module does **not** re-sort as a second ranker.
    * Empty ``ranked`` raises ``ValueError`` (no synthetic High/Low).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from git_cg.intent import RankedIntent

# Normative thresholds (Issue #195). Same magnitude for T_low / T_near is
# intentional; keep distinct names so policy PRs can diverge them later.
LOW_CONFIDENCE_MARGIN = 12.0  # T_low
HIGH_CONFIDENCE_MARGIN = 25.0  # T_high
NEAR_TIE_TOP3_MARGIN = 12.0  # T_near

# Closed reason vocabulary — never open-code these strings at call sites.
REASON_MARGIN_BELOW_LOW_THRESHOLD = "margin_below_low_threshold"
REASON_MIXED_INTENT = "mixed_intent"
REASON_NEAR_TIE_TOP3 = "near_tie_top3"
REASON_EXACT_TIE_TOP = "exact_tie_top"

ReasonCode = Literal[
    "margin_below_low_threshold",
    "mixed_intent",
    "near_tie_top3",
    "exact_tie_top",
]

ConfidenceLevel = Literal["high", "medium", "low"]

V1_REASON_CODES: frozenset[str] = frozenset(
    {
        REASON_MARGIN_BELOW_LOW_THRESHOLD,
        REASON_MIXED_INTENT,
        REASON_NEAR_TIE_TOP3,
        REASON_EXACT_TIE_TOP,
    }
)


class RankingConfidence(BaseModel):
    """Immutable confidence assessment for one deterministic ranking pass."""

    model_config = ConfigDict(frozen=True)

    level: ConfidenceLevel
    margin: float
    top_intent_id: str
    runner_up_intent_id: str | None
    reasons: tuple[ReasonCode, ...] = Field(default_factory=tuple)


def _has_exact_tie_top(ranked: list[RankedIntent], margin: float) -> bool:
    """Return whether the first two ranked rows have identical scores (G2)."""
    return len(ranked) >= 2 and margin == 0.0


def _has_near_tie_top3(ranked: list[RankedIntent]) -> bool:
    """Return whether top-to-third score span is strictly below T_near."""
    return len(ranked) >= 3 and ranked[0].score - ranked[2].score < NEAR_TIE_TOP3_MARGIN


def _has_mixed_intent(ranked: list[RankedIntent], margin: float) -> bool:
    """Return whether close top-two candidates belong to distinct intent groups.

    Uses ``RankedIntent.intent_group`` only. Distinct groups with
    ``margin >= T_low`` must **not** emit ``mixed_intent``.
    """
    return len(ranked) >= 2 and margin < LOW_CONFIDENCE_MARGIN and ranked[0].intent_group != ranked[1].intent_group


def compute_ranking_confidence(
    ranked: list[RankedIntent],
    *,
    mixed_intent: bool = False,
    semantic_lexical_disagreement: bool = False,
) -> RankingConfidence:
    """Compute deterministic confidence without mutating the supplied ranking.

    Parameters:
        ranked: Pre-sorted ``rank_commit_intents`` output (non-empty).
        mixed_intent: Forward-compatible flag. v1 does **not** force Low from
            this flag alone; the emitted ``mixed_intent`` reason is derived only
            from the pure top-2 ``intent_group`` predicate.
        semantic_lexical_disagreement: P3-lex reserved kwarg. Ignored in v1 and
            never emitted as a reason.

    Returns:
        RankingConfidence: Frozen assessment for this rank pass.

    Raises:
        ValueError: If ``ranked`` is empty.
    """
    # Retained for API stability; deliberately unused in v1 policy.
    del mixed_intent, semantic_lexical_disagreement

    if not ranked:
        raise ValueError("ranked must contain at least one ranked intent")

    top = ranked[0]
    runner_up = ranked[1] if len(ranked) >= 2 else None
    margin = 0.0 if runner_up is None else top.score - runner_up.score

    if runner_up is None:
        return RankingConfidence(
            level="high",
            margin=margin,
            top_intent_id=top.intent_id,
            runner_up_intent_id=None,
            reasons=(),
        )

    reasons_list: list[ReasonCode] = []
    if margin < LOW_CONFIDENCE_MARGIN:
        reasons_list.append(REASON_MARGIN_BELOW_LOW_THRESHOLD)
    if _has_exact_tie_top(ranked, margin):
        reasons_list.append(REASON_EXACT_TIE_TOP)
    if _has_near_tie_top3(ranked):
        reasons_list.append(REASON_NEAR_TIE_TOP3)
    if _has_mixed_intent(ranked, margin):
        reasons_list.append(REASON_MIXED_INTENT)
    reasons = tuple(reasons_list)

    if reasons:
        level: ConfidenceLevel = "low"
    elif margin < HIGH_CONFIDENCE_MARGIN:
        level = "medium"
    else:
        level = "high"

    return RankingConfidence(
        level=level,
        margin=margin,
        top_intent_id=top.intent_id,
        runner_up_intent_id=runner_up.intent_id,
        reasons=reasons,
    )
