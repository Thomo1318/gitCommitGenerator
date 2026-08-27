"""Offline Plane A scoring package (S2a/S2b/S2c).

Normal ``git-cg commit`` must not import this package. Scoring is an opt-in
eval surface over S1 ``ape_bundle_v1`` fixtures and product authorities.
"""

from git_cg.eval.scoring.family_i import (
    FAMILY_I_METRIC_IDS,
    build_session_thread_index,
    resolve_case_session_thread_id,
    score_family_i,
    synthesize_family_i_fail_closed,
)
from git_cg.eval.scoring.gates import (
    S2A_REQUIRE_BLOCK,
    S2B_REQUIRE_BLOCK,
    S2C_TOPOLOGY_BLOCK,
    compose_gates,
)
from git_cg.eval.scoring.runner import (
    PreparedSuite,
    ScoreCaseResult,
    ScoreSuiteResult,
    prepare_suite_cases,
    resolve_require_topology,
    score_bundle,
    score_case,
    score_suite,
)

__all__ = [
    "FAMILY_I_METRIC_IDS",
    "S2A_REQUIRE_BLOCK",
    "S2B_REQUIRE_BLOCK",
    "S2C_TOPOLOGY_BLOCK",
    "PreparedSuite",
    "ScoreCaseResult",
    "ScoreSuiteResult",
    "build_session_thread_index",
    "compose_gates",
    "prepare_suite_cases",
    "resolve_case_session_thread_id",
    "resolve_require_topology",
    "score_bundle",
    "score_case",
    "score_family_i",
    "score_suite",
    "synthesize_family_i_fail_closed",
]
