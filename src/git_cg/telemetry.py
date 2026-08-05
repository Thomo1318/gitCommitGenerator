"""
Opik telemetry orchestration for git-cg lifecycle tracking.

This module handles the Two-Point Tracing architecture:
1. prepare-commit-msg: Generates commit, writes state to .git/GIT_CG_OPIK_STATE.json
2. commit-msg: Reads state, reads final message, classifies edits, logs to Opik.
"""

import contextlib
import enum
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from git_cg.models import CommitPlan, CommitType
from git_cg.sop import get_gitmoji_matrix


class Provenance(enum.StrEnum):
    """Classification of who authored the final commit message."""

    AI_ACCEPTED = "ai_accepted"  # User accepted without edits
    AI_ACCEPTED_REFS_ONLY = "ai_accepted_refs_only"  # Only added git trailers/refs
    AI_EDITED_MINOR = "ai_edited_minor"  # Minor tweaks (ratio >= 0.85)
    AI_EDITED_SUBSTANTIVE = "ai_edited_substantive"  # Substantial rewrite (ratio < 0.85)
    HUMAN_AUTHORED = "human_authored"  # Bypassed AI entirely
    CANCELLED = "cancelled"  # Aborted commit


class PreflightMode(enum.StrEnum):
    """How commit-group preflight ran (Phase 0.5 product may populate non-skipped later)."""

    LLM = "llm"
    HEURISTIC = "heuristic"
    SKIPPED = "skipped"


class SemanticRefreshGraph(enum.StrEnum):
    """Whether the opt-in graph refresh ran on the generate path (Phase 7.5 #180).

    Failure detail is carried by ShadowFailOpenReason, not by this enum.
    """

    SKIPPED = "skipped"
    REQUESTED = "requested"
    RAN = "ran"


class ShadowFailOpenReason(enum.StrEnum):
    """Closed telemetry category for shadow/refresh fail-open (Phase 7.5 #180).

    Exactly five members — do not collapse into fewer categories.
    """

    NONE = "none"
    SHADOW_CREATE_FAILED = "shadow_create_failed"
    SHADOW_SYNC_STAGED = "shadow_sync_staged"
    REFRESH_TIMEOUT = "refresh_timeout"
    REFRESH_FAILED = "refresh_failed"


class RankingConfidenceLevel(enum.StrEnum):
    """Closed ranking-confidence levels (Issue #195)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RankingChoicePath(enum.StrEnum):
    """Terminal ranking arbitration choice paths (Issue #195).

    Assign exactly one final value at terminal decision / final auto-continue.
    Intermediate Back / guidance-save / submenu navigation is not a path.
    """

    PICK_A = "pick_a"
    PICK_B = "pick_b"
    PICK_CANDIDATE = "pick_candidate"
    SPECIFY_FUZZY = "specify_fuzzy"
    SPECIFY_BROWSE = "specify_browse"
    CANCEL_CONTINUE_A = "cancel_continue_a"
    CANCEL_ABORT = "cancel_abort"
    NI_TOP_RANK = "ni_top_rank"
    SKIPPED_HIGH_MEDIUM = "skipped_high_medium"
    RE_RANK_AUTO_CONTINUE = "re_rank_auto_continue"


class RankingArbitrateEffective(enum.StrEnum):
    """Closed gate result for whether the arbitration menu was shown (Issue #195)."""

    MENU_SHOWN = "menu_shown"
    SKIPPED_NI = "skipped_ni"
    SKIPPED_HIGH_MEDIUM = "skipped_high_medium"
    FLAG_OFF = "flag_off"


class LockResolution(enum.StrEnum):
    """Closed lock-resolution observability codes (Issue #195)."""

    ACCEPTED = "accepted"
    REJECTED_NOT_ALLOWED = "rejected_not_allowed"
    REJECTED_HARD_VETO = "rejected_hard_veto"
    ABSENT = "absent"


class GoldSelfCorrectionOutcome(enum.StrEnum):
    """Closed gold self-correction outcomes (Issue #191 Option B).

    Do not split ``cleared`` by attempt depth — use ``gold_self_correction_attempts``.
    """

    NOT_NEEDED = "not_needed"
    CLEARED = "cleared"
    ABORTED_STALL = "aborted_stall"
    ABORTED_GROWTH = "aborted_growth"
    EXHAUSTED = "exhausted"


@dataclass
class DeterministicScoreCard:
    """Binary pass/fail structural validation results."""

    header_length_ok: bool = False
    description_length_ok: bool = False
    type_valid: bool = False
    emoji_matrix_aligned: bool = False
    semver_consistent: bool = False
    breaking_change_complete: bool = False

    @property
    def all_pass(self) -> bool:
        return all(asdict(self).values())

    @property
    def failed_checks(self) -> list[str]:
        return [k for k, v in asdict(self).items() if not v]


@dataclass
class GenerationTelemetry:
    """Telemetry data collected across the hook invocation lifecycle."""

    trace_id: str | None
    diff_hash: str
    diff_output: str
    repo_name: str
    engine: str
    model_name: str
    system_prompt_hash: str
    generated_message: str
    commit_plan_json: dict
    score_card: dict  # Dict representation of DeterministicScoreCard
    thread_id: str | None = None
    graph_schema_version: str = "unknown"
    # Phase 1 semantic producer metrics (non-content; safe defaults when disabled)
    semantic_enabled: bool = False
    parser_latency_ms: float = 0.0
    graph_build_latency_ms: float = 0.0
    graph_query_latency_ms: float = 0.0
    semantic_parser_metrics: dict | None = None
    # Phase 2 fingerprint algebra metrics (Issue #160)
    body_similarity_min: float | None = None
    body_similarity_avg: float | None = None
    fingerprint_files_compared: int = 0
    fingerprint_latency_ms: float = 0.0
    fingerprint_class_counts: dict | None = None
    fingerprint_grammar_version: str = "unknown"
    fingerprint_markers: list | None = None
    # Phase 3 preflight telemetry hooks (Issue #161). Default skipped until Phase 0.5.
    preflight_mode: str = PreflightMode.SKIPPED.value
    preflight_groups_count: int = 0
    preflight_fallback_reason: str = ""
    # Phase 7 semantic context product metrics (Issue #162).
    blast_radius_size: int | None = None
    affected_flows_count: int | None = None
    test_coverage_gap: bool | None = None
    test_gaps_count: int | None = None  # optional raw count; summary/debug (Issue #162 nice-to-have)
    semantic_context_schema_version: str = ""
    semantic_context_fallback_reasons: list[str] | None = None
    # Phase 7.5 shadow isolation (Issue #180).
    shadow_workspace_used: bool = False
    semantic_refresh_graph: str = SemanticRefreshGraph.SKIPPED.value
    shadow_fail_open_reason: str = ShadowFailOpenReason.NONE.value
    # Phase 7.29 ranking confidence + arbitration (Issue #195).
    ranking_confidence_level: str | None = None
    ranking_confidence_margin: float | None = None
    ranking_confidence_reasons: list[str] | None = None
    ranking_choice_path: str | None = None
    ranking_override: bool = False  # metadata bool — never store 1.0/0.0 here
    ranking_arbitrate_effective: str | None = None
    lock_resolution: str = LockResolution.ABSENT.value
    # Phase 7.25 gold telemetry parity (absorbed from #191 into #195 Slice 2).
    gold_mode: str = "off"
    gold_findings_count: int = 0
    gold_finding_codes: list[str] | None = None
    gold_blocked: bool = False
    gold_regen_attempts: int = 0
    # Phase 7.26 gold linter v1.1 (Issue #191) — self-correction + P6 only.
    gold_self_correction_attempts: int = 0
    gold_self_correction_outcome: str = GoldSelfCorrectionOutcome.NOT_NEEDED.value
    gold_split_recommendation: bool = False
    # Phase 9 scoped-history producers (Issue #163). Allowlisted non-content + redacted free-text.
    scoped_history_fallback_reason: str = "none"
    scoped_history_latency_ms: float = 0.0
    rename_confidence: str = "none"
    scoped_history_split_high_confidence: bool = False
    scoped_history_guidance: str | None = None
    scoped_history_split_rationale: str = ""
    scoped_history_rename_rationale: str = ""
    structural_error_handling: bool = False
    structural_public_api: bool = False
    structural_new_command: bool = False


def compute_prompt_hash(prompt: str) -> str:
    """
    Generate a 16-character identifier for a prompt.

    Returns:
        str: The first 16 hexadecimal characters of the prompt's SHA-256 hash.
    """
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def compute_diff_hash(diff_output: str) -> str:
    """SHA-256 hash of the git diff."""
    return hashlib.sha256(diff_output.encode()).hexdigest()[:16]


def ranking_override_feedback_score(ranking_override: bool) -> float:
    """Derive the Opik ``ranking_override`` feedback score from the metadata bool.

    Type boundary (Issue #195): ``GenerationTelemetry.ranking_override`` is a
    **bool**; the Opik feedback score is a **float** ``1.0`` / ``0.0`` derived
    only at this score boundary.
    """
    return 1.0 if ranking_override else 0.0


def run_deterministic_checks(commit_plan: CommitPlan) -> DeterministicScoreCard:
    """Run all deterministic structural validations on a CommitPlan."""
    card = DeterministicScoreCard()
    pi = commit_plan.primary_intent

    # Header length
    scope_str = f"({pi.scope})" if pi.scope else ""
    breaking = "!" if commit_plan.breaking_change else ""
    header = f"{pi.gitmoji} {pi.cc_type.value}{scope_str}{breaking}: {pi.description}"
    card.header_length_ok = len(header) <= 72

    # Description length
    card.description_length_ok = len(pi.description) <= 50

    # Type validity
    card.type_valid = isinstance(pi.cc_type, CommitType)

    # Emoji matrix & SemVer alignment
    matrix = get_gitmoji_matrix()
    if matrix:
        entry = next((e for e in matrix if e.get("intent_id") == pi.intent_id), None)
        card.emoji_matrix_aligned = entry is not None and entry.get("emoji") == pi.gitmoji
        if entry:
            card.semver_consistent = entry.get("semver_impact") == pi.semver_impact.value
        else:
            card.semver_consistent = True
    else:
        card.emoji_matrix_aligned = True
        card.semver_consistent = True

    # Breaking change completeness
    if commit_plan.breaking_change:
        card.breaking_change_complete = bool(commit_plan.breaking_change_description)
    else:
        card.breaking_change_complete = True

    return card


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein ratio between two strings (1.0 = identical)."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return 0.0 if len(s1) > 0 else 1.0

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    distance = prev_row[-1]
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)


def _strip_trailers(text: str) -> str:
    """Remove common git trailers and references from the end of a message."""
    lines = text.strip().splitlines()
    trailer_prefixes = (
        "Refs:",
        "Resolves:",
        "Closes:",
        "Fixes:",
        "Co-authored-by:",
        "Signed-off-by:",
        "SemVer-Impact:",
        "Change-Types:",
        "Changelog-Groups:",
    )

    # Strip backwards
    valid_lines = []
    in_trailers = True
    for line in reversed(lines):
        if in_trailers and (not line.strip() or line.strip().startswith(trailer_prefixes)):
            continue
        in_trailers = False
        valid_lines.insert(0, line)

    return "\n".join(valid_lines).strip()


def classify_edit(original: str, edited: str) -> Provenance:
    """
    Classifies how an edited commit message differs from the original message.

    Parameters:
        original (str): The generated commit message.
        edited (str): The final commit message.

    Returns:
        Provenance: The classification of the message edit.
    """
    if original.strip() == edited.strip():
        return Provenance.AI_ACCEPTED

    orig_stripped = _strip_trailers(original)
    edited_stripped = _strip_trailers(edited)

    if orig_stripped == edited_stripped:
        return Provenance.AI_ACCEPTED_REFS_ONLY

    ratio = _levenshtein_ratio(orig_stripped, edited_stripped)

    if ratio >= 0.85:
        return Provenance.AI_EDITED_MINOR
    return Provenance.AI_EDITED_SUBSTANTIVE


def _resolve_intent_fields_from_matrix(
    *,
    gitmoji: str,
    cc_type: str,
    semver_impact: str | None = None,
    changelog_group: str | None = None,
) -> dict[str, str]:
    """
    Resolve rendered commit intent fields against the Gitmoji matrix, using supplied values when no matching entry is found.

    Parameters:
        gitmoji (str): Emoji associated with the commit intent.
        cc_type (str): Conventional commit type associated with the intent.
        semver_impact (str | None): Fallback semantic version impact.
        changelog_group (str | None): Fallback changelog group.

    Returns:
        dict[str, str]: Resolved intent ID, semantic version impact, and changelog group.
    """
    from git_cg.sop import get_gitmoji_matrix

    matrix = get_gitmoji_matrix() or []
    emoji = (gitmoji or "").strip()
    ctype = (cc_type or "").strip()

    def _row_intent_id(row: dict) -> str:
        """Extract an intent identifier from a gitmoji matrix row.

        Parameters:
                row (dict): Matrix row containing an optional ``intent_id`` or ``code`` value.

        Returns:
                str: The row's intent identifier, falling back to the stripped ``code`` or ``"unknown"``.
        """
        intent_id = row.get("intent_id")
        if intent_id:
            return str(intent_id)
        code = row.get("code")
        return str(code or "unknown").strip(":")

    match = None
    if emoji:
        candidates = [row for row in matrix if row.get("emoji") == emoji]
        if ctype:
            typed = [row for row in candidates if row.get("cc_type") == ctype]
            if typed:
                candidates = typed
        if candidates:
            match = candidates[0]
    if match is None and ctype:
        typed = [row for row in matrix if row.get("cc_type") == ctype]
        if typed:
            match = typed[0]

    if match is None:
        return {
            "intent_id": "unknown",
            "semver_impact": semver_impact or "NONE",
            "changelog_group": changelog_group or "Miscellaneous",
        }

    return {
        "intent_id": _row_intent_id(match),
        "semver_impact": str(match.get("semver_impact") or semver_impact or "NONE"),
        "changelog_group": str(match.get("changelog_group") or changelog_group or "Miscellaneous"),
    }


def reverse_parse_commit_message(text: str) -> dict[str, Any]:
    """
    Parse a rendered commit message into a partial CommitPlan-compatible dictionary.

    Recoverable intent, body, secondary changes, trailers, and breaking-change
    information are populated; fields unavailable in the rendered message use
    placeholders, and the result is marked as partial.

    Returns:
        dict[str, Any]: The reconstructed partial commit plan, or an empty dictionary
                if the message contains no lines.
    """
    import re

    lines = [line.strip() for line in text.splitlines()]
    if not lines:
        return {}

    plan: dict[str, Any] = {
        "primary_intent": {
            "intent_id": "unknown",
            "cc_type": "chore",
            "scope": None,
            "description": "",
            "gitmoji": "🔧",
            "semver_impact": "NONE",
            "changelog_group": "other",
        },
        "secondary_intents": [],
        # Unrecoverable CommitPlan fields — placeholders for schema compatibility.
        "split_recommended": False,
        "rationale": "",
        "body_summary": "",
        "breaking_change": False,
        "breaking_change_description": None,
        "_partial": True,
    }
    primary_intent: dict[str, Any] = plan["primary_intent"]

    # 1. Parse header
    header = lines[0]
    # Regex handles optional gitmoji and standard conventional commit syntax
    # e.g., "✨ feat(auth)!: add login" or "fix: typo"
    header_match = re.match(r"^(?:(.*?)\s+)?([a-z]+)(?:\(([^)]+)\))?(!)?:\s+(.*)$", header)
    if header_match:
        emoji, cc_type, scope, breaking, description = header_match.groups()
        primary_intent["gitmoji"] = emoji or ""
        primary_intent["cc_type"] = cc_type
        primary_intent["scope"] = scope
        primary_intent["description"] = description
        if breaking:
            plan["breaking_change"] = True
    else:
        # Fallback if it doesn't match standard conventional commit structure
        primary_intent["description"] = header

    # 2. Extract body, included changes, trailers, and footer
    body_lines = []
    in_secondary = False
    in_trailers = False
    trailers = {}

    i = 1
    while i < len(lines):
        line = lines[i]

        if line == "":
            i += 1
            continue

        if line == "Included changes:":
            in_secondary = True
            i += 1
            continue

        if line.startswith("BREAKING CHANGE:"):
            plan["breaking_change"] = True
            plan["breaking_change_description"] = line.replace("BREAKING CHANGE:", "").strip()
            i += 1
            continue

        if line.startswith(
            (
                "Refs:",
                "Resolves:",
                "Closes:",
                "Fixes:",
                "Null:",
                "Co-authored-by:",
                "Signed-off-by:",
                "SemVer-Impact:",
                "Change-Types:",
                "Changelog-Groups:",
            )
        ):
            in_trailers = True
            in_secondary = False

        if in_trailers:
            if ":" in line:
                key, val = line.split(":", 1)
                trailers[key.strip()] = val.strip()
        elif in_secondary:
            if line.startswith("- "):
                sec_match = re.match(r"^- (?:(.*?)\s+)?([a-z]+)(?:\(([^)]+)\))?:\s+(.*)$", line)
                if sec_match:
                    emoji, cc_type, scope, description = sec_match.groups()
                    plan["secondary_intents"].append(
                        {
                            "intent_id": "unknown",
                            "cc_type": cc_type,
                            "scope": scope,
                            "description": description,
                            "gitmoji": emoji or "",
                            "semver_impact": "NONE",
                            "changelog_group": "other",
                        }
                    )
            else:
                # If it's not a list item, maybe we left the included changes section
                in_secondary = False
                body_lines.append(line)
        else:
            body_lines.append(line)

        i += 1

    plan["body_summary"] = "\n".join(body_lines)

    # Enrich primary intent from trailers if possible
    if "SemVer-Impact" in trailers:
        primary_intent["semver_impact"] = trailers["SemVer-Impact"]
    if "Changelog-Groups" in trailers:
        # First group is the primary changelog group in rendered messages.
        groups = [part.strip() for part in trailers["Changelog-Groups"].split(",") if part.strip()]
        if groups:
            primary_intent["changelog_group"] = groups[0]

    # Resolve intent_id (and fill matrix-owned fields) from emoji/type.
    resolved_primary = _resolve_intent_fields_from_matrix(
        gitmoji=str(primary_intent.get("gitmoji") or ""),
        cc_type=str(primary_intent.get("cc_type") or ""),
        semver_impact=str(primary_intent.get("semver_impact") or "NONE"),
        changelog_group=str(primary_intent.get("changelog_group") or "Miscellaneous"),
    )
    primary_intent["intent_id"] = resolved_primary["intent_id"]
    # Prefer trailer SemVer when present; otherwise matrix value.
    if "SemVer-Impact" not in trailers:
        primary_intent["semver_impact"] = resolved_primary["semver_impact"]
    if "Changelog-Groups" not in trailers:
        primary_intent["changelog_group"] = resolved_primary["changelog_group"]

    for secondary in plan["secondary_intents"]:
        resolved_secondary = _resolve_intent_fields_from_matrix(
            gitmoji=str(secondary.get("gitmoji") or ""),
            cc_type=str(secondary.get("cc_type") or ""),
            semver_impact=str(secondary.get("semver_impact") or "NONE"),
            changelog_group=str(secondary.get("changelog_group") or "Miscellaneous"),
        )
        secondary["intent_id"] = resolved_secondary["intent_id"]
        secondary["semver_impact"] = resolved_secondary["semver_impact"]
        secondary["changelog_group"] = resolved_secondary["changelog_group"]

    return plan


def redact_payload(payload: str) -> str:
    """
    Scrub PII and secrets from strings using betterleaks.
    Acts as a mandatory gateway interceptor before telemetry is enabled.
    """
    if not payload:
        return payload

    try:
        process = subprocess.run(
            ["betterleaks", "stdin", "-f", "json", "-r", "-", "--no-banner", "-l", "fatal"],
            input=payload,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        output = process.stdout.strip()
        findings = json.loads(output)
        if not isinstance(findings, list):
            raise ValueError("Expected JSON list from betterleaks")

        redacted = payload
        for finding in findings:
            secret = finding.get("Secret")
            if secret and secret in redacted:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    except Exception:
        # Fail safe if betterleaks is missing or fails to execute
        return "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]"


def _normalize_optional_bool(value: Any) -> bool | None:
    """
    Normalize persisted/serialized values into ``bool | None``.

    Accepts native bools, 0/1 numerics, and common string forms
    (``true``/``false``/``yes``/``no``/``on``/``off``/``1``/``0``).
    Unrecognized values become ``None``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        if value == 1 or value == 1.0:
            return True
        if value == 0 or value == 0.0:
            return False
        return None
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "on"}:
            return True
        if token in {"false", "0", "no", "off"}:
            return False
        return None
    return None


def get_state_file_path(git_dir: str) -> Path:
    return Path(git_dir) / "GIT_CG_OPIK_STATE.json"


def write_telemetry_state(git_dir: str, telemetry: GenerationTelemetry) -> None:
    """
    Persist redacted telemetry state in the repository's Git directory for retrieval by a later hook.

    Parameters:
        git_dir (str): Path to the Git directory where the state file is stored.
        telemetry (GenerationTelemetry): Telemetry data to redact and persist.
    """
    telemetry.diff_output = redact_payload(telemetry.diff_output)
    telemetry.generated_message = redact_payload(telemetry.generated_message)

    plan_str = json.dumps(telemetry.commit_plan_json)
    redacted_plan_str = redact_payload(plan_str)

    if redacted_plan_str == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
        telemetry.commit_plan_json = {"_redaction": "failed"}
    else:
        telemetry.commit_plan_json = json.loads(redacted_plan_str)

    # Phase 1: redact path/error-bearing fallback reasons inside parser metrics.
    if isinstance(telemetry.semantic_parser_metrics, dict):
        metrics = dict(telemetry.semantic_parser_metrics)
        reasons = metrics.get("semantic_fallback_reasons")
        if isinstance(reasons, list):
            redacted_reasons: list[str] = []
            for reason in reasons:
                if not isinstance(reason, str):
                    continue
                redacted = redact_payload(reason)
                if redacted == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
                    redacted_reasons.append("[REDACTED]")
                else:
                    redacted_reasons.append(redacted)
            metrics["semantic_fallback_reasons"] = redacted_reasons
        telemetry.semantic_parser_metrics = metrics

    # Phase 3: free-text preflight reason through betterleaks gateway.
    if telemetry.preflight_fallback_reason:
        redacted_reason = redact_payload(telemetry.preflight_fallback_reason)
        if redacted_reason == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
            telemetry.preflight_fallback_reason = "[REDACTED]"
        else:
            telemetry.preflight_fallback_reason = redacted_reason

    # Phase 7: redact semantic context fallback reasons (path/error-bearing).
    if isinstance(telemetry.semantic_context_fallback_reasons, list):
        redacted_ctx: list[str] = []
        for reason in telemetry.semantic_context_fallback_reasons:
            if not isinstance(reason, str):
                continue
            redacted = redact_payload(reason)
            if redacted == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
                redacted_ctx.append("[REDACTED]")
            else:
                redacted_ctx.append(redacted)
        telemetry.semantic_context_fallback_reasons = redacted_ctx

    # Phase 9: redact free-text scoped-history guidance/rationales only.
    # Closed enums (fallback_reason / rename_confidence) and bool markers stay as-is
    # and are coerced to the closed vocabulary without betterleaks.
    for attr in (
        "scoped_history_guidance",
        "scoped_history_split_rationale",
        "scoped_history_rename_rationale",
    ):
        value = getattr(telemetry, attr, None)
        if not value:
            if attr == "scoped_history_guidance":
                setattr(telemetry, attr, None)
            else:
                setattr(telemetry, attr, "")
            continue
        redacted = redact_payload(str(value))
        if redacted == "[REDACTION FAILED - PAYLOAD OMITTED FOR SAFETY]":
            # Keep failure distinguishable from "no guidance produced" (None).
            setattr(telemetry, attr, "[REDACTED]")
        else:
            setattr(telemetry, attr, redacted)

    # Coerce closed Phase 9 enums on write (no free-text gateway).
    try:
        from git_cg.scoped_history import coerce_fallback_reason, coerce_rename_confidence

        telemetry.scoped_history_fallback_reason = coerce_fallback_reason(telemetry.scoped_history_fallback_reason)
        telemetry.rename_confidence = coerce_rename_confidence(telemetry.rename_confidence)
    except Exception:
        telemetry.scoped_history_fallback_reason = "none"
        telemetry.rename_confidence = "none"

    state_file = get_state_file_path(git_dir)
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(asdict(telemetry), f, indent=2)


def read_telemetry_state(git_dir: str) -> GenerationTelemetry | None:
    """
    Read persisted commit telemetry from the git directory.

    Parameters:
        git_dir (str): Path to the git directory containing the telemetry state file.

    Returns:
        GenerationTelemetry | None: The stored telemetry, or `None` if the state file is missing or cannot be loaded.
    """
    state_file = get_state_file_path(git_dir)
    if not state_file.exists():
        return None
    try:
        with state_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if "trace_id" not in data:
                data["trace_id"] = None
            if "thread_id" not in data:
                data["thread_id"] = None
            # Phase 1 backward-compat defaults for pre-semantic state files.
            data.setdefault("semantic_enabled", False)
            data.setdefault("parser_latency_ms", 0.0)
            data.setdefault("graph_build_latency_ms", 0.0)
            data.setdefault("graph_query_latency_ms", 0.0)
            data.setdefault("semantic_parser_metrics", None)
            data.setdefault("graph_schema_version", "unknown")
            # Phase 2 fingerprint algebra defaults (Issue #160).
            data.setdefault("body_similarity_min", None)
            data.setdefault("body_similarity_avg", None)
            data.setdefault("fingerprint_files_compared", 0)
            data.setdefault("fingerprint_latency_ms", 0.0)
            data.setdefault("fingerprint_class_counts", None)
            data.setdefault("fingerprint_grammar_version", "unknown")
            data.setdefault("fingerprint_markers", None)
            # Phase 3 preflight telemetry defaults (Issue #161).
            data.setdefault("preflight_mode", PreflightMode.SKIPPED.value)
            data.setdefault("preflight_groups_count", 0)
            data.setdefault("preflight_fallback_reason", "")
            # Phase 7 semantic context defaults (Issue #162).
            data.setdefault("blast_radius_size", None)
            data.setdefault("affected_flows_count", None)
            data.setdefault("test_coverage_gap", None)
            data.setdefault("test_gaps_count", None)
            data.setdefault("semantic_context_schema_version", "")
            data.setdefault("semantic_context_fallback_reasons", None)
            # Phase 7.5 shadow isolation defaults (Issue #180).
            data.setdefault("shadow_workspace_used", False)
            data.setdefault("semantic_refresh_graph", SemanticRefreshGraph.SKIPPED.value)
            data.setdefault("shadow_fail_open_reason", ShadowFailOpenReason.NONE.value)
            # Normalise enum-ish values to plain strings for dataclass storage.
            mode = data.get("preflight_mode")
            if isinstance(mode, PreflightMode):
                data["preflight_mode"] = mode.value
            elif mode not in {m.value for m in PreflightMode}:
                data["preflight_mode"] = PreflightMode.SKIPPED.value
            try:
                data["preflight_groups_count"] = int(data.get("preflight_groups_count") or 0)
            except TypeError, ValueError:
                data["preflight_groups_count"] = 0
            if data.get("preflight_fallback_reason") is None:
                data["preflight_fallback_reason"] = ""
            else:
                data["preflight_fallback_reason"] = str(data["preflight_fallback_reason"])
            # Phase 7 normalise.
            for int_key in ("blast_radius_size", "affected_flows_count", "test_gaps_count"):
                raw = data.get(int_key)
                if raw is None or raw == "":
                    data[int_key] = None
                else:
                    try:
                        data[int_key] = int(raw)
                    except TypeError, ValueError:
                        data[int_key] = None
            data["test_coverage_gap"] = _normalize_optional_bool(data.get("test_coverage_gap"))
            data["semantic_context_schema_version"] = str(data.get("semantic_context_schema_version") or "")
            reasons = data.get("semantic_context_fallback_reasons")
            if reasons is None:
                data["semantic_context_fallback_reasons"] = None
            elif isinstance(reasons, list):
                data["semantic_context_fallback_reasons"] = [str(item) for item in reasons if item is not None]
            else:
                data["semantic_context_fallback_reasons"] = None
            # Phase 7.5 normalise (Issue #180): bounded bool + closed enums.
            data["shadow_workspace_used"] = bool(data.get("shadow_workspace_used"))
            refresh_state = data.get("semantic_refresh_graph")
            if isinstance(refresh_state, SemanticRefreshGraph):
                data["semantic_refresh_graph"] = refresh_state.value
            elif refresh_state not in {s.value for s in SemanticRefreshGraph}:
                data["semantic_refresh_graph"] = SemanticRefreshGraph.SKIPPED.value
            fail_reason = data.get("shadow_fail_open_reason")
            if isinstance(fail_reason, ShadowFailOpenReason):
                data["shadow_fail_open_reason"] = fail_reason.value
            elif fail_reason not in {r.value for r in ShadowFailOpenReason}:
                data["shadow_fail_open_reason"] = ShadowFailOpenReason.NONE.value
            # Phase 7.29 ranking confidence defaults (Issue #195).
            data.setdefault("ranking_confidence_level", None)
            data.setdefault("ranking_confidence_margin", None)
            data.setdefault("ranking_confidence_reasons", None)
            data.setdefault("ranking_choice_path", None)
            data.setdefault("ranking_override", False)
            data.setdefault("ranking_arbitrate_effective", None)
            data.setdefault("lock_resolution", LockResolution.ABSENT.value)
            data.setdefault("gold_mode", "off")
            data.setdefault("gold_findings_count", 0)
            data.setdefault("gold_finding_codes", None)
            data.setdefault("gold_blocked", False)
            data.setdefault("gold_regen_attempts", 0)
            data.setdefault("gold_self_correction_attempts", 0)
            data.setdefault("gold_self_correction_outcome", GoldSelfCorrectionOutcome.NOT_NEEDED.value)
            data.setdefault("gold_split_recommendation", False)
            # Phase 9 scoped-history defaults (Issue #163).
            data.setdefault("scoped_history_fallback_reason", "none")
            data.setdefault("scoped_history_latency_ms", 0.0)
            data.setdefault("rename_confidence", "none")
            data.setdefault("scoped_history_split_high_confidence", False)
            data.setdefault("scoped_history_guidance", None)
            data.setdefault("scoped_history_split_rationale", "")
            data.setdefault("scoped_history_rename_rationale", "")
            data.setdefault("structural_error_handling", False)
            data.setdefault("structural_public_api", False)
            data.setdefault("structural_new_command", False)
            # Normalise ranking fields.
            level = data.get("ranking_confidence_level")
            if level is not None and level not in {m.value for m in RankingConfidenceLevel}:
                data["ranking_confidence_level"] = None
            margin = data.get("ranking_confidence_margin")
            if margin is None or margin == "":
                data["ranking_confidence_margin"] = None
            else:
                try:
                    data["ranking_confidence_margin"] = float(margin)
                except TypeError, ValueError:
                    data["ranking_confidence_margin"] = None
            reasons = data.get("ranking_confidence_reasons")
            if reasons is None:
                data["ranking_confidence_reasons"] = None
            elif isinstance(reasons, list):
                data["ranking_confidence_reasons"] = [str(item) for item in reasons if item is not None]
            else:
                data["ranking_confidence_reasons"] = None
            choice = data.get("ranking_choice_path")
            if choice is not None and choice not in {m.value for m in RankingChoicePath}:
                data["ranking_choice_path"] = None
            # ranking_override is metadata bool — coerce legacy 1.0/0.0 if present.
            raw_override = data.get("ranking_override", False)
            if isinstance(raw_override, bool):
                data["ranking_override"] = raw_override
            elif isinstance(raw_override, (int, float)):
                data["ranking_override"] = bool(raw_override)
            elif isinstance(raw_override, str):
                data["ranking_override"] = raw_override.strip().lower() in {"1", "true", "yes", "on"}
            else:
                data["ranking_override"] = False
            arb = data.get("ranking_arbitrate_effective")
            if arb is not None and arb not in {m.value for m in RankingArbitrateEffective}:
                data["ranking_arbitrate_effective"] = None
            lock_res = data.get("lock_resolution")
            if lock_res not in {m.value for m in LockResolution}:
                data["lock_resolution"] = LockResolution.ABSENT.value
            data["gold_mode"] = str(data.get("gold_mode") or "off")
            try:
                data["gold_findings_count"] = int(data.get("gold_findings_count") or 0)
            except TypeError, ValueError:
                data["gold_findings_count"] = 0
            codes = data.get("gold_finding_codes")
            if codes is None:
                data["gold_finding_codes"] = None
            elif isinstance(codes, list):
                data["gold_finding_codes"] = sorted({str(c) for c in codes if c is not None})
            else:
                data["gold_finding_codes"] = None
            data["gold_blocked"] = bool(data.get("gold_blocked"))
            try:
                data["gold_regen_attempts"] = int(data.get("gold_regen_attempts") or 0)
            except TypeError, ValueError:
                data["gold_regen_attempts"] = 0
            try:
                data["gold_self_correction_attempts"] = int(data.get("gold_self_correction_attempts") or 0)
            except TypeError, ValueError:
                data["gold_self_correction_attempts"] = 0
            outcome = data.get("gold_self_correction_outcome")
            if outcome not in {m.value for m in GoldSelfCorrectionOutcome}:
                data["gold_self_correction_outcome"] = GoldSelfCorrectionOutcome.NOT_NEEDED.value
            else:
                data["gold_self_correction_outcome"] = str(outcome)
            # Mirror ranking_override string/legacy coercion — bare bool("false") is True.
            raw_split = data.get("gold_split_recommendation", False)
            if isinstance(raw_split, bool):
                data["gold_split_recommendation"] = raw_split
            elif isinstance(raw_split, (int, float)) and not isinstance(raw_split, bool):
                data["gold_split_recommendation"] = raw_split == 1
            elif isinstance(raw_split, str):
                data["gold_split_recommendation"] = raw_split.strip().lower() in {"1", "true", "yes", "on"}
            else:
                data["gold_split_recommendation"] = False
            # Phase 9 normalise (Issue #163): closed enums + bounded free-text + bools.
            try:
                from git_cg.scoped_history import coerce_fallback_reason, coerce_rename_confidence

                data["scoped_history_fallback_reason"] = coerce_fallback_reason(
                    data.get("scoped_history_fallback_reason")
                )
                data["rename_confidence"] = coerce_rename_confidence(data.get("rename_confidence"))
            except Exception:
                data["scoped_history_fallback_reason"] = "none"
                data["rename_confidence"] = "none"
            try:
                data["scoped_history_latency_ms"] = float(data.get("scoped_history_latency_ms") or 0.0)
            except TypeError, ValueError:
                data["scoped_history_latency_ms"] = 0.0
            for bkey in (
                "scoped_history_split_high_confidence",
                "structural_error_handling",
                "structural_public_api",
                "structural_new_command",
            ):
                raw_b = data.get(bkey, False)
                if isinstance(raw_b, bool):
                    data[bkey] = raw_b
                elif isinstance(raw_b, (int, float)) and not isinstance(raw_b, bool):
                    data[bkey] = raw_b == 1
                elif isinstance(raw_b, str):
                    data[bkey] = raw_b.strip().lower() in {"1", "true", "yes", "on"}
                else:
                    data[bkey] = False
            guidance = data.get("scoped_history_guidance")
            if guidance is None or guidance == "":
                data["scoped_history_guidance"] = None
            else:
                data["scoped_history_guidance"] = str(guidance)
            data["scoped_history_split_rationale"] = str(data.get("scoped_history_split_rationale") or "")
            data["scoped_history_rename_rationale"] = str(data.get("scoped_history_rename_rationale") or "")
            return GenerationTelemetry(**data)
    except Exception:
        return None


def clear_telemetry_state(git_dir: str) -> None:
    """Delete the telemetry state file."""
    state_file = get_state_file_path(git_dir)
    if state_file.exists():
        with contextlib.suppress(OSError):
            state_file.unlink()
