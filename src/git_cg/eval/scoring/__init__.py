"""Offline Plane A scoring package (S2a/S2b).

Normal ``git-cg commit`` must not import this package. Scoring is an opt-in
eval surface over S1 ``ape_bundle_v1`` fixtures and product authorities.
"""

from git_cg.eval.scoring.gates import S2A_REQUIRE_BLOCK, S2B_REQUIRE_BLOCK, compose_gates
from git_cg.eval.scoring.runner import (
    ScoreCaseResult,
    ScoreSuiteResult,
    score_bundle,
    score_case,
    score_suite,
)

__all__ = [
    "S2A_REQUIRE_BLOCK",
    "S2B_REQUIRE_BLOCK",
    "ScoreCaseResult",
    "ScoreSuiteResult",
    "compose_gates",
    "score_bundle",
    "score_case",
    "score_suite",
]
