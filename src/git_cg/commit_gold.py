"""Deterministic post-enforce commit-message gold linter (Issues #182 / #191 / #204).

Gold checks content quality of a structured ``CommitPlan`` *after*
``enforce_semantic_contract`` and the mixed-policy handle. The checker is pure:
no I/O, no model calls, no SOP mutation, and no mutation of the plan/contract.

Authority boundary (locked):
    * The matrix ranker remains the sole ranking / identity authority
      (``intent_id`` + matrix ``gitmoji``).
    * Issue #204 presentation overlay may legally rewrite rendered presentation
      fields (``cc_type``, scope, SemVer presentation, changelog group, inventory)
      after enforce. When ``presentation_overlay_applied=True``, gold keeps
      identity/wording checks but does not treat those presentation fields as
      matrix-contract smoke failures.
    * Gold never emits ``preferred_type``/``preferred_scope`` steers and never
      rewrites plan fields. It may only request *wording* / *secondary-coverage*
      regeneration via the dedicated ``gold_guidance`` channel.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from git_cg.intent import (
    DiffSignals,
    _is_build_path,
    _is_ci_path,
    _is_config_path,
    _is_docs_path,
    _is_hook_path,
    _is_release_path,
    _is_test_path,
)
from git_cg.models import CommitPlan
from git_cg.regeneration import ResolvedCommitContract

# Shared banned body-opener constant (Slice 2 prompt rubric + Slice 3a linter must
# not drift). Matched case-sensitively against the first line of a stripped body.
BANNED_BODY_OPENERS: tuple[str, ...] = (
    "This commit introduces",
    "This commit adds",
    "This commit updates",
    "This PR",
    "We have",
    # F3 marketing / inventory first-line openers (matched case-sensitively).
    "Adds ",
    "Introduces ",
    "Ensures ",
    "This change ",
    "This change introduces",
    "This change adds",
    "This change updates",
)

# Coverage scoring constants (change only with B2 fixture updates).
GOLD_SECONDARY_SCORE_RATIO: float = 0.5
GOLD_SECONDARY_SCORE_ABS: float = 20.0

# Product-intent Conventional Commit types subject to group-coherence checks.
_PRODUCT_CC_TYPES: frozenset[str] = frozenset({"feat", "fix", "perf"})

# Groups that require an explanatory fix/error-handling intent when the primary
# is a product feat/perf.
_FIX_EXPLAINING_GROUPS: frozenset[str] = frozenset({"Fixed"})

# Normative gitmoji -> (cc_type, frozenset[coherent changelog groups], semver_impact)
# for the closed gitmoji vocabulary (Issue #195 Phase 7.29 F2/F7). Mirrors the SOP
# ``gitmoji_reference_matrix``; keys are normalised (variation selector U+FE0F stripped)
# because the matrix encodes some emoji with and without the selector. Assert-tested
# against the live SOP so it cannot drift.
GITMOJI_CC_GROUPS: dict[str, tuple[str, frozenset[str], str]] = {
    "⏪": ("revert", frozenset({"Changed"}), "PATCH"),
    "♻": ("refactor", frozenset({"Changed"}), "PATCH"),
    "♿": ("feat", frozenset({"Changed"}), "PATCH"),
    "⚗": ("feat", frozenset({"Changed"}), "PATCH"),
    "⚡": ("perf", frozenset({"Changed"}), "PATCH"),
    "⚰": ("refactor", frozenset({"Removed"}), "PATCH"),
    "✅": ("test", frozenset({"Miscellaneous"}), "NONE"),
    "✈": ("feat", frozenset({"Added"}), "MINOR"),
    "✏": ("docs", frozenset({"Miscellaneous"}), "NONE"),
    "✨": ("feat", frozenset({"Added"}), "MINOR"),
    "\u2795": ("build", frozenset({"Changed"}), "PATCH"),
    "\u2796": ("build", frozenset({"Changed"}), "PATCH"),
    "⬆": ("build", frozenset({"Changed"}), "PATCH"),
    "⬇": ("build", frozenset({"Changed"}), "PATCH"),
    "🌐": ("feat", frozenset({"Added"}), "MINOR"),
    "🌱": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🍱": ("chore", frozenset({"Added"}), "PATCH"),
    "🍻": ("refactor", frozenset({"Miscellaneous"}), "NONE"),
    "🎉": ("init", frozenset({"Miscellaneous"}), "NONE"),
    "🎨": ("style", frozenset({"Changed"}), "NONE"),
    "🏗": ("refactor", frozenset({"Changed"}), "MAJOR"),
    "🏷": ("refactor", frozenset({"Changed"}), "PATCH"),
    "🐛": ("fix", frozenset({"Fixed"}), "PATCH"),
    "👔": ("feat", frozenset({"Added"}), "MINOR"),
    "👥": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "👷": ("ci", frozenset({"Miscellaneous"}), "NONE"),
    "👽": ("refactor", frozenset({"Changed"}), "PATCH"),
    "💄": ("style", frozenset({"Changed"}), "PATCH"),
    "💚": ("ci", frozenset({"Miscellaneous"}), "NONE"),
    "💡": ("docs", frozenset({"Miscellaneous"}), "NONE"),
    "💥": ("feat", frozenset({"Changed"}), "MAJOR"),
    "💩": ("refactor", frozenset({"Miscellaneous"}), "NONE"),
    "💫": ("feat", frozenset({"Changed"}), "PATCH"),
    "💬": ("style", frozenset({"Changed"}), "PATCH"),
    "💸": ("feat", frozenset({"Added"}), "MINOR"),
    "📄": ("docs", frozenset({"Miscellaneous"}), "NONE"),
    "📈": ("feat", frozenset({"Added"}), "MINOR"),
    "📌": ("build", frozenset({"Changed"}), "PATCH"),
    "📝": ("docs", frozenset({"Miscellaneous"}), "NONE"),
    "📦": ("build", frozenset({"Changed"}), "PATCH"),
    "📱": ("feat", frozenset({"Changed"}), "PATCH"),
    "📸": ("test", frozenset({"Miscellaneous"}), "NONE"),
    "🔀": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🔇": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🔊": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🔍": ("feat", frozenset({"Changed"}), "PATCH"),
    "🔐": ("chore", frozenset({"Security"}), "PATCH"),
    "🔒": ("fix", frozenset({"Security"}), "PATCH"),
    "🔖": ("release", frozenset({"Miscellaneous"}), "NONE"),
    "🔥": ("refactor", frozenset({"Removed"}), "PATCH"),
    "🔧": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🔨": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🗃": ("feat", frozenset({"Changed"}), "PATCH"),
    "🗑": ("refactor", frozenset({"Deprecated"}), "PATCH"),
    "🙈": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🚀": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🚑": ("fix", frozenset({"Fixed"}), "PATCH"),
    "🚚": ("refactor", frozenset({"Changed"}), "NONE"),
    "🚧": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🚨": ("refactor", frozenset({"Changed"}), "PATCH"),
    "🚩": ("feat", frozenset({"Added"}), "MINOR"),
    "🚸": ("feat", frozenset({"Changed"}), "PATCH"),
    "🛂": ("feat", frozenset({"Security"}), "MINOR"),
    "🤡": ("test", frozenset({"Miscellaneous"}), "NONE"),
    "🥅": ("fix", frozenset({"Fixed"}), "PATCH"),
    "🥚": ("feat", frozenset({"Added"}), "PATCH"),
    "🦖": ("fix", frozenset({"Changed"}), "PATCH"),
    "🦺": ("fix", frozenset({"Changed"}), "PATCH"),
    "🧐": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🧑\u200d💻": ("chore", frozenset({"Miscellaneous"}), "NONE"),
    "🧪": ("test", frozenset({"Miscellaneous"}), "NONE"),
    "🧱": ("ci", frozenset({"Changed"}), "PATCH"),
    "🧵": ("refactor", frozenset({"Changed"}), "MINOR"),
    "🩹": ("fix", frozenset({"Fixed"}), "PATCH"),
    "🩺": ("feat", frozenset({"Added"}), "PATCH"),
}

# SemVer rank for multi-intent max() checks (NONE < PATCH < MINOR < MAJOR).
_SEMVER_RANK: dict[str, int] = {"NONE": 0, "PATCH": 1, "MINOR": 2, "MAJOR": 3}

# Filename-like scope pattern (F4/F5 light): rejects scopes that look like paths or files.
_FILENAME_SCOPE_RE = re.compile(r"[/\\]|\.[A-Za-z0-9]+$")

# Finding codes that fail generation in ``strict`` mode. Single pass/fail source;
# orchestration never re-derives severity from anything else.
STRICT_FAIL_CODES: frozenset[str] = frozenset(
    {
        "GOLD_BODY_INVENTORY",
        "GOLD_INCLUDED_CHANGES_MISSING",
        "GOLD_GROUP_PRIMARY_MISMATCH",
        "GOLD_TYPE_GROUP_INCOHERENT",
        "GOLD_SEMVER_MATRIX_MISMATCH",
        "GOLD_SCOPE_FILENAME",
        "GOLD_SUBJECT_TITLE_CASE",
        "GOLD_SUBJECT_INVENTORY",
        # P-S12 gold-strict truth fails (fallback / process-meta / path-class ceilings).
        "GOLD_SKELETON_FALLBACK_FINAL",
        "GOLD_PROCESS_META_BODY",
        "GOLD_PATH_CLASS_SEMVER_CEILING",
        "GOLD_PATH_CLASS_TYPE_MISMATCH",
        "GOLD_FIXTURE_PRODUCT_FRAMING",
        "GOLD_DOCS_IMPLEMENTATION_CLAIM",
    }
)

# Process-meta phrases that must never appear in a final accepted body (P-S12-1/2).
_PROCESS_META_PHRASES: tuple[str, ...] = (
    "deterministic presentation fallback",
    "guard exhaustion",
    "cleared guard codes",
    "wording constrained to staged paths",
    "path-class priors",
    "presentation fallback after",
    "shared regen budget",
    "skeleton fallback",
)

# Provenance marker written into rationale by apply_guard_skeleton_fallback.
SKELETON_FALLBACK_MARKER = "[presentation-skeleton-fallback]"

# Closed imperative-verb allowlist for GOLD_SUBJECT_INVENTORY (Issue #191).
# Matching is case-insensitive on the first alphabetic token of a clause.
# Amend the issue + this constant together — do not invent fuzzy verbs at runtime.
SUBJECT_INVENTORY_VERBS: frozenset[str] = frozenset(
    {
        "add",
        "adds",
        "added",
        "update",
        "updates",
        "updated",
        "fix",
        "fixes",
        "fixed",
        "remove",
        "removes",
        "removed",
        "delete",
        "deletes",
        "deleted",
        "implement",
        "implements",
        "implemented",
        "introduce",
        "introduces",
        "introduced",
        "ensure",
        "ensures",
        "ensured",
        "create",
        "creates",
        "created",
        "refactor",
        "refactors",
        "refactored",
        "document",
        "documents",
        "documented",
        "test",
        "tests",
        "tested",
        "wire",
        "wires",
        "wired",
        "align",
        "aligns",
        "aligned",
        "enforce",
        "enforces",
        "enforced",
        "harden",
        "hardens",
        "hardened",
        "migrate",
        "migrates",
        "migrated",
        "rename",
        "renames",
        "renamed",
        "replace",
        "replaces",
        "replaced",
        "support",
        "supports",
        "supported",
        "improve",
        "improves",
        "improved",
        "optimize",
        "optimizes",
        "optimized",
        "optimise",
        "optimises",
        "optimised",
        "clean",
        "cleans",
        "cleaned",
        "drop",
        "drops",
        "dropped",
        "handle",
        "handles",
        "handled",
        "validate",
        "validates",
        "validated",
        "parse",
        "parses",
        "parsed",
        "render",
        "renders",
        "rendered",
        "sync",
        "syncs",
        "synced",
        "port",
        "ports",
        "ported",
    }
)

_SUBJECT_CLAUSE_LEAD_RE = re.compile(r"^(?:and|or)\s+", re.IGNORECASE)
_SUBJECT_ALPHA_TOKEN_RE = re.compile(r"[A-Za-z]+")
_SUBJECT_AND_SPLIT_RE = re.compile(r"\s+and\s+", re.IGNORECASE)

_GOLD_MODE_ENV = "GIT_CG_GOLD_MODE"
_GOLD_MODES: frozenset[str] = frozenset({"off", "warn", "strict"})


@dataclass(frozen=True)
class GoldFinding:
    """A single informational gold-lint finding (severity mapped by mode)."""

    code: str
    message: str
    severity: str = "info"  # always informational at emission; mode decides pass/fail
    # Structured P6 signal (≥3 coverage groups prefer split). Telemetry must read this
    # field — never substring-match ``message`` prose across the main.py boundary.
    split_preferred: bool = False


@dataclass(frozen=True)
class GoldReport:
    """Immutable result of ``check_commit_gold`` — findings only, no mutation."""

    findings: tuple[GoldFinding, ...] = field(default_factory=tuple)

    def codes(self) -> frozenset[str]:
        """Return the set of finding codes present in this report."""
        return frozenset(finding.code for finding in self.findings)

    def has_split_recommendation(self) -> bool:
        """True when any finding carries the structured P6 split-prefer signal."""
        return any(finding.split_preferred for finding in self.findings)

    def ok_for_mode(self, mode: str) -> bool:
        """Map findings to a pass/fail decision for a resolved gold mode.

        Normative behaviour (locked):
            * ``off``: always passes (findings suppressed by orchestration).
            * ``warn`` / ``surface``: always passes; findings are still emitted.
            * ``strict``: passes iff no finding code is in ``STRICT_FAIL_CODES``.

        ``GOLD_CONTRACT_SMOKE`` is an assert/smoke class that may hard-fail
        independently of mode; it is not ordinary product ranking policy and is
        excluded from the ``STRICT_FAIL_CODES`` pass/fail source.

        Parameters:
            mode (str): Resolved gold mode (``off``/``warn``/``surface``/``strict``).

        Returns:
            bool: ``True`` when generation may proceed under ``mode``.
        """
        if mode in ("off", "warn", "surface"):
            return True
        if mode == "strict":
            return not (self.codes() & STRICT_FAIL_CODES)
        return True


def resolve_gold_mode(
    *,
    strict: bool = False,
    gold_strict: bool = False,
    interactive: bool = False,
    tty_available: bool = False,
    environ: dict[str, str] | None = None,
) -> str:
    """Resolve the gold lint mode from environment and invocation context.

    Precedence (locked — no hook-argv sniffing; ``surface`` is interactive-derived
    only and is never an accepted env value):
        1. ``GIT_CG_GOLD_MODE`` ∈ {``off``, ``warn``, ``strict``}
        2. ``strict=True`` or ``gold_strict=True`` → ``strict``
        3. interactive TTY review path (``interactive`` and usable TTY) → ``surface``
        4. default → ``warn``

    Parameters:
        strict (bool): CLI/hook strict flag (``--strict``).
        gold_strict (bool): Gold-specific strict flag (``--gold-strict``); equivalent
            to ``strict`` for mode resolution but does not affect non-gold strictness.
        interactive (bool): Interactive review requested (``-i``).
        tty_available (bool): Whether a usable TTY is present (``can_open_tty()``).
        environ (dict[str, str] | None): Environment mapping; defaults to ``os.environ``.

    Returns:
        str: The resolved gold mode.
    """
    env = os.environ if environ is None else environ
    raw = env.get(_GOLD_MODE_ENV, "").strip().lower()
    if raw in _GOLD_MODES:
        return raw
    if strict or gold_strict:
        return "strict"
    if interactive and tty_available:
        return "surface"
    return "warn"


def _body_first_line(body: str | None) -> str:
    """Return the first line of a stripped commit body, or an empty string."""
    if not body:
        return ""
    return body.strip().splitlines()[0].strip() if body.strip() else ""


def _check_body_inventory(plan: CommitPlan) -> list[GoldFinding]:
    """Emit ``GOLD_BODY_INVENTORY`` when the body opens with a banned phrase."""
    first = _body_first_line(plan.body_summary)
    for opener in BANNED_BODY_OPENERS:
        if first.startswith(opener):
            return [
                GoldFinding(
                    code="GOLD_BODY_INVENTORY",
                    message=(
                        f"Body opens with inventory phrasing {opener!r}; lead with the "
                        "user-visible outcome and the why/behaviour delta instead."
                    ),
                )
            ]
    return []


def _first_alpha_token(text: str) -> str:
    """Return the first alphabetic token lowercased, or ``""`` if none."""
    match = _SUBJECT_ALPHA_TOKEN_RE.search(text)
    return match.group(0).lower() if match else ""


def _clause_is_verb_initial(clause: str) -> bool:
    """True when the clause's first alphabetic token is in the closed verb allowlist.

    Leading coordinating ``and``/``or`` (Oxford-comma tails) are stripped before the
    verb check so ``add X, update Y, and fix Z`` still counts three verb-initial clauses.
    """
    cleaned = _SUBJECT_CLAUSE_LEAD_RE.sub("", clause.strip())
    token = _first_alpha_token(cleaned)
    return bool(token) and token in SUBJECT_INVENTORY_VERBS


def _subject_inventory_pattern_a(description: str) -> bool:
    """PATTERN A: ≥3 comma-separated clauses with ≥3 verb-initial allowlist hits."""
    parts = [part.strip() for part in description.split(",") if part.strip()]
    if len(parts) < 3:
        return False
    return sum(1 for part in parts if _clause_is_verb_initial(part)) >= 3


def _subject_inventory_pattern_b(description: str) -> bool:
    """PATTERN B: ≥2 bare coordinating ``and`` connectors joining verb-initial clauses.

    Example hit: ``add X and update Y and fix Z`` (two ``and``s, three verb clauses).
    A single ``and`` (``add X and update Y``) does not fire.
    """
    parts = [part.strip(" ,") for part in _SUBJECT_AND_SPLIT_RE.split(description) if part.strip(" ,")]
    if len(parts) < 3:
        return False
    # Require every coordinated clause to be verb-initial under the allowlist.
    return all(_clause_is_verb_initial(part) for part in parts)


def _check_subject_inventory(plan: CommitPlan) -> list[GoldFinding]:
    """Emit ``GOLD_SUBJECT_INVENTORY`` for multi-action primary descriptions (Issue #191).

    Match target is ``plan.primary_intent.description`` only — never emoji, cc_type,
    scope, or the rendered subject line. Exactly two deterministic patterns over the
    closed ``SUBJECT_INVENTORY_VERBS`` allowlist (no NLP / embeddings).
    """
    description = str(plan.primary_intent.description or "").strip()
    if not description:
        return []
    if not (_subject_inventory_pattern_a(description) or _subject_inventory_pattern_b(description)):
        return []
    return [
        GoldFinding(
            code="GOLD_SUBJECT_INVENTORY",
            message=(
                f"Primary subject description looks like an action inventory ({description!r}); "
                "lead with the outcome, not the action list."
            ),
        )
    ]


def _file_groups(path: str) -> frozenset[str]:
    """Return every coverage group a single path classifies into (may be >1).

    A file can legitimately carry more than one role (e.g. ``CHANGELOG.md`` is both
    ``docs`` and ``release``; ``pyproject.toml`` is ``config_ci``/``build`` and
    ``release``). Callers that count *distinct surfaces* must therefore count files,
    not roles — see ``_distinct_surface_count``.
    """
    groups: set[str] = set()
    if _is_test_path(path):
        groups.add("tests")
    if _is_docs_path(path):
        groups.add("docs")
    if _is_ci_path(path) or _is_config_path(path) or _is_hook_path(path) or _is_build_path(path):
        groups.add("config_ci")
    if _is_release_path(path):
        groups.add("release")
    return frozenset(groups)


def _distinct_surface_count(signals: DiffSignals) -> int:
    """Count the number of *distinct* change surfaces present in the diff.

    Each touched file contributes exactly one surface, no matter how many coverage
    roles it carries, so a lone ``CHANGELOG.md`` (docs+release) or ``pyproject.toml``
    (config_ci+release) cannot by itself look like a multi-surface change. A strong
    product-surface signal (``adds_public_api``) widens the *group* set but never
    creates an additional surface on its own; an ungrouped file list is a single
    product surface.

    Parameters:
        signals (DiffSignals): Deterministic diff signals including ``files``.

    Returns:
        int: The number of distinct surfaces (>= 2 means genuinely multi-surface).
    """
    # Distinct surfaces are counted by *touched files* only. A strong product signal
    # (adds_public_api) widens _coverage_groups (product_src) but does not create an
    # extra surface on its own — a lone CHANGELOG.md or pyproject.toml is one surface
    # even when the diff also adds public API.
    return len(signals.files or [])


def _coverage_groups(signals: DiffSignals) -> set[str]:
    """Derive active coverage groups from signal flags and real path helpers.

    Normative v1 path-group mapping (no fictional classifiers):

        * ``tests``: ``touches_tests`` or any ``_is_test_path``
        * ``docs``: ``touches_docs``/``only_docs`` or any ``_is_docs_path``
        * ``config_ci``: ``touches_ci``/``touches_config``/``touches_hooks``/
          ``touches_build`` or ``_is_ci_path``/``_is_config_path``/``_is_hook_path``/
          ``_is_build_path``
        * ``release``: ``touches_release`` or any ``_is_release_path``
        * ``product_src``: remaining non-grouped product/source paths, or strong
          product-surface evidence (``adds_public_api``) when path helpers under-specify.

    Parameters:
        signals (DiffSignals): Deterministic diff signals including ``files``.

    Returns:
        set[str]: Active coverage group names.
    """
    groups: set[str] = set()
    files = list(signals.files or [])

    if signals.touches_tests or any("tests" in _file_groups(path) for path in files):
        groups.add("tests")
    if signals.touches_docs or signals.only_docs or any("docs" in _file_groups(path) for path in files):
        groups.add("docs")
    if (
        signals.touches_ci
        or signals.touches_config
        or signals.touches_hooks
        or signals.touches_build
        or any("config_ci" in _file_groups(path) for path in files)
    ):
        groups.add("config_ci")
    if signals.touches_release or any("release" in _file_groups(path) for path in files):
        groups.add("release")

    grouped_files = {path for path in files if _file_groups(path)}
    remaining = [path for path in files if path not in grouped_files]
    if remaining or signals.adds_public_api:
        groups.add("product_src")

    return groups


def _check_included_changes(plan: CommitPlan, signals: DiffSignals, ranked_intents: list | None) -> list[GoldFinding]:
    """Emit ``GOLD_INCLUDED_CHANGES_MISSING`` for under-covered multi-surface diffs.

    Fires when >=2 coverage groups are active and a non-primary ranked intent remains
    competitive (score > 0 and (score >= primary*RATIO or score > ABS)), unless the plan
    already carries secondary intents or recommends a split (split alone passes).
    """
    if plan.secondary_intents or plan.split_recommended:
        return []
    if ranked_intents is None:
        return []  # F4: None skips coverage findings only

    groups = _coverage_groups(signals)
    if len(groups) < 2:
        return []
    # A single file that spans two coverage roles (e.g. CHANGELOG.md -> docs+release)
    # is not a multi-surface change; require genuinely distinct touched surfaces.
    if _distinct_surface_count(signals) < 2:
        return []

    if not ranked_intents:
        return []
    primary = ranked_intents[0]
    primary_score = float(getattr(primary, "score", 0.0) or 0.0)
    competitive = any(
        float(getattr(candidate, "score", 0.0) or 0.0) > 0.0
        and (
            float(getattr(candidate, "score", 0.0) or 0.0) >= primary_score * GOLD_SECONDARY_SCORE_RATIO
            or float(getattr(candidate, "score", 0.0) or 0.0) > GOLD_SECONDARY_SCORE_ABS
        )
        for candidate in ranked_intents[1:]
    )
    if not competitive:
        return []

    group_list = ", ".join(sorted(groups))
    n_groups = len(groups)
    # P6 (Issue #191): message-only branch — same finding code; ≥3 groups prefer split.
    if n_groups >= 3:
        message = (
            f"Diff spans {n_groups} coverage groups ({group_list}) with a competitive ranked "
            "secondary and no secondaries/split; recommend splitting this diff. Matrix-legal "
            "secondary intents (Included changes) remain acceptable if a single commit is retained."
        )
        split_preferred = True
    else:
        message = (
            f"Diff spans {n_groups} coverage groups ({group_list}) with a "
            "competitive ranked secondary, but the plan has no secondary intents and no split "
            "recommendation; include matrix-legal secondary intents (Included changes) or split."
        )
        split_preferred = False
    return [
        GoldFinding(
            code="GOLD_INCLUDED_CHANGES_MISSING",
            message=message,
            split_preferred=split_preferred,
        )
    ]


def _check_group_coherence(plan: CommitPlan) -> list[GoldFinding]:
    """Emit ``GOLD_GROUP_PRIMARY_MISMATCH`` / ``GOLD_TYPE_GROUP_INCOHERENT``.

    Operates on structured plan fields only (never re-parses rendered trailers):
        * ``GOLD_GROUP_PRIMARY_MISMATCH``: product feat/perf primary whose primary
          changelog group is a fix-explaining group (e.g. ``Fixed``) with no
          fix/error-handling secondary to explain it.
        * ``GOLD_TYPE_GROUP_INCOHERENT``: smoke for matrix-impossible combinations
          (e.g. docs primary in a ``Fixed`` group post-enforce).
    """
    findings: list[GoldFinding] = []
    primary = plan.primary_intent
    primary_type = primary.cc_type.value if hasattr(primary.cc_type, "value") else str(primary.cc_type)
    primary_group = str(primary.changelog_group or "")

    secondary_types = {
        sec.cc_type.value if hasattr(sec.cc_type, "value") else str(sec.cc_type) for sec in plan.secondary_intents
    }
    fix_secondary = bool(secondary_types & {"fix"}) or any(
        "error_handling" in (sec.intent_id or "") or "bug_fix" in (sec.intent_id or "")
        for sec in plan.secondary_intents
    )

    if primary_type in ("feat", "perf") and primary_group in _FIX_EXPLAINING_GROUPS and not fix_secondary:
        findings.append(
            GoldFinding(
                code="GOLD_GROUP_PRIMARY_MISMATCH",
                message=(
                    f"Primary {primary_type}/{primary_group} reads as a fix-shaped story for a product "
                    "surface with no explaining fix/error-handling secondary; re-check primary selection "
                    "or include the fix secondary that explains the Fixed group."
                ),
            )
        )

    if primary_type in ("docs", "chore") and primary_group in _FIX_EXPLAINING_GROUPS and not fix_secondary:
        findings.append(
            GoldFinding(
                code="GOLD_TYPE_GROUP_INCOHERENT",
                message=(
                    f"Primary {primary_type} with changelog group {primary_group} is matrix-incoherent "
                    "post-enforce (smoke); this combination should be unreachable."
                ),
            )
        )

    return findings


def _norm_gitmoji(emoji: str) -> str:
    """Normalise a gitmoji by stripping variation selectors (U+FE0F, U+FE0E).

    The SOP matrix encodes some emoji both with and without the variation selector
    (e.g. ``\u26a1`` and ``\u26a1\ufe0f``); normalising makes lookup selector-insensitive.
    """
    return emoji.replace("\ufe0f", "").replace("\ufe0e", "")


def _check_type_group_coherence(
    plan: CommitPlan,
    *,
    presentation_overlay_applied: bool = False,
) -> list[GoldFinding]:
    """Emit ``GOLD_TYPE_GROUP_INCOHERENT`` for F7 group-unreachable trailer sets.

    F7: every declared type (primary + secondaries) must be coherent with *every*
    declared ``Changelog-Groups`` entry under the SOP matrix. An unknown gitmoji is
    skipped (enforce owns vocabulary), never failed here. Per-gitmoji coherent
    groups come from the static normative mapping (assert-tested against the SOP).

    When ``presentation_overlay_applied`` is True (Issue #204), presentation may
    legally emit D19 groups such as ``Tests`` / ``Documentation`` that the static
    matrix row maps only to ``Miscellaneous``. In that mode, skip the gitmoji→group
    matrix reachability check and rely on presentation allowlist + identity smoke.
    """
    if presentation_overlay_applied:
        return []

    incoherent: list[str] = []
    for intent in (plan.primary_intent, *plan.secondary_intents):
        entry = GITMOJI_CC_GROUPS.get(_norm_gitmoji(intent.gitmoji))
        if entry is None:
            continue  # enforce owns vocabulary; unknown emoji is out of scope here
        cc_type, coherent_groups, _semver = entry
        group = str(intent.changelog_group or "")
        if group and group not in coherent_groups:
            incoherent.append(f"{intent.gitmoji} ({cc_type}) -> {group}")

    if not incoherent:
        return []
    return [
        GoldFinding(
            code="GOLD_TYPE_GROUP_INCOHERENT",
            message=(
                "Changelog-Groups unreachable from declared Change-Types per SOP matrix (F7): "
                + "; ".join(incoherent)
                + "; re-declare coherent groups/types (e.g. test/docs -> Miscellaneous)."
            ),
        )
    ]


def _intent_semver(intent) -> str:
    """Return the plan intent's SemVer as an uppercase string."""
    raw = intent.semver_impact.value if hasattr(intent.semver_impact, "value") else str(intent.semver_impact)
    return str(raw or "").strip().upper()


def _check_semver_matrix(
    plan: CommitPlan,
    *,
    presentation_overlay_applied: bool = False,
) -> list[GoldFinding]:
    """Emit ``GOLD_SEMVER_MATRIX_MISMATCH`` when an intent's SemVer disagrees with the SOP (F2).

    Each primary/secondary gitmoji has exactly one matrix ``semver_impact``. Gold never
    invents SemVer from type names or issue drama — it only checks the structured plan
    against the static matrix. Unknown gitmojis are skipped (enforce owns vocabulary).

    When ``presentation_overlay_applied`` is True (Issue #204), presentation may clamp
    rendered SemVer below the matrix row (e.g. ✨ MINOR → PATCH/NONE ceiling). Skip the
    exact matrix equality check in that mode; identity smoke still guards intent/gitmoji.
    """
    if presentation_overlay_applied:
        return []

    mismatches: list[str] = []
    for intent in (plan.primary_intent, *plan.secondary_intents):
        entry = GITMOJI_CC_GROUPS.get(_norm_gitmoji(intent.gitmoji))
        if entry is None:
            continue
        _cc, _groups, matrix_semver = entry
        plan_semver = _intent_semver(intent)
        if plan_semver and plan_semver != matrix_semver:
            mismatches.append(f"{intent.gitmoji} plan={plan_semver} matrix={matrix_semver}")

    if not mismatches:
        return []
    return [
        GoldFinding(
            code="GOLD_SEMVER_MATRIX_MISMATCH",
            message=(
                "SemVer-Impact disagrees with the SOP matrix for a declared gitmoji (F2): "
                + "; ".join(mismatches)
                + "; use the matrix-keyed impact (then max across primary+secondaries for the trailer)."
            ),
        )
    ]


def _check_scope_filename(plan: CommitPlan) -> list[GoldFinding]:
    """Emit ``GOLD_SCOPE_FILENAME`` when a scope looks like a path or filename (F4/F5 light).

    Scopes must be product areas (``commit``, ``tui``, ``cli``), never basenames
    (``usage.kdl``) or paths (``docs/usage``).
    """
    bad: list[str] = []
    for intent in (plan.primary_intent, *plan.secondary_intents):
        scope = (intent.scope or "").strip()
        if not scope:
            continue
        if _FILENAME_SCOPE_RE.search(scope):
            bad.append(scope)

    if not bad:
        return []
    return [
        GoldFinding(
            code="GOLD_SCOPE_FILENAME",
            message=(
                "Scope looks like a filename or path (F4/F5): "
                + ", ".join(repr(s) for s in bad)
                + "; use a product-area scope (module/area), not a basename or path."
            ),
        )
    ]


def _is_title_case_subject(description: str) -> bool:
    """Return True when a subject description is Title Case (F5 light).

    Heuristic: >=2 alphabetic words and every alphabetic word starts uppercase.
    Acronym-only tokens (e.g. ``F7``, ``API``) still count as uppercase-leading.
    """
    words = [w for w in description.strip().split() if any(ch.isalpha() for ch in w)]
    if len(words) < 2:
        return False
    return all(next(ch for ch in w if ch.isalpha()).isupper() for w in words)


def _check_subject_title_case(plan: CommitPlan) -> list[GoldFinding]:
    """Emit ``GOLD_SUBJECT_TITLE_CASE`` when the primary description is Title Case (F5)."""
    description = str(plan.primary_intent.description or "")
    if not _is_title_case_subject(description):
        return []
    return [
        GoldFinding(
            code="GOLD_SUBJECT_TITLE_CASE",
            message=(
                f"Primary subject description looks Title Case ({description!r}); "
                "use imperative lowercase (e.g. 'enforce F7 group reachability')."
            ),
        )
    ]


def _check_contract_smoke(
    plan: CommitPlan,
    contract: ResolvedCommitContract | None,
    *,
    presentation_overlay_applied: bool = False,
) -> list[GoldFinding]:
    """Emit ``GOLD_CONTRACT_SMOKE`` when primary fields disagree with the contract.

    This is a bug-class smoke (enforce should make it impossible); it may hard-fail
    independently of mode. Skipped entirely when ``contract`` is ``None`` (direct
    structured fixtures — F4).

    With ``presentation_overlay_applied=True`` (Issue #204), only identity fields
    (``intent_id``, ``gitmoji``) are smoke-checked. Presentation-owned ``cc_type``,
    ``semver_impact``, and ``changelog_group`` may legally diverge after overlay.
    """
    if contract is None:
        return []
    primary = plan.primary_intent
    primary_type = primary.cc_type.value if hasattr(primary.cc_type, "value") else str(primary.cc_type)
    mismatches = []
    if primary.intent_id != contract.primary_intent_id:
        mismatches.append(f"intent_id {primary.intent_id!r} != contract {contract.primary_intent_id!r}")
    if primary.gitmoji != contract.gitmoji:
        mismatches.append(f"gitmoji {primary.gitmoji!r} != contract {contract.gitmoji!r}")
    if not presentation_overlay_applied:
        if primary_type != contract.cc_type:
            mismatches.append(f"cc_type {primary_type!r} != contract {contract.cc_type!r}")
        primary_semver = (
            primary.semver_impact.value if hasattr(primary.semver_impact, "value") else str(primary.semver_impact)
        )
        if primary_semver != contract.semver_impact:
            mismatches.append(f"semver_impact {primary_semver!r} != contract {contract.semver_impact!r}")
        if str(primary.changelog_group) != str(contract.changelog_group):
            mismatches.append(f"changelog_group {primary.changelog_group!r} != contract {contract.changelog_group!r}")
    if not mismatches:
        return []
    return [
        GoldFinding(
            code="GOLD_CONTRACT_SMOKE",
            message="Primary fields diverged from the enforced contract (bug): " + "; ".join(mismatches),
        )
    ]


def _message_blob(plan: CommitPlan, *, include_rationale: bool = True) -> str:
    """Lowercased subject+body blob for phrase matching.

    ``rationale`` is internal provenance and is not rendered by ``CommitPlan.render()``.
    Callers that inspect operator-visible wording should pass
    ``include_rationale=False`` so non-rendered process-meta notes cannot trip
    body/subject guards.
    """
    primary = plan.primary_intent
    parts = [
        str(getattr(primary, "description", "") or ""),
        str(getattr(plan, "body_summary", "") or ""),
    ]
    if include_rationale:
        parts.append(str(getattr(plan, "rationale", "") or ""))
    for sec in getattr(plan, "secondary_intents", None) or []:
        parts.append(str(getattr(sec, "description", "") or ""))
    return "\n".join(parts).lower()


def _is_fixture_path_gold(path: str) -> bool:
    parts = {part.lower() for part in str(path).replace("\\", "/").split("/") if part}
    return bool(parts & {"fixtures", "fixture", "goldens", "corpus"})


def _is_docs_path_gold(path: str) -> bool:
    lowered = str(path).replace("\\", "/").lower()
    name = lowered.rsplit("/", 1)[-1]
    return (
        lowered.startswith("docs/")
        or lowered.startswith("doc/")
        or name in {"readme.md", "changelog.md", "development.md"}
        or (name.endswith(".md") and ("/docs/" in f"/{lowered}" or "/adr" in f"/{lowered}"))
    )


def _is_test_path_gold(path: str) -> bool:
    lowered = str(path).replace("\\", "/").lower()
    parts = {p for p in lowered.split("/") if p}
    name = lowered.rsplit("/", 1)[-1]
    return (
        bool(parts & {"tests", "test", "spec", "__tests__"})
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.go")
        or _is_fixture_path_gold(path)
    )


def _path_family(signals: DiffSignals) -> str | None:
    """Return pure path family: fixtures|tests|docs|None (mixed/product)."""
    paths = [p for p in (signals.files or []) if p]
    if not paths:
        return None
    if all(_is_fixture_path_gold(p) for p in paths):
        return "fixtures"
    if all(_is_test_path_gold(p) for p in paths):
        return "tests"

    # docs-only when every path is docs-class / doc-like text and none are
    # non-md test modules, fixtures, or pure test .py files.
    docs_like = all(
        _is_docs_path_gold(p) or str(p).replace("\\", "/").lower().endswith((".md", ".rst", ".txt", ".adoc"))
        for p in paths
    )
    no_non_md_tests = not any(_is_test_path_gold(p) and not str(p).lower().endswith(".md") for p in paths)
    no_fixtures = not any(_is_fixture_path_gold(p) for p in paths)
    no_test_py = not any(str(p).endswith(".py") and _is_test_path_gold(p) for p in paths)
    if docs_like and no_non_md_tests and no_fixtures and no_test_py:
        return "docs"

    # broader docs: only docs paths via signals flags
    if getattr(signals, "only_docs", False):
        return "docs"
    if getattr(signals, "only_fixtures", False):
        return "fixtures"
    if getattr(signals, "only_tests", False):
        return "tests"
    return None


def _check_skeleton_and_process_meta(plan: CommitPlan) -> list[GoldFinding]:
    """Reject skeleton fallback provenance and process-meta body phrases (P-S12)."""
    findings: list[GoldFinding] = []
    rationale = str(getattr(plan, "rationale", "") or "")
    # Process-meta must inspect only rendered wording. Rationale is provenance-only
    # and is checked separately for skeleton markers.
    rendered_blob = _message_blob(plan, include_rationale=False)

    if SKELETON_FALLBACK_MARKER in rationale or getattr(plan, "_presentation_skeleton_fallback", False):
        findings.append(
            GoldFinding(
                code="GOLD_SKELETON_FALLBACK_FINAL",
                message=(
                    "Final plan is a presentation skeleton fallback; gold-strict "
                    "rejects fallback provenance as an accepted final message."
                ),
            )
        )

    hits = [phrase for phrase in _PROCESS_META_PHRASES if phrase in rendered_blob]
    if hits:
        findings.append(
            GoldFinding(
                code="GOLD_PROCESS_META_BODY",
                message=(
                    "Body/subject contains process-meta fallback phrasing "
                    f"({', '.join(hits[:4])}); final messages must describe staged outcomes only."
                ),
            )
        )
    return findings


def _check_path_class_truth(plan: CommitPlan, signals: DiffSignals) -> list[GoldFinding]:
    """Path-class SemVer ceilings and product-framing bans for pure docs/tests/fixtures."""
    findings: list[GoldFinding] = []
    family = _path_family(signals)
    if family is None:
        return findings

    primary = plan.primary_intent
    cc = getattr(primary.cc_type, "value", primary.cc_type)
    cc_s = str(cc or "").lower()
    sem = getattr(primary.semver_impact, "value", primary.semver_impact)
    sem_s = str(sem or "NONE").upper()
    # Path-class wording bans inspect operator-visible text only. Rationale is
    # provenance and must not trip GOLD_FIXTURE_PRODUCT_FRAMING /
    # GOLD_DOCS_IMPLEMENTATION_CLAIM (same contract as process-meta scans).
    blob = _message_blob(plan, include_rationale=False)

    if family in {"fixtures", "tests", "docs"} and sem_s in {"PATCH", "MINOR", "MAJOR"}:
        findings.append(
            GoldFinding(
                code="GOLD_PATH_CLASS_SEMVER_CEILING",
                message=(f"Pure {family} path-class forbids non-NONE SemVer ({sem_s}); presentation ceiling is NONE."),
            )
        )

    if family == "fixtures" and cc_s in {"feat", "fix"}:
        findings.append(
            GoldFinding(
                code="GOLD_PATH_CLASS_TYPE_MISMATCH",
                message=f"Fixtures-only path-class forbids primary type {cc_s!r}; expected test.",
            )
        )
    elif family == "tests" and cc_s in {"feat", "fix"}:
        findings.append(
            GoldFinding(
                code="GOLD_PATH_CLASS_TYPE_MISMATCH",
                message=f"Tests-only path-class forbids primary type {cc_s!r}; expected test.",
            )
        )
    elif family == "docs" and cc_s in {"feat", "fix"}:
        findings.append(
            GoldFinding(
                code="GOLD_PATH_CLASS_TYPE_MISMATCH",
                message=f"Docs-only path-class forbids primary type {cc_s!r}; expected docs.",
            )
        )

    if family == "fixtures":
        product_framing = (
            "validate",
            "enforce",
            "implement",
            "implementation",
            "runtime recovery",
            "wire telemetry",
            "public api",
        )
        hits = [tok for tok in product_framing if tok in blob]
        # Allow benign "test" framing; flag validate/enforce/implement product claims.
        if hits:
            findings.append(
                GoldFinding(
                    code="GOLD_FIXTURE_PRODUCT_FRAMING",
                    message=(
                        "Fixtures/proof-pack wording uses product validate/enforce/implementation "
                        f"framing ({', '.join(hits[:4])}); describe fixture evidence only."
                    ),
                )
            )

    if family == "docs":
        # Docs-only references to prior work must not claim to add/implement it.
        impl_claims = (
            "implement ",
            "implements ",
            "implemented ",
            "add support for",
            "adds support for",
            "introduce capability",
            "introduces capability",
            "wire the",
            "wires the",
            "enforce the contract",
            "enforces the contract",
        )
        hits = [tok for tok in impl_claims if tok in blob]
        # Path family already established docs-only; do not gate on cc_type so
        # docs-only chore/refactor/style claims are still rejected.
        if hits:
            findings.append(
                GoldFinding(
                    code="GOLD_DOCS_IMPLEMENTATION_CLAIM",
                    message=(
                        "Docs-only message claims to add/implement product behaviour "
                        f"({', '.join(hits[:3])}); document prior work without shipping claims."
                    ),
                )
            )

    return findings


def check_commit_gold(
    plan: CommitPlan,
    contract: ResolvedCommitContract | None,
    *,
    signals: DiffSignals,
    ranked_intents: list | None = None,
    path_summary: object | None = None,
    presentation_overlay_applied: bool = False,
) -> GoldReport:
    """Run the pure gold checks over a structured, post-enforce commit plan.

    Production call sites always pass ``contract`` + ``ranked_intents``. ``None``
    exists for direct structured B2 fixtures: ``contract=None`` skips only
    ``GOLD_CONTRACT_SMOKE``; ``ranked_intents=None`` skips only coverage findings.

    Parameters:
        plan (CommitPlan): Structured plan (post-enforce or a direct fixture).
        contract (ResolvedCommitContract | None): Enforced contract, or ``None`` to
            skip the contract smoke.
        signals (DiffSignals): Deterministic diff signals (path-group authority).
        ranked_intents (list | None): Ranked candidates for coverage scoring, or
            ``None`` to skip coverage findings.
        path_summary (object | None): Optional precomputed cache only — never
            treated as a second source of truth (O-P1.5).
        presentation_overlay_applied (bool): When True, Issue #204 presentation
            overlay has already adjusted rendered presentation fields. Gold keeps
            identity + wording checks, but skips matrix equality on presentation-
            owned SemVer/type/group fields. Default False preserves legacy strict
            behaviour for direct callers/tests.

    Returns:
        GoldReport: Immutable findings; the plan/contract are never mutated.
    """
    del path_summary  # optional cache only; coverage authority is signals.files + helpers

    findings: list[GoldFinding] = []
    findings.extend(_check_body_inventory(plan))
    findings.extend(_check_subject_inventory(plan))
    findings.extend(_check_group_coherence(plan))
    findings.extend(_check_type_group_coherence(plan, presentation_overlay_applied=presentation_overlay_applied))
    findings.extend(_check_semver_matrix(plan, presentation_overlay_applied=presentation_overlay_applied))
    findings.extend(_check_scope_filename(plan))
    findings.extend(_check_subject_title_case(plan))
    findings.extend(_check_included_changes(plan, signals, ranked_intents))
    findings.extend(
        _check_contract_smoke(
            plan,
            contract,
            presentation_overlay_applied=presentation_overlay_applied,
        )
    )
    # P-S12 truth fails: skeleton provenance, process-meta, path-class ceilings.
    findings.extend(_check_skeleton_and_process_meta(plan))
    findings.extend(_check_path_class_truth(plan, signals))
    return GoldReport(findings=tuple(findings))
