"""Pure gold-linter tables for Issues #182 / #191 (Phase 7.25 + 7.26).

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
    SUBJECT_INVENTORY_VERBS,
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
    intent_id: str,
    emoji: str,
    cc_type: str,
    semver: str,
    group: str,
    scope: str | None = None,
    *,
    description: str = "do the thing",
) -> CommitIntent:
    """Construct a structured intent WITHOUT matrix canonicalisation (direct fixture)."""
    return CommitIntent.model_construct(
        intent_id=intent_id,
        gitmoji=emoji,
        cc_type=CommitType(cc_type),
        scope=scope,
        description=description,
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
    ``model_construct``. Asserts the exact finding set — the product primary-mismatch
    plus the F7 type/group-incoherence, never GOLD_CONTRACT_SMOKE (F3).
    """
    feat_fixed = _intent("feature_addition", "✨", "feat", "MINOR", "Fixed")
    report = check_commit_gold(_plan(feat_fixed), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert report.codes() == frozenset({"GOLD_GROUP_PRIMARY_MISMATCH", "GOLD_TYPE_GROUP_INCOHERENT"})
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


def test_presentation_overlay_gold_accepts_legal_semver_and_group_divergence() -> None:
    """After #204 overlay, gold keeps identity checks but allows presentation fields."""
    contract = ResolvedCommitContract(
        primary_intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        semver_impact="MINOR",
        changelog_group="Added",
        secondary_intent_ids=[],
    )
    # Direct fixtures: bypass matrix canonicalisation so presentation fields stick.
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "PATCH",  # presentation ceiling below matrix MINOR
        "Added",
        scope="commit-quality",
        description="apply path-class presentation overlay",
    )
    secondary = _intent(
        "tests_update",
        "✅",
        "test",
        "NONE",
        "Tests",  # D19 presentation group (matrix row is Miscellaneous)
        scope="commit-quality",
        description="lock overlay cases",
    )
    plan = _plan(
        primary,
        [secondary],
        body="Path-class overlay clamps SemVer and repairs changelog groups.",
    )
    report = check_commit_gold(
        plan,
        contract,
        signals=DiffSignals(files=["src/git_cg/commit_quality.py", "tests/test_commit_quality.py"]),
        presentation_overlay_applied=True,
    )
    assert "GOLD_CONTRACT_SMOKE" not in report.codes()
    assert "GOLD_SEMVER_MATRIX_MISMATCH" not in report.codes()
    assert "GOLD_TYPE_GROUP_INCOHERENT" not in report.codes()


def test_presentation_overlay_gold_still_rejects_identity_drift() -> None:
    """Even with overlay flag, intent_id/gitmoji drift remains GOLD_CONTRACT_SMOKE."""
    contract = ResolvedCommitContract(
        primary_intent_id="feature_addition",
        gitmoji="✨",
        cc_type="feat",
        semver_impact="MINOR",
        changelog_group="Added",
        secondary_intent_ids=[],
    )
    drifted = _intent(
        "bug_fix",  # identity drift
        "🐛",
        "fix",
        "PATCH",
        "Fixed",
        scope="commit-quality",
        description="wrong identity after overlay",
    )
    plan = _plan(drifted, body="Identity must remain locked to the enforced contract.")
    report = check_commit_gold(
        plan,
        contract,
        signals=DiffSignals(files=["src/git_cg/commit_quality.py"]),
        presentation_overlay_applied=True,
    )
    assert "GOLD_CONTRACT_SMOKE" in report.codes()
    msg = next(f.message for f in report.findings if f.code == "GOLD_CONTRACT_SMOKE")
    assert "intent_id" in msg
    assert "gitmoji" in msg


def test_presentation_overlay_flag_default_keeps_legacy_matrix_strictness() -> None:
    """Default callers still fail matrix SemVer/group mismatches (no silent relaxation)."""
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "NONE",  # matrix says MINOR
        "Added",
        scope="api",
        description="clamp semver illegally without overlay flag",
    )
    secondary = _intent(
        "tests_update",
        "✅",
        "test",
        "NONE",
        "Tests",  # matrix says Miscellaneous
        scope="test",
        description="bad group",
    )
    plan = _plan(
        primary,
        [secondary],
        body="Legacy gold path remains strict without the overlay flag.",
    )
    report = check_commit_gold(
        plan,
        None,
        signals=DiffSignals(files=["src/git_cg/release.py", "tests/test_release.py"]),
    )
    assert "GOLD_SEMVER_MATRIX_MISMATCH" in report.codes()
    assert "GOLD_TYPE_GROUP_INCOHERENT" in report.codes()


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


def test_type_group_incoherent_fires_on_docs_primary_fixed_group() -> None:
    """Pin GOLD_TYPE_GROUP_INCOHERENT: docs/chore primary in a Fixed group, no fix secondary.

    ``GOLD_TYPE_GROUP_INCOHERENT`` is a STRICT_FAIL_CODES member that can block a commit;
    this positive case pins the branch so it cannot silently go dead.
    """
    docs_fixed = _intent("documentation", "📝", "docs", "NONE", "Fixed")
    report = check_commit_gold(_plan(docs_fixed), None, signals=DiffSignals(files=["docs/usage.md"]))
    assert "GOLD_TYPE_GROUP_INCOHERENT" in report.codes()
    assert "GOLD_TYPE_GROUP_INCOHERENT" in STRICT_FAIL_CODES


def test_gitmoji_cc_groups_matches_sop(sop_matrix: list[dict]) -> None:
    """Static GITMOJI_CC_GROUPS must stay in sync with the live SOP matrix (F7 drift guard).

    Every SOP row's emoji must map to its cc_type/semver, and the static
    changelog-group frozenset must equal the set of groups declared on SOP rows
    that share that normalized emoji.
    """
    from collections import defaultdict

    from git_cg.commit_gold import GITMOJI_CC_GROUPS

    def _norm(e: str) -> str:
        return e.replace("\ufe0f", "").replace("\ufe0e", "")

    expected_groups: dict[str, set[str]] = defaultdict(set)
    expected_cc: dict[str, str] = {}
    expected_semver: dict[str, str] = {}
    for row in sop_matrix:
        emoji = _norm(row["emoji"])
        expected_groups[emoji].add(row["changelog_group"])
        # SOP may list multiple rows per emoji; cc_type/semver must be stable.
        if emoji in expected_cc:
            assert expected_cc[emoji] == row["cc_type"], f"{emoji!r}: mixed cc_type in SOP"
            assert expected_semver[emoji] == row["semver_impact"], f"{emoji!r}: mixed semver in SOP"
        else:
            expected_cc[emoji] = row["cc_type"]
            expected_semver[emoji] = row["semver_impact"]

    assert set(GITMOJI_CC_GROUPS) == set(expected_groups), (
        f"emoji key drift: static-only={set(GITMOJI_CC_GROUPS) - set(expected_groups)!r} "
        f"sop-only={set(expected_groups) - set(GITMOJI_CC_GROUPS)!r}"
    )
    for emoji, sop_groups in expected_groups.items():
        cc_type, groups, semver = GITMOJI_CC_GROUPS[emoji]
        assert cc_type == expected_cc[emoji], f"{emoji!r}: cc_type {cc_type!r} != SOP {expected_cc[emoji]!r}"
        assert set(groups) == sop_groups, (
            f"{emoji!r}: static groups {sorted(groups)} != SOP groups {sorted(sop_groups)}"
        )
        assert semver == expected_semver[emoji], (
            f"{emoji!r}: SOP semver {expected_semver[emoji]!r} != static {semver!r}"
        )


def test_f7_secondary_incoherent_group_fails() -> None:
    """F7: a secondary whose changelog_group is unreachable from its type fails.

    feat/Added primary + test/Changed secondary is matrix-incoherent (test ->
    Miscellaneous only). Fires GOLD_TYPE_GROUP_INCOHERENT and blocks strict mode.
    """
    test_changed = _intent("test_update", "✅", "test", "NONE", "Changed")
    plan = _plan(FEAT, [test_changed])
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_TYPE_GROUP_INCOHERENT" in report.codes()
    assert not report.ok_for_mode("strict")


def test_f7_coherent_mixed_plan_passes() -> None:
    """F7: feat/Added + test/Miscellaneous + docs/Miscellaneous is fully coherent."""
    test_misc = _intent("test_update", "✅", "test", "NONE", "Miscellaneous")
    docs_misc = _intent("documentation", "📝", "docs", "NONE", "Miscellaneous")
    plan = _plan(FEAT, [test_misc, docs_misc])
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert report.codes() == frozenset()
    assert report.ok_for_mode("strict")


def test_f7_unknown_gitmoji_skipped_not_failed() -> None:
    """F7: an out-of-vocabulary gitmoji is skipped (enforce owns it), never failed here."""
    weird = _intent("mystery", "🛸", "chore", "NONE", "Fixed")
    plan = _plan(FEAT, [weird])
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_TYPE_GROUP_INCOHERENT" not in report.codes()


def test_f2_semver_matrix_mismatch_fails() -> None:
    """F2: plan SemVer that disagrees with the matrix gitmoji row fails strict."""
    # ✨ is MINOR in the matrix; inflate to MAJOR.
    inflated = _intent("feature_addition", "✨", "feat", "MAJOR", "Added")
    report = check_commit_gold(_plan(inflated), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SEMVER_MATRIX_MISMATCH" in report.codes()
    assert "GOLD_SEMVER_MATRIX_MISMATCH" in STRICT_FAIL_CODES
    assert not report.ok_for_mode("strict")


def test_f2_semver_matrix_coherent_passes() -> None:
    """F2: matrix-keyed SemVer on primary + secondary passes."""
    test_misc = _intent("test_update", "✅", "test", "NONE", "Miscellaneous")
    plan = _plan(FEAT, [test_misc])  # FEAT is MINOR/Added; test is NONE/Misc
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SEMVER_MATRIX_MISMATCH" not in report.codes()


def test_f2_semver_secondary_mismatch_fails() -> None:
    """F2: a secondary with inflated SemVer fails even when primary is coherent."""
    test_inflated = _intent("test_update", "✅", "test", "MINOR", "Miscellaneous")
    plan = _plan(FEAT, [test_inflated])
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SEMVER_MATRIX_MISMATCH" in report.codes()


def test_f3_expanded_openers_flagged() -> None:
    """F3: expanded marketing/inventory first-line openers fire GOLD_BODY_INVENTORY."""
    for opener in ("Adds ", "Introduces ", "Ensures ", "This change "):
        plan = _plan(FEAT, body=f"{opener}a validation check for F7.")
        report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
        assert "GOLD_BODY_INVENTORY" in report.codes(), opener
        assert not report.ok_for_mode("strict")


def test_f3_mid_body_adds_not_flagged() -> None:
    """F3: 'Adds' mid-body (not first line) must not fire inventory."""
    body = "Close the F7 audit gap at generation time.\n\nAdds a drift guard for the SOP matrix."
    plan = _plan(FEAT, body=body)
    report = check_commit_gold(plan, None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_BODY_INVENTORY" not in report.codes()


def test_f4_filename_scope_fails() -> None:
    """F4/F5 light: filename-like scopes fail GOLD_SCOPE_FILENAME."""
    bad = _intent("documentation", "📝", "docs", "NONE", "Miscellaneous", scope="usage.kdl")
    report = check_commit_gold(_plan(bad), None, signals=DiffSignals(files=["docs/usage.md"]))
    assert "GOLD_SCOPE_FILENAME" in report.codes()
    assert "GOLD_SCOPE_FILENAME" in STRICT_FAIL_CODES
    assert not report.ok_for_mode("strict")


def test_f4_path_scope_fails() -> None:
    """F4/F5 light: path-like scopes fail GOLD_SCOPE_FILENAME."""
    bad = _intent("documentation", "📝", "docs", "NONE", "Miscellaneous", scope="docs/usage")
    report = check_commit_gold(_plan(bad), None, signals=DiffSignals(files=["docs/usage.md"]))
    assert "GOLD_SCOPE_FILENAME" in report.codes()


def test_f4_product_area_scope_passes() -> None:
    """F4/F5 light: product-area scopes (commit, tui, cli) pass."""
    ok = _intent("feature_addition", "✨", "feat", "MINOR", "Added", scope="commit")
    report = check_commit_gold(_plan(ok), None, signals=DiffSignals(files=["src/git_cg/commit_gold.py"]))
    assert "GOLD_SCOPE_FILENAME" not in report.codes()


def test_f5_title_case_subject_fails() -> None:
    """F5 light: Title Case primary description fails GOLD_SUBJECT_TITLE_CASE."""
    titled = CommitIntent.model_construct(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType("feat"),
        scope="commit",
        description="Enforce Group Reachability Now",
        semver_impact=SemVerImpact("MINOR"),
        changelog_group="Added",
    )
    report = check_commit_gold(_plan(titled), None, signals=DiffSignals(files=["src/git_cg/commit_gold.py"]))
    assert "GOLD_SUBJECT_TITLE_CASE" in report.codes()
    assert "GOLD_SUBJECT_TITLE_CASE" in STRICT_FAIL_CODES
    assert not report.ok_for_mode("strict")


def test_f5_imperative_lowercase_subject_passes() -> None:
    """F5 light: imperative lowercase description passes."""
    ok = CommitIntent.model_construct(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType("feat"),
        scope="commit",
        description="enforce F7 group reachability",
        semver_impact=SemVerImpact("MINOR"),
        changelog_group="Added",
    )
    report = check_commit_gold(_plan(ok), None, signals=DiffSignals(files=["src/git_cg/commit_gold.py"]))
    assert "GOLD_SUBJECT_TITLE_CASE" not in report.codes()


def test_single_file_changelog_not_multi_surface(sop_matrix: list[dict]) -> None:
    """Finding 2: a lone CHANGELOG.md (docs+release roles) is ONE surface — no coverage fail."""
    signals = DiffSignals(files=["CHANGELOG.md"], adds_public_api=True)
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert "GOLD_INCLUDED_CHANGES_MISSING" not in report.codes()


def test_single_file_pyproject_not_multi_surface(sop_matrix: list[dict]) -> None:
    """Finding 2: a lone pyproject.toml (config_ci+release roles) is ONE surface."""
    signals = DiffSignals(files=["pyproject.toml"], adds_public_api=True)
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert "GOLD_INCLUDED_CHANGES_MISSING" not in report.codes()


def test_two_distinct_files_still_multi_surface(sop_matrix: list[dict]) -> None:
    """Guard: genuinely distinct surfaces (src + tests) still trigger the coverage finding."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        files=["src/git_cg/release.py", "tests/test_release.py"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    # Deterministic: the live SOP ranking of these signals always yields a competitive
    # secondary (tests_update primary, feature_addition secondary), so the genuinely
    # multi-file diff MUST fire the coverage finding — the single-file exemption above
    # must not suppress it.
    assert (ranked[0].intent_id, ranked[1].intent_id) == ("tests_update", "feature_addition")
    assert "GOLD_INCLUDED_CHANGES_MISSING" in report.codes()


def test_ok_for_mode_normative_behaviour() -> None:
    """ok_for_mode: off/warn/surface always pass; strict gates on STRICT_FAIL_CODES."""
    from git_cg.commit_gold import GoldFinding

    empty_report = GoldReport(findings=())
    assert empty_report.ok_for_mode("strict")

    inventory = GoldReport(findings=tuple([GoldFinding(code="GOLD_BODY_INVENTORY", message="m")]))
    for mode in ("off", "warn", "surface"):
        assert inventory.ok_for_mode(mode)
    assert not inventory.ok_for_mode("strict")
    # A non-strict-fail code never blocks strict.
    smoke_only = GoldReport(findings=tuple([GoldFinding(code="GOLD_CONTRACT_SMOKE", message="m")]))
    assert smoke_only.ok_for_mode("strict")


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


def test_resolve_gold_mode_gold_strict_flag() -> None:
    """--gold-strict resolves strict like --strict, without enabling non-gold strictness."""
    from git_cg.commit_gold import resolve_gold_mode

    assert resolve_gold_mode(gold_strict=True, environ={}) == "strict"


def test_resolve_gold_mode_env_still_beats_gold_strict() -> None:
    """GIT_CG_GOLD_MODE env keeps top precedence over --gold-strict."""
    from git_cg.commit_gold import resolve_gold_mode

    assert resolve_gold_mode(gold_strict=True, environ={"GIT_CG_GOLD_MODE": "warn"}) == "warn"


def test_resolve_gold_mode_surface_env_value_rejected() -> None:
    """surface is interactive-derived only; an env value of ``surface`` is invalid."""
    assert resolve_gold_mode(environ={"GIT_CG_GOLD_MODE": "surface"}, strict=False) == "warn"


# ---------------------------------------------------------------------------
# Issue #191 — GOLD_SUBJECT_INVENTORY + P6 coverage messages (V11-A)
# ---------------------------------------------------------------------------


def test_v11_a01_subject_inventory_pattern_a_fires() -> None:
    """V11-A01: PATTERN A fires on description `add X, update Y, fix Z`."""
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "MINOR",
        "Added",
        description="add helper, update docs, fix edge case",
    )
    report = check_commit_gold(_plan(primary), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SUBJECT_INVENTORY" in report.codes()
    assert "GOLD_SUBJECT_INVENTORY" in STRICT_FAIL_CODES
    assert not report.ok_for_mode("strict")
    assert "lead with the outcome" in report.findings[0].message.lower() or any(
        "lead with the outcome" in f.message.lower() for f in report.findings
    )


def test_v11_a01b_two_comma_clauses_pass() -> None:
    """Exactly 2 comma-separated clauses must not fire subject inventory."""
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "MINOR",
        "Added",
        description="add helper, update docs",
    )
    report = check_commit_gold(_plan(primary), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SUBJECT_INVENTORY" not in report.codes()


def test_v11_a02_subject_inventory_pattern_b_fires() -> None:
    """V11-A02: PATTERN B fires on description `add X and update Y and fix Z`."""
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "MINOR",
        "Added",
        description="add helper and update docs and fix edge case",
    )
    report = check_commit_gold(_plan(primary), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SUBJECT_INVENTORY" in report.codes()
    inv = next(f for f in report.findings if f.code == "GOLD_SUBJECT_INVENTORY")
    assert "lead with the outcome" in inv.message.lower()


def test_v11_a03_noun_tail_non_trigger() -> None:
    """V11-A03: one verb + noun list must pass (no false inventory)."""
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "MINOR",
        "Added",
        description="enforce SemVer, scope, and title checks",
    )
    report = check_commit_gold(_plan(primary), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SUBJECT_INVENTORY" not in report.codes()


def test_v11_a03b_single_and_coordination_passes() -> None:
    """A single coordinating `and` is not PATTERN B."""
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "MINOR",
        "Added",
        description="add helper and update docs",
    )
    report = check_commit_gold(_plan(primary), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SUBJECT_INVENTORY" not in report.codes()


def test_v11_a03c_verb_allowlist_is_closed() -> None:
    """Allowlist miss must not invent fuzzy verbs."""
    assert len(SUBJECT_INVENTORY_VERBS) == 93
    assert "ship" not in SUBJECT_INVENTORY_VERBS
    primary = _intent(
        "feature_addition",
        "✨",
        "feat",
        "MINOR",
        "Added",
        description="ship helper, ship docs, ship tests",
    )
    report = check_commit_gold(_plan(primary), None, signals=DiffSignals(files=["src/git_cg/release.py"]))
    assert "GOLD_SUBJECT_INVENTORY" not in report.codes()


@pytest.mark.parametrize("verb", sorted(SUBJECT_INVENTORY_VERBS))
def test_v11_a03d_verb_allowlist_clause_is_verb_initial(verb: str) -> None:
    """Each closed-allowlist verb is recognized as verb-initial (case-insensitive)."""
    from git_cg.commit_gold import _clause_is_verb_initial

    assert _clause_is_verb_initial(verb)
    assert _clause_is_verb_initial(verb.upper())
    assert _clause_is_verb_initial(f"{verb} helper module")


def test_v11_a08_p6_three_group_split_preferring_message(sop_matrix: list[dict]) -> None:
    """V11-A08: ≥3 coverage groups prefer split wording; code unchanged."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        touches_docs=True,
        files=["src/git_cg/release.py", "tests/test_release.py", "docs/usage.md"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert report.codes() == frozenset({"GOLD_INCLUDED_CHANGES_MISSING"})
    msg = next(f.message for f in report.findings if f.code == "GOLD_INCLUDED_CHANGES_MISSING")
    assert "recommend splitting" in msg
    assert "Included changes" in msg


def test_v11_a08b_p6_two_group_secondary_preferring_message(sop_matrix: list[dict]) -> None:
    """V11-A08: 2 coverage groups prefer secondary fill wording."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        files=["src/git_cg/release.py", "tests/test_release.py"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert "GOLD_INCLUDED_CHANGES_MISSING" in report.codes()
    msg = next(f.message for f in report.findings if f.code == "GOLD_INCLUDED_CHANGES_MISSING")
    assert "secondary intents" in msg
    assert "recommend splitting" not in msg
    assert "Included changes" in msg


def test_v11_a08c_split_recommended_still_passes(sop_matrix: list[dict]) -> None:
    """split_recommended alone still suppresses coverage finding."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        touches_docs=True,
        files=["src/git_cg/release.py", "tests/test_release.py", "docs/usage.md"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT, split=True), None, signals=signals, ranked_intents=ranked)
    assert "GOLD_INCLUDED_CHANGES_MISSING" not in report.codes()


def test_v11_a08d_split_preferred_structured_flag(sop_matrix: list[dict]) -> None:
    """≥3-group coverage finding sets GoldFinding.split_preferred (not message-only)."""
    signals = DiffSignals(
        adds_public_api=True,
        touches_tests=True,
        touches_docs=True,
        files=["src/git_cg/release.py", "tests/test_release.py", "docs/usage.md"],
    )
    ranked = rank_commit_intents(signals, sop_matrix)
    report = check_commit_gold(_plan(FEAT), None, signals=signals, ranked_intents=ranked)
    assert "GOLD_INCLUDED_CHANGES_MISSING" in report.codes()
    assert report.has_split_recommendation() is True
    finding = next(f for f in report.findings if f.code == "GOLD_INCLUDED_CHANGES_MISSING")
    assert finding.split_preferred is True


def test_v11_a03_repo_history_fp_budget() -> None:
    """V11-A03: ≥95/100 recent subjects clean under the real subject-inventory patterns.

    Integration guard over live history (not a pure unit test). Skips when git is
    unavailable or the checkout is too shallow to sample a meaningful corpus —
    CI Run Tests uses ``fetch-depth: 0`` so this path is exercised there.
    """
    import subprocess

    import pytest

    from git_cg.commit_gold import _subject_inventory_pattern_a, _subject_inventory_pattern_b

    try:
        raw = subprocess.check_output(
            ["git", "log", "--format=%s", "-100"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, OSError) as exc:
        pytest.skip(f"git history unavailable for FP-budget guard: {exc}")
    subjects = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(subjects) < 50:
        pytest.skip(f"shallow/insufficient git history for FP-budget guard ({len(subjects)} subjects; need ≥50)")

    def _description_from_subject(subject: str) -> str:
        # Hybrid: "<emoji> <type>(scope): description" or "<emoji> <type>: description"
        if ": " in subject:
            return subject.split(": ", 1)[1].strip()
        return subject

    hits = []
    for subject in subjects:
        desc = _description_from_subject(subject)
        if _subject_inventory_pattern_a(desc) or _subject_inventory_pattern_b(desc):
            hits.append((subject, desc))
    clean = len(subjects) - len(hits)
    ratio = clean / len(subjects)
    assert ratio >= 0.95, f"FP budget failed: {clean}/{len(subjects)} clean; hits={hits}"


def test_skeleton_fallback_is_strict_fail() -> None:
    """P-S12: skeleton fallback provenance fails gold-strict even with clean wording."""
    from git_cg.commit_gold import SKELETON_FALLBACK_MARKER
    from git_cg.commit_quality import apply_guard_skeleton_fallback

    assert "GOLD_SKELETON_FALLBACK_FINAL" in STRICT_FAIL_CODES
    assert "GOLD_PROCESS_META_BODY" in STRICT_FAIL_CODES

    base = _plan(
        _intent("tests_update", "✅", "test", "NONE", "Tests", description="cover staged claim locks"),
        body="Cover staged fixture evidence without product framing.",
    )
    out = apply_guard_skeleton_fallback(base, paths=["tests/fixtures/x.md"])
    assert SKELETON_FALLBACK_MARKER in (out.rationale or "")
    report = check_commit_gold(
        out,
        None,
        signals=DiffSignals(files=["tests/fixtures/x.md"], only_fixtures=True, only_tests=True),
        presentation_overlay_applied=True,
    )
    assert "GOLD_SKELETON_FALLBACK_FINAL" in report.codes()
    assert not report.ok_for_mode("strict")


def test_process_meta_body_is_strict_fail() -> None:
    """P-S12: process-meta fallback phrases fail gold-strict."""
    plan = _plan(
        _intent("tests_update", "✅", "test", "NONE", "Tests", description="cover staged tests"),
        body="Deterministic presentation fallback after guard exhaustion.",
    )
    report = check_commit_gold(
        plan,
        None,
        signals=DiffSignals(files=["tests/test_foo.py"], only_tests=True),
        presentation_overlay_applied=True,
    )
    assert "GOLD_PROCESS_META_BODY" in report.codes()
    assert not report.ok_for_mode("strict")


def test_fixtures_path_class_semver_ceiling() -> None:
    """P-S12: fixtures-only with PATCH fails gold-strict path-class ceiling."""
    plan = _plan(
        _intent("bug_fix", "🐛", "fix", "PATCH", "Fixed", description="cover fixture pins"),
        body="Cover fixture pins without product claims.",
    )
    report = check_commit_gold(
        plan,
        None,
        signals=DiffSignals(files=["tests/fixtures/pack/data.json"], only_fixtures=True, only_tests=True),
        presentation_overlay_applied=True,
    )
    codes = report.codes()
    assert "GOLD_PATH_CLASS_SEMVER_CEILING" in codes
    assert "GOLD_PATH_CLASS_TYPE_MISMATCH" in codes
    assert not report.ok_for_mode("strict")


def test_process_meta_in_rationale_only_is_not_body_fail() -> None:
    """Process-meta phrases in non-rendered rationale must not trip GOLD_PROCESS_META_BODY."""
    plan = _plan(
        _intent("tests_update", "✅", "test", "NONE", "Tests", description="cover staged tests"),
        body="Cover staged fixture evidence without product framing.",
    )
    plan = plan.model_copy(
        update={
            "rationale": (
                "Internal note: deterministic presentation fallback after guard exhaustion "
                "with shared regen budget; not operator-visible."
            )
        }
    )
    report = check_commit_gold(
        plan,
        None,
        signals=DiffSignals(files=["tests/test_foo.py"], only_tests=True),
        presentation_overlay_applied=True,
    )
    assert "GOLD_PROCESS_META_BODY" not in report.codes()


def test_path_class_wording_ignores_rationale_only_claims() -> None:
    """Path-class product/docs wording bans must ignore non-rendered rationale."""
    docs_plan = _plan(
        _intent(
            "docs_update",
            "📝",
            "docs",
            "NONE",
            "Documentation",
            description="document usage flags",
        ),
        body="Document the usage-flags operator guide without shipping claims.",
    )
    docs_plan = docs_plan.model_copy(
        update={
            "rationale": (
                "Internal provenance only: implement support for claim locks and "
                "enforce the contract floor during gold self-correction."
            )
        }
    )
    docs_report = check_commit_gold(
        docs_plan,
        None,
        signals=DiffSignals(files=["docs/usage.md"], only_docs=True, touches_docs=True),
        presentation_overlay_applied=True,
    )
    assert "GOLD_DOCS_IMPLEMENTATION_CLAIM" not in docs_report.codes()

    fixtures_plan = _plan(
        _intent("tests_update", "✅", "test", "NONE", "Tests", description="pin fixture evidence"),
        body="Pin fixture evidence without product framing.",
    )
    fixtures_plan = fixtures_plan.model_copy(
        update={
            "rationale": (
                "Internal provenance only: validate public api and wire telemetry "
                "during presentation repair; not operator-visible."
            )
        }
    )
    fixtures_report = check_commit_gold(
        fixtures_plan,
        None,
        signals=DiffSignals(files=["tests/fixtures/pack/data.json"], only_fixtures=True, only_tests=True),
        presentation_overlay_applied=True,
    )
    assert "GOLD_FIXTURE_PRODUCT_FRAMING" not in fixtures_report.codes()


def test_docs_implementation_claim_fires_for_non_docs_cc_type() -> None:
    """Docs-only path family rejects implementation claims even when cc_type is chore."""
    plan = _plan(
        _intent(
            "chore_maintenance",
            "🔧",
            "chore",
            "NONE",
            "Miscellaneous",
            description="implement support for claim locks",
        ),
        body="Implement the contract floor and add support for staged claim locks.",
    )
    report = check_commit_gold(
        plan,
        None,
        signals=DiffSignals(files=["docs/usage.md"], only_docs=True, touches_docs=True),
        presentation_overlay_applied=True,
    )
    assert "GOLD_DOCS_IMPLEMENTATION_CLAIM" in report.codes()
    assert not report.ok_for_mode("strict")


# ---------------------------------------------------------------------------
# Issue #204 NTH — high-risk theme phrase coverage (warn-only)
# ---------------------------------------------------------------------------


def test_high_risk_theme_missing_when_body_omits_concepts() -> None:
    """Staged telemetry without theme wording emits GOLD_HIGH_RISK_THEME_MISSING."""
    plan = _plan(
        FEAT,
        body="Improve operator messaging for commit presentation quality.",
    )
    signals = DiffSignals(files=["src/git_cg/telemetry.py"])
    report = check_commit_gold(plan, None, signals=signals, ranked_intents=None)
    assert "GOLD_HIGH_RISK_THEME_MISSING" in report.codes()
    # Nice-to-have: not a strict-fail code.
    assert "GOLD_HIGH_RISK_THEME_MISSING" not in STRICT_FAIL_CODES


def test_high_risk_theme_covered_when_body_hits_concepts() -> None:
    """Body covering telemetry must-cover themes clears the high-risk lint."""
    primary = _intent(
        "bug_fix",
        "🐛",
        "fix",
        "PATCH",
        "Fixed",
        scope="telemetry",
        description="cover telemetry redaction",
    )
    plan = _plan(
        primary,
        body=(
            "Cover telemetry fallback-reason transitions and closed-enum tags. "
            "Scrub allow/deny list deltas when redaction coverage changes. "
            "Redaction failure yields the literal token [REDACTED]. "
            "No secret material in payloads."
        ),
    )
    signals = DiffSignals(files=["src/git_cg/telemetry.py"])
    report = check_commit_gold(plan, None, signals=signals, ranked_intents=None)
    assert "GOLD_HIGH_RISK_THEME_MISSING" not in report.codes()


def test_high_risk_theme_skipped_for_low_risk_paths() -> None:
    plan = _plan(FEAT, body="Document operator usage for presentation quality.")
    signals = DiffSignals(files=["docs/usage.md"])
    report = check_commit_gold(plan, None, signals=signals, ranked_intents=None)
    assert "GOLD_HIGH_RISK_THEME_MISSING" not in report.codes()
