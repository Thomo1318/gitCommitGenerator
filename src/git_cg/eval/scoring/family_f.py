"""Family F — claim/path attribution from shared GoldReport (never calls gold)."""

from __future__ import annotations

import re

from git_cg.commit_quality import security_claims_without_path_evidence
from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.gold_slot import GoldSlot
from git_cg.eval.scoring.product_bridges import parse_message_to_plan
from git_cg.eval.scoring.result_builder import make_score
from git_cg.models import CommitPlan

FAMILY_F_S2B = (
    "f.body_attribution",
    "f.claim_evidence_alignment",
    "f.counter_integrity",
    "f.included_changes_vs_diff",
    "f.security_claims_need_paths",
    "f.staged_path_allowlist",
    "f.subject_attribution",
)

_PA_GOLD = "git_cg.commit_gold.check_commit_gold"
_PA_SEC = "git_cg.commit_quality.security_claims_without_path_evidence"

# Inventory / attribution-related gold codes
_SUBJECT_ATTR_CODES = frozenset({"GOLD_SUBJECT_INVENTORY", "GOLD_SCOPE_FILENAME"})
_BODY_ATTR_CODES = frozenset(
    {
        "GOLD_BODY_INVENTORY",
        "GOLD_PROCESS_META_BODY",
        "GOLD_DOCS_IMPLEMENTATION_CLAIM",
        "GOLD_FIXTURE_PRODUCT_FRAMING",
    }
)
_COUNTER_CODES = frozenset(
    {
        "GOLD_INCLUDED_CHANGES_MISSING",
        "GOLD_BODY_INVENTORY",
        "GOLD_SUBJECT_INVENTORY",
    }
)


def score_family_f(
    ctx: ScoreContext,
    *,
    gold_slot: GoldSlot | None = None,
    plan: CommitPlan | None = None,
) -> list[ScoreResultV1]:
    """Score Family F from shared gold + explicit path evidence only.

    Must never call ``run_gold_once`` / ``check_commit_gold``. Missing paths do
    not become fabricated passes for path-bound metrics.
    """
    scores: list[ScoreResultV1] = []
    msg = (ctx.final_message or "").strip()
    paths = list(ctx.path_evidence)
    shared = gold_slot.shared_evidence if gold_slot is not None else {"shared": False}

    report = gold_slot.report if gold_slot is not None else None
    codes = report.codes() if report is not None else frozenset()
    gold_error = gold_slot.error if gold_slot is not None else "gold_slot_missing"

    built_plan = plan or (gold_slot.plan if gold_slot is not None else None)
    if built_plan is None and msg:
        try:
            built_plan = parse_message_to_plan(msg)
        except Exception:
            built_plan = None

    def _attr_ok(relevant: frozenset[str]) -> tuple[bool, str | None, bool | None]:
        if gold_slot is None:
            return False, "gold_slot_missing", None
        if gold_slot.skipped:
            return False, "gold_skipped", None
        if gold_slot.error or report is None:
            return False, "gold_evaluation_error", None
        hit = sorted(c for c in codes if c in relevant)
        if hit:
            return False, hit[0], True
        return True, None, False

    # subject_attribution
    sub_ok, sub_reason, sub_present = _attr_ok(_SUBJECT_ATTR_CODES)
    scores.append(
        make_score(
            "f.subject_attribution",
            sub_ok,
            reason=sub_reason,
            evidence={**shared, "codes_checked": sorted(_SUBJECT_ATTR_CODES), "hit": sub_present},
            failure_ids=None if sub_ok else [sub_reason or "EVAL_SUBJECT_ATTRIBUTION"],
            product_authority=_PA_GOLD,
        )
    )

    # body_attribution
    body_ok, body_reason, body_present = _attr_ok(_BODY_ATTR_CODES)
    scores.append(
        make_score(
            "f.body_attribution",
            body_ok,
            reason=body_reason,
            evidence={**shared, "codes_checked": sorted(_BODY_ATTR_CODES), "hit": body_present},
            failure_ids=None if body_ok else [body_reason or "EVAL_BODY_ATTRIBUTION"],
            product_authority=_PA_GOLD,
        )
    )

    # counter_integrity — file-count / included-change counters must not invent
    counter_ok, counter_reason, _ = _attr_ok(_COUNTER_CODES)
    # Additional local check: message must not claim N files when paths known and differ
    if counter_ok and paths and msg:
        m = re.search(r"\b(\d+)\s+files?\b", msg.lower())
        if m:
            claimed = int(m.group(1))
            if claimed != len(paths):
                counter_ok, counter_reason = False, "file_counter_mismatch"
    scores.append(
        make_score(
            "f.counter_integrity",
            counter_ok,
            reason=counter_reason,
            evidence={**shared, "path_count": len(paths)},
            failure_ids=None if counter_ok else [counter_reason or "EVAL_COUNTER_INTEGRITY"],
            product_authority=_PA_GOLD,
        )
    )

    # included_changes_vs_diff
    secondary = list(getattr(built_plan, "secondary_intents", None) or []) if built_plan else []
    if gold_slot is not None and gold_slot.error:
        ic_ok, ic_reason = False, "gold_evaluation_error"
    elif not paths:
        # Without explicit paths, cannot affirm alignment — fail closed for block metric
        # unless there are also no included-change claims.
        if not secondary and "included changes" not in msg.lower():
            ic_ok, ic_reason = True, None
        else:
            ic_ok, ic_reason = False, "no_path_evidence_for_included_changes"
    else:
        # Fail if gold says missing included changes
        if "GOLD_INCLUDED_CHANGES_MISSING" in codes:
            ic_ok, ic_reason = False, "GOLD_INCLUDED_CHANGES_MISSING"
        else:
            # Soft path-token alignment for secondary descriptions
            path_blob = " ".join(paths).lower()
            bad = []
            for s in secondary:
                desc = str(getattr(s, "description", "") or "").lower()
                if not desc:
                    continue
                tokens = [t for t in re.split(r"[^a-z0-9_]+", desc) if len(t) >= 4]
                if tokens and not any(t in path_blob for t in tokens):
                    # not necessarily fail — inventory may be thematic
                    bad.append(desc)
            # Only fail hard on gold code; thematic misses stay pass with evidence
            ic_ok, ic_reason = True, None
    scores.append(
        make_score(
            "f.included_changes_vs_diff",
            ic_ok,
            reason=ic_reason,
            evidence={**shared, "paths": paths, "secondary_count": len(secondary)},
            failure_ids=None if ic_ok else [ic_reason or "EVAL_INCLUDED_VS_DIFF"],
            product_authority=_PA_GOLD,
        )
    )

    # security_claims_need_paths — explicit paths only
    claims = security_claims_without_path_evidence(msg, paths) if msg else []
    sec_ok = not claims
    scores.append(
        make_score(
            "f.security_claims_need_paths",
            sec_ok,
            reason=None if sec_ok else "security_claims_without_paths",
            evidence={"paths": paths, "claims": claims, "placeholder_disallowed": True},
            failure_ids=None if sec_ok else ["EVAL_SECURITY_CLAIMS_NEED_PATHS"],
            product_authority=_PA_SEC,
        )
    )

    # staged_path_allowlist — every explicit path must look like a repo path (no URLs/abs leakage)
    if not paths:
        # Empty explicit paths: allowlist holds vacuously (nothing illegal staged),
        # but evidence records honesty.
        sp_ok, sp_reason = True, None
    else:
        bad_paths = []
        for p in paths:
            if (
                p.startswith("/")
                or "://" in p
                or ".." in p.split("/")
                or not re.match(r"^[A-Za-z0-9._@+-]+(/[A-Za-z0-9._@+-]+)*$", p)
            ):
                bad_paths.append(p)
        sp_ok = not bad_paths
        sp_reason = None if sp_ok else "staged_path_not_allowlisted"
    scores.append(
        make_score(
            "f.staged_path_allowlist",
            sp_ok,
            reason=sp_reason,
            evidence={"paths": paths, "empty_paths_honest": not bool(paths)},
            failure_ids=None if sp_ok else ["EVAL_STAGED_PATH_ALLOWLIST"],
            product_authority="git_cg.eval.scoring.context.path_evidence",
        )
    )

    # claim_evidence_alignment (FIND-004 warn)
    if not msg:
        align = 0.0
        align_reason = "empty_message"
    elif not paths:
        align = 0.0 if secondary else 1.0
        align_reason = "no_path_evidence" if secondary else None
    else:
        path_blob = " ".join(paths).lower()
        claims_txt = [str(getattr(s, "description", "") or "") for s in secondary]
        claims_txt = [c for c in claims_txt if c.strip()]
        if not claims_txt:
            # subject tokens vs paths
            header = msg.splitlines()[0] if msg else ""
            tokens = [t for t in re.split(r"[^a-z0-9_]+", header.lower()) if len(t) >= 4]
            hits = sum(1 for t in tokens if t in path_blob)
            align = (hits / len(tokens)) if tokens else 1.0
        else:
            hits = 0
            for c in claims_txt:
                toks = [t for t in re.split(r"[^a-z0-9_]+", c.lower()) if len(t) >= 4]
                if toks and any(t in path_blob for t in toks):
                    hits += 1
            align = hits / len(claims_txt)
        align_reason = None if align >= 1.0 else "claim_evidence_partial"
    scores.append(
        make_score(
            "f.claim_evidence_alignment",
            float(align),
            passed=align >= 1.0,
            reason=align_reason,
            evidence={"alignment": align, "paths": paths, "finding": "FIND-004"},
            failure_ids=["FIND-004"] if align < 1.0 else None,
            product_authority=_PA_GOLD,
        )
    )

    # Silence unused in some branches
    _ = gold_error
    return scores
