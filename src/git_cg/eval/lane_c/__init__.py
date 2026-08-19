"""Lane C-prime — secondary semantic LLM cohort (gated, non-authoritative).

Lane C-prime is the **only** plane that may call LLM judges. It is strictly
advisory (D3/F3): no ``cprime.*`` score can solely pass CI, the accept-path, or
golden promotion. Lane A/B remain offline-capable and never require judge
credentials (D4'/F4).

Entry authorization (D4)::

    gate.semantic_cohort_eligible =
        suite.allows_lane_c
        AND (gate.deterministic_pass OR suite.lab_override)
        AND judge_identity_pins_resolvable   # model/pack/params — NOT secrets

Credentials affect **availability / skip class only** (D4').

Supported execution API
    :func:`run_lane_c` — gated runner (only supported execution entrypoint)

This package is import-safe with no provider SDK, no network, and no ambient
secret export. Provider SDKs are lazy-imported only inside transport paths
(Slice 4); ``import git_cg.eval.lane_c`` must remain SDK-free (S5-E08).
"""

from __future__ import annotations

from git_cg.eval.lane_c.availability import (
    ENV_JUDGE_API_KEY,
    ENV_JUDGE_BASE_URL,
    LaneCAvailability,
    credentials_present,
    evaluate_judge_availability,
    provider_client_constructible,
)
from git_cg.eval.lane_c.eligibility import (
    DEFAULT_OUTPUT_CONTRACT_IDENTITY,
    DEFAULT_PACK_IDENTITY,
    DEFAULT_SAMPLING_IDENTITY,
    ENV_JUDGE_MODEL,
    LaneCEligibility,
    evaluate_semantic_cohort_eligibility,
    is_undated_model_alias,
    judge_identity_pins_resolvable,
    judge_pins_resolvable,
    resolve_allows_lane_c,
    resolve_lab_override,
)
from git_cg.eval.lane_c.prompt_pack import (
    DEFAULT_PROMPT_ROOT,
    DEFAULT_UNIVERSE_ROOT,
    PromptPackError,
    UniverseFingerprint,
    build_prompt_pack,
    lint_prompt_pack_hygiene,
    load_pack_prompt_text,
    prompt_pack_content_hash,
    prompt_pack_pin,
    record_universe_fingerprint,
    resolve_judge_pack,
    validate_prompt_pack,
)
from git_cg.eval.lane_c.runner import (
    DEFAULT_LANE_C_METRICS,
    LaneCRunResult,
    run_lane_c,
)
from git_cg.eval.lane_c.taxonomy import (
    EXECUTION_CODES,
    GATE_DISPOSITION_CODES,
    GATE_TO_EXECUTION,
    TaxonomyError,
    assert_execution_code,
    assert_gate_disposition,
    failure_id_for,
    map_gate_to_execution,
    mapping_table,
    validate_closed_reason,
)

__all__ = [
    "DEFAULT_LANE_C_METRICS",
    "DEFAULT_OUTPUT_CONTRACT_IDENTITY",
    "DEFAULT_PACK_IDENTITY",
    "DEFAULT_PROMPT_ROOT",
    "DEFAULT_SAMPLING_IDENTITY",
    "DEFAULT_UNIVERSE_ROOT",
    "ENV_JUDGE_API_KEY",
    "ENV_JUDGE_BASE_URL",
    "ENV_JUDGE_MODEL",
    "EXECUTION_CODES",
    "GATE_DISPOSITION_CODES",
    "GATE_TO_EXECUTION",
    "LaneCAvailability",
    "LaneCEligibility",
    "LaneCRunResult",
    "PromptPackError",
    "TaxonomyError",
    "UniverseFingerprint",
    "assert_execution_code",
    "assert_gate_disposition",
    "build_prompt_pack",
    "credentials_present",
    "evaluate_judge_availability",
    "evaluate_semantic_cohort_eligibility",
    "failure_id_for",
    "is_undated_model_alias",
    "judge_identity_pins_resolvable",
    "judge_pins_resolvable",
    "lint_prompt_pack_hygiene",
    "load_pack_prompt_text",
    "map_gate_to_execution",
    "mapping_table",
    "prompt_pack_content_hash",
    "prompt_pack_pin",
    "provider_client_constructible",
    "record_universe_fingerprint",
    "resolve_allows_lane_c",
    "resolve_judge_pack",
    "resolve_lab_override",
    "run_lane_c",
    "validate_closed_reason",
    "validate_prompt_pack",
]
