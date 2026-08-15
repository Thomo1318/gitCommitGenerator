"""Family G — policy / identity / local secret-shape (offline only)."""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

from git_cg.eval.score_result import ScoreResultV1
from git_cg.eval.scoring.context import ScoreContext
from git_cg.eval.scoring.gold_slot import GoldSlot
from git_cg.eval.scoring.product_bridges import extract_trailers, parse_message_to_plan
from git_cg.eval.scoring.result_builder import make_score
from git_cg.models import CommitPlan

FAMILY_G_S2B = (
    "g.issue_null_policy",
    "g.no_eval_policy_fork",
    "g.ranked_identity_preserved",
    "g.secrets_not_in_message",
    "g.semantic_contract_bound",
    "g.sop_not_mutated",
)

_SCORING_ROOT = Path(__file__).resolve().parent

# Local deterministic secret-shape patterns (final message only — no vault/env).
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_access_key", re.compile(r"\b(?:=|\s)([A-Za-z0-9/+=]{40})\b")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{36,}\b")),
    ("github_fine_grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "generic_api_key_assignment",
        re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    ),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("jwt_like", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
)

_FORBIDDEN_POLICY_NAMES = frozenset(
    {
        "SOP_EMOJI_MAP",
        "GITMOJI_MATRIX",
        "CHANGELOG_GROUP_TABLE",
        "eval_only_gold",
        "EVAL_ONLY_GOLD",
        "GOLD_CODE_TABLE",
    }
)

# Product symbols that must be imported/wrapped somewhere in scoring.
_REQUIRED_PRODUCT_IMPORT_HINTS = (
    "check_commit_gold",
    "reverse_parse_commit_message",
    "run_deterministic_checks",
    "STRICT_FAIL_CODES",
)


def _scan_secrets(message: str) -> list[str]:
    """Return matched secret-shape labels in final message text only."""
    hits: list[str] = []
    if not message:
        return hits
    for label, pat in _SECRET_PATTERNS:
        if pat.search(message):
            hits.append(label)
    return hits


@lru_cache(maxsize=1)
def _audit_policy_fork() -> tuple[bool, tuple[str, ...], dict]:
    """Non-vacuous static audit of the scoring package for eval policy forks.

    Checks:
    * Forbidden local SOP/gold table names.
    * Eval-only ``GOLD_*`` constant definitions outside product_bridges map values.
    * Duplicate Hybrid header regex definitions beyond the single bridge.
    * Missing product authority imports/re-exports in ``product_bridges``.
    * Direct ``check_commit_gold`` calls outside ``product_bridges`` / tests.
    """
    findings: list[str] = []
    header_regex_files: list[str] = []
    gold_const_defs: list[str] = []
    direct_gold_calls: list[str] = []
    forbidden_hits: list[str] = []

    bridges_path = _SCORING_ROOT / "product_bridges.py"
    bridges_text = ""
    if bridges_path.is_file():
        try:
            bridges_text = bridges_path.read_text(encoding="utf-8")
        except OSError:
            bridges_text = ""
            findings.append("unreadable:product_bridges.py")

    # Required product re-exports / imports in bridges
    for sym in _REQUIRED_PRODUCT_IMPORT_HINTS:
        if sym not in bridges_text:
            findings.append(f"missing_product_symbol:{sym}")

    # Bridges must import from product modules, not redefine gold.
    if "from git_cg.commit_gold import" not in bridges_text and "import git_cg.commit_gold" not in bridges_text:
        findings.append("bridges_missing_commit_gold_import")
    if "check_commit_gold" not in bridges_text:
        findings.append("bridges_missing_check_commit_gold")

    for path in sorted(_SCORING_ROOT.glob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(f"unreadable:{path.name}:{type(exc).__name__}")
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            findings.append(f"syntax_error:{path.name}:{exc}")
            continue

        # Forbidden names
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in _FORBIDDEN_POLICY_NAMES:
                forbidden_hits.append(f"{path.name}:{node.id}")
            if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_POLICY_NAMES:
                forbidden_hits.append(f"{path.name}:{node.attr}")
            # GOLD_* assignments (eval-only constants)
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    name = None
                    if isinstance(t, ast.Name):
                        name = t.id
                    if (
                        name
                        and name.startswith("GOLD_")
                        and name
                        not in {
                            "GOLD_CODE_TO_D_METRIC",
                        }
                    ):
                        gold_const_defs.append(f"{path.name}:{name}")
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name = node.target.id
                if name.startswith("GOLD_") and name not in {"GOLD_CODE_TO_D_METRIC"}:
                    gold_const_defs.append(f"{path.name}:{name}")
            # Direct check_commit_gold calls outside product_bridges
            if isinstance(node, ast.Call):
                func = node.func
                fname = None
                if isinstance(func, ast.Name):
                    fname = func.id
                elif isinstance(func, ast.Attribute):
                    fname = func.attr
                if fname == "check_commit_gold" and path.name != "product_bridges.py":
                    direct_gold_calls.append(path.name)

        # Header regex authority: only the product_bridges Hybrid subject compiler.
        # Flag other modules that define a Hybrid header re.compile with cc_type group.
        if (path.name == "product_bridges.py" and "_HYBRID_HEADER_RE" in text) or (
            path.name != "product_bridges.py"
            and (
                re.search(r"_HYBRID_HEADER_RE\s*=\s*re\.compile", text)
                or re.search(r"re\.compile\([\s\S]{0,200}\(\?P<cc_type>", text)
            )
        ):
            header_regex_files.append(path.name)

    if forbidden_hits:
        findings.extend(f"forbidden_name:{h}" for h in forbidden_hits)
    if gold_const_defs:
        findings.extend(f"eval_gold_const:{h}" for h in gold_const_defs)
    if direct_gold_calls:
        findings.extend(f"direct_gold_call:{h}" for h in sorted(set(direct_gold_calls)))

    # Exactly one hybrid header authority file expected: product_bridges
    hybrid_definers = [f for f in header_regex_files if f == "product_bridges.py"]
    extra_header = [f for f in header_regex_files if f != "product_bridges.py"]
    if not hybrid_definers:
        findings.append("missing_hybrid_header_bridge")
    if extra_header:
        findings.extend(f"duplicate_header_regex:{f}" for f in extra_header)

    # family modules must import product_bridges (wrap, don't fork)
    for fam in ("family_b.py", "family_c.py", "family_d.py", "family_e.py", "family_f.py", "family_g.py"):
        fp = _SCORING_ROOT / fam
        if not fp.is_file():
            findings.append(f"missing_family_module:{fam}")
            continue
        try:
            ft = fp.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(f"unreadable:{fam}:{type(exc).__name__}")
            continue
        if (
            fam in {"family_b.py", "family_d.py", "family_c.py", "family_f.py", "family_e.py"}
            and "git_cg.eval.scoring.product_bridges" not in ft
            and "product_bridges" not in ft
        ):
            # g may not need bridges deeply but should still not fork - allow gold_slot only
            findings.append(f"family_missing_bridges_import:{fam}")

    # Opik must not enter scoring
    for path in _SCORING_ROOT.glob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"^\s*(import opik|from opik)", text, re.M):
            findings.append(f"opik_import:{path.name}")
        # Build legacy script token without embedding the banned import path literal
        # in this source file (test_no_eval_policy_fork scans for it).
        _legacy = "opik" + "_" + "metrics"
        if _legacy in text:
            findings.append(f"legacy_metrics_ref:{path.name}")

    ok = not findings
    findings_t = tuple(findings)
    evidence = {
        "findings": list(findings_t),
        "forbidden_hits": list(forbidden_hits),
        "gold_const_defs": list(gold_const_defs),
        "direct_gold_calls": sorted(set(direct_gold_calls)),
        "header_regex_files": list(header_regex_files),
        "scoring_root": str(_SCORING_ROOT),
    }
    return ok, findings_t, evidence


@lru_cache(maxsize=1)
def _audit_sop_mutation() -> tuple[bool, tuple[str, ...]]:
    """Static audit: scoring package must not write SOP config paths.

    Target-aware: a module may mention SOP paths and separately call write_text
    for unrelated purposes. Only treat as a violation when a write-like call
    targets an SOP path expression in the same statement/window.
    """
    findings: list[str] = []
    sop_names = ("gitops_agent_sop.json", "gitops_sop.schema.json")
    write_names = ("write_text", "write_bytes", "writelines")
    for path in sorted(_SCORING_ROOT.glob("*.py")):
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            # Packaged/unreadable layouts are not evaluator errors for this metric.
            continue
        # Line-local correlation: SOP path token and a write/open-w must co-occur.
        for lineno, line in enumerate(src.splitlines(), 1):
            has_sop = any(name in line for name in sop_names)
            if not has_sop:
                continue
            lower = line.lower()
            has_write = any(w in line for w in write_names)
            has_open_w = bool(re.search(r"open\([^\n]*['\"]w", line))
            has_dump = "dump(" in line or "json.dump" in lower
            if has_write or has_open_w or has_dump:
                findings.append(f"sop_write:{path.name}:{lineno}")
                break
        if path.name != "family_g.py" and "load_sop" in src:
            # dump/write targeting sop after load_sop in same file still needs target co-occurrence
            for lineno, line in enumerate(src.splitlines(), 1):
                if "load_sop" not in line:
                    continue
                if re.search(r"write|dump", line) and any(name in line for name in sop_names):
                    tag = f"sop_dump:{path.name}:{lineno}"
                    if tag not in findings:
                        findings.append(tag)
                    break
    return (not findings), tuple(findings)


def score_family_g(
    ctx: ScoreContext,
    *,
    gold_slot: GoldSlot | None = None,
    plan: CommitPlan | None = None,
) -> list[ScoreResultV1]:
    """Score Family G policy/identity/secret-shape metrics (local, deterministic)."""
    scores: list[ScoreResultV1] = []
    msg = (ctx.final_message or "").strip()
    trailers = extract_trailers(msg)

    built_plan = plan or (gold_slot.plan if gold_slot is not None else None)
    if built_plan is None and msg:
        try:
            built_plan = parse_message_to_plan(msg)
        except Exception:
            built_plan = None

    # g.issue_null_policy — Null valid only as #0
    null_val = trailers.get("Null")
    other_issue = any(k in trailers for k in ("Refs", "Resolves", "Closes", "Fixes"))
    if null_val is not None:
        norm = null_val.strip()
        if re.fullmatch(r"\d+", norm):
            norm = f"#{norm}"
        null_ok = norm == "#0"
        null_reason = None if null_ok else "null_must_be_zero"
    else:
        # No Null trailer: policy holds (not violated)
        null_ok = True
        null_reason = None
        if not other_issue and not trailers:
            # missing issue refs handled by Family B; G null policy is specifically Null form
            null_ok = True
    scores.append(
        make_score(
            "g.issue_null_policy",
            null_ok,
            reason=null_reason,
            evidence={"Null": null_val, "trailers": dict(trailers)},
            failure_ids=None if null_ok else ["EVAL_NULL_POLICY"],
            product_authority="git_cg.eval.scoring.product_bridges.issue_ref_ok",
        )
    )

    # g.secrets_not_in_message — local final-message scan only
    secret_hits = _scan_secrets(msg)
    sec_ok = not secret_hits
    scores.append(
        make_score(
            "g.secrets_not_in_message",
            sec_ok,
            reason=None if sec_ok else "secret_shape_in_message",
            evidence={"hits": secret_hits, "scanner": "local_final_message_only"},
            failure_ids=None if sec_ok else ["EVAL_SECRET_IN_MESSAGE"],
            product_authority="git_cg.eval.scoring.family_g._scan_secrets",
        )
    )

    # g.no_eval_policy_fork
    fork_ok, fork_findings, fork_ev = _audit_policy_fork()
    scores.append(
        make_score(
            "g.no_eval_policy_fork",
            fork_ok,
            reason=None if fork_ok else "eval_policy_fork_detected",
            evidence=fork_ev,
            failure_ids=None if fork_ok else ["EVAL_POLICY_FORK", *fork_findings[:5]],
            product_authority="git_cg.eval.scoring.family_g._audit_policy_fork",
        )
    )

    # g.ranked_identity_preserved — primary intent identity stable vs reverse-parse
    rank_ok = True
    rank_reason = None
    if built_plan is None:
        rank_ok = False
        rank_reason = "plan_missing"
    else:
        pi = built_plan.primary_intent
        # Identity fields must be present and not the unevaluated unknown-only shell
        if not getattr(pi, "intent_id", None):
            rank_ok = False
            rank_reason = "missing_intent_id"
        elif not getattr(pi, "gitmoji", None):
            rank_ok = False
            rank_reason = "missing_gitmoji"
        elif not getattr(pi, "cc_type", None):
            rank_ok = False
            rank_reason = "missing_cc_type"
        # Card override must not disagree when product_card carries intent_id
        card = ctx.product_card or {}
        card_intent = None
        if isinstance(card, dict):
            card_intent = card.get("intent_id") or (card.get("primary_intent") or {}).get("intent_id")
        if card_intent and str(card_intent) != str(pi.intent_id) and str(pi.intent_id) != "unknown":
            # Prefer plan from message; card mismatch is a warn-level identity issue → fail
            rank_ok = False
            rank_reason = "card_intent_mismatch"
    scores.append(
        make_score(
            "g.ranked_identity_preserved",
            rank_ok,
            reason=rank_reason,
            evidence={
                "intent_id": getattr(getattr(built_plan, "primary_intent", None), "intent_id", None),
            },
            failure_ids=None if rank_ok else ["EVAL_RANKED_IDENTITY"],
            product_authority="git_cg.models.CommitPlan",
        )
    )

    # g.semantic_contract_bound — offline: message-bound plan exists + Hybrid-shaped
    if built_plan is None:
        sc_ok, sc_reason = False, "plan_unbound"
    else:
        # Bound when we have primary cc_type + description from message
        pi = built_plan.primary_intent
        sc_ok = bool(getattr(pi, "cc_type", None) and getattr(pi, "description", None))
        sc_reason = None if sc_ok else "semantic_fields_missing"
        # If gold slot says contract not provided, still message-bound (not contract-bound)
        # Metric is semantic contract bound to scored artifact, not LLM contract object.
    scores.append(
        make_score(
            "g.semantic_contract_bound",
            sc_ok,
            reason=sc_reason,
            evidence={
                "scored_target": ctx.scored_target,
                "has_plan": built_plan is not None,
                "contract_provided": bool(gold_slot and gold_slot.contract_provided),
            },
            failure_ids=None if sc_ok else ["EVAL_SEMANTIC_CONTRACT_UNBOUND"],
            product_authority="git_cg.telemetry.reverse_parse_commit_message",
        )
    )

    # g.sop_not_mutated — scoring must not write SOP config (cached static audit)
    sop_ok, sop_findings_t = _audit_sop_mutation()
    scores.append(
        make_score(
            "g.sop_not_mutated",
            sop_ok,
            reason=None if sop_ok else "sop_mutation_surface",
            evidence={"findings": list(sop_findings_t)},
            failure_ids=None if sop_ok else ["EVAL_SOP_MUTATED"],
            product_authority="git_cg.eval.scoring.family_g",
        )
    )

    return scores
