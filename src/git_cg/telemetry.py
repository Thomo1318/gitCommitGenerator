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


def compute_prompt_hash(prompt: str) -> str:
    """
    Produce a version-tracking identifier for a prompt.

    Returns:
        str: The first 16 hexadecimal characters of the prompt's SHA-256 hash.
    """
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def compute_diff_hash(diff_output: str) -> str:
    """SHA-256 hash of the git diff."""
    return hashlib.sha256(diff_output.encode()).hexdigest()[:16]


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
    """Classify edit magnitude using a trailer-aware Levenshtein ratio."""
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


def reverse_parse_commit_message(text: str) -> dict[str, Any]:
    """
    Reverse-parse a finalized commit message text into a CommitPlan-compatible dict.

    Extracts components matching the deterministic format from `CommitPlan.render()`.
    Fields that cannot be recovered from rendered text (`split_recommended`, `rationale`)
    are filled with explicit placeholders and `_partial` is set to True.

    Returns:
        dict: Partial plan with primary_intent, body_summary, secondary_intents, and placeholders.
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


def get_state_file_path(git_dir: str) -> Path:
    return Path(git_dir) / "GIT_CG_OPIK_STATE.json"


def write_telemetry_state(git_dir: str, telemetry: GenerationTelemetry) -> None:
    """Write the current telemetry state to the .git directory for the commit-msg hook."""
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
            return GenerationTelemetry(**data)
    except Exception:
        return None


def clear_telemetry_state(git_dir: str) -> None:
    """Delete the telemetry state file."""
    state_file = get_state_file_path(git_dir)
    if state_file.exists():
        with contextlib.suppress(OSError):
            state_file.unlink()
