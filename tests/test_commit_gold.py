"""Pure gold-linter tables for Issue #182 Phase 7.25 (Slice 3a).

Covers the B2 fixture set (B2_01-B2_06 + B2_04b), Claim A purity properties
(A_04 no-mutation), the empty-matrix exemption, ``ok_for_mode`` normative
behaviour, and ``resolve_gold_mode`` precedence. No live LLM, no enforce
round-trip for deliberately illegal mismatch rows (B2_03 is a direct structured
fixture via ``model_construct`` to bypass matrix canonicalisation).
"""

from __future__ import annotations

import pytest

from git_cg.commit_gold import (
    BANNED_BODY_OPENERS,
    STRICT_FAIL_CODES,
    GoldReport,
    check_commit_gold,
    resolve_gold_mode,
)
from git_cg.intent import DiffSignals, rank_commit_intents
from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact
from git_cg.regeneration import ResolvedCommitContract
from git_cg.sop import load_sop


@pytest.fixture(scope="module")
def sop_matrix() -> list[dict]:
    """Load the production SOP matrix used for ranked coverage fixtures."""
    return load_sop().get("gitmoji_reference_matrix", [])


def _intent(
    intent_id: str, emoji: str, cc_type: str, semver: str, group: str, scope: str | None = None
) -> CommitIntent:
    """Construct a structured intent WITHOUT matrix canonicalisation (direct fixture)."""
    return CommitIntent.model_construct(
        intent_id=intent_id,
        gitmoji=emoji,
        cc_type=CommitType(cc_type),
        scope=scope,
        description="do the thing",
        semver_impact=SemVerImpact(semver),
        changelog_group=group,
    )


def _plan(
    primary: CommitIntent,
    secondaries: list[CommitIntent] | None = None,
    *,
    body: str | None = None,
    split: bool = False,
) -> CommitPlan:
    """Construct a structured plan WITHOUT model validators (direct fixture)."""
    return CommitPlan.model_construct(
        primary_intent=primary,
        secondary_intents=secondaries or [],
        split_recommended=split,
        rationale="fixture rationale",
        body_summary=body,
        breaking_change=False,
        breaking_change_description=None,
    )


FEAT = _intent("feature_addition", "✨", "feat", "MINOR", "Added")
BUGFIX = _intent("bug_fix", "🐛", "fix", "PATCH", "Fixed")


# ---------------------------------------------------------------------------
# B2 fixture set
# ---------------------------------------------------------------------------


def test_b2_01_coherent_feat_passes() -> None:
    """B2_01: coherent feat/Added single-surface plan emits no findings."""
    report = check_commit_gold(_plan(FEAT), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert report.codes() == frozenset()


def test_b2_02_fix_primary_feat_secondary_minor_trailer_passes() -> None:
    """B2_02: fix primary + feat secondary explains MINOR trailer - must PASS.

    Guards the multi-intent SemVer rule: ``max(primary + secondaries)`` means a
    fix+MINOR header is legal when a feat secondary explains the MINOR.
    """
    plan = _plan(BUGFIX, [FEAT])
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert report.codes() == frozenset()


def test_b2_03_feat_primary_fixed_only_group_fails() -> None:
    """B2_03: feat primary with Fixed-only group fails GOLD_GROUP_PRIMARY_MISMATCH.

    Direct structured fixture (no enforce round-trip): matrix-canonicalisation would
    repair ``changelog_group`` to ``Added``, so the illegal combination is built via
    ``model_construct``. Asserts the exact finding set — only the target product
    finding, never GOLD_CONTRACT_SMOKE (F3).
    """
    feat_fixed = _intent("feature_addition", "✨", "feat", "MINOR", "Fixed")
    report = check_commit_gold(_plan(feat_fixed), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert report.codes() == frozenset({"GOLD_GROUP_PRIMARY_MISMATCH"})
    assert "GOLD_CONTRACT_SMOKE" not in report.codes()


def test_b2_04_multi_surface_missing_secondaries_fails(sop_matrix: list[dict]) -> None:
    """B2_04: multi-surface diff with a competitive ranked secondary fails coverage."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        touches_docs=True,
        files=["src/git_cg/release.py", "tests/test_release.py", "docs/usage.md"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert report.codes() == frozenset({"GOLD_INCLUDED_CHANGES_MISSING"})


def test_b2_04b_multi_surface_split_recommended_passes(sop_matrix: list[dict]) -> None:
    """B2_04b: split_recommended alone passes coverage even without secondaries."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        touches_docs=True,
        files=["src/git_cg/release.py", "tests/test_release.py", "docs/usage.md"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT, split=True), None, signals=signals, ranked_intents=ranked)
    assert report.codes() == frozenset()


def test_b2_05_banned_body_opener_fails_in_strict_warns_in_warn() -> None:
    """B2_05: banned inventory opener fails in strict, warns (passes) in warn."""
    plan = _plan(FEAT, body="This commit adds a new helper.")
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert report.codes() == frozenset({"GOLD_BODY_INVENTORY"})
    assert not report.ok_for_mode("strict")
    assert report.ok_for_mode("warn")


def test_b2_06_single_surface_no_secondaries_passes(sop_matrix: list[dict]) -> None:
    """B2_06: single-surface plan without secondaries passes coverage."""
    signals = DiffSignals(files=["src/git_cg/release.py"])
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert report.codes() == frozenset()


@pytest.mark.parametrize("opener", BANNED_BODY_OPENERS)
def test_banned_openers_all_flagged(opener: str) -> None:
    """Every shared banned opener is flagged (prompt/linter constant stays in sync)."""
    plan = _plan(FEAT, body=f"{opener} something.")
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_BODY_INVENTORY" in report.codes()


# ---------------------------------------------------------------------------
# Claim A purity + normative behaviour
# ---------------------------------------------------------------------------


def test_a04_check_commit_gold_does_not_mutate_primary_fields() -> None:
    """A_04: the checker leaves primary matrix fields identical before/after."""
    feat_fixed = _intent("feature_addition", "✨", "feat", "MINOR", "Fixed")
    plan = _plan(feat_fixed, body="This commit adds x.")
    before = (
        plan.primary_intent.intent_id,
        plan.primary_intent.gitmoji,
        plan.primary_intent.cc_type,
        plan.primary_intent.semver_impact,
        plan.primary_intent.changelog_group,
    )
    check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    after = (
        plan.primary_intent.intent_id,
        plan.primary_intent.gitmoji,
        plan.primary_intent.cc_type,
        plan.primary_intent.semver_impact,
        plan.primary_intent.changelog_group,
    )
    assert before == after


def test_contract_smoke_fires_on_diverged_primary() -> None:
    """GOLD_CONTRACT_SMOKE fires when primary fields disagree with the contract."""
    contract = ResolvedCommitContract(
        primary_intent_id="bug_fix",
        gitmoji="🐛",
        cc_type="fix",
        semver_impact="PATCH",
        changelog_group="Fixed",
        secondary_intent_ids=[],
    )
    report = check_commit_gold(_plan(FEAT), contract, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_CONTRACT_SMOKE" in report.codes()
    # Smoke may hard-fail independent of mode; it is not in the strict product set.
    assert "GOLD_CONTRACT_SMOKE" not in STRICT_FAIL_CODES


def test_contract_none_skips_smoke() -> None:
    """F4: contract=None skips only GOLD_CONTRACT_SMOKE (direct fixtures)."""
    report = check_commit_gold(_plan(FEAT), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_CONTRACT_SMOKE" not in report.codes()


def test_empty_matrix_unknown_contract_exemption() -> None:
    """Empty-matrix / unknown fallback must not hard-fail product coherence rules."""
    unknown = _intent("unknown", "🔧", "chore", "NONE", "Miscellaneous")
    report = check_commit_gold(_plan(unknown), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_GROUP_PRIMARY_MISMATCH" not in report.codes()
    assert "GOLD_TYPE_GROUP_INCOHERENT" not in report.codes()


def test_ok_for_mode_normative_behaviour() -> None:
    """ok_for_mode: off/warn/surface always pass; strict gates on STRICT_FAIL_CODES."""
    fail_report = GoldReport(findings=())
    assert fail_report.ok_for_mode("strict")

    import dataclasses

    from git_cg.commit_gold import GoldFinding

    inventory = GoldReport(findings=tuple([GoldFinding(code="GOLD_BODY_INVENTORY", message="m")]))
    for mode in ("off", "warn", "surface"):
        assert inventory.ok_for_mode(mode)
    assert not inventory.ok_for_mode("strict")
    # A non-strict-fail code never blocks strict.
    smoke_only = GoldReport(findings=tuple([GoldFinding(code="GOLD_CONTRACT_SMOKE", message="m")]))
    assert smoke_only.ok_for_mode("strict")
    _ = dataclasses  # silence unused if layout changes


# ---------------------------------------------------------------------------
# resolve_gold_mode precedence
# ---------------------------------------------------------------------------


def test_resolve_gold_mode_env_override_wins() -> None:
    assert resolve_gold_mode(environ={"GIT_CG_GOLD_MODE": "strict"}, strict=False) == "strict"
    assert resolve_gold_mode(environ={"GIT_CG_GOLD_MODE": "off"}, strict=True) == "off"
    assert resolve_gold_mode(environ={"GIT_CG_GOLD_MODE": "warn"}, strict=True) == "warn"


def test_resolve_gold_mode_strict_flag() -> None:
    assert resolve_gold_mode(strict=True, environ={}) == "strict"


def test_resolve_gold_mode_surface_interactive_tty() -> None:
    assert resolve_gold_mode(interactive=True, tty_available=True, environ={}) == "surface"


def test_resolve_gold_mode_warn_default() -> None:
    assert resolve_gold_mode(environ={}) == "warn"
    # Non-interactive even with TTY is warn, not surface.
    assert resolve_gold_mode(interactive=False, tty_available=True, environ={}) == "warn"


def test_resolve_gold_mode_surface_env_value_rejected() -> None:
    """surface is interactive-derived only; an env value of ``surface`` is invalid."""
    assert resolve_gold_mode(environ={"GIT_CG_GOLD_MODE": "surface"}, strict=False) == "warn"
