"""Lane C-prime — secondary semantic LLM cohort (gated, non-authoritative).

Lane C-prime is the **only** plane that may call LLM judges. It is strictly
advisory (F3): no ``cprime.*`` / ``lab.*`` / ``nlp.*`` score can solely pass
CI, the accept-path, or golden promotion. Lane A/B remain offline-capable and
never require judge credentials (F4).

Entry is gated by ``gate.semantic_cohort_eligible`` (plan §6.11)::

    gate.semantic_cohort_eligible =
        suite.allows_lane_c
        AND (gate.deterministic_pass OR suite.lab_override)
        AND pins_resolvable(judge)

This package is import-safe with no Opik SDK, no credentials, and no network:
every public entrypoint degrades to a skip/lab-fail classification instead of
raising into the offline scoring path.
"""

from git_cg.eval.lane_c.eligibility import (
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
    judge_pins_resolvable,
    resolve_allows_lane_c,
    resolve_lab_override,
)
from git_cg.eval.lane_c.judge import (
    JudgeOutcome,
    resolve_judge_credentials,
    run_pinned_judge,
)
from git_cg.eval.lane_c.prompt_pack import (
    PromptPackError,
    build_prompt_pack,
    load_pack_prompt_text,
    prompt_pack_content_hash,
    resolve_judge_pack,
    validate_prompt_pack,
)

__all__ = [
    "JudgeOutcome",
    "LaneCEligibility",
    "PromptPackError",
    "build_prompt_pack",
    "evaluate_semantic_cohort_eligibility",
    "judge_pins_resolvable",
    "load_pack_prompt_text",
    "prompt_pack_content_hash",
    "resolve_allows_lane_c",
    "resolve_judge_credentials",
    "resolve_judge_pack",
    "resolve_lab_override",
    "run_pinned_judge",
    "validate_prompt_pack",
]
