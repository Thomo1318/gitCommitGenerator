"""Deterministic post-enforce commit-message gold linter (Issue #182 Phase 7.25).

Gold checks content quality of a structured ``CommitPlan`` *after*
``enforce_semantic_contract`` and the mixed-policy handle. The checker is pure:
no I/O, no model calls, no SOP mutation, and no mutation of the plan/contract.

Authority boundary (locked):
    * The matrix ranker remains the sole ranking / ``semver_impact`` authority.
    * Gold never emits ``preferred_type``/``preferred_scope`` steers and never
      rewrites ``intent_id``/``gitmoji``/``cc_type``/``semver_impact``/
      ``changelog_group``. It may only request *wording* / *secondary-coverage*
      regeneration via the dedicated ``gold_guidance`` channel.
"""

from __future__ import annotations

import os
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
)

# Coverage scoring constants (change only with B2 fixture updates).
GOLD_SECONDARY_SCORE_RATIO: float = 0.5
GOLD_SECONDARY_SCORE_ABS: float = 20.0

# Product-intent Conventional Commit types subject to group-coherence checks.
_PRODUCT_CC_TYPES: frozenset[str] = frozenset({"feat", "fix", "perf"})

# Groups that require an explanatory fix/error-handling intent when the primary
# is a product feat/perf.
_FIX_EXPLAINING_GROUPS: frozenset[str] = frozenset({"Fixed"})

# Normative gitmoji -> (cc_type, frozenset[coherent changelog groups]) for the closed
# gitmoji vocabulary (Issue #195 Phase 7.29 F7). Mirrors the SOP
# ``gitmoji_reference_matrix``; keys are normalised (variation selector U+FE0F stripped)
# because the matrix encodes some emoji with and without the selector. Assert-tested
# against the live SOP so it cannot drift.
GITMOJI_CC_GROUPS: dict[str, tuple[str, frozenset[str]]] = {
    "⏪": ("revert", frozenset({"Changed"})),
    "♻": ("refactor", frozenset({"Changed"})),
    "♿": ("feat", frozenset({"Changed"})),
    "⚗": ("feat", frozenset({"Changed"})),
    "⚡": ("perf", frozenset({"Changed"})),
    "⚰": ("refactor", frozenset({"Removed"})),
    "✅": ("test", frozenset({"Miscellaneous"})),
    "✈": ("feat", frozenset({"Added"})),
    "✏": ("docs", frozenset({"Miscellaneous"})),
    "✨": ("feat", frozenset({"Added"})),
    "\u2795": ("build", frozenset({"Changed"})),
    "\u2796": ("build", frozenset({"Changed"})),
    "⬆": ("build", frozenset({"Changed"})),
    "⬇": ("build", frozenset({"Changed"})),
    "🌐": ("feat", frozenset({"Added"})),
    "🌱": ("chore", frozenset({"Miscellaneous"})),
    "🍱": ("chore", frozenset({"Added"})),
    "🍻": ("refactor", frozenset({"Miscellaneous"})),
    "🎉": ("init", frozenset({"Miscellaneous"})),
    "🎨": ("style", frozenset({"Changed"})),
    "🏗": ("refactor", frozenset({"Changed"})),
    "🏷": ("refactor", frozenset({"Changed"})),
    "🐛": ("fix", frozenset({"Fixed"})),
    "👔": ("feat", frozenset({"Added"})),
    "👥": ("chore", frozenset({"Miscellaneous"})),
    "👷": ("ci", frozenset({"Miscellaneous"})),
    "👽": ("refactor", frozenset({"Changed"})),
    "💄": ("style", frozenset({"Changed"})),
    "💚": ("ci", frozenset({"Miscellaneous"})),
    "💡": ("docs", frozenset({"Miscellaneous"})),
    "💥": ("feat", frozenset({"Changed"})),
    "💩": ("refactor", frozenset({"Miscellaneous"})),
    "💫": ("feat", frozenset({"Changed"})),
    "💬": ("style", frozenset({"Changed"})),
    "💸": ("feat", frozenset({"Added"})),
    "📄": ("docs", frozenset({"Miscellaneous"})),
    "📈": ("feat", frozenset({"Added"})),
    "📌": ("build", frozenset({"Changed"})),
    "📝": ("docs", frozenset({"Miscellaneous"})),
    "📦": ("build", frozenset({"Changed"})),
    "📱": ("feat", frozenset({"Changed"})),
    "📸": ("test", frozenset({"Miscellaneous"})),
    "🔀": ("chore", frozenset({"Miscellaneous"})),
    "🔇": ("chore", frozenset({"Miscellaneous"})),
    "🔊": ("chore", frozenset({"Miscellaneous"})),
    "🔍": ("feat", frozenset({"Changed"})),
    "🔐": ("chore", frozenset({"Security"})),
    "🔒": ("fix", frozenset({"Security"})),
    "🔖": ("release", frozenset({"Miscellaneous"})),
    "🔥": ("refactor", frozenset({"Removed"})),
    "🔧": ("chore", frozenset({"Miscellaneous"})),
    "🔨": ("chore", frozenset({"Miscellaneous"})),
    "🗃": ("feat", frozenset({"Changed"})),
    "🗑": ("refactor", frozenset({"Deprecated"})),
    "🙈": ("chore", frozenset({"Miscellaneous"})),
    "🚀": ("chore", frozenset({"Miscellaneous"})),
    "🚑": ("fix", frozenset({"Fixed"})),
    "🚚": ("refactor", frozenset({"Changed"})),
    "🚧": ("chore", frozenset({"Miscellaneous"})),
    "🚨": ("refactor", frozenset({"Changed"})),
    "🚩": ("feat", frozenset({"Added"})),
    "🚸": ("feat", frozenset({"Changed"})),
    "🛂": ("feat", frozenset({"Security"})),
    "🤡": ("test", frozenset({"Miscellaneous"})),
    "🥅": ("fix", frozenset({"Fixed"})),
    "🥚": ("feat", frozenset({"Added"})),
    "🦖": ("fix", frozenset({"Changed"})),
    "🦺": ("fix", frozenset({"Changed"})),
    "🧐": ("chore", frozenset({"Miscellaneous"})),
    "🧑\u200d💻": ("chore", frozenset({"Miscellaneous"})),
    "🧪": ("test", frozenset({"Miscellaneous"})),
    "🧱": ("ci", frozenset({"Changed"})),
    "🧵": ("refactor", frozenset({"Changed"})),
    "🩹": ("fix", frozenset({"Fixed"})),
    "🩺": ("feat", frozenset({"Added"})),
}


# Finding codes that fail generation in ``strict`` mode. Single pass/fail source;
# orchestration never re-derives severity from anything else.
STRICT_FAIL_CODES: frozenset[str] = frozenset(
    {
        "GOLD_BODY_INVENTORY",
        "GOLD_INCLUDED_CHANGES_MISSING",
        "GOLD_GROUP_PRIMARY_MISMATCH",
        "GOLD_TYPE_GROUP_INCOHERENT",
    }
)

_GOLD_MODE_ENV = "GIT_CG_GOLD_MODE"
_GOLD_MODES: frozenset[str] = frozenset({"off", "warn", "strict"})


@dataclass(frozen=True)
class GoldFinding:
    """A single informational gold-lint finding (severity mapped by mode)."""

    code: str
    message: str
    severity: str = "info"  # always informational at emission; mode decides pass/fail


@dataclass(frozen=True)
class GoldReport:
    """Immutable result of ``check_commit_gold`` — findings only, no mutation."""

    findings: tuple[GoldFinding, ...] = field(default_factory=tuple)

    def codes(self) -> frozenset[str]:
        """Return the set of finding codes present in this report."""
        return frozenset(finding.code for finding in self.findings)

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

    return [
        GoldFinding(
            code="GOLD_INCLUDED_CHANGES_MISSING",
            message=(
                f"Diff spans {len(groups)} coverage groups ({', '.join(sorted(groups))}) with a "
                "competitive ranked secondary, but the plan has no secondary intents and no split "
                "recommendation; include matrix-legal secondary intents (Included changes) or split."
            ),
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


def _check_type_group_coherence(plan: CommitPlan) -> list[GoldFinding]:
    """Emit ``GOLD_TYPE_GROUP_INCOHERENT`` for F7 group-unreachable trailer sets.

    F7: every declared type (primary + secondaries) must be coherent with *every*
    declared ``Changelog-Groups`` entry under the SOP matrix. An unknown gitmoji is
    skipped (enforce owns vocabulary), never failed here. Per-gitmoji coherent
    groups come from the static normative mapping (assert-tested against the SOP).
    """
    incoherent: list[str] = []
    for intent in (plan.primary_intent, *plan.secondary_intents):
        entry = GITMOJI_CC_GROUPS.get(_norm_gitmoji(intent.gitmoji))
        if entry is None:
            continue  # enforce owns vocabulary; unknown emoji is out of scope here
        cc_type, coherent_groups = entry
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


def _check_contract_smoke(plan: CommitPlan, contract: ResolvedCommitContract | None) -> list[GoldFinding]:
    """Emit ``GOLD_CONTRACT_SMOKE`` when primary fields disagree with the contract.

    This is a bug-class smoke (enforce should make it impossible); it may hard-fail
    independently of mode. Skipped entirely when ``contract`` is ``None`` (direct
    structured fixtures — F4).
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


def check_commit_gold(
    plan: CommitPlan,
    contract: ResolvedCommitContract | None,
    *,
    signals: DiffSignals,
    ranked_intents: list | None = None,
    path_summary: object | None = None,
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

    Returns:
        GoldReport: Immutable findings; the plan/contract are never mutated.
    """
    del path_summary  # optional cache only; coverage authority is signals.files + helpers

    findings: list[GoldFinding] = []
    findings.extend(_check_body_inventory(plan))
    findings.extend(_check_group_coherence(plan))
    findings.extend(_check_type_group_coherence(plan))
    findings.extend(_check_included_changes(plan, signals, ranked_intents))
    findings.extend(_check_contract_smoke(plan, contract))
    return GoldReport(findings=tuple(findings))
