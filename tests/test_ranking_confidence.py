"""Table-driven tests for pure RankingConfidence policy (Issue #195 Slice 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from git_cg.intent import RankedIntent
from git_cg.ranking_confidence import (
    HIGH_CONFIDENCE_MARGIN,
    LOW_CONFIDENCE_MARGIN,
    NEAR_TIE_TOP3_MARGIN,
    REASON_EXACT_TIE_TOP,
    REASON_MARGIN_BELOW_LOW_THRESHOLD,
    REASON_MIXED_INTENT,
    REASON_NEAR_TIE_TOP3,
    RankingConfidence,
    compute_ranking_confidence,
)


def _ranked_intent(
    intent_id: str,
    score: float,
    *,
    intent_group: str = "feature",
) -> RankedIntent:
    return RankedIntent(
        intent_id=intent_id,
        emoji="✨",
        code=":sparkles:",
        cc_type="feat",
        description=f"{intent_id} description",
        semver_impact="MINOR",
        changelog_group="Added",
        intent_group=intent_group,
        score=score,
        priority=100,
        specificity=100,
        split_weight=100,
    )


def test_single_ranked_row_is_high_with_zero_margin() -> None:
    """A_02: single row → High, margin 0, empty reasons."""
    confidence = compute_ranking_confidence([_ranked_intent("feature_addition", 84.0)])

    assert confidence.level == "high"
    assert confidence.margin == 0.0
    assert confidence.top_intent_id == "feature_addition"
    assert confidence.runner_up_intent_id is None
    assert confidence.reasons == ()


@pytest.mark.parametrize(
    ("runner_up_score", "expected_level", "expected_reasons"),
    [
        (93.8, "low", (REASON_MARGIN_BELOW_LOW_THRESHOLD,)),
        (88.0, "medium", ()),  # margin == T_low → not Low
        (75.1, "medium", ()),
        (75.0, "high", ()),  # margin == T_high → not Medium
    ],
    ids=["below-low", "at-low", "below-high", "at-high"],
)
def test_margin_boundaries_are_exclusive(
    runner_up_score: float,
    expected_level: str,
    expected_reasons: tuple[str, ...],
) -> None:
    """A_01: exclusive T_low / T_high boundaries."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0),
            _ranked_intent("feature_refinement", runner_up_score),
        ]
    )

    assert confidence.level == expected_level
    assert confidence.reasons == expected_reasons
    assert confidence.margin == pytest.approx(100.0 - runner_up_score)


def test_low_margin_exposes_runner_up_and_exact_margin() -> None:
    """A_01: margin 6.2 → Low with margin_below_low_threshold."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 84.0),
            _ranked_intent("feature_refinement", 77.8),
        ]
    )

    assert confidence.level == "low"
    assert confidence.margin == pytest.approx(6.2)
    assert confidence.top_intent_id == "feature_addition"
    assert confidence.runner_up_intent_id == "feature_refinement"
    assert confidence.reasons == (REASON_MARGIN_BELOW_LOW_THRESHOLD,)


def test_exact_tie_is_low_and_distinct_from_single_row_fallback() -> None:
    """A_12 / G2: len≥2 and margin==0 → Low + exact_tie_top."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0),
            _ranked_intent("feature_refinement", 100.0),
        ]
    )

    assert confidence.level == "low"
    assert confidence.margin == 0.0
    assert confidence.reasons == (REASON_MARGIN_BELOW_LOW_THRESHOLD, REASON_EXACT_TIE_TOP)


def test_near_tie_top3_is_reported_for_three_close_candidates() -> None:
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0),
            _ranked_intent("feature_refinement", 95.0),
            _ranked_intent("feature_extension", 89.0),
        ]
    )

    assert confidence.level == "low"
    assert confidence.reasons == (REASON_MARGIN_BELOW_LOW_THRESHOLD, REASON_NEAR_TIE_TOP3)


def test_mixed_intent_is_reported_for_close_top_two_groups() -> None:
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0, intent_group="feature"),
            _ranked_intent("bug_fix", 88.5, intent_group="bugfix"),
        ]
    )

    assert confidence.level == "low"
    assert confidence.reasons == (REASON_MARGIN_BELOW_LOW_THRESHOLD, REASON_MIXED_INTENT)


def test_conflicts_compound_without_mutating_ranked_rows() -> None:
    ranked = [
        _ranked_intent("feature_addition", 100.0, intent_group="feature"),
        _ranked_intent("bug_fix", 100.0, intent_group="bugfix"),
        _ranked_intent("documentation_update", 89.0, intent_group="docs"),
    ]

    confidence = compute_ranking_confidence(ranked)

    assert confidence.level == "low"
    assert confidence.reasons == (
        REASON_MARGIN_BELOW_LOW_THRESHOLD,
        REASON_EXACT_TIE_TOP,
        REASON_NEAR_TIE_TOP3,
        REASON_MIXED_INTENT,
    )
    assert [row.score for row in ranked] == [100.0, 100.0, 89.0]


def test_semantic_lexical_disagreement_is_ignored_in_v1() -> None:
    """P3-lex: reserved kwarg must not emit or gate Low."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0),
            _ranked_intent("feature_refinement", 60.0),
        ],
        semantic_lexical_disagreement=True,
    )

    assert confidence.level == "high"
    assert confidence.reasons == ()
    assert "semantic_lexical_disagreement" not in confidence.reasons


def test_empty_ranking_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one ranked intent"):
        compute_ranking_confidence([])


def test_ranking_confidence_model_is_frozen() -> None:
    confidence = compute_ranking_confidence([_ranked_intent("feature_addition", 84.0)])
    with pytest.raises(ValidationError):
        confidence.level = "low"  # type: ignore[misc]


def test_distinct_groups_high_margin_does_not_emit_mixed_intent() -> None:
    """A_18: distinct intent_group with margin ≥ T_low must not emit mixed_intent."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0, intent_group="feature"),
            _ranked_intent("bug_fix", 100.0 - LOW_CONFIDENCE_MARGIN, intent_group="bugfix"),
        ]
    )

    assert confidence.margin == pytest.approx(LOW_CONFIDENCE_MARGIN)
    assert confidence.level == "medium"
    assert REASON_MIXED_INTENT not in confidence.reasons
    assert confidence.reasons == ()


def test_top_to_third_exactly_t_near_does_not_emit_near_tie() -> None:
    """A_18: (top - 3rd) == T_near must not emit near_tie_top3 (exclusive <)."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0),
            _ranked_intent("feature_refinement", 94.0),
            _ranked_intent("feature_extension", 100.0 - NEAR_TIE_TOP3_MARGIN),
        ]
    )

    assert confidence.margin == pytest.approx(6.0)
    assert confidence.level == "low"
    assert REASON_NEAR_TIE_TOP3 not in confidence.reasons
    assert confidence.reasons == (REASON_MARGIN_BELOW_LOW_THRESHOLD,)


def test_len_less_than_three_never_emits_near_tie_top3() -> None:
    """A_18: n < 3 must never trigger near_tie_top3."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0),
            _ranked_intent("feature_refinement", 99.0),
        ]
    )

    assert REASON_NEAR_TIE_TOP3 not in confidence.reasons
    assert confidence.level == "low"


def test_mixed_intent_kwarg_does_not_force_low_on_high_margin_same_group() -> None:
    """A_19: mixed_intent=True must not force Low on high-margin same-group lists."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0, intent_group="feature"),
            _ranked_intent("feature_refinement", 100.0 - HIGH_CONFIDENCE_MARGIN, intent_group="feature"),
        ],
        mixed_intent=True,
    )

    assert confidence.level == "high"
    assert confidence.reasons == ()
    assert REASON_MIXED_INTENT not in confidence.reasons


def test_reason_constants_match_emitted_codes() -> None:
    """Reason constants are the only vocabulary emitted by the pure module."""
    confidence = compute_ranking_confidence(
        [
            _ranked_intent("feature_addition", 100.0, intent_group="feature"),
            _ranked_intent("bug_fix", 100.0, intent_group="bugfix"),
            _ranked_intent("documentation_update", 89.0, intent_group="docs"),
        ]
    )
    assert set(confidence.reasons) <= {
        REASON_MARGIN_BELOW_LOW_THRESHOLD,
        REASON_EXACT_TIE_TOP,
        REASON_NEAR_TIE_TOP3,
        REASON_MIXED_INTENT,
    }
    # Frozen model round-trip preserves closed codes.
    restored = RankingConfidence.model_validate(confidence.model_dump())
    assert restored == confidence
