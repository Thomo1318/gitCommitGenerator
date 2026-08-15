"""Family C — path-class / presentation gates (product authority only)."""

from __future__ import annotations

from git_cg.commit_quality import (
    classify_diff_class,
    evaluate_presentation_gates,
    has_security_path_evidence,
    presentation_constraints,
    security_claims_without_path_evidence,
)
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.gold_slot import GoldSlot
from git_cg.eval.scoring.product_bridges import parse_message_to_plan
from git_cg.eval.scoring.result_builder import make_score
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan

FAMILY_C_S2B = (
    "c.changelog_antisignal",
    "c.contract_smoke",
    "c.diff_class_resolved",
    "c.evidence_surface_precision",
    "c.evidence_surface_recall",
    "c.scope_forced_ok",
    "c.security_claim_evidence",
    "c.semver_ceiling",
    "c.type_allowed",
)

_PA_GATES = "git_cg.commit_quality.evaluate_presentation_gates"
_PA_CLASS = "git_cg.commit_quality.classify_diff_class"
_PA_GOLD = "git_cg.commit_gold.check_commit_gold"
_PA_SEC = "git_cg.commit_quality.security_claims_without_path_evidence"

# Exact product gate codes (substring matching is rejected — false positives on
# unrelated tokens such as SCOPE/TYPE/SEMVER embedded in other codes).
_SCOPE_GATE_CODES = frozenset({"GATE_PATH_SCOPE_MISMATCH"})
_TYPE_GATE_CODES = frozenset(
    {
        "GATE_TYPE_FORCE_MISMATCH",
        "GATE_TYPE_FORBIDDEN",
        "GATE_TYPE_DOMINANT_MISMATCH",
        "GATE_TYPE_GROUP_MISSING",
        "GATE_TYPE_REQUIRED_GROUP_MISSING",
        "GATE_TYPE_SINGLE_GROUP_ONLY",
    }
)
_SEMVER_GATE_CODES = frozenset(
    {
        "GATE_SEMVER_FORCE_MISMATCH",
        "GATE_SEMVER_FORBIDDEN",
        "GATE_SEMVER_CEILING",
        "GATE_SEMVER_SECONDARY_CEILING",
    }
)
_CHANGELOG_GATE_CODES = frozenset(
    {
        "PATH_CLASS_CHANGELOG_ANTISIGNAL",
        "GATE_PATH_CLASS_CHANGELOG_ANTISIGNAL",
        "CHANGELOG_ANTISIGNAL",
    }
)


def score_family_c(
    ctx: ScoreContext,
    *,
    gold_slot: GoldSlot | None = None,
    plan: CommitPlan | None = None,
    signals: DiffSignals | None = None,
) -> list[ScoreResultV1]:
    """Score Family C via product path-class gates + shared gold dual rows.

    Never calls gold or ``evaluate_presentation_guards``. Security evidence uses
    explicit ``ctx.path_evidence`` only (placeholders never create a pass).
    ``c.contract_smoke`` is fail-closed when contract was not supplied to gold.
    """
    scores: list[ScoreResultV1] = []
    msg = (ctx.final_message or "").strip()
    paths = list(ctx.path_evidence)
    shared = gold_slot.shared_evidence if gold_slot is not None else {"shared": False}

    # Resolve plan/signals from slot when available.
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

    # --- diff class ---
    diff_class = None
    dc_ok = False
    dc_reason = "no_path_evidence"
    try:
        if paths:
            diff_class = classify_diff_class(paths)
            dc_ok = diff_class is not None
            dc_reason = None if dc_ok else "diff_class_unresolved"
        else:
            # Gate-string fallback is informational only — still fail-closed without paths.
            dc_ok = False
            dc_reason = "no_explicit_paths_for_diff_class"
    except Exception as exc:
        dc_reason = f"{type(exc).__name__}: {exc}"
        dc_ok = False

    scores.append(
        make_score(
            "c.diff_class_resolved",
            dc_ok,
            reason=dc_reason,
            evidence={
                "paths": paths,
                "diff_class": getattr(diff_class, "value", str(diff_class) if diff_class else None),
                "path_class_gate": ctx.path_class_gate,
            },
            failure_ids=None if dc_ok else ["EVAL_DIFF_CLASS_UNRESOLVED"],
            product_authority=_PA_CLASS,
        )
    )

    constraints = None
    if diff_class is not None:
        try:
            constraints = presentation_constraints(diff_class)
        except Exception:
            constraints = None

    # --- presentation gates (C only — never guards) ---
    gate_report = None
    gate_codes: set[str] = set()
    gate_status: dict[str, str] = {}
    if built_plan is not None:
        try:
            gate_report = evaluate_presentation_gates(
                built_plan,
                paths=paths or None,
                signals=built_signals,
                constraints=constraints,
                evidence_text=msg,
                included_changes=[
                    getattr(s, "description", None) or str(s) for s in (built_plan.secondary_intents or [])
                ]
                or None,
            )
            gate_codes = set(gate_report.codes or ())
            gate_status = {k: v for k, v in (gate_report.gate_status or ())}
        except Exception as exc:
            gate_codes = {f"GATE_EVAL_ERROR:{type(exc).__name__}"}

    def _gate_pass(allowed_codes: frozenset[str], *, status_keys: tuple[str, ...] = ()) -> tuple[bool, str | None]:
        if gate_report is None:
            return False, "gates_not_evaluated"
        for c in gate_codes:
            if c in allowed_codes:
                return False, c
        for sk in status_keys:
            st = gate_status.get(sk)
            if st and st not in {"pass", "ok", "skip", "skipped", "na", "n/a"}:
                return False, f"gate_status:{sk}={st}"
        return True, None

    # scope_forced_ok — exact product gate codes only (no substring false positives)
    scope_ok, scope_reason = _gate_pass(
        _SCOPE_GATE_CODES,
        status_keys=("scope", "path_class", "craft"),
    )
    # Prefer explicit constraint force-scope check when available.
    if constraints is not None and built_plan is not None:
        forced = getattr(constraints, "force_scope", None) or getattr(constraints, "forced_scope", None)
        if forced:
            actual = getattr(built_plan.primary_intent, "scope", None)
            if actual is not None and str(actual) != str(forced):
                scope_ok, scope_reason = False, "forced_scope_mismatch"
            elif actual is not None:
                scope_ok, scope_reason = True, None
    scores.append(
        make_score(
            "c.scope_forced_ok",
            scope_ok,
            reason=scope_reason,
            evidence={"gate_codes": sorted(gate_codes), "gate_status": gate_status, "paths": paths},
            failure_ids=None if scope_ok else ["EVAL_SCOPE_FORCED"],
            product_authority=_PA_GATES,
        )
    )

    # type_allowed — dual with d.path_class_type
    type_code = "GOLD_PATH_CLASS_TYPE_MISMATCH"
    type_from_gold = None
    if gold_slot is not None and gold_slot.report is not None:
        type_from_gold = type_code in gold_slot.report.codes()
    type_gate_fail = any(c in _TYPE_GATE_CODES for c in gate_codes) or any(
        k == "type" and v not in {"pass", "ok", "skip", "skipped", "na", "n/a"} for k, v in gate_status.items()
    )
    if type_from_gold is True:
        type_ok, type_reason = False, type_code
    elif type_from_gold is False and gold_slot is not None and gold_slot.report is not None:
        type_ok, type_reason = True, None
    else:
        # No shared report: use gates; fail-closed if neither available.
        if gate_report is None:
            type_ok, type_reason = False, "path_class_type_unevaluable"
        else:
            type_ok, type_reason = (False, "path_class_type_gate") if type_gate_fail else (True, None)

    scores.append(
        make_score(
            "c.type_allowed",
            type_ok,
            reason=type_reason,
            evidence={**shared, "gold_code": type_code, "present": type_from_gold, "gate_codes": sorted(gate_codes)},
            failure_ids=None if type_ok else [type_reason or "EVAL_TYPE_ALLOWED"],
            product_authority=_PA_GOLD if type_from_gold is not None else _PA_GATES,
        )
    )

    # semver_ceiling — dual with d.path_class_semver
    sem_code = "GOLD_PATH_CLASS_SEMVER_CEILING"
    sem_from_gold = None
    if gold_slot is not None and gold_slot.report is not None:
        sem_from_gold = sem_code in gold_slot.report.codes()
    sem_gate_fail = any(c in _SEMVER_GATE_CODES for c in gate_codes) or any(
        k == "semver" and v not in {"pass", "ok", "skip", "skipped", "na", "n/a"} for k, v in gate_status.items()
    )
    if sem_from_gold is True:
        sem_ok, sem_reason = False, sem_code
    elif sem_from_gold is False and gold_slot is not None and gold_slot.report is not None:
        sem_ok, sem_reason = True, None
    else:
        if gate_report is None:
            sem_ok, sem_reason = False, "path_class_semver_unevaluable"
        else:
            sem_ok, sem_reason = (False, "path_class_semver_gate") if sem_gate_fail else (True, None)

    scores.append(
        make_score(
            "c.semver_ceiling",
            sem_ok,
            reason=sem_reason,
            evidence={**shared, "gold_code": sem_code, "present": sem_from_gold, "gate_codes": sorted(gate_codes)},
            failure_ids=None if sem_ok else [sem_reason or "EVAL_SEMVER_CEILING"],
            product_authority=_PA_GOLD if sem_from_gold is not None else _PA_GATES,
        )
    )

    # changelog_antisignal (warn)
    anti_ok, anti_reason = _gate_pass(
        _CHANGELOG_GATE_CODES,
        status_keys=("changelog",),
    )
    scores.append(
        make_score(
            "c.changelog_antisignal",
            anti_ok,
            reason=anti_reason,
            evidence={"gate_codes": sorted(gate_codes)},
            failure_ids=None if anti_ok else ["PATH_CLASS_CHANGELOG_ANTISIGNAL"],
            product_authority=_PA_GATES,
        )
    )

    # security_claim_evidence — explicit paths only
    claims = security_claims_without_path_evidence(msg, paths) if msg else []
    has_ev = has_security_path_evidence(paths) if paths else False
    if not claims or has_ev:
        sec_ok, sec_reason = True, None
    else:
        sec_ok, sec_reason = False, "security_claims_without_path_evidence"
    scores.append(
        make_score(
            "c.security_claim_evidence",
            sec_ok,
            reason=sec_reason,
            evidence={
                "paths": paths,
                "claims": claims,
                "has_security_path_evidence": has_ev,
                "placeholder_disallowed": True,
            },
            failure_ids=None if sec_ok else ["EVAL_SECURITY_CLAIM_EVIDENCE"],
            product_authority=_PA_SEC,
        )
    )

    # contract_smoke — C-only; fail-closed when contract not provided (D43)
    contract_code = "GOLD_CONTRACT_SMOKE"
    if gold_slot is None:
        cs_ok, cs_reason = False, "gold_slot_missing"
        cs_present = None
    elif gold_slot.error:
        cs_ok, cs_reason = False, "gold_evaluation_error"
        cs_present = None
    elif not gold_slot.contract_provided:
        cs_ok, cs_reason = False, "contract_not_provided_smoke_skipped"
        cs_present = None
    elif gold_slot.report is None:
        cs_ok, cs_reason = False, "gold_report_missing"
        cs_present = None
    else:
        cs_present = contract_code in gold_slot.report.codes()
        cs_ok = not cs_present
        cs_reason = contract_code if cs_present else None
    scores.append(
        make_score(
            "c.contract_smoke",
            cs_ok,
            reason=cs_reason,
            evidence={
                **shared,
                "gold_code": contract_code,
                "present": cs_present,
                "contract_provided": bool(gold_slot and gold_slot.contract_provided),
            },
            failure_ids=None if cs_ok else [cs_reason or "GOLD_CONTRACT_SMOKE"],
            product_authority=_PA_GOLD,
        )
    )

    # evidence surface precision/recall (FIND-004 warn) — local deterministic proxy
    # Precision: fraction of secondary claims that are non-empty / path-groundable.
    secs = list(getattr(built_plan, "secondary_intents", None) or []) if built_plan else []
    claim_texts = [str(getattr(s, "description", "") or "").strip() for s in secs]
    claim_texts = [c for c in claim_texts if c]
    if not claim_texts and not paths:
        prec = 1.0
        rec = 1.0
        er = "no_claims_no_paths"
    elif not paths:
        # Claims without path evidence → low precision; recall undefined→0 fail-closed warn
        prec = 0.0 if claim_texts else 1.0
        rec = 0.0
        er = "no_path_evidence"
    else:
        # Path-token overlap heuristic (deterministic, offline).
        path_blob = " ".join(paths).lower()
        hits = sum(
            1 for c in claim_texts if any(tok and tok in path_blob for tok in c.lower().replace("/", " ").split())
        )
        prec = (hits / len(claim_texts)) if claim_texts else 1.0
        # Recall: path stems mentioned in message body/subject
        stems = []
        for p in paths:
            stem = p.rsplit("/", 1)[-1].split(".")[0].lower()
            if stem:
                stems.append(stem)
        body = msg.lower()
        covered = sum(1 for s in stems if s and s in body)
        rec = (covered / len(stems)) if stems else 1.0
        er = None
    scores.append(
        make_score(
            "c.evidence_surface_precision",
            float(prec),
            passed=prec >= 1.0,
            reason=er if prec < 1.0 else None,
            evidence={"precision": prec, "claims": claim_texts, "paths": paths, "finding": "FIND-004"},
            failure_ids=["FIND-004"] if prec < 1.0 else None,
            product_authority=_PA_GATES,
        )
    )
    scores.append(
        make_score(
            "c.evidence_surface_recall",
            float(rec),
            passed=rec >= 1.0,
            reason=er if rec < 1.0 else None,
            evidence={"recall": rec, "paths": paths, "finding": "FIND-004"},
            failure_ids=["FIND-004"] if rec < 1.0 else None,
            product_authority=_PA_GATES,
        )
    )

    return scores
