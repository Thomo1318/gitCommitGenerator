"""Orchestration layer for guided regeneration and semantic contract resolution."""

from dataclasses import dataclass, field

from git_cg.intent import DiffSignals, IntentSelectionConstraints, RankedIntent
from git_cg.models import CommitPlan
from git_cg.sop import get_gitmoji_matrix


@dataclass
class GenerationContext:
    """Deterministic context derived from the diff and SOP."""

    diff_signals: DiffSignals
    ranked_intents: list[RankedIntent]
    constraints: IntentSelectionConstraints


@dataclass
class RegenerationState:
    """Review-loop steering state."""

    previous_plan: CommitPlan
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
    Determine the semantic commit contract to use for the next generation cycle.
    
    Selects a primary intent row from the gitmoji contract matrix using an optional
    active directive (`preferred_type`) while respecting allowed-intent constraints,
    and otherwise anchors selection to the previous plan's primary intent to avoid
    semantic drift. Secondary intent ids are taken from the previous plan.
    
    Parameters:
        context (GenerationContext): Deterministic inputs for resolution, including ranked intents and selection constraints.
        state (RegenerationState): Review-loop steering state, including active directives and the previous commit plan.
    
    Returns:
        ResolvedCommitContract: The resolved semantic contract containing the chosen primary intent id, associated emoji, commit classification type, SemVer impact, changelog group, and secondary intent ids.
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

    if preferred_type:
        allowed_ids = set(context.constraints.allowed_intent_ids) if context.constraints.allowed_intent_ids else None

        for ranked in context.ranked_intents:
            if ranked.cc_type == preferred_type:
                if allowed_ids and ranked.intent_id not in allowed_ids:
                    continue
                resolved_row = next(
                    (r for r in matrix if r.get("intent_id", r.get("code", "").strip(":")) == ranked.intent_id), None
                )
                if resolved_row:
                    break

        if not resolved_row:
            # Fallback to the first matrix row matching the type if no ranked candidates work
            resolved_row = next((r for r in matrix if r.get("cc_type") == preferred_type), None)

    if not resolved_row:
        # Stable anchor to the previous plan
        prev_intent_id = state.previous_plan.primary_intent.intent_id
        resolved_row = next(
            (r for r in matrix if r.get("intent_id", r.get("code", "").strip(":")) == prev_intent_id), matrix[0]
        )

    primary_id = resolved_row.get("intent_id", resolved_row.get("code", "unknown").strip(":"))

    return ResolvedCommitContract(
        primary_intent_id=primary_id,
        gitmoji=resolved_row.get("emoji", ""),
        cc_type=resolved_row.get("cc_type", "chore"),
        semver_impact=resolved_row.get("semver_impact", "NONE"),
        changelog_group=resolved_row.get("changelog_group", "Miscellaneous"),
        secondary_intent_ids=[sec.intent_id for sec in state.previous_plan.secondary_intents],
    )
