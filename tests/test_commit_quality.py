"""Commit presentation quality — Slice 2 TrailerPriors characterisation (#204).

Locks path-role → TrailerPriors defaults. Does **not** wire priors into
``rank_commit_intents`` scoring (matrix remains sole ranking authority).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from git_cg.commit_quality import (
    DIFF_CLASS_ADR,
    DIFF_CLASS_DOCS,
    DIFF_CLASS_FIXTURES,
    DIFF_CLASS_PRODUCT,
    DIFF_CLASS_TESTS,
    PresentationConstraints,
    changelog_groups_allowlisted,
    classify_diff_class,
    constraints_from_paths,
    derive_trailer_priors,
    dominant_presentation_cc_type,
    filter_paths_for_content_signals,
    has_security_path_evidence,
    min_included_change_bullets,
    presentation_constraints,
    prose_has_security_negative_markers,
    required_changelog_groups,
    security_claims_without_path_evidence,
    semver_presentation_ceiling,
)
from git_cg.intent import DiffSignals
from git_cg.models import CommitType, SemVerImpact, TrailerPriors
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
                "cc_type": CommitType.DOCS,
                "semver_impact": SemVerImpact.NONE,
                "changelog_group": "Documentation",
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
            CommitType.DOCS,
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
