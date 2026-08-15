"""Family E — presentation guards / craft (product authority only)."""

from __future__ import annotations

from git_cg.commit_gold import BANNED_BODY_OPENERS
from git_cg.commit_quality import (
    changelog_groups_allowlisted,
    classify_diff_class,
    evaluate_presentation_guards,
    fill_secondary_intents_from_stubs,
    is_low_confidence_posture,
    min_included_change_bullets,
    presentation_constraints,
)
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.gold_slot import GoldSlot
from git_cg.eval.scoring.product_bridges import extract_trailers, parse_message_to_plan
from git_cg.eval.scoring.result_builder import make_score
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan

FAMILY_E_S2B = (
    "e.banned_craft_openers",
    "e.changelog_groups_allowlisted",
    "e.docs_tests_craft",
    "e.low_confidence_posture",
    "e.min_included_bullets",
    "e.presentation_constraints_applied",
    "e.secondary_intent_fill_legal",
    "e.skeleton_avoidance",
    "e.stub_inventory_coherent",
)

_PA_GUARDS = "git_cg.commit_quality.evaluate_presentation_guards"
_PA_CG = "git_cg.commit_quality.changelog_groups_allowlisted"
_PA_FILL = "git_cg.commit_quality.fill_secondary_intents_from_stubs"


def score_family_e(
    ctx: ScoreContext,
    *,
    gold_slot: GoldSlot | None = None,
    plan: CommitPlan | None = None,
    signals: DiffSignals | None = None,
) -> list[ScoreResultV1]:
    """Score Family E via product presentation guards + craft helpers only.

    Never calls ``evaluate_presentation_gates`` or gold. Included-change claims
    derive only from ``plan.secondary_intents``.
    """
    scores: list[ScoreResultV1] = []
    msg = (ctx.final_message or "").strip()
    paths = list(ctx.path_evidence)

    built_plan = plan
    built_signals = signals
    if gold_slot is not None:
        built_plan = built_plan or gold_slot.plan
        built_signals = built_signals or gold_slot.signals
    if built_plan is None and msg:
        try:
            built_plan = parse_message_to_plan(msg)
        except Exception:
            built_plan = None

    constraints = None
    if paths:
        try:
            constraints = presentation_constraints(classify_diff_class(paths))
        except Exception:
            constraints = None

    guard = None
    guard_codes: set[str] = set()
    if built_plan is not None:
        try:
            guard = evaluate_presentation_guards(
                built_plan,
                paths=paths or None,
                signals=built_signals,
                evidence_text=msg,
                constraints=constraints,
            )
            for f in guard.findings or ():
                code = getattr(f, "code", None)
                if code:
                    guard_codes.add(str(code))
        except Exception as exc:
            guard_codes.add(f"GUARD_EVAL_ERROR:{type(exc).__name__}")

    # banned craft openers
    banned_hit = any("BANNED" in c or "OPENER" in c for c in guard_codes)
    if not banned_hit and msg:
        # Direct product opener scan as fail-closed complement.
        body_lines = [ln.strip() for ln in msg.splitlines()[1:] if ln.strip()]
        for ln in body_lines:
            for op in BANNED_BODY_OPENERS:
                if ln.startswith(op) or ln.lower().startswith(str(op).lower()):
                    banned_hit = True
                    break
            if banned_hit:
                break
    # Fail closed when guards are unevaluable, regardless of direct opener hits.
    banned_ok = not banned_hit and guard is not None
    scores.append(
        make_score(
            "e.banned_craft_openers",
            banned_ok,
            reason=None if banned_ok else "banned_craft_opener",
            evidence={
                "guard_codes": sorted(guard_codes),
                "craft_guard_fired": getattr(guard, "craft_guard_fired", None),
            },
            failure_ids=None if banned_ok else ["GUARD_BANNED_BODY_OPENER"],
            product_authority=_PA_GUARDS,
        )
    )

    # changelog groups allowlisted
    trailers = extract_trailers(msg)
    ct_raw = trailers.get("Change-Types", "")
    cg_raw = trailers.get("Changelog-Groups", "")
    change_types = [x.strip() for x in ct_raw.split(",") if x.strip()]
    changelog_groups = [x.strip() for x in cg_raw.split(",") if x.strip()]
    primary_cc = None
    if built_plan is not None:
        primary_cc = getattr(built_plan.primary_intent, "cc_type", None)
        if hasattr(primary_cc, "value"):
            primary_cc = primary_cc.value
    try:
        cg_ok = changelog_groups_allowlisted(
            change_types or [],
            changelog_groups or [],
            primary_cc_type=primary_cc,
        )
        # Empty trailers: product may return True vacuously — require presence for block metric.
        if not change_types and not changelog_groups:
            cg_ok = False
            cg_reason = "missing_changelog_trailers"
        else:
            cg_reason = None if cg_ok else "changelog_groups_not_allowlisted"
    except Exception as exc:
        cg_ok = False
        cg_reason = f"{type(exc).__name__}: {exc}"
    scores.append(
        make_score(
            "e.changelog_groups_allowlisted",
            bool(cg_ok),
            reason=cg_reason,
            evidence={"change_types": change_types, "changelog_groups": changelog_groups},
            failure_ids=None if cg_ok else ["EVAL_CHANGELOG_GROUPS"],
            product_authority=_PA_CG,
        )
    )

    # docs_tests_craft (warn)
    docs_tests_fail = any("DOCS" in c or "TESTS" in c or "CRAFT" in c for c in guard_codes) and getattr(
        guard, "craft_guard_fired", False
    )
    # Softer: craft fired on docs/tests surfaces
    only_docs = bool(built_signals and getattr(built_signals, "only_docs", False))
    only_tests = bool(built_signals and getattr(built_signals, "only_tests", False))
    if guard is not None and (only_docs or only_tests) and guard.craft_guard_fired:
        docs_tests_fail = True
    dt_ok = guard is not None and not docs_tests_fail
    scores.append(
        make_score(
            "e.docs_tests_craft",
            dt_ok,
            reason=None if dt_ok else "docs_tests_craft_guard",
            evidence={"only_docs": only_docs, "only_tests": only_tests, "guard_codes": sorted(guard_codes)},
            failure_ids=None if dt_ok else ["EVAL_DOCS_TESTS_CRAFT"],
            product_authority=_PA_GUARDS,
        )
    )

    # low_confidence_posture (warn) — no ranking confidence in offline bundle ⇒ posture not forced
    # Fail only when product card explicitly marks low confidence and body lacks posture.
    conf = None
    card = ctx.product_card or ctx.score_card or {}
    if isinstance(card, dict):
        conf = card.get("ranking_confidence") or card.get("confidence")
    try:
        low = is_low_confidence_posture(conf) if conf is not None else False
    except Exception:
        low = False
    # When low posture required, body should not claim high certainty - simple marker check.
    posture_ok = any(tok in msg.lower() for tok in ("low confidence", "uncertain", "possibly", "may ")) if low else True
    scores.append(
        make_score(
            "e.low_confidence_posture",
            posture_ok,
            reason=None if posture_ok else "low_confidence_posture_missing",
            evidence={"low_confidence": low, "confidence": conf},
            failure_ids=None if posture_ok else ["EVAL_LOW_CONFIDENCE_POSTURE"],
            product_authority="git_cg.commit_quality.is_low_confidence_posture",
        )
    )

    # min_included_bullets (warn)
    try:
        need = min_included_change_bullets(paths) if paths else 0
    except Exception:
        need = 0
    secondary = list(getattr(built_plan, "secondary_intents", None) or []) if built_plan else []
    have = len(secondary)
    # Also count "- " bullets under Included changes section
    if "included changes" in msg.lower():
        bullets = [ln for ln in msg.splitlines() if ln.strip().startswith(("- ", "* "))]
        have = max(have, len(bullets))
    min_ok = have >= need
    scores.append(
        make_score(
            "e.min_included_bullets",
            min_ok,
            reason=None if min_ok else "min_included_bullets_unmet",
            evidence={"need": need, "have": have, "paths": paths},
            failure_ids=None if min_ok else ["EVAL_MIN_INCLUDED_BULLETS"],
            product_authority="git_cg.commit_quality.min_included_change_bullets",
        )
    )

    # presentation_constraints_applied
    constraints_ok = constraints is not None or not paths
    if constraints is not None and built_plan is not None and guard is not None:
        # Constraints applied if guards ran with them (no constraint violation codes)
        constraints_ok = not any("CONSTRAINT" in c for c in guard_codes)
    elif paths and constraints is None:
        constraints_ok = False
    scores.append(
        make_score(
            "e.presentation_constraints_applied",
            bool(constraints_ok),
            reason=None if constraints_ok else "presentation_constraints_missing",
            evidence={"has_constraints": constraints is not None, "paths": paths},
            failure_ids=None if constraints_ok else ["EVAL_PRESENTATION_CONSTRAINTS"],
            product_authority="git_cg.commit_quality.presentation_constraints",
        )
    )

    # secondary_intent_fill_legal — fill must not mutate primary identity
    fill_ok = True
    fill_reason = None
    if built_plan is not None:
        try:
            before_primary = built_plan.primary_intent.model_dump()
            filled = fill_secondary_intents_from_stubs(
                built_plan,
                paths=paths or None,
                signals=built_signals,
                constraints=constraints,
            )
            after_primary = filled.primary_intent.model_dump()
            # Primary identity fields must be preserved
            for key in ("intent_id", "cc_type", "gitmoji", "semver_impact"):
                if before_primary.get(key) != after_primary.get(key):
                    fill_ok = False
                    fill_reason = f"primary_mutated:{key}"
                    break
        except Exception as exc:
            fill_ok = False
            fill_reason = f"{type(exc).__name__}: {exc}"
    else:
        fill_ok = False
        fill_reason = "plan_missing"
    scores.append(
        make_score(
            "e.secondary_intent_fill_legal",
            fill_ok,
            reason=fill_reason,
            evidence={"paths": paths},
            failure_ids=None if fill_ok else ["EVAL_SECONDARY_FILL"],
            product_authority=_PA_FILL,
        )
    )

    # skeleton_avoidance — craft/guard fallback must not be skeleton final
    skel = False
    if guard is not None and guard.fallback_reason and "skeleton" in str(guard.fallback_reason).lower():
        skel = True
    if (
        gold_slot is not None
        and gold_slot.report is not None
        and "GOLD_SKELETON_FALLBACK_FINAL" in gold_slot.report.codes()
    ):
        skel = True
    # Product fallback marker only — bare "SKELETON" falsely fails legitimate prose.
    if "LOW-CONFIDENCE BODY SKELETON" in msg.upper():
        skel = True
    skel_ok = not skel and (guard is not None or bool(msg))
    if guard is None and not msg:
        skel_ok = False
    scores.append(
        make_score(
            "e.skeleton_avoidance",
            skel_ok,
            reason=None if skel_ok else "skeleton_fallback_detected",
            evidence={
                "fallback_reason": getattr(guard, "fallback_reason", None),
                "hallucination_guard_fired": getattr(guard, "hallucination_guard_fired", None),
            },
            failure_ids=None if skel_ok else ["EVAL_SKELETON_AVOIDANCE"],
            product_authority=_PA_GUARDS,
        )
    )

    # stub_inventory_coherent (warn) — secondary descriptions non-empty / non-duplicate
    stubs = [str(getattr(s, "description", "") or "").strip() for s in secondary]
    if not stubs:
        stub_ok = True  # nothing to be incoherent about
        stub_reason = None
    else:
        nonempty = all(bool(s) for s in stubs)
        unique = len(set(s.lower() for s in stubs)) == len(stubs)
        stub_ok = nonempty and unique
        stub_reason = None if stub_ok else "stub_inventory_incoherent"
    scores.append(
        make_score(
            "e.stub_inventory_coherent",
            stub_ok,
            reason=stub_reason,
            evidence={"stubs": stubs},
            failure_ids=None if stub_ok else ["EVAL_STUB_INVENTORY"],
            product_authority=_PA_FILL,
        )
    )

    return scores
