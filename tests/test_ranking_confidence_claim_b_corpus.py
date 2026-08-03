"""Claim B near-tie / margin corpus for RankingConfidence (Issue #195).

Deterministic before/after-style ladder over pure score fixtures.
No live LLM, Opik, or SOP weight changes.

Corpus path:
    tests/fixtures/ranking_confidence_near_tie/corpus.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.intent import RankedIntent
from git_cg.ranking_confidence import (
    HIGH_CONFIDENCE_MARGIN,
    LOW_CONFIDENCE_MARGIN,
    NEAR_TIE_TOP3_MARGIN,
    compute_ranking_confidence,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ranking_confidence_near_tie"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"


def _load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _ranked_intent(row: dict) -> RankedIntent:
    return RankedIntent(
        intent_id=row["intent_id"],
        emoji="✨",
        code=":sparkles:",
        cc_type="feat",
        description=f"{row['intent_id']} description",
        semver_impact="MINOR",
        changelog_group="Added",
        intent_group=row.get("intent_group", "feature"),
        score=float(row["score"]),
        priority=100,
        specificity=100,
        split_weight=100,
    )


@pytest.fixture(scope="module")
def corpus() -> dict:
    return _load_corpus()


def test_corpus_thresholds_match_module_constants(corpus: dict) -> None:
    thr = corpus["thresholds"]
    assert thr["T_low"] == LOW_CONFIDENCE_MARGIN
    assert thr["T_high"] == HIGH_CONFIDENCE_MARGIN
    assert thr["T_near"] == NEAR_TIE_TOP3_MARGIN


def test_corpus_has_unique_case_ids(corpus: dict) -> None:
    ids = [case["id"] for case in corpus["cases"]]
    assert ids, "corpus must define at least one case"
    assert len(ids) == len(set(ids))


def test_corpus_case_ids_are_claim_b_prefixed(corpus: dict) -> None:
    for case in corpus["cases"]:
        assert case["id"].startswith("B_"), case["id"]


@pytest.mark.parametrize("case_id", [c["id"] for c in _load_corpus()["cases"]])
def test_claim_b_near_tie_corpus_case(case_id: str, corpus: dict) -> None:
    case = next(c for c in corpus["cases"] if c["id"] == case_id)
    ranked = [_ranked_intent(row) for row in case["ranked"]]
    confidence = compute_ranking_confidence(ranked)
    expected = case["expected"]

    assert confidence.level == expected["level"], case["title"]
    assert confidence.margin == pytest.approx(float(expected["margin"]))
    assert confidence.top_intent_id == expected["top_intent_id"]
    assert confidence.runner_up_intent_id == expected["runner_up_intent_id"]
    assert list(confidence.reasons) == list(expected["reasons"])
