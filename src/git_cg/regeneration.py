"""Orchestration layer for guided regeneration and semantic contract resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from git_cg.intent import DiffSignals, IntentSelectionConstraints, RankedIntent, matrix_row_intent_id
from git_cg.models import CommitPlan
from git_cg.ranking_confidence import RankingConfidence
from git_cg.sop import get_gitmoji_matrix
from git_cg.telemetry import LockResolution


@dataclass
class GenerationContext:
    """Deterministic context derived from the diff and SOP.

    Phase 7 optional fields (``semantic_summary``, ``risk_assessment``) are ignored by
    ``resolve_semantic_contract`` / ``enforce_semantic_contract`` — matrix authority only.

    Issue #195: ``ranked_intents`` + ``ranking_confidence`` form an immutable pair owned
    by the sole rank-pass seam (``_build_generation_context``). Downstream consumers
    must receive this snapshot and must not re-run ranking or confidence.

    Issue #204: ``scope_priors`` carries frozen ``TrailerPriors`` (edge-typed as Any to
    avoid a regeneration → commit_quality import cycle). Presentation only — never a
    second ranker.
    """

    diff_signals: DiffSignals
    ranked_intents: list[RankedIntent]
    constraints: IntentSelectionConstraints
    semantic_summary: Any | None = None  # SemanticDiffSummary | None (typed at edges)
    risk_assessment: Any | None = None  # RiskAssessment | None
    scope_priors: Any | None = None  # Issue #204 TrailerPriors (edge-typed; D25)
    presentation_constraints: Any | None = None  # Issue #204 DiffClass constraints (D25)
    preflight_groups: Any | None = None  # Phase 0.5 placeholder
    ranking_confidence: RankingConfidence | None = None  # Issue #195 — same rank-pass


@dataclass
class RegenerationState:
    """Review-loop steering state."""

    previous_plan: CommitPlan | None = None
    active_directives: dict[str, str] = field(default_factory=dict)
    residual_guidance: str | None = None
    # Issue #195: human / cancel→A lock. First-class field — do not overload preferred_type.
    locked_intent_id: str | None = None


@dataclass
class ResolvedCommitContract:
    """The Python-owned semantic contract for the next render."""

    primary_intent_id: str
    gitmoji: str
    cc_type: str
    semver_impact: str
    changelog_group: str
    secondary_intent_ids: list[str]
    # Issue #195: closed observability for lock acceptance / rejection.
    lock_resolution: LockResolution = "absent"


def _row_is_eligible(intent_id: str, allowed_ids: set[str] | None) -> bool:
    """Return whether ``intent_id`` is inside the constrained eligible set."""
    if allowed_ids is None:
        return True
    return intent_id in allowed_ids


def _classify_lock_rejection(
    locked_intent_id: str,
    *,
    allowed_ids: set[str] | None,
    matrix_ids: set[str],
) -> LockResolution:
    """Classify why a lock was not selected (closed codes only)."""
    if allowed_ids is not None and locked_intent_id not in allowed_ids:
        return "rejected_not_allowed"
    if locked_intent_id not in matrix_ids:
        return "rejected_hard_veto"
    # Present on matrix and allowed, but still not selected (e.g. preferred_type
    # path already chose something else without an eligible lock — should not
    # happen when lock is eligible). Treat as hard veto for observability.
    return "rejected_hard_veto"


def _matrix_row_for_intent(matrix: list[dict], intent_id: str) -> dict | None:
    return next((r for r in matrix if matrix_row_intent_id(r) == intent_id), None)


def resolve_semantic_contract(context: GenerationContext, state: RegenerationState) -> ResolvedCommitContract:
    """
    Resolve the semantic commit contract for the next generation cycle.

    Selection order over the already-constrained eligible set (Issue #195):
    ``locked_intent_id`` (if still eligible) → ``previous_plan`` (if eligible) →
    ranked/default fallback. ``preferred_type`` narrows inside eligible but must
    not discard an eligible human lock and must not select outside eligible.

    Parameters:
        context (GenerationContext): Inputs containing ranked intents and selection constraints.
        state (RegenerationState): Steering state containing active directives, optional previous plan,
            and optional ``locked_intent_id``.

    Returns:
        ResolvedCommitContract: The selected primary intent metadata, secondary intent identifiers,
            and closed ``lock_resolution`` observability.
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
            lock_resolution="absent",
        )

    preferred_type = state.active_directives.get("preferred_type")
    locked_intent_id = state.locked_intent_id
    allowed_ids = set(context.constraints.allowed_intent_ids) if context.constraints.allowed_intent_ids else None
    matrix_ids = {matrix_row_intent_id(r) for r in matrix}

    resolved_row: dict | None = None
    lock_resolution: LockResolution = "absent"

    def _try_lock() -> dict | None:
        nonlocal lock_resolution
        if locked_intent_id is None:
            lock_resolution = "absent"
            return None
        if not _row_is_eligible(locked_intent_id, allowed_ids):
            lock_resolution = _classify_lock_rejection(
                locked_intent_id,
                allowed_ids=allowed_ids,
                matrix_ids=matrix_ids,
            )
            return None
        row = _matrix_row_for_intent(matrix, locked_intent_id)
        if row is None:
            lock_resolution = "rejected_hard_veto"
            return None
        lock_resolution = "accepted"
        return row

    def _try_previous_plan() -> dict | None:
        if state.previous_plan is None:
            return None
        prev_intent_id = state.previous_plan.primary_intent.intent_id
        if not _row_is_eligible(prev_intent_id, allowed_ids):
            return None
        return _matrix_row_for_intent(matrix, prev_intent_id)

    def _try_ranked_or_matrix(*, cc_type_filter: str | None = None) -> dict | None:
        for ranked in context.ranked_intents:
            if allowed_ids and ranked.intent_id not in allowed_ids:
                continue
            if cc_type_filter is not None and ranked.cc_type != cc_type_filter:
                continue
            row = _matrix_row_for_intent(matrix, ranked.intent_id)
            if row is not None:
                return row
        # Matrix fallback inside eligible (+ optional preferred_type).
        for row in matrix:
            intent_id = matrix_row_intent_id(row)
            if allowed_ids and intent_id not in allowed_ids:
                continue
            if cc_type_filter is not None and row.get("cc_type") != cc_type_filter:
                continue
            return row
        return None

    # Normative algorithm (Issue #195 contract lock):
    # preferred_type narrows inside eligible; eligible lock still beats preferred drift.
    if preferred_type:
        preferred_hit = _try_ranked_or_matrix(cc_type_filter=preferred_type)
        if preferred_hit is not None:
            locked_row = _try_lock()
            # Lock absent or rejected - preferred_type may select among eligible.
            resolved_row = locked_row if locked_row is not None else preferred_hit
        else:
            # No preferred_type hit inside eligible → lock → previous_plan → ranked/default.
            resolved_row = _try_lock() or _try_previous_plan() or _try_ranked_or_matrix()
    else:
        resolved_row = _try_lock() or _try_previous_plan() or _try_ranked_or_matrix()

    if resolved_row is None:
        if allowed_ids:
            resolved_row = next(
                (r for r in matrix if matrix_row_intent_id(r) in allowed_ids),
                matrix[0],
            )
        else:
            resolved_row = matrix[0]
        if locked_intent_id is not None and lock_resolution == "absent":
            lock_resolution = _classify_lock_rejection(
                locked_intent_id,
                allowed_ids=allowed_ids,
                matrix_ids=matrix_ids,
            )

    # If a lock was supplied but we did not accept it, ensure rejection is classified.
    if locked_intent_id is not None and lock_resolution == "absent":
        selected_id = matrix_row_intent_id(resolved_row)
        if selected_id == locked_intent_id:
            lock_resolution = "accepted"
        else:
            lock_resolution = _classify_lock_rejection(
                locked_intent_id,
                allowed_ids=allowed_ids,
                matrix_ids=matrix_ids,
            )

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
        lock_resolution=lock_resolution,
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

    # 2. Lock scope if a preferred_scope directive is active.
    # I-12 / #204 §J: always route through normalize_scope (never assign raw token).
    if active_directives and "preferred_scope" in active_directives:
        from git_cg.scope_canon import normalize_scope

        plan.primary_intent.scope = normalize_scope(active_directives["preferred_scope"])

    return plan


# Closed SemVer rank for lift-only floor comparisons (presentation must not demote
# a locked contract). Mirrors commit_quality._SEMVER_RANK without importing it
# (avoids regeneration → commit_quality cycle).
_CONTRACT_SEMVER_RANK: dict[str, int] = {
    "NONE": 0,
    "PATCH": 1,
    "MINOR": 2,
    "MAJOR": 3,
}


def lift_plan_to_contract_semver(
    plan: CommitPlan,
    contract: ResolvedCommitContract,
) -> tuple[CommitPlan, bool, str | None]:
    """Lift primary SemVer up to the locked contract floor when presentation demoted it.

    Slice 5 hotfix (#204): ``enforce_semantic_contract`` runs *before* presentation
    seed/overlay. Overlay ceilings and low-confidence seeds may clamp SemVer below
    the locked contract. This guard re-asserts the contract as a hard lower bound.

    Lift-only semantics:
    * If plan SemVer rank < contract SemVer rank → lift plan to contract value.
    * If plan already ≥ contract → no-op (never lower).
    * Never mutates intent_id / gitmoji / cc_type / changelog / scope.
    * Never raises on bad enum values — returns no-op.

    Returns:
        tuple[CommitPlan, bool, str | None]: ``(plan, lift_applied, from_semver)``.
        ``from_semver`` is the pre-lift value when a lift occurred, else ``None``.
    """
    from git_cg.models import SemVerImpact

    try:
        contract_raw = str(getattr(contract, "semver_impact", "") or "").upper()
        plan_raw = str(getattr(plan.primary_intent, "semver_impact", "") or "").upper()
        # Normalise enum members to their value strings.
        if hasattr(plan.primary_intent.semver_impact, "value"):
            plan_raw = str(plan.primary_intent.semver_impact.value).upper()
        contract_rank = _CONTRACT_SEMVER_RANK.get(contract_raw)
        plan_rank = _CONTRACT_SEMVER_RANK.get(plan_raw)
        if contract_rank is None or plan_rank is None:
            return plan, False, None
        if plan_rank >= contract_rank:
            return plan, False, None
        from_semver = plan_raw
        plan.primary_intent.semver_impact = SemVerImpact(contract_raw)
        return plan, True, from_semver
    except Exception:
        return plan, False, None


@dataclass(frozen=True)
class ContractLifecycleSnapshot:
    """Closed-vocabulary contract lifecycle snapshot (Issue #204 · Slice 5.5)."""

    contract_locked_semver: str | None
    llm_raw_semver: str | None
    plan_persisted_semver: str | None
    contract_lift_applied: bool
    contract_lift_from_semver: str | None
    contract_violation: bool
    plan_normaliser_applied: bool
    plan_normaliser_reason: str
    contract_consistent: bool


def _closed_semver_str(value: object) -> str | None:
    """Normalise a SemVer-like value to the closed vocabulary or ``None``."""
    if value is None or value == "":
        return None
    if hasattr(value, "value"):
        value = value.value
    raw = str(value).strip().upper()
    return raw if raw in _CONTRACT_SEMVER_RANK else None


def evaluate_contract_lifecycle(
    *,
    locked_semver: object,
    llm_raw_semver: object,
    persisted_semver: object,
    lift_applied: bool,
    lift_from_semver: object = None,
    presentation_touched: bool = False,
    residual_below_floor: bool = False,
) -> ContractLifecycleSnapshot:
    """Evaluate locked → LLM raw → lifted/persisted contract lifecycle fields.

    Pure helper (Issue #204 · Slice 5.5). Never mutates plans. Emits only closed
    SemVer strings / bools / ``PlanNormaliserReason`` values.

    Precedence for ``plan_normaliser_reason`` (single primary):
    1. residual_violation — persisted still below locked floor after lift
    2. malformed_semver — locked or persisted not in closed vocab
    3. contract_lift — Slice 5 lift repaired a demotion
    4. presentation_clamp — presentation path touched SemVer but lift not needed
       or lift already accounted separately; used when presentation ran and
       raw/persisted differ without residual violation
    5. none
    """
    from git_cg.telemetry import PlanNormaliserReason

    locked = _closed_semver_str(locked_semver)
    raw = _closed_semver_str(llm_raw_semver)
    persisted = _closed_semver_str(persisted_semver)
    from_sem = _closed_semver_str(lift_from_semver)
    lift = bool(lift_applied)

    locked_rank = _CONTRACT_SEMVER_RANK.get(locked) if locked is not None else None
    persisted_rank = _CONTRACT_SEMVER_RANK.get(persisted) if persisted is not None else None

    malformed = locked is None or persisted is None
    below_floor = False
    if locked_rank is not None and persisted_rank is not None:
        below_floor = persisted_rank < locked_rank
    # Residual violation: still below floor after the lift attempt, or explicit flag.
    residual = bool(residual_below_floor) or below_floor
    # contract_violation is true when locked floor is not honoured by persisted plan.
    violation = residual or (malformed and locked is not None and persisted is not None and locked != persisted)

    if residual:
        reason = PlanNormaliserReason.RESIDUAL_VIOLATION.value
        normaliser_applied = True
    elif malformed and (locked is None or persisted is None):
        reason = PlanNormaliserReason.MALFORMED_SEMVER.value
        normaliser_applied = lift or presentation_touched
        # Malformed alone is not a hard violation if we cannot compare ranks.
        violation = False if locked is None or persisted is None else violation
    elif lift:
        reason = PlanNormaliserReason.CONTRACT_LIFT.value
        normaliser_applied = True
        violation = False  # lift repaired demotion; persisted should match floor
        # Re-check: if lift claimed applied but still below, residual wins above.
    elif presentation_touched and raw is not None and persisted is not None and raw != persisted:
        reason = PlanNormaliserReason.PRESENTATION_CLAMP.value
        normaliser_applied = True
    elif (
        presentation_touched
        and locked is not None
        and persisted is not None
        and locked != persisted
        and not below_floor
    ):
        # Presentation raised or changed without demoting below floor.
        reason = PlanNormaliserReason.PRESENTATION_CLAMP.value
        normaliser_applied = True
    else:
        reason = PlanNormaliserReason.NONE.value
        normaliser_applied = False

    # If lift applied, persisted is expected >= locked; treat as consistent unless residual.
    if lift and not residual:
        violation = False

    consistent = not violation

    return ContractLifecycleSnapshot(
        contract_locked_semver=locked,
        llm_raw_semver=raw,
        plan_persisted_semver=persisted,
        contract_lift_applied=lift,
        contract_lift_from_semver=from_sem if lift else None,
        contract_violation=bool(violation),
        plan_normaliser_applied=bool(normaliser_applied),
        plan_normaliser_reason=reason,
        contract_consistent=bool(consistent),
    )
