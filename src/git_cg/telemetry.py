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
from dataclasses import asdict, dataclass
from pathlib import Path

from git_cg.models import CommitPlan, CommitType
from git_cg.sentry_config import init_sentry
from git_cg.sop import get_gitmoji_matrix

init_sentry()


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

    return "\\n".join(valid_lines).strip()


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


def get_state_file_path(git_dir: str) -> Path:
    return Path(git_dir) / "GIT_CG_OPIK_STATE.json"


def write_telemetry_state(git_dir: str, telemetry: GenerationTelemetry) -> None:
    """Write the current telemetry state to the .git directory for the commit-msg hook."""
    state_file = get_state_file_path(git_dir)
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(asdict(telemetry), f, indent=2)


def read_telemetry_state(git_dir: str) -> GenerationTelemetry | None:
    """
    Reads the telemetry state written by prepare-commit-msg, backfilling missing fields for backwards compatibility.

    Returns:
        The persisted GenerationTelemetry instance, or None if the state file does not exist or cannot be read.
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
            return GenerationTelemetry(**data)
    except Exception:
        return None


def clear_telemetry_state(git_dir: str) -> None:
    """Delete the telemetry state file."""
    state_file = get_state_file_path(git_dir)
    if state_file.exists():
        with contextlib.suppress(OSError):
            state_file.unlink()
