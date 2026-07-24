"""Orchestration layer for guided regeneration and semantic contract resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from git_cg.intent import DiffSignals, IntentSelectionConstraints, RankedIntent, matrix_row_intent_id
from git_cg.models import CommitPlan
from git_cg.sop import get_gitmoji_matrix


@dataclass
class GenerationContext:
    """Deterministic context derived from the diff and SOP.

    Phase 7 optional fields (``semantic_summary``, ``risk_assessment``) are ignored by
    ``resolve_semantic_contract`` / ``enforce_semantic_contract`` — matrix authority only.
    """

    diff_signals: DiffSignals
    ranked_intents: list[RankedIntent]
    constraints: IntentSelectionConstraints
    semantic_summary: Any | None = None  # SemanticDiffSummary | None (typed at edges)
    risk_assessment: Any | None = None  # RiskAssessment | None
    scope_priors: Any | None = None  # Phase 8.5 placeholder
    preflight_groups: Any | None = None  # Phase 0.5 placeholder


@dataclass
class RegenerationState:
    """Review-loop steering state."""

    previous_plan: CommitPlan | None = None
    active_directives: dict[str, str] = field(default_factory=dict)
    residual_guidance: str | None = None


@dataclass
class ResolvedCommitContract:
    """The Python-owned semantic contract for the next render."""

    primary_intent_id: str
    gitmoji: str
    cc_type: str
    semver_impact: str
    changelog_group: str
    secondary_intent_ids: list[str]


def resolve_semantic_contract(context: GenerationContext, state: RegenerationState) -> ResolvedCommitContract:
    """
    Resolve the semantic commit contract for the next generation cycle.

    Selects a primary intent using active directives, allowed-intent constraints, ranked
    intents, and the previous plan when available. Uses a graceful fallback contract when
    the gitmoji matrix is unavailable.

    Parameters:
        context (GenerationContext): Inputs containing ranked intents and selection constraints.
        state (RegenerationState): Steering state containing active directives and an optional previous plan.

    Returns:
        ResolvedCommitContract: The selected primary intent metadata and secondary intent identifiers.
    """
    matrix = get_gitmoji_matrix()
    if not matrix:
        # Extremely graceful fallback if SOP is broken
        return ResolvedCommitContract(
            primary_intent_id="unknown",
            gitmoji="🔧",
            cc_type="chore",
            semver_impact="NONE",
            changelog_group="Miscellaneous",
            secondary_intent_ids=[],
        )

    preferred_type = state.active_directives.get("preferred_type")
    resolved_row = None
    allowed_ids = set(context.constraints.allowed_intent_ids) if context.constraints.allowed_intent_ids else None

    if preferred_type:
        for ranked in context.ranked_intents:
            if ranked.cc_type == preferred_type:
                if allowed_ids and ranked.intent_id not in allowed_ids:
                    continue
                resolved_row = next(
                    (r for r in matrix if matrix_row_intent_id(r) == ranked.intent_id),
                    None,
                )
                if resolved_row:
                    break

        if not resolved_row:
            # Fallback to the first matrix row matching the type if no ranked candidates work
            if allowed_ids:
                resolved_row = next(
                    (
                        r
                        for r in matrix
                        if r.get("cc_type") == preferred_type and matrix_row_intent_id(r) in allowed_ids
                    ),
                    None,
                )
            else:
                resolved_row = next((r for r in matrix if r.get("cc_type") == preferred_type), None)

    if not resolved_row and state.previous_plan is not None:
        # Stable anchor to the previous plan only when still allowed by constraints.
        prev_intent_id = state.previous_plan.primary_intent.intent_id
        if not allowed_ids or prev_intent_id in allowed_ids:
            resolved_row = next(
                (r for r in matrix if matrix_row_intent_id(r) == prev_intent_id),
                None,
            )

    if not resolved_row:
        # First-pass / disallowed previous plan: lock to top ranked intent (constraints-aware)
        for ranked in context.ranked_intents:
            if allowed_ids and ranked.intent_id not in allowed_ids:
                continue
            resolved_row = next(
                (r for r in matrix if matrix_row_intent_id(r) == ranked.intent_id),
                None,
            )
            if resolved_row:
                break

    if not resolved_row:
        if allowed_ids:
            resolved_row = next(
                (r for r in matrix if matrix_row_intent_id(r) in allowed_ids),
                matrix[0],
            )
        else:
            resolved_row = matrix[0]

    primary_id = matrix_row_intent_id(resolved_row)

    return ResolvedCommitContract(
        primary_intent_id=primary_id,
        gitmoji=resolved_row.get("emoji", ""),
        cc_type=resolved_row.get("cc_type", "chore"),
        semver_impact=resolved_row.get("semver_impact", "NONE"),
        changelog_group=resolved_row.get("changelog_group", "Miscellaneous"),
        secondary_intent_ids=(
            [sec.intent_id for sec in state.previous_plan.secondary_intents] if state.previous_plan else []
        ),
    )


def enforce_semantic_contract(
    plan: CommitPlan, contract: ResolvedCommitContract, active_directives: dict[str, str] | None = None
) -> CommitPlan:
    """
    Overwrite a CommitPlan's primary intent fields to match a resolved semantic contract.

    If `active_directives` contains `preferred_scope`, the plan's primary intent scope is set to that value.

    Parameters:
        active_directives (dict[str, str] | None): Optional directives; recognise `preferred_scope` to override the primary intent scope.

    Returns:
        CommitPlan: The same plan instance with its primary intent aligned to the contract.
    """
    from git_cg.models import CommitType, SemVerImpact

    # 1. Lock primary intent fields to the contract
    plan.primary_intent.intent_id = contract.primary_intent_id
    plan.primary_intent.gitmoji = contract.gitmoji
    plan.primary_intent.cc_type = CommitType(contract.cc_type)
    plan.primary_intent.semver_impact = SemVerImpact(contract.semver_impact)
    plan.primary_intent.changelog_group = contract.changelog_group

    # 2. Lock scope if a preferred_scope directive is active
    if active_directives and "preferred_scope" in active_directives:
        plan.primary_intent.scope = active_directives["preferred_scope"]

    return plan
