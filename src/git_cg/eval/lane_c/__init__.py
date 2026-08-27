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

Slice 6 lab residuals (advisory/non-gating only)
    :func:`run_judge_meta_eval` — R2 Equals / FP / FN lab envelope
    :func:`resolve_richer_rubric_metrics` — R1 opt-in richer rubric ids
    :func:`measure_flakiness` — R8 lab flakiness hooks
    :func:`compute_nlp_diagnostics` — R10 NLP diagnostics
    :func:`evaluate_moderation_ops` — R6 scrubbed ops signal (#219 plane)
    :func:`activate_dirty_overlay` — R5 dirty-overlay provenance guard

This package is import-safe with no provider SDK, no network, and no ambient
secret export. Provider SDKs are lazy-imported only inside transport paths
(Slice 4); ``import git_cg.eval.lane_c`` must remain SDK-free (S5-E08).

Import law: import-light. Package attribute exports are lazy so submodule
imports such as ``git_cg.eval.lane_c.prompt_pack`` stay free of binder /
judge-transport composition until those symbols are actually resolved.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "DEFAULT_LANE_C_METRICS",
    "DEFAULT_MAX_DIFF_SUMMARY_CHARS",
    "DEFAULT_MAX_INPUT_CHARS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_OUTPUT_CONTRACT_IDENTITY",
    "DEFAULT_OVERLAY_DIR",
    "DEFAULT_PACK_IDENTITY",
    "DEFAULT_PROMPT_ROOT",
    "DEFAULT_RICHER_RUBRIC_METRICS",
    "DEFAULT_SAMPLING_IDENTITY",
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_UNIVERSE_ROOT",
    "DIRTY_PROVENANCE_LABEL",
    "ENV_JUDGE_API_KEY",
    "ENV_JUDGE_BASE_URL",
    "ENV_JUDGE_MODEL",
    "ERROR_TYPES",
    "EXECUTION_CODES",
    "GATE_DISPOSITION_CODES",
    "GATE_TO_EXECUTION",
    "GEVAL_SCALE",
    "MAX_RATIONALE_CHARS",
    "NLP_METRIC_IDS",
    "RICHER_RUBRIC_METRICS",
    "DiagnosticError",
    "DirtyOverlayError",
    "DirtyOverlayProvenance",
    "FlakinessResult",
    "JudgeCredentialView",
    "JudgeFn",
    "JudgeInput",
    "JudgeInputError",
    "JudgeOutcome",
    "JudgeTransportResult",
    "LaneCAvailability",
    "LaneCEligibility",
    "LaneCRunResult",
    "MetaEvalError",
    "MetaEvalItem",
    "MetaEvalResult",
    "ModerationResult",
    "NlpDiagnosticResult",
    "PromptPackError",
    "TaxonomyError",
    "UniverseFingerprint",
    "activate_dirty_overlay",
    "assert_execution_code",
    "assert_gate_disposition",
    "assert_labels_absent_from_ordinary_payload",
    "assert_overlay_not_on_green_path",
    "build_judge_meta_eval",
    "build_prompt_pack",
    "classify_equals_error",
    "classify_judge_input_size",
    "compute_nlp_diagnostics",
    "credentials_present",
    "emit_meta_eval_scores",
    "evaluate_judge_availability",
    "evaluate_moderation_ops",
    "evaluate_semantic_cohort_eligibility",
    "failure_id_for",
    "is_undated_model_alias",
    "judge_identity_pins_resolvable",
    "judge_pins_resolvable",
    "lint_prompt_pack_hygiene",
    "load_pack_prompt_text",
    "make_advisory_score",
    "make_advisory_skip",
    "map_gate_to_execution",
    "mapping_table",
    "measure_flakiness",
    "openai_compatible_judge_fn",
    "overlays_exist_in_tree",
    "parse_judge_score",
    "project_diff_summary",
    "project_judge_input",
    "prompt_pack_content_hash",
    "prompt_pack_pin",
    "provider_client_constructible",
    "record_universe_fingerprint",
    "resolve_allows_lane_c",
    "resolve_judge_credentials",
    "resolve_judge_pack",
    "resolve_lab_override",
    "resolve_richer_rubric_metrics",
    "run_judge_meta_eval",
    "run_lane_c",
    "run_pinned_judge",
    "scrub_rationale",
    "stamp_dirty_provenance",
    "summarize_meta_eval",
    "validate_closed_reason",
    "validate_prompt_pack",
]

_EXPORT_MODULES: dict[str, str] = {
    "DEFAULT_LANE_C_METRICS": "git_cg.eval.lane_c.runner",
    "DEFAULT_MAX_DIFF_SUMMARY_CHARS": "git_cg.eval.lane_c.judge_input",
    "DEFAULT_MAX_INPUT_CHARS": "git_cg.eval.lane_c.judge_input",
    "DEFAULT_MAX_RETRIES": "git_cg.eval.lane_c.judge",
    "DEFAULT_OUTPUT_CONTRACT_IDENTITY": "git_cg.eval.lane_c.eligibility",
    "DEFAULT_OVERLAY_DIR": "git_cg.eval.lane_c.provenance",
    "DEFAULT_PACK_IDENTITY": "git_cg.eval.lane_c.eligibility",
    "DEFAULT_PROMPT_ROOT": "git_cg.eval.lane_c.prompt_pack",
    "DEFAULT_RICHER_RUBRIC_METRICS": "git_cg.eval.lane_c.diagnostics",
    "DEFAULT_SAMPLING_IDENTITY": "git_cg.eval.lane_c.eligibility",
    "DEFAULT_TIMEOUT_S": "git_cg.eval.lane_c.judge",
    "DEFAULT_UNIVERSE_ROOT": "git_cg.eval.lane_c.prompt_pack",
    "DIRTY_PROVENANCE_LABEL": "git_cg.eval.lane_c.provenance",
    "ENV_JUDGE_API_KEY": "git_cg.eval.lane_c.availability",
    "ENV_JUDGE_BASE_URL": "git_cg.eval.lane_c.availability",
    "ENV_JUDGE_MODEL": "git_cg.eval.lane_c.eligibility",
    "ERROR_TYPES": "git_cg.eval.lane_c.meta_eval",
    "EXECUTION_CODES": "git_cg.eval.lane_c.taxonomy",
    "GATE_DISPOSITION_CODES": "git_cg.eval.lane_c.taxonomy",
    "GATE_TO_EXECUTION": "git_cg.eval.lane_c.taxonomy",
    "GEVAL_SCALE": "git_cg.eval.lane_c.advisory",
    "MAX_RATIONALE_CHARS": "git_cg.eval.lane_c.advisory",
    "NLP_METRIC_IDS": "git_cg.eval.lane_c.diagnostics",
    "RICHER_RUBRIC_METRICS": "git_cg.eval.lane_c.diagnostics",
    "DiagnosticError": "git_cg.eval.lane_c.diagnostics",
    "DirtyOverlayError": "git_cg.eval.lane_c.provenance",
    "DirtyOverlayProvenance": "git_cg.eval.lane_c.provenance",
    "FlakinessResult": "git_cg.eval.lane_c.diagnostics",
    "JudgeCredentialView": "git_cg.eval.lane_c.judge",
    "JudgeFn": "git_cg.eval.lane_c.judge",
    "JudgeInput": "git_cg.eval.lane_c.judge_input",
    "JudgeInputError": "git_cg.eval.lane_c.judge_input",
    "JudgeOutcome": "git_cg.eval.lane_c.judge",
    "JudgeTransportResult": "git_cg.eval.lane_c.judge",
    "LaneCAvailability": "git_cg.eval.lane_c.availability",
    "LaneCEligibility": "git_cg.eval.lane_c.eligibility",
    "LaneCRunResult": "git_cg.eval.lane_c.runner",
    "MetaEvalError": "git_cg.eval.lane_c.meta_eval",
    "MetaEvalItem": "git_cg.eval.lane_c.meta_eval",
    "MetaEvalResult": "git_cg.eval.lane_c.meta_eval",
    "ModerationResult": "git_cg.eval.lane_c.diagnostics",
    "NlpDiagnosticResult": "git_cg.eval.lane_c.diagnostics",
    "PromptPackError": "git_cg.eval.lane_c.prompt_pack",
    "TaxonomyError": "git_cg.eval.lane_c.taxonomy",
    "UniverseFingerprint": "git_cg.eval.lane_c.prompt_pack",
    "activate_dirty_overlay": "git_cg.eval.lane_c.provenance",
    "assert_execution_code": "git_cg.eval.lane_c.taxonomy",
    "assert_gate_disposition": "git_cg.eval.lane_c.taxonomy",
    "assert_labels_absent_from_ordinary_payload": "git_cg.eval.lane_c.meta_eval",
    "assert_overlay_not_on_green_path": "git_cg.eval.lane_c.provenance",
    "build_judge_meta_eval": "git_cg.eval.lane_c.meta_eval",
    "build_prompt_pack": "git_cg.eval.lane_c.prompt_pack",
    "classify_equals_error": "git_cg.eval.lane_c.meta_eval",
    "classify_judge_input_size": "git_cg.eval.lane_c.judge_input",
    "compute_nlp_diagnostics": "git_cg.eval.lane_c.diagnostics",
    "credentials_present": "git_cg.eval.lane_c.availability",
    "emit_meta_eval_scores": "git_cg.eval.lane_c.meta_eval",
    "evaluate_judge_availability": "git_cg.eval.lane_c.availability",
    "evaluate_moderation_ops": "git_cg.eval.lane_c.diagnostics",
    "evaluate_semantic_cohort_eligibility": "git_cg.eval.lane_c.eligibility",
    "failure_id_for": "git_cg.eval.lane_c.taxonomy",
    "is_undated_model_alias": "git_cg.eval.lane_c.eligibility",
    "judge_identity_pins_resolvable": "git_cg.eval.lane_c.eligibility",
    "judge_pins_resolvable": "git_cg.eval.lane_c.eligibility",
    "lint_prompt_pack_hygiene": "git_cg.eval.lane_c.prompt_pack",
    "load_pack_prompt_text": "git_cg.eval.lane_c.prompt_pack",
    "make_advisory_score": "git_cg.eval.lane_c.advisory",
    "make_advisory_skip": "git_cg.eval.lane_c.advisory",
    "map_gate_to_execution": "git_cg.eval.lane_c.taxonomy",
    "mapping_table": "git_cg.eval.lane_c.taxonomy",
    "measure_flakiness": "git_cg.eval.lane_c.diagnostics",
    "openai_compatible_judge_fn": "git_cg.eval.lane_c.judge",
    "overlays_exist_in_tree": "git_cg.eval.lane_c.provenance",
    "parse_judge_score": "git_cg.eval.lane_c.judge",
    "project_diff_summary": "git_cg.eval.lane_c.judge_input",
    "project_judge_input": "git_cg.eval.lane_c.judge_input",
    "prompt_pack_content_hash": "git_cg.eval.lane_c.prompt_pack",
    "prompt_pack_pin": "git_cg.eval.lane_c.prompt_pack",
    "provider_client_constructible": "git_cg.eval.lane_c.availability",
    "record_universe_fingerprint": "git_cg.eval.lane_c.prompt_pack",
    "resolve_allows_lane_c": "git_cg.eval.lane_c.eligibility",
    "resolve_judge_credentials": "git_cg.eval.lane_c.judge",
    "resolve_judge_pack": "git_cg.eval.lane_c.prompt_pack",
    "resolve_lab_override": "git_cg.eval.lane_c.eligibility",
    "resolve_richer_rubric_metrics": "git_cg.eval.lane_c.diagnostics",
    "run_judge_meta_eval": "git_cg.eval.lane_c.meta_eval",
    "run_lane_c": "git_cg.eval.lane_c.runner",
    "run_pinned_judge": "git_cg.eval.lane_c.judge",
    "scrub_rationale": "git_cg.eval.lane_c.advisory",
    "stamp_dirty_provenance": "git_cg.eval.lane_c.provenance",
    "summarize_meta_eval": "git_cg.eval.lane_c.meta_eval",
    "validate_closed_reason": "git_cg.eval.lane_c.taxonomy",
    "validate_prompt_pack": "git_cg.eval.lane_c.prompt_pack",
}

if TYPE_CHECKING:
    from git_cg.eval.lane_c.advisory import (
        GEVAL_SCALE,
        MAX_RATIONALE_CHARS,
        make_advisory_score,
        make_advisory_skip,
        scrub_rationale,
    )
    from git_cg.eval.lane_c.availability import (
        ENV_JUDGE_API_KEY,
        ENV_JUDGE_BASE_URL,
        LaneCAvailability,
        credentials_present,
        evaluate_judge_availability,
        provider_client_constructible,
    )
    from git_cg.eval.lane_c.diagnostics import (
        DEFAULT_RICHER_RUBRIC_METRICS,
        NLP_METRIC_IDS,
        RICHER_RUBRIC_METRICS,
        DiagnosticError,
        FlakinessResult,
        ModerationResult,
        NlpDiagnosticResult,
        compute_nlp_diagnostics,
        evaluate_moderation_ops,
        measure_flakiness,
        resolve_richer_rubric_metrics,
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
    from git_cg.eval.lane_c.judge import (
        DEFAULT_MAX_RETRIES,
        DEFAULT_TIMEOUT_S,
        JudgeCredentialView,
        JudgeFn,
        JudgeOutcome,
        JudgeTransportResult,
        openai_compatible_judge_fn,
        parse_judge_score,
        resolve_judge_credentials,
        run_pinned_judge,
    )
    from git_cg.eval.lane_c.judge_input import (
        DEFAULT_MAX_DIFF_SUMMARY_CHARS,
        DEFAULT_MAX_INPUT_CHARS,
        JudgeInput,
        JudgeInputError,
        classify_judge_input_size,
        project_diff_summary,
        project_judge_input,
    )
    from git_cg.eval.lane_c.meta_eval import (
        ERROR_TYPES,
        MetaEvalError,
        MetaEvalItem,
        MetaEvalResult,
        assert_labels_absent_from_ordinary_payload,
        build_judge_meta_eval,
        classify_equals_error,
        emit_meta_eval_scores,
        run_judge_meta_eval,
        summarize_meta_eval,
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
    from git_cg.eval.lane_c.provenance import (
        DEFAULT_OVERLAY_DIR,
        DIRTY_PROVENANCE_LABEL,
        DirtyOverlayError,
        DirtyOverlayProvenance,
        activate_dirty_overlay,
        assert_overlay_not_on_green_path,
        overlays_exist_in_tree,
        stamp_dirty_provenance,
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


def __getattr__(name: str) -> Any:
    """Resolve public exports lazily (import-light package surface)."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
