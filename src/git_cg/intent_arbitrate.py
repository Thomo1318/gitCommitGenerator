"""Pre-LLM interactive intent arbitration stack (Issue #195).

Orchestrates MAIN → LOCK / CANDIDATES / GUIDANCE / SPECIFY / CANCEL_MENU with
one-level Back navigation. Returns a typed ``ArbitrationResult`` only — never
mutates generation globals implicitly.

Frame IDs (canonical body law):
  MAIN, LOCK_A, LOCK_B, CANDIDATES, LOCK_N, GUIDANCE, REGEN,
  SPECIFY, FUZZY, BROWSE, LOCK_M, CANCEL_MENU, GENERATING, ABORT
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from git_cg.intent import IntentSelectionConstraints, RankedIntent, matrix_row_intent_id
from git_cg.interaction import (
    GumOutcome,
    can_open_tty,
    emit_terminal_bell,
    format_regeneration_guidance_status,
    gum_choose,
    gum_filter,
    gum_filter_available,
    gum_input,
)
from git_cg.ranking_confidence import LOW_CONFIDENCE_MARGIN, RankingConfidence
from git_cg.sop import get_gitmoji_matrix

# ---------------------------------------------------------------------------
# Closed path / action vocabularies
# ---------------------------------------------------------------------------

RankingChoicePath = Literal[
    "pick_a",
    "pick_b",
    "pick_candidate",
    "specify_fuzzy",
    "specify_browse",
    "cancel_continue_a",
    "cancel_abort",
    "ni_top_rank",
    "skipped_high_medium",
    "re_rank_auto_continue",
]

ArbitrationAction = Literal["locked", "re_rank", "aborted", "continue_top"]

GuidanceParseStatus = Literal["mapped", "no_op_unparseable", "cancelled"]

FrameId = Literal[
    "MAIN",
    "LOCK_A",
    "LOCK_B",
    "CANDIDATES",
    "LOCK_N",
    "GUIDANCE",
    "SPECIFY",
    "FUZZY",
    "BROWSE",
    "LOCK_M",
    "CANCEL_MENU",
]


@dataclass(frozen=True)
class ArbitrationResult:
    """Principal integration seam: intent_arbitrate → main generation loop."""

    action: ArbitrationAction
    locked_intent_id: str | None
    guidance: str | None
    re_rank_requested: bool
    choice_path: RankingChoicePath | None
    override: bool
    aborted: bool
    # Optional retained draft when guidance is no-op / cancelled mid-edit.
    retained_draft: str | None = None
    # Closed directives extracted from guidance when mapped (preferred_type/scope).
    active_directives: dict[str, str] = field(default_factory=dict)
    residual_guidance: str | None = None


@dataclass(frozen=True)
class GuidanceParseResult:
    """G1: guidance may only affect rank when mapped to existing deterministic inputs."""

    status: GuidanceParseStatus
    deterministic_inputs: dict[str, str]
    retained_draft: str
    is_noop: bool
    residual_guidance: str | None = None


@dataclass(frozen=True)
class EligibleIntent:
    """Constraint-eligible matrix-legal row offered in the TUI."""

    intent_id: str
    emoji: str
    cc_type: str
    description: str
    semver_impact: str
    changelog_group: str
    intent_group: str
    score: float | None  # None for specify-only matrix rows not in ranked list
    code: str = ""
    scope_hint: str = "core"

    def label_short(self) -> str:
        scope = self.scope_hint or "core"
        return f"{self.emoji} {self.cc_type}({scope}) — {self.intent_id}"

    def label_with_score(self) -> str:
        base = self.label_short()
        if self.score is None:
            return base
        return f"{base}  {self.score:.1f}"


# Injectable gum callables for tests (default to real interaction wrappers).
GumChooseFn = Callable[..., GumOutcome]
GumInputFn = Callable[..., GumOutcome]
GumFilterFn = Callable[..., GumOutcome]
FilterAvailableFn = Callable[..., bool]


@dataclass
class ArbitrationDeps:
    """Test seams for gum + capability probes."""

    choose: GumChooseFn = gum_choose
    input: GumInputFn = gum_input
    filter: GumFilterFn = gum_filter
    filter_available: FilterAvailableFn = gum_filter_available
    can_open_tty: Callable[[], bool] = can_open_tty
    emit_bell: Callable[[], None] = emit_terminal_bell


# ---------------------------------------------------------------------------
# Eligibility / catalogue helpers
# ---------------------------------------------------------------------------


def _allowed_id_set(constraints: IntentSelectionConstraints) -> set[str] | None:
    if not constraints.allowed_intent_ids:
        return None
    return set(constraints.allowed_intent_ids)


def filter_eligible_ranked(
    ranked: Sequence[RankedIntent],
    constraints: IntentSelectionConstraints,
    *,
    limit: int | None = None,
) -> list[EligibleIntent]:
    """Return ranked rows that are currently constraint-eligible (A_24)."""
    allowed = _allowed_id_set(constraints)
    out: list[EligibleIntent] = []
    for row in ranked:
        if allowed is not None and row.intent_id not in allowed:
            continue
        out.append(
            EligibleIntent(
                intent_id=row.intent_id,
                emoji=row.emoji,
                cc_type=row.cc_type,
                description=row.description,
                semver_impact=row.semver_impact,
                changelog_group=row.changelog_group,
                intent_group=row.intent_group,
                score=float(row.score),
                code=row.code,
            )
        )
        if limit is not None and len(out) >= limit:
            break
    return out


def filter_eligible_matrix_rows(
    matrix: Sequence[dict],
    constraints: IntentSelectionConstraints,
    ranked_by_id: dict[str, RankedIntent] | None = None,
) -> list[EligibleIntent]:
    """Return full-matrix rows that are currently constraint-eligible."""
    allowed = _allowed_id_set(constraints)
    ranked_by_id = ranked_by_id or {}
    out: list[EligibleIntent] = []
    for row in matrix:
        intent_id = matrix_row_intent_id(row)
        if allowed is not None and intent_id not in allowed:
            continue
        ranked = ranked_by_id.get(intent_id)
        out.append(
            EligibleIntent(
                intent_id=intent_id,
                emoji=str(row.get("emoji") or (ranked.emoji if ranked else "🔧")),
                cc_type=str(row.get("cc_type") or (ranked.cc_type if ranked else "chore")),
                description=str(row.get("description") or (ranked.description if ranked else intent_id)),
                semver_impact=str(row.get("semver_impact") or (ranked.semver_impact if ranked else "NONE")),
                changelog_group=str(
                    row.get("changelog_group") or (ranked.changelog_group if ranked else "Miscellaneous")
                ),
                intent_group=str(row.get("intent_group") or (ranked.intent_group if ranked else "miscellaneous")),
                score=float(ranked.score) if ranked is not None else None,
                code=str(row.get("code") or (ranked.code if ranked else "")),
            )
        )
    return out


def narrow_eligible_by_directives(
    eligible: Sequence[EligibleIntent],
    directives: dict[str, str] | None,
) -> tuple[list[EligibleIntent], str | None]:
    """
    Presentation-only narrowing for mapped guidance (preferred_type / preferred_scope).

    Does **not** mutate SOP scores. Returns (narrowed_or_original, status_note).
    If a directive is set but no rows match, returns the original list plus a note
    so the human can Specify rather than seeing a silent no-op.
    """
    directives = dict(directives or {})
    preferred_type = (directives.get("preferred_type") or "").strip().lower() or None
    preferred_scope = (directives.get("preferred_scope") or "").strip().lower() or None
    if not preferred_type and not preferred_scope:
        return list(eligible), None

    narrowed = list(eligible)
    notes: list[str] = []

    if preferred_type:
        typed = [row for row in narrowed if row.cc_type.lower() == preferred_type]
        if typed:
            narrowed = typed
            notes.append(f"preferred_type={preferred_type}")
        else:
            notes.append(f"preferred_type={preferred_type} (no ranked hits — showing full list)")

    if preferred_scope:
        scoped = [row for row in narrowed if (row.scope_hint or "core").lower() == preferred_scope]
        if scoped:
            narrowed = scoped
            notes.append(f"preferred_scope={preferred_scope}")
        else:
            # Scope is a weak signal on ranked rows (default core); do not empty the list.
            notes.append(f"preferred_scope={preferred_scope} (no ranked hits — type filter kept)")

    if not narrowed:
        return list(eligible), "guidance filter emptied list — showing full rank"

    # Short closed note for status composition (avoid "Re-ranked view:" —
    # the still-Low presentation_note already owns the REGEN narrative).
    note = "filtered: " + ", ".join(notes) if notes else None
    return narrowed, note


def ranked_intents_for_directives(
    ranked: Sequence[RankedIntent],
    directives: dict[str, str] | None,
) -> tuple[list[RankedIntent], str | None]:
    """Filter the authoritative ranked snapshot for guidance REGEN presentation."""
    directives = dict(directives or {})
    preferred_type = (directives.get("preferred_type") or "").strip().lower() or None
    if not preferred_type:
        return list(ranked), None
    filtered = [row for row in ranked if str(row.cc_type).lower() == preferred_type]
    if not filtered:
        return list(ranked), (f"preferred_type={preferred_type} (no ranked hits — full list retained)")
    return filtered, f"preferred_type={preferred_type}"


def parse_guidance_text(text: str) -> GuidanceParseResult:
    """
    Map free-text guidance onto existing deterministic directive inputs (G1).

    Reuses the same high-confidence heuristics as ``ReviewState._extract_directives``:
    preferred_type / preferred_scope only. Unparseable text is a declared no-op.
    """
    import re

    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return GuidanceParseResult(
            status="cancelled",
            deterministic_inputs={},
            retained_draft="",
            is_noop=True,
            residual_guidance=None,
        )

    directives: dict[str, str] = {}
    residual = normalized

    type_match = re.search(
        r"\b(?:this is a|make it a|use type|type is)\s+"
        r"(feat|feature|fix|docs|style|refactor|perf|test|build|ci|chore|revert|init|release)\b",
        residual,
        re.IGNORECASE,
    )
    if type_match:
        matched_type = type_match.group(1).lower()
        if matched_type == "feature":
            matched_type = "feat"
        directives["preferred_type"] = matched_type
        residual = residual[: type_match.start()] + residual[type_match.end() :]

    scope_match = re.search(r"\b(?:use scope)\s+([a-zA-Z0-9_-]+)\b", residual, re.IGNORECASE)
    if scope_match:
        directives["preferred_scope"] = scope_match.group(1).lower()
        residual = residual[: scope_match.start()] + residual[scope_match.end() :]

    residual = " ".join(residual.split()).strip()
    residual_or_none = residual if residual else None

    if directives:
        return GuidanceParseResult(
            status="mapped",
            deterministic_inputs=directives,
            retained_draft=normalized,
            is_noop=False,
            residual_guidance=residual_or_none,
        )

    return GuidanceParseResult(
        status="no_op_unparseable",
        deterministic_inputs={},
        retained_draft=normalized,
        is_noop=True,
        residual_guidance=normalized,
    )


def looks_like_commit_subject(text: str) -> bool:
    """True when draft looks like a Hybrid/Conventional subject, not directive guidance."""
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return False
    # Optional leading emoji, then conventional type, optional (scope), then ": <non-space>".
    pattern = (
        r"^(?:"
        r"[🌀-🫿☀-➿]" + r"\s*"
        r")?"
        r"(?:feat|feature|fix|docs|style|refactor|perf|test|build|ci|chore|revert|init|release)"
        r"(?:" + r"\([^)]*\)" + r")?" + r"\s*:\s*\S"
    )
    return bool(re.match(pattern, normalized, flags=re.IGNORECASE))


def subject_shaped_guidance_hint(text: str) -> str | None:
    """Copy shown when the human pasted a commit subject into guidance."""
    if not looks_like_commit_subject(text):
        return None
    return (
        "This looks like a commit subject, not directive guidance. "
        "Use Specify to lock intent, or enter e.g. `this is a feat` / `use scope intent`."
    )


def format_regen_still_low_note(
    *,
    preferred_type: str | None = None,
    preferred_scope: str | None = None,
    narrowed: bool = False,
) -> str:
    """Explicit MAIN banner after REGEN that remains Low (must not be silent)."""
    bits: list[str] = ["Re-ranked"]
    if preferred_type:
        bits.append(f"with preferred_type={preferred_type}")
    if preferred_scope:
        bits.append(f"preferred_scope={preferred_scope}")
    bits.append("· still Low")
    if narrowed:
        bits.append("· presentation filtered (SOP scores unchanged)")
    else:
        bits.append("· scores unchanged")
    return " ".join(bits)


def compose_arbitration_status_strip(
    *,
    presentation_note: str | None = None,
    guidance: str | None = None,
    directive_note: str | None = None,
    extra: Sequence[str] | None = None,
) -> str | None:
    """Build MAIN status strip without repeating preferred_type / re-rank facts.

    Priority / ownership:
    1. ``presentation_note`` — still-Low REGEN banner (authoritative after REGEN)
    2. guidance retained-draft status (once)
    3. ``directive_note`` — only if it adds facts not already in presentation_note
    4. optional extras (e.g. saved-without-re-rank)
    """
    parts: list[str] = []
    seen_norm: set[str] = set()

    def _norm(s: str) -> str:
        return " ".join(s.lower().split())

    def _add(piece: str | None) -> None:
        if not piece:
            return
        cleaned = " ".join(str(piece).split()).strip()
        if not cleaned:
            return
        key = _norm(cleaned)
        if key in seen_norm:
            return
        # Drop directive fragments already covered by an earlier banner.
        for prior in parts:
            prior_n = _norm(prior)
            if key in prior_n or prior_n in key:
                return
            # preferred_type=feat already stated → skip "filtered: preferred_type=feat"
            if "preferred_type=" in key and "preferred_type=" in prior_n:
                # extract values
                import re as _re

                vals_new = set(_re.findall(r"preferred_type=([a-z0-9_-]+)", key))
                vals_old = set(_re.findall(r"preferred_type=([a-z0-9_-]+)", prior_n))
                if vals_new and vals_new <= vals_old:
                    return
            if "preferred_scope=" in key and "preferred_scope=" in prior_n:
                import re as _re

                vals_new = set(_re.findall(r"preferred_scope=([a-z0-9_-]+)", key))
                vals_old = set(_re.findall(r"preferred_scope=([a-z0-9_-]+)", prior_n))
                if vals_new and vals_new <= vals_old:
                    return
        seen_norm.add(key)
        parts.append(cleaned)

    _add(presentation_note)
    if guidance:
        _add(format_regeneration_guidance_status(guidance))
    _add(directive_note)
    for item in extra or ():
        _add(item)
    return " · ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Panel / menu copy builders
# ---------------------------------------------------------------------------


def _fmt_score(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{score:.1f}"


def build_main_body(
    confidence: RankingConfidence,
    top: EligibleIntent | None,
    runner: EligibleIntent | None,
    *,
    guidance_status: str | None = None,
) -> str:
    # Prefer presentation A/B margin when both have scores; fall back to confidence margin.
    if top is not None and runner is not None and top.score is not None and runner.score is not None:
        shown_margin = float(top.score) - float(runner.score)
    else:
        shown_margin = float(confidence.margin)

    lines = [
        f"Top score margin is only +{shown_margin:.1f} (threshold {LOW_CONFIDENCE_MARGIN:.1f}).",
        "Confirm the primary contract before generation.",
        "",
    ]
    if top is not None:
        margin_note = f"  (+{shown_margin:.1f})" if runner is not None else ""
        lines.append(f"  A  {top.label_with_score()}{margin_note}")
    if runner is not None:
        lines.append(f"  B  {runner.label_with_score()}")
    if top is not None and runner is not None:
        lines.append("")
        lines.append(f"SemVer if A: {top.semver_impact} · if B: {runner.semver_impact}")
    if confidence.reasons:
        lines.append(f"Reasons: {', '.join(confidence.reasons)}")
    if guidance_status:
        lines.append("")
        lines.append(guidance_status)
    return "\n".join(lines)


def build_lock_body(
    candidate: EligibleIntent,
    *,
    option_label: str,
    confidence: RankingConfidence,
    top: EligibleIntent | None,
    override: bool,
    original_top: EligibleIntent | None = None,
) -> str:
    lines = [
        "Contract to lock (wording generated after this):",
        "",
        f"  {candidate.emoji} {candidate.cc_type}({candidate.scope_hint}): <subject — model fills>",
        f"  intent_id:     {candidate.intent_id}",
        f"  score:         {_fmt_score(candidate.score)}",
        f"  SemVer-Impact: {candidate.semver_impact}",
        f"  Changelog:     {candidate.changelog_group}",
        "",
    ]
    if (
        option_label == "A"
        and top is not None
        and top.score is not None
        and candidate.score is not None
        and candidate.intent_id == top.intent_id
    ):
        # Presentation margin only when locking current A against a scored B is unavailable here.
        lines.append(f"Authoritative rank margin: +{confidence.margin:.1f}")
    rank_top = original_top or top
    if override and rank_top is not None:
        lines.append(f"You are overriding the top rank (A: {rank_top.intent_id} {_fmt_score(rank_top.score)}).")
    return "\n".join(lines)


def _option_key(prefix: str, intent: EligibleIntent) -> str:
    """Stable menu label that embeds intent_id for reverse lookup."""
    return f"{prefix}{intent.label_with_score()}"


def _intent_id_from_option(choice: str, mapping: dict[str, str]) -> str | None:
    return mapping.get(choice)


# ---------------------------------------------------------------------------
# Stack runner
# ---------------------------------------------------------------------------


def _result_locked(
    intent_id: str,
    *,
    top_id: str,
    choice_path: RankingChoicePath,
    guidance: str | None,
    directives: dict[str, str] | None = None,
    residual: str | None = None,
) -> ArbitrationResult:
    return ArbitrationResult(
        action="locked",
        locked_intent_id=intent_id,
        guidance=guidance,
        re_rank_requested=False,
        choice_path=choice_path,
        override=(intent_id != top_id),
        aborted=False,
        active_directives=dict(directives or {}),
        residual_guidance=residual,
    )


def _result_continue_top(
    top_id: str,
    *,
    guidance: str | None,
    directives: dict[str, str] | None = None,
    residual: str | None = None,
) -> ArbitrationResult:
    return ArbitrationResult(
        action="continue_top",
        locked_intent_id=top_id,
        guidance=guidance,
        re_rank_requested=False,
        choice_path="cancel_continue_a",
        override=False,
        aborted=False,
        active_directives=dict(directives or {}),
        residual_guidance=residual,
    )


def _result_abort(*, guidance: str | None = None) -> ArbitrationResult:
    return ArbitrationResult(
        action="aborted",
        locked_intent_id=None,
        guidance=guidance,
        re_rank_requested=False,
        choice_path="cancel_abort",
        override=False,
        aborted=True,
    )


def _result_re_rank(
    *,
    guidance: str,
    directives: dict[str, str],
    residual: str | None,
) -> ArbitrationResult:
    return ArbitrationResult(
        action="re_rank",
        locked_intent_id=None,
        guidance=guidance,
        re_rank_requested=True,
        choice_path=None,  # terminal path assigned after REGEN by main
        override=False,
        aborted=False,
        retained_draft=guidance,
        active_directives=dict(directives),
        residual_guidance=residual,
    )


def run_intent_arbitration(
    *,
    ranked_intents: Sequence[RankedIntent],
    ranking_confidence: RankingConfidence,
    constraints: IntentSelectionConstraints,
    existing_guidance: str | None = None,
    existing_directives: dict[str, str] | None = None,
    existing_residual: str | None = None,
    presentation_note: str | None = None,
    deps: ArbitrationDeps | None = None,
) -> ArbitrationResult:
    """
    Run the nested pre-LLM arbitration stack.

    Preconditions:
      * Caller already gated Low + interactive + TTY + flag.
      * ``ranked_intents`` / ``ranking_confidence`` are the sole rank-pass pair.

    Returns:
      ArbitrationResult with terminal action. Does not write commit messages.
    """
    deps = deps or ArbitrationDeps()
    if not deps.can_open_tty():
        # Defensive: caller should have gated; fail closed without user abort label.
        top_id = ranking_confidence.top_intent_id
        return ArbitrationResult(
            action="continue_top",
            locked_intent_id=top_id,
            guidance=existing_guidance,
            re_rank_requested=False,
            choice_path="ni_top_rank",
            override=False,
            aborted=False,
            active_directives=dict(existing_directives or {}),
            residual_guidance=existing_residual,
        )

    directives = dict(existing_directives or {})
    guidance = existing_guidance
    residual = existing_residual

    eligible = filter_eligible_ranked(ranked_intents, constraints)
    # Mapped guidance narrows what A/B/See more present (presentation only; scores unchanged).
    eligible, directive_note = narrow_eligible_by_directives(eligible, directives)
    if not eligible:
        # Nothing legal to offer — continue with top of confidence object if present.
        return _result_continue_top(
            ranking_confidence.top_intent_id,
            guidance=existing_guidance,
            directives=existing_directives,
            residual=existing_residual,
        )

    # Presentation A/B after optional directive narrowing.
    # Override telemetry still compares against the *authoritative* ranker top.
    original_top_id = ranking_confidence.top_intent_id
    top = next((e for e in eligible if e.intent_id == original_top_id), eligible[0])
    runner = None
    if ranking_confidence.runner_up_intent_id:
        runner = next((e for e in eligible if e.intent_id == ranking_confidence.runner_up_intent_id), None)
    if runner is None and len(eligible) >= 2:
        runner = next((e for e in eligible if e.intent_id != top.intent_id), None)

    status_strip: str | None = compose_arbitration_status_strip(
        presentation_note=presentation_note,
        guidance=guidance,
        directive_note=directive_note,
    )
    # One-shot: after REGEN still-Low, ring bell so the banner cannot be missed.
    if presentation_note and "still Low" in presentation_note:
        with contextlib.suppress(Exception):
            deps.emit_bell()

    # Nested navigation state
    frame: FrameId = "MAIN"
    lock_target: EligibleIntent | None = None
    lock_path: RankingChoicePath | None = None
    lock_back: FrameId = "MAIN"
    specify_source: RankingChoicePath = "specify_browse"
    candidates = eligible[:5]

    ranked_by_id = {r.intent_id: r for r in ranked_intents}

    while True:
        if frame == "MAIN":
            body = build_main_body(ranking_confidence, top, runner, guidance_status=status_strip)
            options: list[str] = []
            opt_map: dict[str, str] = {}

            preferred_type = (directives.get("preferred_type") or "").strip().lower() or None
            # When guidance narrowed the list, offer a one-shot lock of the best matching row.
            lock_best_label = None
            if preferred_type and top is not None and top.cc_type.lower() == preferred_type:
                lock_best_label = f"Lock best ranked {preferred_type}: {top.label_with_score()}"
                options.append(lock_best_label)
                opt_map[lock_best_label] = "LOCK_BEST"

            use_a = f"Use A: {top.label_with_score()}"
            options.append(use_a)
            opt_map[use_a] = "USE_A"

            if runner is not None:
                use_b = f"Use B: {runner.label_with_score()}"
                options.append(use_b)
                opt_map[use_b] = "USE_B"

            if len(eligible) > 2:
                options.append("See more candidates…")
                opt_map["See more candidates…"] = "CANDIDATES"

            options.append("Add regeneration guidance…")
            opt_map["Add regeneration guidance…"] = "GUIDANCE"
            options.append("Specify from matrix…")
            opt_map["Specify from matrix…"] = "SPECIFY"
            options.append("Cancel")
            opt_map["Cancel"] = "CANCEL"

            outcome = deps.choose(
                options,
                title="Low confidence — pick primary intent",
                body=body,
                prompt_text="[bold cyan]Select action[/bold cyan]",
            )
            if outcome.status == "cancelled":
                frame = "CANCEL_MENU"
                continue
            if outcome.status in {"unavailable", "failed"}:
                # Infrastructure failure — not user abort (A_21).
                return ArbitrationResult(
                    action="continue_top",
                    locked_intent_id=top.intent_id,
                    guidance=guidance,
                    re_rank_requested=False,
                    choice_path="ni_top_rank",
                    override=False,
                    aborted=False,
                    active_directives=directives,
                    residual_guidance=residual,
                )
            action_key = opt_map.get(outcome.value or "")
            if (action_key == "LOCK_BEST" and top is not None) or action_key == "USE_A":
                lock_target = top
                lock_path = "pick_a"
                lock_back = "MAIN"
                frame = "LOCK_A"
            elif action_key == "USE_B" and runner is not None:
                lock_target = runner
                lock_path = "pick_b"
                lock_back = "MAIN"
                frame = "LOCK_B"
            elif action_key == "CANDIDATES":
                candidates = eligible[:5]
                frame = "CANDIDATES"
            elif action_key == "GUIDANCE":
                frame = "GUIDANCE"
            elif action_key == "SPECIFY":
                frame = "SPECIFY"
            elif action_key == "CANCEL":
                frame = "CANCEL_MENU"
            else:
                # Unknown selection — redisplay MAIN
                continue
            continue

        if frame in {"LOCK_A", "LOCK_B", "LOCK_N", "LOCK_M"}:
            assert lock_target is not None and lock_path is not None
            override = lock_target.intent_id != original_top_id
            option_label = {
                "LOCK_A": "A",
                "LOCK_B": "B",
                "LOCK_N": "N",
                "LOCK_M": "M",
            }[frame]
            # R5: plain lock U+1F512 only in headings — never pair with VS16 (U+FE0F).
            title = {
                "LOCK_A": "🔒 Lock primary intent — Option A",
                "LOCK_B": "🔒 Lock primary intent — Option B",
                "LOCK_N": "🔒 Lock primary intent — candidate",
                "LOCK_M": "🔒 Lock primary intent — matrix selection",
            }[frame]
            original_top_row = next(
                (e for e in filter_eligible_ranked(ranked_intents, constraints) if e.intent_id == original_top_id),
                None,
            )
            body = build_lock_body(
                lock_target,
                option_label=option_label,
                confidence=ranking_confidence,
                top=top,
                override=override,
                original_top=original_top_row,
            )
            lock_label = "Lock and generate message"
            back_label = "← Back"
            outcome = deps.choose(
                [lock_label, back_label],
                title=title,
                body=body,
                prompt_text="[bold cyan]Confirm lock[/bold cyan]",
            )
            if outcome.status == "cancelled" or (outcome.status == "selected" and outcome.value == back_label):
                frame = lock_back
                lock_target = None
                lock_path = None
                continue
            if outcome.status in {"unavailable", "failed"}:
                return ArbitrationResult(
                    action="continue_top",
                    locked_intent_id=top.intent_id,
                    guidance=guidance,
                    re_rank_requested=False,
                    choice_path="ni_top_rank",
                    override=False,
                    aborted=False,
                    active_directives=directives,
                    residual_guidance=residual,
                )
            if outcome.status == "selected" and outcome.value == lock_label:
                return _result_locked(
                    lock_target.intent_id,
                    # Override compares against authoritative ranker top, not presentation A.
                    top_id=original_top_id,
                    choice_path=lock_path,
                    guidance=guidance,
                    directives=directives,
                    residual=residual,
                )
            continue

        if frame == "CANDIDATES":
            candidates = eligible[:5]
            options = []
            opt_map = {}
            for idx, cand in enumerate(candidates, start=1):
                marker = ""
                if cand.intent_id == top.intent_id:
                    marker = "  ← current A"
                elif runner is not None and cand.intent_id == runner.intent_id:
                    marker = "  ← current B"
                label = f"{idx}. {cand.label_with_score()}{marker}"
                options.append(label)
                opt_map[label] = cand.intent_id
            options.append("← Back")
            opt_map["← Back"] = "__BACK__"

            outcome = deps.choose(
                options,
                title="Top candidates (5) — this diff only",
                body="Ranked intents for the current staged diff. Pick one to lock, or go back.",
                prompt_text="[bold cyan]Select candidate[/bold cyan]",
            )
            if outcome.status == "cancelled" or (
                outcome.status == "selected" and opt_map.get(outcome.value or "") == "__BACK__"
            ):
                frame = "MAIN"
                continue
            if outcome.status in {"unavailable", "failed"}:
                return ArbitrationResult(
                    action="continue_top",
                    locked_intent_id=top.intent_id,
                    guidance=guidance,
                    re_rank_requested=False,
                    choice_path="ni_top_rank",
                    override=False,
                    aborted=False,
                    active_directives=directives,
                    residual_guidance=residual,
                )
            intent_id = opt_map.get(outcome.value or "")
            if not intent_id or intent_id == "__BACK__":
                frame = "MAIN"
                continue
            lock_target = next(c for c in candidates if c.intent_id == intent_id)
            lock_path = "pick_candidate"
            lock_back = "CANDIDATES"
            frame = "LOCK_N"
            continue

        if frame == "GUIDANCE":
            body_lines = [
                "Optional notes for the next generation pass. Does not lock intent by itself.",
                f"Primary stays A ({top.intent_id}) unless you pick another path after saving.",
                "",
                "Directive examples (these can re-rank / narrow A·B):",
                "  • this is a feat",
                "  • make it a fix",
                "  • use scope tui",
                "",
                "Not directives: pasting a full subject like `feat(intent): add module`",
                "— use Specify to lock intent, or rewrite as the examples above.",
            ]
            if guidance:
                body_lines.extend(["", format_regeneration_guidance_status(guidance)])
            outcome = deps.input(
                title="Add regeneration guidance",
                body="\n".join(body_lines),
                prompt_text="[bold cyan]Enter guidance[/bold cyan]",
                placeholder="this is a feat",
                value=guidance or "",
            )
            if outcome.status == "cancelled":
                frame = "MAIN"
                continue
            if outcome.status in {"unavailable", "failed"}:
                frame = "MAIN"
                continue

            draft = " ".join((outcome.value or "").split()).strip()
            # After input, choose save mode. Regenerate is listed first (explicit re-rank path).
            save_rerank = "Regenerate ranking with this guidance (re-run ranker)"
            save_return = "Save guidance only (return to menu — no re-rank)"
            back = "← Back without saving"
            action_body_lines = [f"Draft: {draft or '(empty)'}"]
            subject_hint = subject_shaped_guidance_hint(draft) if draft else None
            if subject_hint:
                action_body_lines.extend(["", f"⚠ {subject_hint}"])
            mode = deps.choose(
                [save_rerank, save_return, back],
                title="Add regeneration guidance",
                body="\n".join(action_body_lines),
                prompt_text="[bold cyan]Guidance action[/bold cyan]",
            )
            if mode.status == "cancelled" or (mode.status == "selected" and mode.value == back):
                frame = "MAIN"
                continue
            if mode.status in {"unavailable", "failed"}:
                frame = "MAIN"
                continue
            if not draft:
                # Empty draft = clear guidance, stay on MAIN (no lock).
                guidance = None
                directives = {}
                residual = None
                status_strip = None
                frame = "MAIN"
                continue

            parsed = parse_guidance_text(draft)
            guidance = parsed.retained_draft
            status_strip = format_regeneration_guidance_status(guidance)

            if parsed.status == "mapped":
                directives = dict(parsed.deterministic_inputs)
                residual = parsed.residual_guidance
            else:
                # G1 no-op: keep draft, do not mutate rank inputs / directives.
                residual = parsed.residual_guidance
                directives = {}

            if mode.status == "selected" and mode.value == save_return:
                # Non-terminal — no choice_path. Refresh A/B presentation if mapped.
                extras: list[str] = []
                local_directive_note: str | None = None
                if parsed.status == "mapped":
                    base_eligible = filter_eligible_ranked(ranked_intents, constraints)
                    eligible, local_directive_note = narrow_eligible_by_directives(base_eligible, directives)
                    if eligible:
                        top = next(
                            (e for e in eligible if e.intent_id == original_top_id),
                            eligible[0],
                        )
                        runner = next(
                            (e for e in eligible if e.intent_id != top.intent_id),
                            None,
                        )
                        candidates = eligible[:5]
                    extras.append("saved without re-rank")
                else:
                    if subject_hint:
                        extras.append(subject_hint)
                    extras.append("saved without re-rank (unparseable — no rank change)")
                status_strip = compose_arbitration_status_strip(
                    guidance=guidance,
                    directive_note=local_directive_note,
                    extra=extras,
                )
                frame = "MAIN"
                continue

            if mode.status == "selected" and mode.value == save_rerank:
                if parsed.status != "mapped":
                    # G1: unparseable cannot re-rank — impossible to miss (bell + banner).
                    with contextlib.suppress(Exception):
                        deps.emit_bell()
                    noop_lines = [
                        "Re-rank no-op: guidance did not map to deterministic rank inputs.",
                        format_regeneration_guidance_status(guidance),
                    ]
                    if subject_hint:
                        noop_lines.append(subject_hint)
                    else:
                        noop_lines.append("Try: `this is a feat` / `make it a fix` / `use scope intent`.")
                    noop_lines.append("Draft retained — ranking unchanged.")
                    # Blocking acknowledge so the no-op cannot scroll past unnoticed.
                    ack = deps.choose(
                        ["OK — return to menu"],
                        title="Guidance re-rank no-op",
                        body="\n".join(noop_lines),
                        prompt_text="[bold yellow]Acknowledge[/bold yellow]",
                    )
                    status_strip = (
                        format_regeneration_guidance_status(guidance)
                        + " · [no-op re-rank: could not map to deterministic rank inputs]"
                    )
                    if subject_hint:
                        status_strip += " · subject-shaped draft"
                    _ = ack  # any outcome returns to MAIN
                    frame = "MAIN"
                    continue
                return _result_re_rank(
                    guidance=guidance or draft,
                    directives=directives,
                    residual=residual,
                )
            frame = "MAIN"
            continue

        if frame == "SPECIFY":
            fuzzy_ok = deps.filter_available()
            options = []
            opt_map = {}
            if fuzzy_ok:
                options.append("Fuzzy search matrix…")
                opt_map["Fuzzy search matrix…"] = "FUZZY"
            options.append("Browse matrix catalogue…")
            opt_map["Browse matrix catalogue…"] = "BROWSE"
            options.append("← Back")
            opt_map["← Back"] = "__BACK__"

            hub_note = (
                "Lock a matrix-legal primary from the full SOP vocabulary."
                if fuzzy_ok
                else "Fuzzy search unavailable — browse catalogue only (G4)."
            )
            outcome = deps.choose(
                options,
                title="Specify from matrix",
                body=hub_note,
                prompt_text="[bold cyan]Specify path[/bold cyan]",
            )
            if outcome.status == "cancelled" or (
                outcome.status == "selected" and opt_map.get(outcome.value or "") == "__BACK__"
            ):
                frame = "MAIN"
                continue
            if outcome.status in {"unavailable", "failed"}:
                frame = "MAIN"
                continue
            key = opt_map.get(outcome.value or "")
            if key == "FUZZY":
                frame = "FUZZY"
            elif key == "BROWSE":
                frame = "BROWSE"
            else:
                frame = "MAIN"
            continue

        if frame in {"FUZZY", "BROWSE"}:
            matrix = get_gitmoji_matrix()
            catalogue = filter_eligible_matrix_rows(matrix, constraints, ranked_by_id)
            if not catalogue:
                frame = "SPECIFY"
                continue

            labels = []
            label_to_intent: dict[str, EligibleIntent] = {}
            for item in catalogue:
                # Match tokens: intent_id, cc_type, emoji/code, description
                label = (
                    f"{item.emoji} {item.cc_type} — {item.intent_id}  "
                    f"[{item.semver_impact}/{item.changelog_group}]  {item.description}"
                )
                labels.append(label)
                label_to_intent[label] = item

            if frame == "FUZZY":
                if not deps.filter_available():
                    frame = "BROWSE"
                    continue
                outcome = deps.filter(
                    labels,
                    title="Fuzzy search matrix",
                    body="Type to filter SOP matrix rows. Selection must be a listed row.",
                    prompt_text="[bold cyan]Filter intents[/bold cyan]",
                    placeholder="intent_id, type, description…",
                )
                specify_source = "specify_fuzzy"
            else:
                outcome = deps.choose(
                    [*labels, "← Back"],
                    title="Browse matrix catalogue",
                    body="Constraint-eligible SOP rows only. Pick one or go back.",
                    prompt_text="[bold cyan]Browse intents[/bold cyan]",
                )
                specify_source = "specify_browse"

            if outcome.status == "cancelled":
                frame = "SPECIFY"
                continue
            if outcome.status in {"unavailable", "failed"}:
                # G4 / infra: fall back to specify hub, never crash.
                frame = "SPECIFY"
                continue
            value = outcome.value or ""
            if value == "← Back":
                frame = "SPECIFY"
                continue
            selected = label_to_intent.get(value)
            if selected is None:
                # Free-typed / non-list value — reject (A_05).
                frame = "SPECIFY"
                continue
            lock_target = selected
            lock_path = specify_source
            lock_back = "SPECIFY"  # A_09: LOCK_M Back → Specify hub
            frame = "LOCK_M"
            continue

        if frame == "CANCEL_MENU":
            cont = "Continue with top rank (A) non-interactively"
            abort = "Abort commit message generation"
            back = "← Back"
            outcome = deps.choose(
                [cont, abort, back],
                title="Cancel intent arbitration?",
                body="No new contract lock from this menu unless you continue with A.",
                prompt_text="[bold cyan]Cancel options[/bold cyan]",
            )
            if outcome.status == "cancelled" or (outcome.status == "selected" and outcome.value == back):
                frame = "MAIN"
                continue
            if outcome.status in {"unavailable", "failed"}:
                # Infra failure on cancel menu — fail closed without user abort label.
                return ArbitrationResult(
                    action="continue_top",
                    locked_intent_id=top.intent_id,
                    guidance=guidance,
                    re_rank_requested=False,
                    choice_path="ni_top_rank",
                    override=False,
                    aborted=False,
                    active_directives=directives,
                    residual_guidance=residual,
                )
            if outcome.status == "selected" and outcome.value == cont:
                return _result_continue_top(
                    top.intent_id,
                    guidance=guidance,
                    directives=directives,
                    residual=residual,
                )
            if outcome.status == "selected" and outcome.value == abort:
                return _result_abort(guidance=guidance)
            frame = "MAIN"
            continue

        # Unknown frame — fail closed to MAIN
        frame = "MAIN"
