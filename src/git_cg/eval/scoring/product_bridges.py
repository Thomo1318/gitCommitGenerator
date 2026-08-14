"""Narrow bridges from eval scoring into product authorities.

S2 must wrap product modules — never reimplement Hybrid/gold/path-class law.
"""

from __future__ import annotations

import re
from typing import Any

from git_cg.commit_gold import STRICT_FAIL_CODES, GoldReport, check_commit_gold
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan, CommitType, SemVerImpact
from git_cg.telemetry import reverse_parse_commit_message, run_deterministic_checks

# Product Hybrid subject regex aligned with hooks/validate_commit.mjs vocabulary.
_HYBRID_HEADER_RE = re.compile(
    r"^(?P<gitmoji>(?:[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+|:[a-z0-9_+-]+:))\s+"
    r"(?P<cc_type>[a-z]+)"
    r"(?:\((?P<scope>[a-z0-9_,\-\s]+)\))?"
    r"(?P<breaking>!)?"
    r":\s+(?P<subject>.+)$",
    re.UNICODE,
)

_CC_TYPES = frozenset(t.value for t in CommitType)
_SEMVER_VALUES = frozenset(v.value for v in SemVerImpact)

_ISSUE_KEY_RE = {
    "Refs": re.compile(r"^#\d+$"),
    "Resolves": re.compile(r"^#\d+$"),
    "Closes": re.compile(r"^#\d+$"),
    "Fixes": re.compile(r"^#\d+$"),
    "Null": re.compile(r"^#0$"),
}

_TRAILER_PREFIXES = (
    "Refs:",
    "Resolves:",
    "Closes:",
    "Fixes:",
    "Null:",
    "SemVer-Impact:",
    "Change-Types:",
    "Changelog-Groups:",
    "Co-authored-by:",
    "Signed-off-by:",
)

# Gold code → Family D metric_id (catalog).
GOLD_CODE_TO_D_METRIC: dict[str, str] = {
    "GOLD_BODY_INVENTORY": "d.body_inventory",
    "GOLD_SUBJECT_INVENTORY": "d.subject_inventory",
    "GOLD_INCLUDED_CHANGES_MISSING": "d.included_changes_coverage",
    "GOLD_GROUP_PRIMARY_MISMATCH": "d.group_primary_match",
    "GOLD_TYPE_GROUP_INCOHERENT": "d.type_group_coherent",
    "GOLD_SEMVER_MATRIX_MISMATCH": "d.semver_matrix",
    "GOLD_SCOPE_FILENAME": "d.scope_filename",
    "GOLD_SUBJECT_TITLE_CASE": "d.subject_title_case",
    "GOLD_SKELETON_FALLBACK_FINAL": "d.skeleton_fallback_final",
    "GOLD_PROCESS_META_BODY": "d.process_meta_body",
    "GOLD_PATH_CLASS_SEMVER_CEILING": "d.path_class_semver",
    "GOLD_PATH_CLASS_TYPE_MISMATCH": "d.path_class_type",
    "GOLD_FIXTURE_PRODUCT_FRAMING": "d.fixture_product_framing",
    "GOLD_DOCS_IMPLEMENTATION_CLAIM": "d.docs_implementation_claim",
    "GOLD_BREAKING_COMPAT_CONTRADICTION": "d.breaking_compat",
    "GOLD_HIGH_RISK_THEME_MISSING": "d.high_risk_theme_coverage",
}

D_METRIC_TO_GOLD_CODE: dict[str, str] = {v: k for k, v in GOLD_CODE_TO_D_METRIC.items()}


def parse_hybrid_header(message: str) -> dict[str, Any]:
    """Parse Hybrid subject line shape for Family B (wrap product grammar only)."""
    if not message or not str(message).strip():
        return {"ok": False, "reason": "empty_message", "header": "", "header_len": 0}
    header = message.splitlines()[0].strip()
    m = _HYBRID_HEADER_RE.match(header)
    if not m:
        parsed = reverse_parse_commit_message(message)
        pi = parsed.get("primary_intent") or {}
        return {
            "ok": False,
            "reason": "header_shape_mismatch",
            "header": header,
            "header_len": len(header),
            "gitmoji": pi.get("gitmoji") or "",
            "cc_type": str(pi.get("cc_type") or ""),
            "scope": pi.get("scope"),
            "subject": str(pi.get("description") or ""),
            "breaking": bool(parsed.get("breaking_change")),
            "soft_parse": True,
        }
    gd = m.groupdict()
    return {
        "ok": True,
        "header": header,
        "header_len": len(header),
        "gitmoji": gd.get("gitmoji") or "",
        "cc_type": gd.get("cc_type") or "",
        "scope": gd.get("scope"),
        "subject": gd.get("subject") or "",
        "breaking": bool(gd.get("breaking")),
        "soft_parse": False,
    }


def extract_trailers(message: str) -> dict[str, str]:
    """Extract machine trailers by product line-prefix contract."""
    trailers: dict[str, str] = {}
    if not message:
        return trailers
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_TRAILER_PREFIXES):
            key, _, val = stripped.partition(":")
            trailers[key.strip()] = val.strip()
    return trailers


def parse_message_to_plan(message: str, *, rationale: str | None = None) -> CommitPlan:
    """Build ``CommitPlan`` via product ``reverse_parse_commit_message`` + normalize."""
    parsed = reverse_parse_commit_message(message)
    if not parsed:
        raise ValueError("reverse_parse_commit_message returned empty plan")

    pi_raw = dict(parsed.get("primary_intent") or {})
    cc = str(pi_raw.get("cc_type") or "chore")
    if cc not in _CC_TYPES:
        cc = "chore"
    pi_raw["cc_type"] = cc
    sem = str(pi_raw.get("semver_impact") or "NONE").upper()
    if sem not in _SEMVER_VALUES:
        sem = "NONE"
    pi_raw["semver_impact"] = sem
    pi_raw.setdefault("description", "unparsed subject")
    if not pi_raw.get("description"):
        pi_raw["description"] = "unparsed subject"
    if not pi_raw.get("gitmoji"):
        pi_raw["gitmoji"] = "🔧"
    if not pi_raw.get("changelog_group"):
        pi_raw["changelog_group"] = "Miscellaneous"
    if not pi_raw.get("intent_id"):
        pi_raw["intent_id"] = "unknown"

    secondary: list[dict[str, Any]] = []
    for sec in parsed.get("secondary_intents") or []:
        if not isinstance(sec, dict):
            continue
        s = dict(sec)
        scc = str(s.get("cc_type") or "chore")
        if scc not in _CC_TYPES:
            scc = "chore"
        s["cc_type"] = scc
        ssem = str(s.get("semver_impact") or "NONE").upper()
        if ssem not in _SEMVER_VALUES:
            ssem = "NONE"
        s["semver_impact"] = ssem
        s.setdefault("description", "secondary")
        if not s.get("description"):
            s["description"] = "secondary"
        if not s.get("gitmoji"):
            s["gitmoji"] = "🔧"
        if not s.get("changelog_group"):
            s["changelog_group"] = "Miscellaneous"
        if not s.get("intent_id"):
            s["intent_id"] = "unknown"
        secondary.append(s)

    plan_data: dict[str, Any] = {
        "primary_intent": pi_raw,
        "secondary_intents": secondary,
        "split_recommended": bool(parsed.get("split_recommended", False)),
        "rationale": rationale if rationale is not None else (parsed.get("rationale") or "eval_reverse_parse"),
        "body_summary": parsed.get("body_summary") or None,
        "breaking_change": bool(parsed.get("breaking_change", False)),
        "breaking_change_description": parsed.get("breaking_change_description"),
    }
    return CommitPlan.model_validate(plan_data)


def signals_from_context(
    *,
    path_class_gate: str | None,
    generation_task_input: dict[str, str] | None,
    files: list[str] | None = None,
) -> DiffSignals:
    """Project lightweight ``DiffSignals`` from fixture/path-class context only."""
    paths = list(files or [])
    gti = generation_task_input or {}
    gate = (path_class_gate or gti.get("path_class_gate") or "").strip().lower()
    summary = (gti.get("diff_summary") or "").lower()

    only_docs = gate in {"docs_only", "docs"} or gate.endswith("docs")
    only_tests = gate in {"tests_only", "tests", "test"}
    only_fixtures = gate in {"fixtures_only", "fixtures"} or "fixture" in gate
    product_src = gate in {"product_src", "src", "product"}

    if only_docs and not paths:
        paths = ["docs/eval/README.md"]
    elif only_tests and not paths:
        paths = ["tests/eval/test_placeholder.py"]
    elif only_fixtures and not paths:
        paths = ["tests/fixtures/eval/cases/valid/seed.json"]
    elif product_src and not paths:
        paths = ["src/git_cg/commit_quality.py"]

    return DiffSignals(
        files=paths,
        files_changed_count=len(paths),
        touches_docs=only_docs or "doc" in summary,
        touches_tests=only_tests or only_fixtures or "test" in summary or "fixture" in summary,
        only_docs=only_docs,
        only_tests=only_tests,
        only_fixtures=only_fixtures,
    )


def run_gold_once(
    plan: CommitPlan,
    signals: DiffSignals,
    *,
    gold_mode: str = "strict",
) -> tuple[GoldReport, frozenset[str], bool]:
    """Invoke product ``check_commit_gold`` once; return report, strict set, mode-ok."""
    report = check_commit_gold(
        plan,
        None,
        signals=signals,
        ranked_intents=None,
        presentation_overlay_applied=False,
    )
    strict_hits = report.codes() & STRICT_FAIL_CODES
    ok = report.ok_for_mode(gold_mode)
    return report, strict_hits, ok


def deterministic_card_from_plan(plan: CommitPlan) -> dict[str, Any]:
    """Wrap product ``run_deterministic_checks`` into a plain evidence dict."""
    card = run_deterministic_checks(plan)
    if hasattr(card, "model_dump"):
        return card.model_dump()
    if hasattr(card, "__dict__"):
        return {k: getattr(card, k) for k in vars(card) if not k.startswith("_")}
    return {
        "header_length_ok": getattr(card, "header_length_ok", None),
        "description_length_ok": getattr(card, "description_length_ok", None),
        "type_valid": getattr(card, "type_valid", None),
    }


def known_cc_type(cc_type: str | None) -> bool:
    """True when ``cc_type`` is in the product conventional-commit set."""
    return bool(cc_type) and str(cc_type) in _CC_TYPES


def known_semver(value: str | None) -> bool:
    """True when value is a known SemVer-Impact token (case-insensitive)."""
    return bool(value) and str(value).upper() in _SEMVER_VALUES


def issue_ref_ok(trailers: dict[str, str]) -> tuple[bool, str | None]:
    """Validate issue-ref trailer form; ``Null`` must be ``#0`` only."""
    present = [k for k in ("Refs", "Resolves", "Closes", "Fixes", "Null") if k in trailers]
    if not present:
        return False, "missing_issue_ref"
    for key in present:
        val = trailers[key].strip()
        # Accept either "#123" or "123"
        if re.fullmatch(r"\d+", val):
            val = f"#{val}"
        pat = _ISSUE_KEY_RE[key]
        if not pat.match(val):
            if key == "Null":
                return False, "null_must_be_zero"
            return False, f"malformed_issue_ref:{key}"
    return True, None


__all__ = [
    "D_METRIC_TO_GOLD_CODE",
    "GOLD_CODE_TO_D_METRIC",
    "STRICT_FAIL_CODES",
    "deterministic_card_from_plan",
    "extract_trailers",
    "issue_ref_ok",
    "known_cc_type",
    "known_semver",
    "parse_hybrid_header",
    "parse_message_to_plan",
    "run_gold_once",
    "signals_from_context",
]
