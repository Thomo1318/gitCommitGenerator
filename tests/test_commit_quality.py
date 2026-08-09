"""Commit presentation quality — Slice 2 TrailerPriors characterisation (#204).

Locks path-role → TrailerPriors defaults. Does **not** wire priors into
``rank_commit_intents`` scoring (matrix remains sole ranking authority).
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from git_cg.commit_quality import (
    DIFF_CLASS_ADR,
    DIFF_CLASS_DOCS,
    DIFF_CLASS_EMPTY,
    DIFF_CLASS_FIXTURES,
    DIFF_CLASS_MIXED,
    DIFF_CLASS_PRODUCT,
    DIFF_CLASS_TESTS,
    LOW_CONFIDENCE_TRIGGER_REASONS,
    PRESENTATION_FALLBACK_CRAFT,
    PRESENTATION_FALLBACK_HALLUCINATION,
    PRESENTATION_FALLBACK_LOW_CONFIDENCE,
    PRESENTATION_FALLBACK_NONE,
    SLICE9_GATE_ORDER,
    PresentationAdjustment,
    PresentationConstraints,
    Stub,
    apply_guard_skeleton_fallback,
    apply_low_confidence_presentation,
    apply_presentation_overlay,
    apply_presentation_seed,
    build_high_risk_checklist_themes,
    build_included_change_stubs,
    build_low_confidence_body_skeleton,
    changelog_groups_allowlisted,
    classify_diff_class,
    constraints_from_paths,
    derive_trailer_priors,
    detect_high_risk_surfaces,
    dominant_presentation_cc_type,
    evaluate_presentation_gates,
    evaluate_presentation_guards,
    filter_paths_for_content_signals,
    format_guard_guidance,
    format_high_risk_body_checklist,
    format_included_change_stub_inventory,
    format_low_confidence_guidance,
    harvest_claim_tags,
    has_security_path_evidence,
    is_generic_feature_presentation,
    is_high_risk_path_set,
    is_low_confidence_posture,
    merge_presentation_fallback_reason,
    min_included_change_bullets,
    presentation_constraints,
    prose_has_security_negative_markers,
    repair_security_noun_claims,
    required_changelog_groups,
    security_claims_without_path_evidence,
    semver_presentation_ceiling,
    slice9_letter_map,
    strip_included_changes_from_body_summary,
    try_repair_presentation_guards,
)
from git_cg.intent import DiffSignals
from git_cg.models import CommitIntent, CommitPlan, CommitType, SemVerImpact, TrailerPriors
from git_cg.scope_canon import normalize_scope

# ---------------------------------------------------------------------------
# Model contract (D22)
# ---------------------------------------------------------------------------


def test_trailer_priors_is_frozen() -> None:
    priors = TrailerPriors(
        cc_type=CommitType.TEST,
        semver_impact=SemVerImpact.NONE,
        changelog_group="Tests",
        scope_hint="test",
        role="tests",
    )
    with pytest.raises(ValidationError):
        priors.cc_type = CommitType.FEAT  # type: ignore[misc]


def test_trailer_priors_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        TrailerPriors(
            cc_type=CommitType.TEST,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Tests",
            scope_hint="test",
            role="not-a-real-role",
        )


# ---------------------------------------------------------------------------
# Single-role defaults (Slice 2 table)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        pytest.param(
            ["tests/test_scope_canon.py"],
            {
                "role": "tests",
                "cc_type": CommitType.TEST,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Tests",
                "scope_hint": "test",
            },
            id="tests_only",
        ),
        pytest.param(
            ["tests/test_main.py", "tests/test_intent.py"],
            {
                "role": "tests",
                "cc_type": CommitType.TEST,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Tests",
                "scope_hint": "test",
            },
            id="tests_only_multi",
        ),
        pytest.param(
            ["tests/fixtures/commit_quality/README.md"],
            {
                "role": "fixtures",
                "cc_type": CommitType.TEST,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Tests",
                "scope_hint": "fixtures",
            },
            id="fixtures_readme_only",
        ),
        pytest.param(
            ["docs/usage.md"],
            {
                "role": "docs",
                "cc_type": CommitType.DOCS,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Documentation",
                "scope_hint": "usage",
            },
            id="docs_usage",
        ),
        pytest.param(
            ["docs/DEVELOPMENT.md", "CHANGELOG.md"],
            {
                "role": "docs",
                "cc_type": CommitType.DOCS,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Documentation",
                "scope_hint": "docs",
            },
            id="docs_changelog_dev",
        ),
        pytest.param(
            ["docs/ADRs/0163-scoped-reasoning-history.md"],
            {
                "role": "adr",
                "cc_type": CommitType.DOCS,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Documentation",
                "scope_hint": "adr",
            },
            id="adr_only",
        ),
        pytest.param(
            [".github/workflows/promptfoo-code-scan.yml"],
            {
                "role": "config_ci",
                "cc_type": CommitType.CI,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Miscellaneous",
                "scope_hint": "ci",
            },
            id="ci_workflow_only",
        ),
        pytest.param(
            ["mise.toml"],
            {
                "role": "config_ci",
                "cc_type": CommitType.BUILD,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Miscellaneous",
                "scope_hint": "build",
            },
            id="build_tooling_only",
        ),
        pytest.param(
            ["hk.pkl"],
            {
                "role": "config_ci",
                "cc_type": CommitType.CHORE,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Miscellaneous",
                "scope_hint": "chore",
            },
            id="hooks_config_only",
        ),
    ],
)
def test_v12_a02_path_role_priors_evaluation(paths: list[str], expected: dict) -> None:
    priors = derive_trailer_priors(paths)
    assert isinstance(priors, TrailerPriors)
    assert priors.role == expected["role"]
    assert priors.cc_type == expected["cc_type"]
    assert priors.semver_impact == expected["semver_impact"]
    assert priors.changelog_group == expected["changelog_group"]
    assert priors.scope_hint == expected["scope_hint"]


def test_docs_phase9_scope_hint() -> None:
    priors = derive_trailer_priors(["docs/phase9/overview.md"])
    assert priors.role == "docs"
    assert priors.cc_type == CommitType.DOCS
    assert priors.semver_impact == SemVerImpact.NONE
    assert priors.changelog_group == "Documentation"
    assert priors.scope_hint == "phase9"


def test_product_src_does_not_force_feat_minor() -> None:
    priors = derive_trailer_priors(["src/git_cg/main.py"])
    assert priors.role == "product_src"
    assert priors.cc_type != CommitType.FEAT
    assert priors.semver_impact != SemVerImpact.MINOR
    assert priors.semver_impact != SemVerImpact.MAJOR
    # Dominant single module → canonical scope hint
    assert priors.scope_hint == "main"


def test_mixed_roles_do_not_force_feat_minor() -> None:
    priors = derive_trailer_priors(
        [
            "src/git_cg/main.py",
            "tests/test_main.py",
            "docs/usage.md",
        ]
    )
    assert priors.role == "mixed"
    assert priors.cc_type != CommitType.FEAT
    assert priors.semver_impact not in {SemVerImpact.MINOR, SemVerImpact.MAJOR}


def test_empty_paths_are_soft_mixed() -> None:
    priors = derive_trailer_priors([])
    assert priors.role in {"mixed", "product_src"}
    assert priors.cc_type != CommitType.FEAT
    assert priors.semver_impact not in {SemVerImpact.MINOR, SemVerImpact.MAJOR}


def test_signals_files_used_when_paths_empty() -> None:
    signals = DiffSignals(files=["tests/test_scope_canon.py"], only_tests=True, touches_tests=True)
    priors = derive_trailer_priors([], signals=signals)
    assert priors.role == "tests"
    assert priors.changelog_group == "Tests"


def test_scope_hint_runs_through_canon() -> None:
    """scope_hint values must already be canonical (I-12 / Slice 1 composition)."""
    priors = derive_trailer_priors(["docs/ADRs/0163-scoped-reasoning-history.md"])
    assert priors.scope_hint == normalize_scope(priors.scope_hint)


def test_derive_trailer_priors_does_not_import_ranker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Priors must not call into ranking (Slice 2 exit criterion)."""

    def _boom(*_a, **_k):
        raise AssertionError("rank_commit_intents must not be called from derive_trailer_priors")

    import git_cg.intent as intent_mod

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    derive_trailer_priors(["tests/test_foo.py"])


def test_build_generation_context_attaches_scope_priors(monkeypatch: pytest.MonkeyPatch) -> None:
    """D25: GenerationContext.scope_priors carries TrailerPriors from the rank-pass seam."""
    from git_cg.main import _build_generation_context

    monkeypatch.setattr(
        "git_cg.main.extract_diff_signals",
        lambda _diff: DiffSignals(
            files=["tests/test_scope_canon.py"],
            only_tests=True,
            touches_tests=True,
        ),
    )
    monkeypatch.setattr("git_cg.main.rank_commit_intents", lambda *_a, **_k: [])
    monkeypatch.setattr(
        "git_cg.main.load_sop",
        lambda: {"gitmoji_reference_matrix": []},
    )

    ctx = _build_generation_context("diff --git a/x b/x\n", enable_semantic=False)
    assert isinstance(ctx.scope_priors, TrailerPriors)
    assert ctx.scope_priors.role == "tests"
    assert ctx.scope_priors.changelog_group == "Tests"


# ---------------------------------------------------------------------------
# Slice 2b — Diff-class gates · changelog anti-signal · security path evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paths", "diff_name", "force_cc", "forbid_extra"),
    [
        pytest.param(
            ["tests/test_scope_canon.py"],
            DIFF_CLASS_TESTS,
            CommitType.TEST,
            {"feat", "fix"},
            id="tests_only_gate",
        ),
        pytest.param(
            ["tests/fixtures/commit_quality/README.md"],
            DIFF_CLASS_FIXTURES,
            CommitType.TEST,
            {"feat", "fix"},
            id="fixtures_only_gate",
        ),
        pytest.param(
            ["docs/usage.md", "CHANGELOG.md", "DEVELOPMENT.md"],
            DIFF_CLASS_DOCS,
            CommitType.DOCS,
            {"feat", "fix"},
            id="docs_changelog_gate_g4",
        ),
        pytest.param(
            ["docs/ADRs/0163-scoped-reasoning-history.md"],
            DIFF_CLASS_ADR,
            CommitType.DOCS,
            {"feat", "fix", "chore"},
            id="adr_only_gate",
        ),
    ],
)
def test_v12_a08_diff_class_gates_tip_g2_g3_g4(
    paths: list[str],
    diff_name: str,
    force_cc: CommitType,
    forbid_extra: set[str],
) -> None:
    dc = classify_diff_class(paths)
    assert dc.name == diff_name
    assert dc.has_runtime_surface is False
    cons = presentation_constraints(dc)
    assert isinstance(cons, PresentationConstraints)
    assert cons.force_cc_type == force_cc
    assert cons.force_semver == SemVerImpact.NONE
    assert forbid_extra <= set(cons.forbid_cc_types)
    assert "MAJOR" in cons.forbid_semver
    assert "MINOR" in cons.forbid_semver
    assert "PATCH" in cons.forbid_semver
    assert cons.forbid_security_primary is True


def test_changelog_antisignal_exclude_from_signals() -> None:
    paths = ["docs/usage.md", "CHANGELOG.md", "DEVELOPMENT.md"]
    filtered = filter_paths_for_content_signals(paths)
    assert "CHANGELOG.md" not in filtered
    assert "docs/usage.md" in filtered
    cons = constraints_from_paths(paths)
    assert cons.changelog_antisignal_applied is True
    assert cons.force_cc_type == CommitType.DOCS
    assert cons.force_semver == SemVerImpact.NONE
    assert cons.force_changelog_group == "Documentation"
    # Must not look like fix primary
    assert "fix" in cons.forbid_cc_types


def test_security_path_evidence_positive() -> None:
    assert has_security_path_evidence(["src/git_cg/secrets.py"]) is True
    assert has_security_path_evidence([".github/workflows/secret-scan.yml"]) is True
    assert has_security_path_evidence(["config/gitleaks.toml"]) is True
    assert has_security_path_evidence(["docs/usage.md"]) is False
    assert has_security_path_evidence(["tests/fixtures/auth_flow.md"]) is False


def test_security_negative_prose_does_not_imply_path_evidence() -> None:
    readme = (
        "The matrix remains the sole authority for intent_id. "
        "Agents never authorise intent_id overrides. Authority untouched. "
        "Telemetry values are redacted on write. Auth and billing are flow names only."
    )
    assert prose_has_security_negative_markers(readme) is True
    paths = ["tests/fixtures/README.md"]
    assert has_security_path_evidence(paths) is False
    claims = security_claims_without_path_evidence(
        "🔐 chore(security): rotate secrets and credentials",
        paths,
    )
    assert "secrets" in claims
    assert "credentials" in claims
    cons = constraints_from_paths(paths)
    assert cons.forbid_security_primary is True


def test_product_src_allows_non_none_without_forcing_feat() -> None:
    dc = classify_diff_class(["src/git_cg/main.py"])
    assert dc.name == DIFF_CLASS_PRODUCT
    assert dc.has_runtime_surface is True
    cons = presentation_constraints(dc)
    assert cons.force_cc_type is None  # matrix owns product framing
    assert cons.force_semver is None or cons.force_semver != SemVerImpact.MAJOR


def test_empty_path_class_is_unknown_not_force_none() -> None:
    """Missing path evidence must not invent a pure non-product NONE envelope."""
    dc = classify_diff_class([])
    assert dc.name == DIFF_CLASS_EMPTY
    cons = presentation_constraints(dc)
    assert cons.diff_class == DIFF_CLASS_EMPTY
    assert cons.force_semver is None
    assert "PATCH" not in cons.forbid_semver
    assert "MINOR" not in cons.forbid_semver
    assert "MAJOR" not in cons.forbid_semver
    assert "empty_paths_unknown_no_semver_force" in cons.notes
    # Open ceiling: do not demote matrix PATCH/MINOR via presentation clamp.
    assert semver_presentation_ceiling([]) == SemVerImpact.MAJOR
    assert constraints_from_paths([]).force_semver is None


def test_constraints_from_paths_fallback_to_signals_files() -> None:
    """Empty staged list must recover concrete paths from DiffSignals.files."""
    signals = DiffSignals(files=["src/git_cg/intent.py", "tests/test_intent.py"])
    cons = constraints_from_paths([], signals=signals)
    assert cons.diff_class == DIFF_CLASS_MIXED
    assert cons.force_semver is None
    assert "PATCH" not in cons.forbid_semver
    assert semver_presentation_ceiling([], signals=signals) == SemVerImpact.PATCH


def test_product_plus_tests_preserves_patch_ceiling() -> None:
    paths = ["src/git_cg/regeneration.py", "tests/test_regeneration_contract.py"]
    dc = classify_diff_class(paths)
    assert dc.name == DIFF_CLASS_MIXED
    assert dc.has_runtime_surface is True
    cons = presentation_constraints(dc)
    assert cons.force_semver is None
    assert cons.force_cc_type is None
    assert semver_presentation_ceiling(paths) == SemVerImpact.PATCH


def test_build_generation_context_attaches_presentation_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from git_cg.main import _build_generation_context

    monkeypatch.setattr(
        "git_cg.main.extract_diff_signals",
        lambda _diff: DiffSignals(
            files=["docs/usage.md", "CHANGELOG.md"],
            only_docs=True,
            touches_docs=True,
        ),
    )
    monkeypatch.setattr("git_cg.main.rank_commit_intents", lambda *_a, **_k: [])
    monkeypatch.setattr(
        "git_cg.main.load_sop",
        lambda: {"gitmoji_reference_matrix": []},
    )

    ctx = _build_generation_context("diff --git a/x b/x\n", enable_semantic=False)
    assert isinstance(ctx.presentation_constraints, PresentationConstraints)
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_DOCS
    assert ctx.presentation_constraints.changelog_antisignal_applied is True
    assert ctx.presentation_constraints.force_semver == SemVerImpact.NONE


def test_build_generation_context_recovers_paths_when_signal_files_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second-chance path harvest from raw diff must avoid empty→NONE demotion."""
    from git_cg.main import _build_generation_context

    monkeypatch.setattr(
        "git_cg.main.extract_diff_signals",
        lambda _diff: DiffSignals(files=[]),
    )
    monkeypatch.setattr("git_cg.main.rank_commit_intents", lambda *_a, **_k: [])
    monkeypatch.setattr(
        "git_cg.main.load_sop",
        lambda: {"gitmoji_reference_matrix": []},
    )

    diff = (
        "diff --git a/src/git_cg/intent.py b/src/git_cg/intent.py\n"
        "--- a/src/git_cg/intent.py\n"
        "+++ b/src/git_cg/intent.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    ctx = _build_generation_context(diff, enable_semantic=False)
    assert ctx.presentation_constraints is not None
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_PRODUCT
    assert ctx.presentation_constraints.force_semver is None
    assert "src/git_cg/intent.py" in (ctx.diff_signals.files or [])


# ---------------------------------------------------------------------------
# Slice 2c — SemVer ceiling · type dominance · changelog allowlist · cardinality
# ---------------------------------------------------------------------------


def test_semver_ceiling_pure_docs_is_none() -> None:
    assert semver_presentation_ceiling(["docs/ADRs/0163.md", "docs/usage.md"]) == SemVerImpact.NONE


def test_semver_ceiling_s2_g1_internal_correctness_is_patch() -> None:
    paths = ["src/git_cg/telemetry.py", "src/git_cg/main.py", "tests/test_telemetry.py"]
    ceiling = semver_presentation_ceiling(
        paths,
        concern_tags={"correctness", "scrub_sentinel", "fallback_none_overwrite"},
    )
    assert ceiling == SemVerImpact.PATCH
    # never MAJOR without break markers
    assert ceiling != SemVerImpact.MAJOR


def test_semver_ceiling_s3_g1_correctness_forbids_minor_major() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/scoped_history.py"]
    ceiling = semver_presentation_ceiling(paths, concern_tags={"correctness", "parse_harden"})
    assert ceiling == SemVerImpact.PATCH


def test_semver_ceiling_dark_launch_feat_still_patch() -> None:
    paths = ["src/git_cg/semantic.py", "tests/test_semantic.py"]
    ceiling = semver_presentation_ceiling(
        paths,
        concern_tags={"free_harvest", "dark_launch"},
    )
    assert ceiling == SemVerImpact.PATCH


def test_semver_ceiling_operator_visible_allows_minor() -> None:
    paths = ["src/git_cg/main.py"]
    ceiling = semver_presentation_ceiling(
        paths,
        concern_tags={"operator_visible_capability"},
    )
    assert ceiling == SemVerImpact.MINOR


def test_semver_ceiling_contract_break_allows_major() -> None:
    paths = ["src/git_cg/models.py"]
    ceiling = semver_presentation_ceiling(
        paths,
        evidence_text="BREAKING CHANGE: public API removed from CommitPlan",
    )
    assert ceiling == SemVerImpact.MAJOR


def test_dominant_type_correctness_forces_fix() -> None:
    paths = ["src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"]
    cc = dominant_presentation_cc_type(
        paths,
        concern_tags={"correctness", "redaction_sentinel"},
    )
    assert cc == CommitType.FIX


def test_dominant_type_tests_only_forces_test() -> None:
    assert dominant_presentation_cc_type(["tests/test_foo.py"]) == CommitType.TEST


def test_changelog_groups_test_docs_require_both() -> None:
    required = required_changelog_groups(["test", "docs"])
    assert "Tests" in required
    assert "Documentation" in required
    assert changelog_groups_allowlisted(["test", "docs"], ["Tests", "Documentation"]) is True
    assert changelog_groups_allowlisted(["test", "docs"], ["Miscellaneous"]) is False


def test_changelog_groups_fix_requires_fixed_not_added_only() -> None:
    assert required_changelog_groups(["fix"], primary_cc_type="fix") == ["Fixed"]
    assert changelog_groups_allowlisted(["fix"], ["Fixed"], primary_cc_type="fix") is True
    assert changelog_groups_allowlisted(["fix"], ["Added"], primary_cc_type="fix") is False
    assert changelog_groups_allowlisted(["fix", "test"], ["Fixed", "Tests"], primary_cc_type="fix") is True


def test_min_bullets_prod_plus_test_is_at_least_two() -> None:
    n = min_included_change_bullets(
        ["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"],
        concern_tags={"correctness"},
    )
    assert n >= 2


def test_min_bullets_multi_concern_matches_concern_count() -> None:
    n = min_included_change_bullets(
        ["src/git_cg/telemetry.py"],
        concern_tags={"scrub_sentinel", "fallback_none_overwrite", "closed_enum"},
    )
    assert n >= 3


# ---------------------------------------------------------------------------
# Presentation overlay wiring (post-rank / post-LLM, presentation-only)
# ---------------------------------------------------------------------------


def _plan(
    *,
    intent_id: str = "feature_addition",
    gitmoji: str = "✨",
    cc_type: CommitType = CommitType.FEAT,
    scope: str | None = "api",
    description: str = "add something big",
    semver: SemVerImpact = SemVerImpact.MINOR,
    changelog: str = "Added",
    secondaries: list | None = None,
) -> CommitPlan:

    return CommitPlan(
        primary_intent=CommitIntent(
            intent_id=intent_id,
            gitmoji=gitmoji,
            cc_type=cc_type,
            scope=scope,
            description=description,
            semver_impact=semver,
            changelog_group=changelog,
        ),
        secondary_intents=secondaries or [],
        rationale="test",
        body_summary="test body",
    )


def test_apply_presentation_overlay_tests_only_forces_test_none_tests() -> None:
    from git_cg.commit_quality import apply_presentation_overlay
    from git_cg.models import CommitPlan

    paths = ["tests/test_foo.py", "tests/test_bar.py"]
    plan = _plan()
    ranked_intent_id = plan.primary_intent.intent_id
    out = apply_presentation_overlay(plan, paths=paths)

    assert isinstance(out, CommitPlan)
    assert out.primary_intent.intent_id == ranked_intent_id  # D1: identity preserved
    assert out.primary_intent.cc_type == CommitType.TEST
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Tests"
    assert out.primary_intent.scope == "test"
    rendered = out.render()
    assert "SemVer-Impact: NONE" in rendered
    assert "Change-Types: test" in rendered
    assert "Changelog-Groups: Tests" in rendered


def test_apply_presentation_overlay_docs_adr_only() -> None:
    from git_cg.commit_quality import apply_presentation_overlay

    paths = ["docs/ADRs/0163-phase9.md"]
    plan = _plan(cc_type=CommitType.FIX, semver=SemVerImpact.PATCH, changelog="Fixed", scope="main")
    intent_id = plan.primary_intent.intent_id
    out = apply_presentation_overlay(plan, paths=paths)

    assert out.primary_intent.intent_id == intent_id
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Documentation"
    assert out.primary_intent.scope == "adr"


def test_apply_presentation_overlay_correctness_caps_patch_and_fix() -> None:
    from git_cg.commit_quality import apply_presentation_overlay

    paths = ["src/git_cg/telemetry.py", "src/git_cg/main.py", "tests/test_telemetry.py"]
    plan = _plan(
        intent_id="feature_addition",
        cc_type=CommitType.FEAT,
        semver=SemVerImpact.MINOR,
        changelog="Added",
        scope="telemetry",
    )
    out = apply_presentation_overlay(
        plan,
        paths=paths,
        concern_tags={"correctness", "scrub_sentinel"},
    )

    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.cc_type == CommitType.FIX
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH
    assert out.primary_intent.changelog_group == "Fixed"
    # prod + test inventory must keep Fixed + Tests when a test secondary exists or is required
    groups = {out.primary_intent.changelog_group, *(s.changelog_group for s in out.secondary_intents)}
    assert "Fixed" in groups
    # Ceiling must never leave MINOR/MAJOR on correctness
    assert out.primary_intent.semver_impact != SemVerImpact.MINOR
    assert out.primary_intent.semver_impact != SemVerImpact.MAJOR


def test_apply_presentation_overlay_clamps_secondary_semver() -> None:
    from git_cg.commit_quality import apply_presentation_overlay
    from git_cg.models import CommitIntent

    secondary = CommitIntent(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        scope="api",
        description="extra feat",
        semver_impact=SemVerImpact.MAJOR,
        changelog_group="Added",
    )
    plan = _plan(secondaries=[secondary])
    out = apply_presentation_overlay(plan, paths=["docs/usage.md"])

    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.secondary_intents[0].semver_impact == SemVerImpact.NONE
    assert out.primary_intent.intent_id == "feature_addition"


def test_apply_presentation_overlay_scope_hint_when_missing() -> None:
    from git_cg.commit_quality import apply_presentation_overlay

    plan = _plan(scope=None, cc_type=CommitType.CHORE, semver=SemVerImpact.NONE, changelog="Miscellaneous")
    out = apply_presentation_overlay(plan, paths=["src/git_cg/telemetry.py"])
    # product_src soft priors may supply dominant module scope
    assert out.primary_intent.scope in {None, "telemetry"}
    if out.primary_intent.scope:
        assert out.primary_intent.scope == normalize_scope(out.primary_intent.scope)


def test_apply_presentation_overlay_preferred_scope_already_normalised_wins_soft_hint() -> None:
    """Directive scope (already applied pre-overlay) is kept unless path-class force_scope exists."""
    from git_cg.commit_quality import apply_presentation_overlay

    plan = _plan(
        scope="scoped-history",
        cc_type=CommitType.FIX,
        semver=SemVerImpact.PATCH,
        changelog="Fixed",
        intent_id="bug_fix",
        gitmoji="🐛",
    )
    out = apply_presentation_overlay(
        plan,
        paths=["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"],
        concern_tags={"correctness"},
    )
    # mixed/product has no force_scope — keep directive/canonical scope
    assert out.primary_intent.scope == "scoped-history"
    assert out.primary_intent.cc_type == CommitType.FIX
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH


def test_apply_presentation_overlay_does_not_call_ranker(monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg import intent as intent_mod
    from git_cg.commit_quality import apply_presentation_overlay

    def _boom(*_a, **_k):
        raise AssertionError("rank_commit_intents must not be called")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    plan = _plan()
    apply_presentation_overlay(plan, paths=["tests/test_x.py"])


def test_apply_presentation_overlay_preserves_intent_id_and_gitmoji() -> None:
    """Presentation may change type/SemVer/group, never ranked identity fields."""
    from git_cg.commit_quality import apply_presentation_overlay

    plan = _plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        semver=SemVerImpact.MINOR,
        changelog="Added",
        scope="commit-quality",
    )
    paths = ["src/git_cg/commit_quality.py", "tests/test_commit_quality.py"]
    out = apply_presentation_overlay(plan, paths=paths)

    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    # Mixed product+test ceiling clamps presentation SemVer without identity drift.
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH
    groups = {out.primary_intent.changelog_group, *(s.changelog_group for s in out.secondary_intents)}
    assert "Tests" in groups or any(s.cc_type == CommitType.TEST for s in out.secondary_intents)


def test_apply_presentation_overlay_forced_type_keeps_matrix_gitmoji() -> None:
    """Pure tests force presentation type/group but keep the ranked gitmoji."""
    from git_cg.commit_quality import apply_presentation_overlay

    plan = _plan(intent_id="feature_addition", gitmoji="✨")
    out = apply_presentation_overlay(plan, paths=["tests/test_foo.py"])
    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    assert out.primary_intent.cc_type == CommitType.TEST
    assert out.primary_intent.changelog_group == "Tests"
    assert out.primary_intent.semver_impact == SemVerImpact.NONE


def test_apply_presentation_overlay_changelog_allowlist_fix_test() -> None:
    from git_cg.commit_quality import apply_presentation_overlay
    from git_cg.models import CommitIntent

    secondary = CommitIntent(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type=CommitType.TEST,
        scope="test",
        description="cover overlay",
        semver_impact=SemVerImpact.NONE,
        changelog_group="Miscellaneous",
    )
    plan = _plan(
        intent_id="bug_fix",
        gitmoji="🐛",
        cc_type=CommitType.FIX,
        semver=SemVerImpact.PATCH,
        changelog="Fixed",
        scope="telemetry",
        secondaries=[secondary],
    )
    out = apply_presentation_overlay(
        plan,
        paths=["src/git_cg/telemetry.py", "tests/test_telemetry.py"],
        concern_tags={"correctness"},
    )
    types = [out.primary_intent.cc_type.value, *(s.cc_type.value for s in out.secondary_intents)]
    groups = [out.primary_intent.changelog_group, *(s.changelog_group for s in out.secondary_intents)]
    assert changelog_groups_allowlisted(types, groups, primary_cc_type=out.primary_intent.cc_type)


def test_changelog_antisignal_excludes_prose_from_content_signals() -> None:
    """D12: CHANGELOG.md prose must not feed security/fix content markers."""
    from git_cg.intent import extract_diff_signals

    diff = """diff --git a/docs/usage.md b/docs/usage.md
--- a/docs/usage.md
+++ b/docs/usage.md
@@ -1,3 +1,4 @@
+# Usage
+See docs.
diff --git a/CHANGELOG.md b/CHANGELOG.md
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -1,3 +1,6 @@
+# Changelog
+### Fixed
+- fix(telemetry): secret scanning password token credential leak
+- BREAKING CHANGE: public API removed
"""
    signals = extract_diff_signals(diff)
    # paths still include changelog for docs coverage
    assert any(p.lower().endswith("changelog.md") for p in signals.files)
    assert signals.touches_docs is True
    # prose-driven content markers must not fire from changelog alone
    assert signals.secret_scanning_changed is False
    assert signals.has_breaking_change is False


# ---------------------------------------------------------------------------
# Slice 4 — Included-change stubs (D5 / D18 / §K)
# ---------------------------------------------------------------------------


def test_stubs_single_surface_no_pressure() -> None:
    """Single product file, no multi-concern tags → empty stubs (no junk)."""
    stubs = build_included_change_stubs(["src/git_cg/scoped_history.py"])
    assert stubs == []


def test_stubs_single_fixture_no_pressure() -> None:
    stubs = build_included_change_stubs(["tests/fixtures/scoped_history/README.md"])
    assert stubs == []


def test_stubs_multi_test_modules_non_empty() -> None:
    paths = [
        "tests/test_scoped_history.py",
        "tests/test_scoped_history_telemetry.py",
        "tests/test_main.py",
        "tests/test_semantic.py",
    ]
    stubs = build_included_change_stubs(paths, claim_tags=["P9-A05", "P9-B07", "P9-B10"])
    assert stubs, "TIP-G1 multi-module tests must produce inventory pressure"
    roles = {s.role for s in stubs}
    assert "test" in roles
    notes = " ".join(s.note or "" for s in stubs)
    assert "test_scoped_history" in notes or "scoped_history" in notes
    # claim tags attached once
    claim_stubs = [s for s in stubs if s.claim_tags]
    assert claim_stubs
    assert list(claim_stubs[0].claim_tags) == ["P9-A05", "P9-B07", "P9-B10"]
    # pure tests never seed feat/fix capability
    assert all(s.suggested_cc_type == CommitType.TEST for s in stubs)


def test_stubs_tip_g4_multi_doc_surfaces() -> None:
    paths = ["docs/usage.md", "CHANGELOG.md", "DEVELOPMENT.md"]
    stubs = build_included_change_stubs(paths)
    assert stubs, "multi-doc surfaces must produce inventory"
    assert all(s.suggested_cc_type == CommitType.DOCS for s in stubs)
    surfaces = {s.surface for s in stubs}
    assert "usage" in surfaces or any("usage" in (s.note or "") for s in stubs)
    # no runtime recovery seeds from docs
    blob = " ".join(f"{s.note} {s.role}" for s in stubs).lower()
    assert "recover" not in blob
    assert "fail-open" not in blob or "document" in blob


def test_stubs_tip_g5_multi_concern_product() -> None:
    paths = ["src/git_cg/main.py", "src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"]
    tags = {
        "closed_enum",
        "correctness",
        "fallback_none_overwrite",
        "parser_batch_results",
        "redacted_sentinel",
        "scrub_vars",
    }
    stubs = build_included_change_stubs(paths, concern_tags=tags)
    assert len(stubs) >= 5
    notes = " ".join(s.note or "" for s in stubs).lower()
    assert "fallback_reason=none" in notes or "fallback" in notes
    assert "parser_batch_results" in notes
    assert "redacted" in notes
    assert "scrub" in notes
    # correctness → fix framing, not feat capability invention
    assert any(s.suggested_cc_type == CommitType.FIX for s in stubs)
    assert not any(s.suggested_cc_type == CommitType.FEAT for s in stubs)


def test_stubs_tip_g8_tests_adr_no_feat_minor() -> None:
    paths = [
        "tests/test_scoped_history.py",
        "docs/ADRs/0163-scoped-reasoning-history.md",
    ]
    stubs = build_included_change_stubs(paths)
    assert stubs
    roles = {s.role for s in stubs}
    assert "test" in roles
    assert "adr" in roles or "docs" in roles
    assert all(s.suggested_cc_type in {CommitType.TEST, CommitType.DOCS} for s in stubs)
    assert not any(s.suggested_cc_type in {CommitType.FEAT, CommitType.FIX} for s in stubs)


def test_stubs_tip_g9_prod_plus_test() -> None:
    paths = ["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"]
    tags = {"authority_leakage_ban", "correctness", "directive_verb_drop"}
    stubs = build_included_change_stubs(paths, concern_tags=tags)
    assert stubs
    roles = {s.role for s in stubs}
    assert "prod" in roles or any(s.role in {"prod", "telemetry"} for s in stubs)
    assert "test" in roles
    assert any(s.suggested_cc_type == CommitType.FIX for s in stubs)
    assert any(s.suggested_cc_type == CommitType.TEST for s in stubs)
    # hyphen behaviour scope preferred
    scopes = {s.scope for s in stubs if s.scope}
    assert "scoped-history" in scopes
    assert "scoped_history" not in scopes


def test_stubs_tip_g11_carry_through_no_phase_product_actor() -> None:
    paths = ["src/git_cg/main.py", "tests/test_semantic.py"]
    tags = {"elevation", "preflight_carry_through"}
    stubs = build_included_change_stubs(paths, concern_tags=tags)
    assert stubs
    blob = " ".join(s.note or "" for s in stubs).lower()
    assert "phase 0.5" not in blob
    assert "product" not in blob or "preflight" in blob
    roles = {s.role for s in stubs}
    assert "test" in roles
    scopes = {s.scope for s in stubs if s.scope}
    assert "scoped-history" in scopes


def test_stubs_tip_g12_docs_only_no_fix_runtime() -> None:
    paths = ["docs/ADRs/0163-scoped-reasoning-history.md", "docs/usage.md"]
    stubs = build_included_change_stubs(paths)
    assert stubs
    assert all(s.suggested_cc_type == CommitType.DOCS for s in stubs)
    assert all(s.role in {"docs", "adr"} for s in stubs)
    blob = " ".join(f"{s.note} {s.suggested_cc_type.value}" for s in stubs).lower()
    assert "fix" not in blob
    assert "recover" not in blob


def test_stubs_adr_rename_and_fixture_gpg_seeds() -> None:
    paths = [
        "tests/test_scoped_history.py",
        "tests/fixtures/scoped_history/README.md",
        "docs/ADRs/0163-scoped-reasoning-history.md",
        "docs/ADRs/index.md",
    ]
    stubs = build_included_change_stubs(paths)
    notes = " ".join(s.note or "" for s in stubs).lower()
    assert "adr" in notes or any(s.role == "adr" for s in stubs)
    assert any(s.role == "fixtures" for s in stubs)
    assert any(s.role == "test" for s in stubs)


def test_format_stub_inventory_empty() -> None:
    assert format_included_change_stub_inventory([]) == ""


def test_format_stub_inventory_lists_surfaces() -> None:
    stubs = build_included_change_stubs(
        ["src/git_cg/telemetry.py", "tests/test_telemetry.py"],
        concern_tags={"correctness", "redacted_sentinel"},
    )
    text = format_included_change_stub_inventory(stubs)
    assert "INCLUDED-CHANGES INVENTORY" in text
    assert "test" in text.lower()
    assert "cover" in text.lower() or "preserve" in text.lower()


def test_stub_frozen_and_role_validated() -> None:
    s = Stub(role="test", surface="scoped-history", suggested_cc_type=CommitType.TEST, note="x")
    with pytest.raises(ValueError):
        Stub(role="not-a-role", surface="x", suggested_cc_type=CommitType.TEST)
    assert s.role == "test"
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        s.role = "docs"  # type: ignore[misc]


def test_min_bullets_multi_test_modules_counts_modules() -> None:
    n = min_included_change_bullets(
        [
            "tests/test_scoped_history.py",
            "tests/test_scoped_history_telemetry.py",
            "tests/test_main.py",
            "tests/test_semantic.py",
        ]
    )
    assert n >= 4


# ---------------------------------------------------------------------------
# Slice 5 — Low-confidence presentation posture (D7)
# ---------------------------------------------------------------------------


def _low_conf(*reasons: str, level: str = "low"):
    from git_cg.ranking_confidence import RankingConfidence

    return RankingConfidence(
        level=level,  # type: ignore[arg-type]
        margin=4.0,
        top_intent_id="feature_addition",
        runner_up_intent_id="bug_fix",
        reasons=tuple(reasons),  # type: ignore[arg-type]
    )


def _lc_intent(**kwargs):
    """Build CommitIntent without SOP matrix rewrite (presentation tests)."""
    payload = {
        "intent_id": "feature_addition",
        "gitmoji": "✨",
        "cc_type": CommitType.FEAT,
        "scope": "api",
        "description": "add thing",
        "semver_impact": SemVerImpact.MINOR,
        "changelog_group": "Added",
    }
    payload.update(kwargs)
    return CommitIntent.model_construct(**payload)


def _lc_plan(primary=None, **kwargs):
    """Build CommitPlan without matrix rewrite on nested intents."""
    payload = {
        "primary_intent": primary if primary is not None else _lc_intent(),
        "secondary_intents": [],
        "split_recommended": False,
        "rationale": "r",
        "body_summary": None,
        "breaking_change": False,
        "breaking_change_description": None,
    }
    payload.update(kwargs)
    return CommitPlan.model_construct(**payload)


def _has_context_changes_section_headers(text: str) -> bool:
    """True when text teaches banned Context:/Changes: section headers (not ban mentions)."""
    return bool(
        re.search(r"(?m)^Context:\s*$", text)
        or re.search(r"(?m)^Changes:\s*$", text)
        or re.search(r"(?m)^Context:\s+\S", text)
        or re.search(r"(?m)^Changes:\s+\S", text)
        or "Structure body_summary with Context/Changes prose only" in text
        or "BODY_SUMMARY STRUCTURE ONLY (Context/Changes prose" in text
    )


@pytest.mark.parametrize("reason", sorted(LOW_CONFIDENCE_TRIGGER_REASONS))
def test_low_confidence_posture_triggers_on_each_v1_reason(reason: str) -> None:
    conf = _low_conf(reason)
    assert is_low_confidence_posture(conf) is True
    priors = derive_trailer_priors(["tests/test_x.py"])
    adj = apply_low_confidence_presentation(None, conf, priors)
    assert adj.active is True
    assert adj.fallback_reason == PRESENTATION_FALLBACK_LOW_CONFIDENCE
    # Hybrid-safe: must NOT teach banned Context:/Changes: headers (Session 12 / Opik G1).
    assert not _has_context_changes_section_headers(adj.body_skeleton)
    assert "Do NOT use `Context:` or `Changes:`" in adj.body_skeleton
    # Skeleton teaches body_summary only; final Included changes is secondary_intents-owned.
    assert "Included changes:" not in adj.body_skeleton.split("Do NOT put an `Included changes:`")[0]
    assert "body_summary" in adj.body_skeleton.lower() or "BODY_SUMMARY" in adj.body_skeleton
    assert "- cover each distinct" not in adj.body_skeleton
    assert "[tests/" not in adj.body_skeleton


def test_low_confidence_unknown_reason_does_not_activate() -> None:
    conf = _low_conf()  # empty reasons
    # Build with a non-v1 reason via model_construct if needed
    from git_cg.ranking_confidence import RankingConfidence

    conf = RankingConfidence.model_construct(
        level="low",
        margin=1.0,
        top_intent_id="feature_addition",
        runner_up_intent_id=None,
        reasons=("not_a_v1_reason",),
    )
    assert is_low_confidence_posture(conf) is False
    priors = derive_trailer_priors(["tests/test_x.py"])
    adj = apply_low_confidence_presentation(None, conf, priors)
    assert adj.active is False
    assert adj.fallback_reason == PRESENTATION_FALLBACK_NONE


def test_low_confidence_none_confidence_inactive() -> None:
    priors = derive_trailer_priors(["docs/usage.md"])
    adj = apply_low_confidence_presentation(None, None, priors)
    assert adj.active is False


def test_generic_feature_presentation_definition() -> None:
    generic = _lc_plan(_lc_intent(semver_impact=SemVerImpact.MINOR))
    assert is_generic_feature_presentation(generic) is True
    assert is_generic_feature_presentation(None) is True
    # feat+NONE is generic too: model over-demotes SemVer under low confidence.
    none_feat = _lc_plan(_lc_intent(semver_impact=SemVerImpact.NONE))
    assert is_generic_feature_presentation(none_feat) is True
    non = _lc_plan(_lc_intent(semver_impact=SemVerImpact.PATCH))
    assert is_generic_feature_presentation(non) is False


def test_low_confidence_feat_none_repaired_to_patch() -> None:
    # Product/mixed low confidence: the model over-demotes feat to NONE after
    # reading the uncertainty guidance. feat+NONE must be recognised as generic
    # so the deterministic PATCH seed repairs it instead of NONE surviving.
    paths = ["src/git_cg/commit_quality.py", "tests/test_commit_quality.py"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("mixed_intent")
    plan = _lc_plan(_lc_intent(scope="commit_quality", description="add posture", semver_impact=SemVerImpact.NONE))

    adj = apply_low_confidence_presentation(plan, conf, priors)
    assert adj.active and adj.seed_presentation is True
    assert adj.semver_impact == SemVerImpact.PATCH

    out = apply_presentation_seed(plan, adj)
    out = apply_presentation_overlay(out, paths=paths, priors=priors)

    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    assert out.primary_intent.cc_type == CommitType.FEAT
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH
    assert out.primary_intent.semver_impact != SemVerImpact.NONE


def test_low_confidence_tests_only_seeds_test_none_not_feat_minor() -> None:
    paths = ["tests/test_scope_canon.py", "tests/test_commit_quality.py"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("margin_below_low_threshold")
    generic = _lc_plan(_lc_intent(scope="git_cg", description="add capability", semver_impact=SemVerImpact.MINOR))
    adj = apply_low_confidence_presentation(generic, conf, priors)
    assert adj.active and adj.seed_presentation
    assert adj.cc_type == CommitType.TEST
    assert adj.semver_impact == SemVerImpact.NONE
    assert adj.changelog_group == "Tests"
    out = apply_presentation_seed(generic, adj)
    out = apply_presentation_overlay(out, paths=paths, priors=priors)
    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.gitmoji == "✨"
    assert out.primary_intent.cc_type == CommitType.TEST
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Tests"
    assert not (
        out.primary_intent.cc_type == CommitType.FEAT and out.primary_intent.semver_impact == SemVerImpact.MINOR
    )


def test_low_confidence_docs_adr_seeds_docs_none() -> None:
    paths = ["docs/ADRs/ADR-0163-scoped-history.md", "docs/usage.md"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("mixed_intent")
    generic = _lc_plan(_lc_intent(scope=None, description="add docs feature", semver_impact=SemVerImpact.MINOR))
    adj = apply_low_confidence_presentation(generic, conf, priors)
    out = apply_presentation_seed(generic, adj)
    out = apply_presentation_overlay(out, paths=paths, priors=priors)
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Documentation"
    assert out.primary_intent.intent_id == "feature_addition"


def test_low_confidence_dark_launch_no_unearned_minor() -> None:
    paths = ["src/git_cg/semantic.py", "tests/test_semantic.py"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("near_tie_top3")
    plan = _lc_plan(_lc_intent(scope="semantic", description="harvest free fields", semver_impact=SemVerImpact.MINOR))
    adj = apply_low_confidence_presentation(plan, conf, priors)
    assert adj.active
    # product_src/mixed: seed only when generic feat+MINOR
    assert adj.seed_presentation is True
    out = apply_presentation_seed(plan, adj)
    out = apply_presentation_overlay(
        out,
        paths=paths,
        priors=priors,
        concern_tags={"dark_launch", "free_harvest"},
    )
    assert out.primary_intent.semver_impact != SemVerImpact.MINOR
    assert out.primary_intent.semver_impact != SemVerImpact.MAJOR
    assert out.primary_intent.intent_id == "feature_addition"


def test_low_confidence_carry_through_patch_changed_scope() -> None:
    paths = ["src/git_cg/main.py", "tests/test_main.py"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("exact_tie_top")
    plan = _lc_plan(_lc_intent(scope="semantic", description="wire preflight carry", semver_impact=SemVerImpact.MINOR))
    adj = apply_low_confidence_presentation(plan, conf, priors)
    out = apply_presentation_seed(plan, adj)
    out = apply_presentation_overlay(
        out,
        paths=paths,
        priors=priors,
        concern_tags={"carry_through", "preflight_carry"},
    )
    assert out.primary_intent.semver_impact == SemVerImpact.PATCH
    assert out.primary_intent.changelog_group == "Changed"
    assert out.primary_intent.intent_id == "feature_addition"


def test_low_confidence_skeleton_deterministic_and_complete() -> None:
    priors = derive_trailer_priors(["tests/test_a.py", "tests/test_b.py"])
    stubs = build_included_change_stubs(
        ["tests/test_a.py", "tests/test_b.py"],
        None,
        None,
    )
    sk1 = build_low_confidence_body_skeleton(priors=priors, stubs=stubs)
    sk2 = build_low_confidence_body_skeleton(priors=priors, stubs=stubs)
    assert sk1 == sk2
    # Must stay Hybrid-safe — never teach banned Context:/Changes: headers.
    assert not _has_context_changes_section_headers(sk1)
    assert "plain Hybrid prose" in sk1 or "plain-prose" in sk1
    assert "Do NOT use `Context:` or `Changes:`" in sk1
    # Must not teach a final Included-changes prose block inside body_summary.
    assert sk1.count("Included changes:") == 0 or "Do NOT put an `Included changes:`" in sk1
    assert not any(line.startswith("- [") or line.startswith("- cover each distinct") for line in sk1.splitlines())
    # No inventory bullets promoted under an Included changes heading.
    assert "INCLUDED-CHANGES INVENTORY" not in sk1
    guidance = format_low_confidence_guidance(
        PresentationAdjustment(
            active=True,
            fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
            seed_presentation=True,
            cc_type=CommitType.TEST,
            semver_impact=SemVerImpact.NONE,
            changelog_group="Tests",
            scope_hint="test",
            body_skeleton=sk1,
            role="tests",
        )
    )
    assert "LOW-CONFIDENCE BODY SKELETON" in guidance
    assert "preferred_type" not in guidance.split("MUST NOT set preferred_type")[0]
    assert not _has_context_changes_section_headers(guidance)
    assert "Do NOT use `Context:` or `Changes:`" in guidance
    assert "exactly one" in guidance.lower()
    assert "Hybrid mini-subject" in guidance
    assert "second" in guidance.lower() and "Included changes" in guidance
    assert "`- <emoji> <cc_type>(<scope>): <subject>`" in guidance
    # inactive → empty
    assert format_low_confidence_guidance(PresentationAdjustment()) == ""


def test_low_confidence_skeleton_rejects_prose_included_changes_bullets() -> None:
    """Regression: Slice 5 must not teach hook-illegal prose nested bullets."""
    priors = derive_trailer_priors(["src/git_cg/commit_quality.py", "tests/test_commit_quality.py"])
    stubs = build_included_change_stubs(
        ["src/git_cg/commit_quality.py", "tests/test_commit_quality.py"],
        None,
        None,
    )
    skeleton = build_low_confidence_body_skeleton(priors=priors, stubs=stubs)
    guidance = format_low_confidence_guidance(
        PresentationAdjustment(
            active=True,
            fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
            body_skeleton=skeleton,
            role=priors.role,
        )
    )
    # Skeleton itself must not contain a literal Included changes section with bullets.
    assert "\nIncluded changes:\n-" not in f"\n{skeleton}\n"
    assert "- cover each distinct staged surface" not in skeleton
    assert "- [" not in skeleton
    assert not _has_context_changes_section_headers(skeleton)
    # Guidance must forbid duplicate headings and require Hybrid shape.
    assert "exactly one" in guidance.lower()
    assert "Never emit plain prose bullets" in guidance or "never emit plain prose bullets" in guidance.lower()
    assert "inventory" in guidance.lower()
    assert "Do NOT use `Context:` or `Changes:`" in guidance
    assert not _has_context_changes_section_headers(guidance)


def test_strip_included_changes_from_body_summary_removes_leaked_section() -> None:
    leaked = (
        "Context:\n"
        "Ranking confidence may fall below thresholds.\n"
        "\n"
        "Changes:\n"
        "Implement Slice 5 logic.\n"
        "\n"
        "Included changes:\n"
        "- Add `PresentationAdjustment` dataclass and confidence trigger checks\n"
        "- Implement body skeleton builder and presentation seed applier\n"
        "- Cover new logic with unit tests for trigger reasons\n"
    )
    cleaned = strip_included_changes_from_body_summary(leaked)
    assert cleaned is not None
    assert "Included changes:" not in cleaned
    assert "PresentationAdjustment" not in cleaned
    assert "Context:" in cleaned
    assert "Implement Slice 5 logic." in cleaned
    assert strip_included_changes_from_body_summary(None) is None
    assert strip_included_changes_from_body_summary("plain body") == "plain body"


def test_apply_presentation_seed_strips_leaked_included_changes_when_active() -> None:
    plan = _lc_plan(
        _lc_intent(scope="commit_quality", description="implement low-confidence posture"),
        body_summary=(
            "Context:\nUncertainty under low ranking confidence.\n\n"
            "Changes:\nAdd presentation posture.\n\n"
            "Included changes:\n"
            "- Add PresentationAdjustment dataclass\n"
            "- Cover new logic with unit tests\n"
        ),
        secondary_intents=[
            _lc_intent(
                intent_id="tests_update",
                gitmoji="✅",
                cc_type=CommitType.TEST,
                scope="commit_quality",
                description="add unit tests for Slice 5 logic",
                semver_impact=SemVerImpact.NONE,
                changelog_group="Tests",
            )
        ],
    )
    adj = PresentationAdjustment(
        active=True,
        fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
        seed_presentation=False,
        body_skeleton=(
            "BODY_SUMMARY STRUCTURE ONLY (plain Hybrid prose — never final Included changes):\n"
            "- Write body_summary as plain prose only.\n"
            "- Do NOT use `Context:` or `Changes:` section headers anywhere in body_summary."
        ),
        role="mixed",
    )
    out = apply_presentation_seed(plan, adj)
    assert out.body_summary is not None
    assert "Included changes:" not in out.body_summary
    rendered = out.render()
    assert rendered.count("Included changes:") == 1
    assert "✅ test(commit_quality): add unit tests for Slice 5 logic" in rendered
    assert "Add PresentationAdjustment dataclass" not in rendered


def test_low_confidence_does_not_call_ranker(monkeypatch: pytest.MonkeyPatch) -> None:
    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("rank_commit_intents must not be called")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    priors = derive_trailer_priors(["tests/test_x.py"])
    conf = _low_conf("margin_below_low_threshold", "mixed_intent")
    apply_low_confidence_presentation(None, conf, priors)
    apply_presentation_seed(
        _lc_plan(_lc_intent(scope=None, description="x", semver_impact=SemVerImpact.MINOR)),
        apply_low_confidence_presentation(None, conf, priors),
    )


def test_low_confidence_preserves_confidence_pair_identity() -> None:
    conf = _low_conf("margin_below_low_threshold")
    reasons_before = conf.reasons
    top_before = conf.top_intent_id
    priors = derive_trailer_priors(["docs/usage.md"])
    apply_low_confidence_presentation(None, conf, priors)
    assert conf.reasons is reasons_before
    assert conf.top_intent_id == top_before
    assert conf.level == "low"


def test_low_confidence_tip_g2_fixtures_no_security_primary() -> None:
    """TIP-G2: fixture README under Low must not become security/feat+MINOR."""
    paths = ["tests/fixtures/scoped_history/README.md"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("margin_below_low_threshold")
    generic = _lc_plan(
        _lc_intent(
            scope="fixtures",
            description="add or update secrets",
            semver_impact=SemVerImpact.MINOR,
            changelog_group="Security",
        )
    )
    adj = apply_low_confidence_presentation(generic, conf, priors)
    out = apply_presentation_seed(generic, adj)
    out = apply_presentation_overlay(out, paths=paths, priors=priors)
    assert out.primary_intent.intent_id == "feature_addition"
    assert out.primary_intent.cc_type == CommitType.TEST
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Tests"
    assert out.primary_intent.changelog_group.lower() != "security"
    assert out.primary_intent.cc_type != CommitType.CHORE or out.primary_intent.changelog_group != "Security"


def test_low_confidence_tip_g3_adr_no_security_primary() -> None:
    """TIP-G3: ADR-only under Low must not become security chore + PATCH."""
    paths = ["docs/ADRs/ADR-0163-scoped-history.md", "docs/ADRs/index.md"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("mixed_intent")
    generic = _lc_plan(
        _lc_intent(
            scope="adr",
            description="update secrets policy",
            cc_type=CommitType.CHORE,
            semver_impact=SemVerImpact.PATCH,
            changelog_group="Security",
        )
    )
    # Even non-generic chore+PATCH security: forced adr role still seeds docs/NONE.
    adj = apply_low_confidence_presentation(generic, conf, priors)
    assert adj.active and adj.seed_presentation
    assert adj.cc_type == CommitType.DOCS
    out = apply_presentation_seed(generic, adj)
    out = apply_presentation_overlay(out, paths=paths, priors=priors)
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Documentation"
    assert out.primary_intent.changelog_group.lower() != "security"
    assert out.primary_intent.intent_id == "feature_addition"


def test_low_confidence_config_ci_seeds_chore_none() -> None:
    paths = [".github/workflows/ci.yml"]
    priors = derive_trailer_priors(paths)
    conf = _low_conf("near_tie_top3")
    generic = _lc_plan(_lc_intent(scope="ci", description="add pipeline", semver_impact=SemVerImpact.MINOR))
    adj = apply_low_confidence_presentation(generic, conf, priors)
    assert adj.active and adj.seed_presentation
    assert adj.role == "config_ci"
    out = apply_presentation_seed(generic, adj)
    out = apply_presentation_overlay(out, paths=paths, priors=priors)
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.cc_type in {CommitType.CHORE, CommitType.CI}
    assert not (
        out.primary_intent.cc_type == CommitType.FEAT and out.primary_intent.semver_impact == SemVerImpact.MINOR
    )
    assert out.primary_intent.intent_id == "feature_addition"


def test_low_confidence_medium_high_does_not_seed() -> None:
    priors = derive_trailer_priors(["tests/test_x.py"])
    for level in ("medium", "high"):
        conf = _low_conf("margin_below_low_threshold", level=level)
        # reasons alone are not enough without being the low posture owner —
        # is_low_confidence_posture keys off reasons only (v1 codes), so medium
        # with a low reason still activates. Guard the level-only path via empty reasons.
        from git_cg.ranking_confidence import RankingConfidence

        conf = RankingConfidence(
            level=level,  # type: ignore[arg-type]
            margin=20.0,
            top_intent_id="feature_addition",
            runner_up_intent_id="bug_fix",
            reasons=(),
        )
        adj = apply_low_confidence_presentation(None, conf, priors)
        assert adj.active is False, level


def test_low_confidence_skeleton_never_teaches_context_changes_headers() -> None:
    """Session 12 / Opik: LC skeleton must not reintroduce GUARD_CONTEXT_CHANGES_TEMPLATE."""
    priors = derive_trailer_priors(["src/git_cg/intent.py", "tests/test_intent.py"])
    skeleton = build_low_confidence_body_skeleton(priors=priors)
    guidance = format_low_confidence_guidance(
        PresentationAdjustment(
            active=True,
            fallback_reason=PRESENTATION_FALLBACK_LOW_CONFIDENCE,
            body_skeleton=skeleton,
            role=priors.role,
        )
    )
    for blob in (skeleton, guidance):
        assert not _has_context_changes_section_headers(blob)
        assert "Do NOT use `Context:` or `Changes:`" in blob


def test_format_guard_guidance_emphasises_context_changes_ban() -> None:
    from git_cg.commit_quality import GuardFinding, GuardReport, format_guard_guidance

    report = GuardReport(
        findings=[
            GuardFinding(
                code="GUARD_CONTEXT_CHANGES_TEMPLATE",
                message="Body uses banned Context:/Changes: template",
                kind="hallucination",
                token="Context:/Changes:",
            )
        ]
    )
    text = format_guard_guidance(report)
    assert "GUARD_CONTEXT_CHANGES_TEMPLATE" in text
    assert "must NOT use `Context:` or `Changes:`" in text
    assert "plain Hybrid prose" in text


def test_build_system_prompt_includes_low_confidence_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.main import build_system_prompt

    monkeypatch.setattr("git_cg.main.load_sop", lambda: {})
    prompt = build_system_prompt(
        "diff --git a/x b/x\n",
        ranked_candidates=[],
        low_confidence_guidance=(
            "LOW-CONFIDENCE BODY SKELETON (wording structure only — does not change "
            "intent_id / gitmoji authority):\n"
            "Write body_summary as plain Hybrid prose only.\n"
            "Do NOT use `Context:` or `Changes:` section headers in body_summary.\n"
            "Emit exactly one Included changes section via secondary_intents."
        ),
    )
    assert "LOW-CONFIDENCE BODY SKELETON" in prompt
    assert "plain Hybrid prose" in prompt
    assert "Do NOT use `Context:` or `Changes:`" in prompt
    # Prompt may mention the ban; it must not teach a Context:/Changes: skeleton block.
    assert "Context:\n- sample" not in prompt


# ---------------------------------------------------------------------------
# Slice 6 — Contract-aware high-risk body checklist (D6 / D20)
# ---------------------------------------------------------------------------


def test_detect_high_risk_surfaces_exact_and_suffix() -> None:
    surfaces = detect_high_risk_surfaces(
        [
            "src/git_cg/telemetry.py",
            "src/git_cg/sentry_config.py",
            "docs/usage.md",
            "tests/test_telemetry.py",
        ]
    )
    assert surfaces == ("sentry_config", "telemetry")
    assert is_high_risk_path_set(["src/git_cg/main.py"]) is True
    assert is_high_risk_path_set(["docs/ADRs/0001.md", "tests/test_x.py"]) is False


def test_docs_authority_prose_is_not_high_risk_path() -> None:
    """D13: docs/ADR mentions of authority/redaction are not high-risk path evidence."""
    paths = [
        "docs/ADRs/0163-scoped-history.md",
        "docs/usage.md",
        "CHANGELOG.md",
    ]
    assert detect_high_risk_surfaces(paths) == ()
    assert format_high_risk_body_checklist(paths) == ""


def test_telemetry_themes_include_d20_must_cover() -> None:
    themes = build_high_risk_checklist_themes(["src/git_cg/telemetry.py"])
    for required in (
        "telemetry_fallback_transitions",
        "telemetry_closed_enum_tags",
        "telemetry_scrub_list_deltas",
        "telemetry_redaction_failure_token",
        "telemetry_no_secret_leakage",
    ):
        assert required in themes, required

    text = format_high_risk_body_checklist(["src/git_cg/telemetry.py"])
    assert "HIGH-RISK BODY CHECKLIST" in text
    assert "[REDACTED]" in text
    assert "pre-populated `none`" in text
    assert "preferred_type" in text  # explicit ban language
    assert "does not set preferred_type" in text


def test_main_and_scoped_history_themes() -> None:
    themes = build_high_risk_checklist_themes(["src/git_cg/main.py", "src/git_cg/scoped_history.py"])
    assert "main_channel4_directive_free" in themes
    assert "main_fallback_error_visibility" in themes
    assert "scoped_history_policy_b_lifetime" in themes
    # D20 producer orchestration themes also apply via main.
    assert "telemetry_fallback_transitions" in themes


def test_intent_and_secrets_themes() -> None:
    assert "intent_closed_enrichment_markers" in build_high_risk_checklist_themes(["src/git_cg/intent.py"])
    secrets_themes = build_high_risk_checklist_themes(["src/git_cg/secrets.py"])
    assert "secrets_path_handling" in secrets_themes
    assert "telemetry_no_secret_leakage" in secrets_themes


def test_high_risk_checklist_absent_for_low_risk_paths() -> None:
    assert format_high_risk_body_checklist(["tests/test_commit_quality.py"]) == ""
    assert format_high_risk_body_checklist([]) == ""
    assert format_high_risk_body_checklist(None) == ""


def test_v12_a06_high_risk_prompt_checklist_directive_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Checklist present for high-risk paths; directive extractor gains no preferred_type."""
    from git_cg.main import ReviewState, build_system_prompt

    monkeypatch.setattr("git_cg.main.load_sop", lambda: {})

    high_risk_prompt = build_system_prompt(
        "diff --git a/src/git_cg/telemetry.py b/src/git_cg/telemetry.py\n",
        ranked_candidates=[],
        staged_paths=["src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"],
    )
    assert "HIGH-RISK BODY CHECKLIST" in high_risk_prompt
    assert "telemetry_redaction_failure_token" in high_risk_prompt
    assert "[REDACTED]" in high_risk_prompt
    assert "does not set preferred_type" in high_risk_prompt

    low_risk_prompt = build_system_prompt(
        "diff --git a/docs/usage.md b/docs/usage.md\n",
        ranked_candidates=[],
        staged_paths=["docs/usage.md", "tests/test_x.py"],
    )
    assert "HIGH-RISK BODY CHECKLIST" not in low_risk_prompt

    # Channel-4 invariant: feeding checklist text through directive extraction
    # must not produce preferred_type / preferred_scope steers.
    checklist = format_high_risk_body_checklist(
        ["src/git_cg/main.py", "src/git_cg/telemetry.py", "src/git_cg/scoped_history.py"]
    )
    assert checklist
    state = ReviewState(commit_plan=None, regeneration_guidance=None)  # type: ignore[arg-type]
    directives, residual = state._extract_directives(checklist)
    assert "preferred_type" not in directives
    assert "preferred_scope" not in directives
    # Residual may retain checklist prose; that is fine — it is not a steer.
    assert residual is None or "preferred_type" not in (directives or {})


def test_high_risk_checklist_deterministic() -> None:
    paths = ["src/git_cg/sentry_config.py", "src/git_cg/telemetry.py", "src/git_cg/main.py"]
    a = format_high_risk_body_checklist(paths)
    b = format_high_risk_body_checklist(list(reversed(paths)))
    assert a == b
    assert build_high_risk_checklist_themes(paths) == build_high_risk_checklist_themes(list(reversed(paths)))


# ---------------------------------------------------------------------------
# Issue #204 Slice 7 — CommitBlueprint parse / validate / apply
# ---------------------------------------------------------------------------


def test_commit_blueprint_rejects_unknown_field() -> None:
    import pytest
    from pydantic import ValidationError

    from git_cg.models import CommitBlueprint

    with pytest.raises(ValidationError):
        CommitBlueprint.model_validate({"cc_type": "docs", "unknown": 1})


def test_commit_blueprint_rejects_unknown_enum() -> None:
    import pytest
    from pydantic import ValidationError

    from git_cg.models import CommitBlueprint

    with pytest.raises(ValidationError):
        CommitBlueprint.model_validate({"cc_type": "not-a-type"})


def test_blueprint_stub_rejects_path_surface_and_bad_role() -> None:
    import pytest
    from pydantic import ValidationError

    from git_cg.models import BlueprintStub

    with pytest.raises(ValidationError):
        BlueprintStub(role="docs", surface="docs/ADRs/x")
    with pytest.raises(ValidationError):
        BlueprintStub(role="nope", surface="adr")


def test_parse_commit_blueprint_inline_json() -> None:
    from git_cg.commit_quality import parse_commit_blueprint
    from git_cg.models import CommitType, SemVerImpact

    bp = parse_commit_blueprint(
        '{"cc_type":"docs","scope":"adr","semver_impact":"NONE","changelog_groups":["Documentation"]}'
    )
    assert bp.cc_type == CommitType.DOCS
    assert bp.scope == "adr"
    assert bp.semver_impact == SemVerImpact.NONE
    assert bp.changelog_groups is not None
    assert bp.changelog_groups[0].value == "Documentation"


def test_parse_commit_blueprint_from_file(tmp_path, monkeypatch) -> None:
    from git_cg.commit_quality import parse_commit_blueprint
    from git_cg.models import CommitType

    monkeypatch.chdir(tmp_path)
    bp_path = tmp_path / "bp.json"
    bp_path.write_text('{"cc_type":"docs","scope":"adr"}', encoding="utf-8")
    bp = parse_commit_blueprint(f"@{bp_path.name}", repo_root=tmp_path, cwd=tmp_path)
    assert bp.cc_type == CommitType.DOCS
    assert bp.scope == "adr"


def test_load_blueprint_rejects_path_escape(tmp_path, monkeypatch) -> None:
    import pytest

    from git_cg.commit_quality import BlueprintError, load_blueprint_source

    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside-bp.json"
    outside.write_text('{"cc_type":"docs"}', encoding="utf-8")
    with pytest.raises(BlueprintError) as ei:
        load_blueprint_source(f"@{outside}", repo_root=tmp_path, cwd=tmp_path)
    assert ei.value.kind == "error"


def test_load_blueprint_rejects_oversized_inline() -> None:
    import pytest

    from git_cg.commit_quality import BLUEPRINT_MAX_BYTES, BlueprintError, load_blueprint_source

    huge = '{"cc_type":"docs","subject_hint":"' + ("x" * (BLUEPRINT_MAX_BYTES + 10)) + '"}'
    with pytest.raises(BlueprintError) as ei:
        load_blueprint_source(huge)
    assert ei.value.kind == "error"


def test_load_blueprint_rejects_symlink_escape(tmp_path, monkeypatch) -> None:
    import os

    import pytest

    from git_cg.commit_quality import BlueprintError, load_blueprint_source

    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / f"outside-symlink-target-{os.getpid()}.json"
    outside.write_text('{"cc_type":"docs"}', encoding="utf-8")
    link = tmp_path / "escape.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not permitted")
    try:
        with pytest.raises(BlueprintError) as ei:
            load_blueprint_source(f"@{link.name}", repo_root=tmp_path, cwd=tmp_path)
        assert ei.value.kind == "error"
    finally:
        # leave outside file; do not delete without trash — tests use tmp
        pass


def test_validate_blueprint_rejects_illegal_adr_feat_minor() -> None:
    import pytest

    from git_cg.commit_quality import (
        BlueprintError,
        classify_diff_class,
        presentation_constraints,
        validate_blueprint_against_constraints,
    )
    from git_cg.models import CommitBlueprint, CommitType, SemVerImpact

    paths = ["docs/ADRs/0204-slice7.md"]
    cons = presentation_constraints(classify_diff_class(paths))
    bp = CommitBlueprint(
        cc_type=CommitType.FEAT,
        scope="api",
        semver_impact=SemVerImpact.MINOR,
    )
    with pytest.raises(BlueprintError) as ei:
        validate_blueprint_against_constraints(bp, cons, ceiling=SemVerImpact.NONE)
    assert ei.value.kind == "blueprint"


def test_apply_blueprint_legal_adr_docs_none() -> None:
    from git_cg.commit_quality import apply_blueprint, classify_diff_class, presentation_constraints
    from git_cg.models import ChangelogGroup, CommitBlueprint, CommitType, SemVerImpact

    paths = ["docs/ADRs/0204-slice7.md"]
    cons = presentation_constraints(classify_diff_class(paths))
    plan = _plan(cc_type=CommitType.FIX, semver=SemVerImpact.PATCH, changelog="Fixed", scope="main")
    ranked_id = plan.primary_intent.intent_id
    ranked_gitmoji = plan.primary_intent.gitmoji
    bp = CommitBlueprint(
        cc_type=CommitType.DOCS,
        scope="adr",
        semver_impact=SemVerImpact.NONE,
        changelog_groups=[ChangelogGroup.DOCUMENTATION],
        subject_hint="document slice 7 blueprint overlay",
    )
    state = apply_blueprint(plan, bp, cons, ceiling=SemVerImpact.NONE, paths=paths)
    assert state.blueprint_applied is True
    out = state.plan
    assert out.primary_intent.intent_id == ranked_id
    assert out.primary_intent.gitmoji == ranked_gitmoji
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.scope == "adr"
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert out.primary_intent.changelog_group == "Documentation"
    assert "document slice 7" in out.primary_intent.description


def test_apply_blueprint_path_class_envelope_wins_over_blueprint() -> None:
    """Path-class force remains authoritative when blueprint agrees after validate."""
    from git_cg.commit_quality import (
        apply_blueprint,
        apply_presentation_overlay,
        classify_diff_class,
        presentation_constraints,
    )
    from git_cg.models import ChangelogGroup, CommitBlueprint, CommitType, SemVerImpact

    paths = ["docs/ADRs/0204-slice7.md"]
    cons = presentation_constraints(classify_diff_class(paths))
    plan = _plan(cc_type=CommitType.CHORE, semver=SemVerImpact.NONE, changelog="Miscellaneous")
    ranked_id = plan.primary_intent.intent_id
    bp = CommitBlueprint(
        cc_type=CommitType.DOCS,
        scope="adr",
        semver_impact=SemVerImpact.NONE,
        changelog_groups=[ChangelogGroup.DOCUMENTATION],
    )
    state = apply_blueprint(plan, bp, cons, ceiling=SemVerImpact.NONE, paths=paths)
    out = apply_presentation_overlay(state.plan, paths=paths, constraints=cons)
    assert out.primary_intent.intent_id == ranked_id
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.scope == "adr"
    assert out.primary_intent.semver_impact == SemVerImpact.NONE


def test_format_blueprint_guidance_has_no_raw_json() -> None:
    from git_cg.commit_quality import format_blueprint_guidance
    from git_cg.models import CommitBlueprint, CommitType

    bp = CommitBlueprint(cc_type=CommitType.DOCS, scope="adr", subject_hint="seed subject")
    text = format_blueprint_guidance(bp)
    assert "OPERATOR BLUEPRINT" in text
    assert "docs" in text
    assert "{" not in text  # no JSON dump
    assert "intent_id" in text  # authority reminder present


# ---------------------------------------------------------------------------
# Slice 8 — Hallucination / craft / claim-tag harvest (D14/D21)
# ---------------------------------------------------------------------------


def test_harvest_claim_tags_tip_g1_order_and_dedupe() -> None:
    tags = harvest_claim_tags(
        [
            "locks P9-A05 authority",
            "also P9-B07 and P9-B10; repeat P9-A05",
            "noise without tags",
        ]
    )
    assert tags == ["P9-A05", "P9-B07", "P9-B10"]


def test_harvest_claim_tags_caps_at_eight() -> None:
    blob = " ".join(f"P9-A{i:02d}" for i in range(1, 12))
    tags = harvest_claim_tags([blob])
    assert len(tags) == 8
    assert tags[0] == "P9-A01"


def test_guard_tip_g2_secrets_without_path_evidence() -> None:
    plan = _plan(
        intent_id="security_hardening",
        gitmoji="🔐",
        cc_type=CommitType.CHORE,
        scope="fixtures",
        description="Add or update secrets",
        semver=SemVerImpact.PATCH,
        changelog="Security",
    )
    plan.body_summary = "Document credentials rotation."
    report = evaluate_presentation_guards(
        plan,
        paths=["tests/fixtures/scoped_history/README.md"],
    )
    assert report.hallucination_guard_fired is True
    assert report.fallback_reason == PRESENTATION_FALLBACK_HALLUCINATION
    codes = report.codes()
    assert "GUARD_SECURITY_NOUN" in codes
    # fixtures-only also treats Add opener as craft, but hallucination wins reason.


def test_guard_tip_g4_docs_runtime_verbs() -> None:
    plan = _plan(
        intent_id="documentation_update",
        gitmoji="📝",
        cc_type=CommitType.DOCS,
        scope="usage",
        description="handle graph unavailable errors",
        semver=SemVerImpact.PATCH,
        changelog="Fixed",
    )
    plan.body_summary = "Recovers gracefully when graph/shadow unavailable."
    report = evaluate_presentation_guards(
        plan,
        paths=["docs/usage.md", "CHANGELOG.md", "DEVELOPMENT.md"],
    )
    assert report.dirty
    assert "GUARD_DOCS_RUNTIME_VERB" in report.codes()
    assert report.fallback_reason == PRESENTATION_FALLBACK_HALLUCINATION


def test_guard_tip_g5_vague_improve_subject() -> None:
    plan = _plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        scope="telemetry",
        description="improve metrics scrubbing and fallbacks",
        semver=SemVerImpact.MAJOR,
        changelog="Added",
    )
    plan.body_summary = "Tighten scrubbing paths."
    report = evaluate_presentation_guards(
        plan,
        paths=["src/git_cg/main.py", "src/git_cg/telemetry.py", "src/git_cg/sentry_config.py"],
    )
    assert "GUARD_VAGUE_SUBJECT_VERB" in report.codes()
    assert report.fallback_reason == PRESENTATION_FALLBACK_CRAFT


def test_guard_tip_g8_unearned_adds_guidance() -> None:
    plan = _plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        scope="scoped-history",
        description="adds guidance for scoped history",
        semver=SemVerImpact.MINOR,
        changelog="Added",
    )
    plan.body_summary = "Adds guidance rows."
    report = evaluate_presentation_guards(
        plan,
        paths=["tests/test_scoped_history.py", "docs/ADRs/0163-scoped-reasoning-history.md"],
    )
    assert "GUARD_UNEARNED_CAPABILITY" in report.codes()


def test_guard_tip_g9_adds_guard_assertion_ban() -> None:
    plan = _plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        scope="scoped_history",
        description="adds authority leakage guard",
        semver=SemVerImpact.MINOR,
        changelog="Added",
    )
    plan.body_summary = "Adds assertion coverage."
    report = evaluate_presentation_guards(
        plan,
        paths=["src/git_cg/scoped_history.py", "tests/test_scoped_history.py"],
    )
    assert "GUARD_UNEARNED_CAPABILITY" in report.codes()


def test_guard_tip_g11_unshipped_phase_product_actor() -> None:
    plan = _plan(
        intent_id="feature_addition",
        gitmoji="✨",
        cc_type=CommitType.FEAT,
        scope="semantic",
        description="wire preflight carry-through counters",
        semver=SemVerImpact.MINOR,
        changelog="Added",
    )
    plan.body_summary = "Values come from the Phase 0.5 product elevation path."
    report = evaluate_presentation_guards(
        plan,
        paths=["src/git_cg/main.py", "tests/test_semantic.py"],
        evidence_text="+ carry counter only\n",
    )
    assert "GUARD_UNSHIPPED_PRODUCT_ACTOR" in report.codes()


def test_guard_tip_g12_docs_adr_rejects_fix_runtime_story() -> None:
    plan = _plan(
        intent_id="bug_fix",
        gitmoji="🥅",
        cc_type=CommitType.FIX,
        scope="adr",
        description="recover fail-open graph paths",
        semver=SemVerImpact.PATCH,
        changelog="Fixed",
    )
    plan.body_summary = "Handle runtime fallback errors in the ADR mermaid."
    report = evaluate_presentation_guards(
        plan,
        paths=["docs/ADRs/0163-scoped-reasoning-history.md", "docs/usage.md"],
    )
    assert report.hallucination_guard_fired
    assert "GUARD_DOCS_RUNTIME_VERB" in report.codes()


def test_guard_title_case_add_unit_tests_on_tests_only() -> None:
    plan = _plan(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type=CommitType.TEST,
        scope="scoped_history",
        description="Add Unit Tests For Claims",
        semver=SemVerImpact.NONE,
        changelog="Tests",
    )
    plan.body_summary = "Cover locks."
    report = evaluate_presentation_guards(
        plan,
        paths=[
            "tests/test_scoped_history.py",
            "tests/test_scoped_history_telemetry.py",
            "tests/test_main.py",
            "tests/test_semantic.py",
        ],
    )
    codes = report.codes()
    assert "GUARD_TITLE_CASE_SUBJECT" in codes or "GUARD_TEST_DOCS_ADD_OPENER" in codes


def test_merge_presentation_fallback_reason_precedence() -> None:
    assert merge_presentation_fallback_reason("low_confidence", "hallucination_guard") == "hallucination_guard"
    assert merge_presentation_fallback_reason("hallucination_guard", "craft_guard") == "hallucination_guard"
    assert merge_presentation_fallback_reason("none", "craft_guard") == "craft_guard"
    assert merge_presentation_fallback_reason("error", "hallucination_guard") == "error"


def test_format_guard_guidance_directive_free() -> None:
    plan = _plan(description="improve scrubbing")
    plan.body_summary = "This commit introduces scrubbing."
    report = evaluate_presentation_guards(
        plan,
        paths=["src/git_cg/telemetry.py"],
    )
    text = format_guard_guidance(report)
    assert "PRESENTATION GUARD FINDINGS" in text
    assert "preferred_type" not in text.lower()
    assert "OVERRIDE" not in text
    assert "intent_id" in text  # authority preservation note


def test_format_guard_guidance_does_not_repoison_security_nouns() -> None:
    plan = _plan(
        intent_id="validation_update",
        gitmoji="🦺",
        cc_type=CommitType.FIX,
        scope="telemetry",
        description="redact secrets on scanner exit",
        semver=SemVerImpact.PATCH,
        changelog="Changed",
    )
    plan.body_summary = "Keep ordinary payloads when secrets are found."
    report = evaluate_presentation_guards(
        plan,
        paths=["src/git_cg/telemetry.py", "tests/test_telemetry.py"],
    )
    assert "GUARD_SECURITY_NOUN" in report.codes()
    text = format_guard_guidance(report).lower()
    # Guidance must not re-inject banned claim nouns into the regen prompt.
    for tok in ("secrets", "secret", "credentials", "credential", "password", "token", "api key", "apikey"):
        if " " in tok:
            assert tok not in text
        else:
            assert re.search(rf"\b{re.escape(tok)}\b", text) is None


def test_repair_security_noun_claims_scrubs_wording() -> None:
    plan = _plan(
        intent_id="validation_update",
        gitmoji="🦺",
        cc_type=CommitType.FIX,
        scope="telemetry",
        description="apply betterleaks secrets redaction on exit 1",
        semver=SemVerImpact.PATCH,
        changelog="Changed",
    )
    plan.body_summary = "Keep ordinary payloads when secrets are found."
    out, changed = repair_security_noun_claims(
        plan,
        paths=["src/git_cg/telemetry.py", "tests/test_telemetry.py"],
    )
    assert changed is True
    blob = f"{out.primary_intent.description}\n{out.body_summary}".lower()
    assert "secret" not in blob
    assert "sensitive" in blob
    post = evaluate_presentation_guards(
        out,
        paths=["src/git_cg/telemetry.py", "tests/test_telemetry.py"],
    )
    assert post.dirty is False


def test_try_repair_presentation_guards_clears_security_noun_only() -> None:
    plan = _plan(
        intent_id="validation_update",
        gitmoji="🦺",
        cc_type=CommitType.FIX,
        scope="telemetry",
        description="redact secrets from telemetry payloads",
        semver=SemVerImpact.PATCH,
        changelog="Changed",
    )
    plan.body_summary = "Drop credentials framing on ordinary writes."
    repaired, report, ok = try_repair_presentation_guards(
        plan,
        paths=["src/git_cg/telemetry.py", "tests/test_telemetry.py"],
    )
    assert ok is True
    assert report.dirty is False
    blob = f"{repaired.primary_intent.description}\n{repaired.body_summary}".lower()
    assert "secret" not in blob
    assert "credential" not in blob


def test_apply_guard_skeleton_fallback_preserves_identity_and_docs_force() -> None:
    plan = _plan(
        intent_id="documentation_update",
        gitmoji="📝",
        cc_type=CommitType.FIX,
        scope="usage",
        description="handle secrets recovery",
        semver=SemVerImpact.PATCH,
        changelog="Fixed",
    )
    plan.body_summary = "Recovers secrets at runtime."
    report = evaluate_presentation_guards(
        plan,
        paths=["docs/usage.md"],
    )
    out = apply_guard_skeleton_fallback(
        plan,
        paths=["docs/usage.md"],
        claim_tags=["P9-A05"],
        report=report,
    )
    assert out.primary_intent.intent_id == "documentation_update"
    assert out.primary_intent.gitmoji == "📝"
    assert out.primary_intent.cc_type == CommitType.DOCS
    assert out.primary_intent.semver_impact == SemVerImpact.NONE
    assert "document" in (out.primary_intent.description or "").lower()
    assert "P9-A05" in (out.body_summary or "")


def test_clean_message_does_not_fire_guards() -> None:
    plan = _plan(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type=CommitType.TEST,
        scope="scoped-history",
        description="cover claim locks for scoped history",
        semver=SemVerImpact.NONE,
        changelog="Tests",
    )
    plan.body_summary = "Pin P9-A05 / P9-B07 authority rows without inventing runtime recovery."
    report = evaluate_presentation_guards(
        plan,
        paths=["tests/test_scoped_history.py", "tests/test_main.py"],
    )
    assert report.dirty is False
    assert report.fallback_reason == PRESENTATION_FALLBACK_NONE
    assert report.hallucination_guard_fired is False


# ---------------------------------------------------------------------------
# Slice 9 - ordered pure gate evaluator unit coverage
# ---------------------------------------------------------------------------


def test_slice9_gate_order_constant() -> None:
    assert SLICE9_GATE_ORDER == (
        "path_class",
        "type",
        "semver",
        "no_hallucination",
        "inventory",
        "craft",
    )
    assert list(slice9_letter_map()) == [chr(c) for c in range(ord("A"), ord("N") + 1)]


def test_slice9_gate_first_fail_skips_later_gates() -> None:
    """Illegal docs fix fails at type; later craft/hallucination still recorded as skip."""
    import conftest as _cq

    primary = _cq.make_commit_intent(
        intent_id="bug_fix",
        gitmoji="🥅",
        cc_type="fix",
        scope="adr",
        description="Clarify fail-open fallback for scoped history",
        semver_impact="PATCH",
        changelog_group="Fixed",
        construct=True,
    )
    plan = _cq.make_commit_plan(
        primary=primary,
        body_summary="Handle runtime fail-open recovery described in mermaid prose.",
        construct=True,
    )
    paths = [
        "docs/usage.md",
        "docs/ADRs/0163-scoped-reasoning-history.md",
    ]
    report = evaluate_presentation_gates(plan, paths=paths)
    assert report.passed is False
    assert report.first_fail_gate == "type"
    status = dict(report.gate_status)
    assert status["path_class"] == "pass"
    assert status["type"] == "fail"
    assert status["semver"] == "skip"
    assert status["craft"] == "skip"
    assert "GATE_TYPE_FORBIDDEN" in report.codes or "GATE_TYPE_FORCE_MISMATCH" in report.codes


def test_slice9_h_signing_inventory_token_required() -> None:
    import conftest as _cq

    paths = [
        "tests/test_scoped_history.py",
        "tests/fixtures/scoped_history/README.md",
        "tests/fixtures/scoped_history/no-gpg-sign.md",
    ]
    primary = _cq.make_commit_intent(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="scoped-history",
        description="harden fixture signing and scoped-history locks",
        semver_impact="NONE",
        changelog_group="Tests",
        construct=True,
    )
    sec = _cq.make_commit_intent(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="fixtures",
        description="harden fixture GPG/signing setup",
        semver_impact="NONE",
        changelog_group="Tests",
        construct=True,
    )
    legal = _cq.make_commit_plan(
        primary=primary,
        secondary_intents=[sec],
        body_summary="Keep hermetic tests with commit.gpgsign=false fixture docs.",
        construct=True,
    )
    ok = evaluate_presentation_gates(
        legal,
        paths=paths,
        included_changes=[
            "✅ test(scoped-history): cover test_scoped_history suite",
            "✅ test(fixtures): harden fixture GPG/signing setup",
            "✅ test(fixtures): cover fixture README",
        ],
        require_stub_note_tokens=["gpg", "signing"],
    )
    assert ok.passed is True

    bad_primary = _cq.make_commit_intent(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="scoped-history",
        description="expand scoped-history fixture coverage",
        semver_impact="NONE",
        changelog_group="Tests",
        construct=True,
    )
    bad_sec = _cq.make_commit_intent(
        intent_id="tests_update",
        gitmoji="✅",
        cc_type="test",
        scope="fixtures",
        description="cover fixture README",
        semver_impact="NONE",
        changelog_group="Tests",
        construct=True,
    )
    bad = _cq.make_commit_plan(
        primary=bad_primary,
        secondary_intents=[bad_sec],
        body_summary="Update fixtures without mentioning signing.",
        construct=True,
    )
    report = evaluate_presentation_gates(
        bad,
        paths=paths,
        included_changes=[
            "✅ test(scoped-history): cover test_scoped_history suite",
            "✅ test(fixtures): cover fixture README",
        ],
        require_stub_note_tokens=["gpg", "signing"],
    )
    assert report.passed is False
    assert report.first_fail_gate == "inventory"
    assert "GATE_INVENTORY_MISSING_TOKEN" in report.codes


def test_slice9_evaluate_gates_never_calls_ranker(monkeypatch: pytest.MonkeyPatch) -> None:
    import conftest as _cq

    import git_cg.intent as intent_mod

    def _boom(*_a, **_k):
        raise AssertionError("ranker invoked")

    monkeypatch.setattr(intent_mod, "rank_commit_intents", _boom)
    primary = _cq.make_commit_intent(
        intent_id="documentation_update",
        gitmoji="📝",
        cc_type="docs",
        scope="adr",
        description="document graph_unavailable posture",
        semver_impact="NONE",
        changelog_group="Documentation",
        construct=True,
    )
    plan = _cq.make_commit_plan(
        primary=primary,
        body_summary="Docs-only graph_unavailable posture.",
        construct=True,
    )
    report = evaluate_presentation_gates(
        plan,
        paths=["docs/usage.md", "docs/ADRs/0163-scoped-reasoning-history.md"],
    )
    assert report.passed is True
