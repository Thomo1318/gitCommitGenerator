"""Slice 0 characterisation freeze for the deterministic intent engine (#161).

Locks marker sets, full rank snapshots, and selection constraints against the
production SOP matrix before marker-path / enrichment edits land.
"""

from __future__ import annotations

import copy
import hashlib
import json
from itertools import pairwise
from pathlib import Path

import pytest

from git_cg.intent import (
    DiffSignals,
    _generate_signal_markers,
    derive_intent_selection_constraints,
    rank_commit_intents,
)
from git_cg.sop import load_sop

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "intent_characterisation"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"
GOLDENS_PATH = FIXTURE_DIR / "goldens.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sop_matrix_sha256(matrix: list[dict]) -> str:
    payload = json.dumps(matrix, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _canonical_rank_key(row: dict) -> tuple:
    """Documented compare key for reorder-invariant assertions."""
    return (
        -float(row["score"]),
        -int(row["priority"]),
        -int(row["specificity"]),
        str(row["intent_id"]),
    )


def _rank_snapshot(ranked) -> list[dict]:
    return [
        {
            "intent_id": item.intent_id,
            "score": item.score,
            "priority": item.priority,
            "specificity": item.specificity,
            "semver_impact": item.semver_impact,
            "intent_group": item.intent_group,
            "cc_type": item.cc_type,
        }
        for item in ranked
    ]


def _constraints_snapshot(constraints) -> dict:
    return {
        "reasons": list(constraints.reasons),
        "allowed_intent_ids": list(constraints.allowed_intent_ids),
        "disallowed_intent_ids": list(constraints.disallowed_intent_ids),
    }


@pytest.fixture(scope="module")
def sop_matrix() -> list[dict]:
    data = load_sop()
    matrix = data.get("gitmoji_reference_matrix", [])
    assert matrix, "production SOP matrix must be loadable for characterisation"
    return matrix


@pytest.fixture(scope="module")
def corpus() -> dict:
    assert CORPUS_PATH.is_file(), f"missing corpus fixture: {CORPUS_PATH}"
    return _load_json(CORPUS_PATH)


@pytest.fixture(scope="module")
def goldens() -> dict:
    assert GOLDENS_PATH.is_file(), f"missing goldens fixture: {GOLDENS_PATH}"
    return _load_json(GOLDENS_PATH)


@pytest.fixture(scope="module")
def corpus_case_ids(corpus: dict) -> list[str]:
    return [case["id"] for case in corpus["cases"]]


def test_characterisation_fixtures_pin_production_sop(sop_matrix: list[dict], corpus: dict, goldens: dict) -> None:
    """Corpus and goldens must record the live SOP matrix identity."""
    live_hash = _sop_matrix_sha256(sop_matrix)
    assert corpus["sop_matrix_sha256"] == live_hash
    assert goldens["sop_matrix_sha256"] == live_hash
    assert corpus["sop_matrix_row_count"] == len(sop_matrix)
    assert goldens["sop_matrix_row_count"] == len(sop_matrix)
    assert set(goldens["cases"]) == {case["id"] for case in corpus["cases"]}


@pytest.mark.parametrize(
    "case_id",
    [
        "empty_baseline",
        "docs_only",
        "tests_only",
        "dependency_upgrade_only",
        "security_fix",
        "feature_with_docs_mixed",
        "breaking_change",
        "breaking_with_tests",
        "formatting_only",
        "generic_refactor_centralization",
        "bug_fix_error_handling",
        "architecture_restructure",
        "ci_hooks",
        "files_added_deleted_renamed",
    ],
)
def test_characterisation_case_matches_golden(
    case_id: str,
    sop_matrix: list[dict],
    corpus: dict,
    goldens: dict,
) -> None:
    """Full markers + rank + constraints snapshot for each corpus family."""
    case = next(item for item in corpus["cases"] if item["id"] == case_id)
    expected = goldens["cases"][case_id]

    signals = DiffSignals(**case["signals"])
    markers = sorted(_generate_signal_markers(signals))
    ranked = rank_commit_intents(signals, sop_matrix)
    constraints = derive_intent_selection_constraints(signals, sop_matrix)

    assert markers == expected["markers"]
    assert _rank_snapshot(ranked) == expected["rank"]
    assert _constraints_snapshot(constraints) == expected["constraints"]


def test_breaking_with_tests_accumulates_independent_marker_families(corpus: dict, goldens: dict) -> None:
    """Additive contract sample: breaking + tests markers coexist on one diff."""
    case = next(item for item in corpus["cases"] if item["id"] == "breaking_with_tests")
    markers = set(goldens["cases"]["breaking_with_tests"]["markers"])
    # Recompute to keep the assertion tied to engine output as well.
    live = set(_generate_signal_markers(DiffSignals(**case["signals"])))
    assert live == markers
    assert {"breaking_change_declared", "breaking_change_footer"} <= markers
    assert {"tests_added", "tests_updated", "test_fixtures_changed"} <= markers


def test_matrix_row_reorder_preserves_per_intent_scores_and_semver(sop_matrix: list[dict], corpus: dict) -> None:
    """Row order must not change per-intent score or matrix-owned semver_impact."""
    case = next(item for item in corpus["cases"] if item["id"] == "feature_with_docs_mixed")
    signals = DiffSignals(**case["signals"])

    baseline = {
        row.intent_id: (row.score, row.semver_impact, row.priority, row.specificity)
        for row in rank_commit_intents(signals, sop_matrix)
    }

    reordered = list(reversed(sop_matrix))
    assert [r.get("intent_id") for r in reordered] != [r.get("intent_id") for r in sop_matrix]

    reshuffled = {
        row.intent_id: (row.score, row.semver_impact, row.priority, row.specificity)
        for row in rank_commit_intents(signals, reordered)
    }
    assert reshuffled == baseline


def test_matrix_row_reorder_canonical_order_is_stable(sop_matrix: list[dict], corpus: dict) -> None:
    """Canonical (score, priority, specificity, intent_id) order is reorder-invariant."""
    case = next(item for item in corpus["cases"] if item["id"] == "security_fix")
    signals = DiffSignals(**case["signals"])

    def canonical(matrix: list[dict]) -> list[str]:
        snap = _rank_snapshot(rank_commit_intents(signals, matrix))
        return [row["intent_id"] for row in sorted(snap, key=_canonical_rank_key)]

    assert canonical(sop_matrix) == canonical(list(reversed(copy.deepcopy(sop_matrix))))


def test_engine_rank_sort_keys_match_documented_tie_break(sop_matrix: list[dict], corpus: dict, goldens: dict) -> None:
    """Engine order must be non-increasing on (score, priority, specificity)."""
    case = next(item for item in corpus["cases"] if item["id"] == "empty_baseline")
    ranked = goldens["cases"]["empty_baseline"]["rank"]
    assert len(ranked) == len(sop_matrix)

    for previous, current in pairwise(ranked):
        prev_key = (
            float(previous["score"]),
            int(previous["priority"]),
            int(previous["specificity"]),
        )
        curr_key = (
            float(current["score"]),
            int(current["priority"]),
            int(current["specificity"]),
        )
        assert prev_key >= curr_key

    # Live engine agrees with golden for the empty baseline.
    live = _rank_snapshot(rank_commit_intents(DiffSignals(**case["signals"]), sop_matrix))
    assert live == ranked
