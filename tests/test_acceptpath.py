"""Issue #212 accept-path characterization (APC-A / APC-B / APC-C).

Frozen fixtures under ``tests/fixtures/acceptpath/`` capture the 2026-08-09
MTPLX dogfood failures where non-empty staged paths collapsed to
``path_class_gate=empty``. These tests lock the deterministic recovery surface
before live MTPLX confirmation (APC-D).
"""

from __future__ import annotations

import conftest as _cq
import pytest
from acceptpath_pack import (
    ALL_CASES,
    CLOSE_GATE_CASES,
    INFO_CASES,
    PACK_ROOT,
    assert_docs_only_post_repair_snapshot,
    assert_pack_integrity,
    case_dir,
    iter_close_gate_cases,
    iter_info_cases,
    load_case,
    staged_diff as _fixture_diff,
)

from git_cg.commit_quality import (
    DIFF_CLASS_DOCS,
    DIFF_CLASS_EMPTY,
    DIFF_CLASS_PRODUCT,
    DIFF_CLASS_TESTS,
    apply_presentation_overlay,
    constraints_from_paths,
)
from git_cg.intent import extract_diff_file_summary, extract_diff_signals
from git_cg.main import (
    _build_generation_context,
    _presentation_telemetry_from_context,
    _staged_diff_command,
    extract_git_diff,
    pack_prompt_diff,
)
from git_cg.models import CommitType, SemVerImpact
from git_cg.regeneration import (
    RegenerationState,
    enforce_semantic_contract,
    lift_plan_to_contract_semver,
    resolve_semantic_contract,
)

# Back-compat alias for any local references / bakeoff copy-paste.
FIXTURES = PACK_ROOT

# RTK-style summarized non-unified output observed in live dogfood (docs-only).
_RTK_DOCS_SUMMARY = """\
docs/usage.md | 5 +++++
1 file changed, 5 insertions(+)

Changes:

docs/usage.md
  + ## Review checklist
  + - verify commit subjects stay within 72 characters
  + - preserve machine-readable trailers
  + - keep change sets focused
  + - document graph refresh workspace scope
  + secret token password age
"""


def _final_plan_from_context(ctx, *, hostile_plan):
    """Mirror production order: contract → overlay → contract SemVer lift."""
    contract = resolve_semantic_contract(ctx, RegenerationState())
    enforced = enforce_semantic_contract(hostile_plan, contract, {})
    overlaid = apply_presentation_overlay(
        enforced,
        paths=list(ctx.diff_signals.files or []),
        signals=ctx.diff_signals,
        priors=ctx.scope_priors,
        constraints=ctx.presentation_constraints,
    )
    lifted, _applied, _from = lift_plan_to_contract_semver(overlaid, contract)
    return contract, lifted


# ---------------------------------------------------------------------------
# APC-A — path harvest / DiffClass / telemetry gate alignment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "expected_path", "expected_gate"),
    [
        ("docs-only", "docs/usage.md", DIFF_CLASS_DOCS),
        ("tests-only", "tests/test_mathy.py", DIFF_CLASS_TESTS),
        ("product-source", "src/demo/greeter.py", DIFF_CLASS_PRODUCT),
        ("gold-trigger", "src/demo/util.py", DIFF_CLASS_PRODUCT),
    ],
)
def test_apc_a_fixture_diff_harvests_paths_and_gates(case: str, expected_path: str, expected_gate: str) -> None:
    """APC-A01/A02/A03: frozen unified diffs classify non-empty gates."""
    diff = _fixture_diff(case)
    summary = extract_diff_file_summary(diff)
    signals = extract_diff_signals(diff)
    assert expected_path in summary.paths
    assert expected_path in (signals.files or [])
    assert signals.files, "non-empty staged paths must harvest"

    ctx = _build_generation_context(diff, enable_semantic=False)
    assert ctx.presentation_constraints is not None
    assert ctx.presentation_constraints.diff_class == expected_gate
    assert expected_path in (ctx.diff_signals.files or [])

    gate, _anti, _scope = _presentation_telemetry_from_context(ctx)
    assert gate == expected_gate  # APC-A04


def test_apc_a04_telemetry_gate_equals_constraints_gate() -> None:
    diff = _fixture_diff("docs-only")
    ctx = _build_generation_context(diff, enable_semantic=False)
    gate, anti, _scope = _presentation_telemetry_from_context(ctx)
    assert gate == ctx.presentation_constraints.diff_class
    assert anti == ctx.presentation_constraints.changelog_antisignal_applied


def test_apc_a05_true_empty_remains_empty() -> None:
    """APC-A05: genuinely empty path harvest stays ``empty`` (no false recovery)."""
    cons = constraints_from_paths([])
    assert cons.diff_class == DIFF_CLASS_EMPTY
    ctx = _build_generation_context("", enable_semantic=False)
    # empty analysis string still builds context; gate must not invent product_src
    assert ctx.presentation_constraints.diff_class in {DIFF_CLASS_EMPTY, "empty"}
    gate, _anti, _scope = _presentation_telemetry_from_context(ctx)
    assert gate == DIFF_CLASS_EMPTY


def test_apc_a06_docs_negative_not_secrets_update() -> None:
    """APC-A06: docs-only must not resolve secrets_update; force docs/NONE note."""
    diff = _fixture_diff("docs-only")
    ctx = _build_generation_context(diff, enable_semantic=False)
    cons = ctx.presentation_constraints
    assert cons.diff_class == DIFF_CLASS_DOCS
    assert "docs_only_force_docs_none" in cons.notes
    assert cons.force_cc_type == CommitType.DOCS
    assert cons.force_semver == SemVerImpact.NONE

    ranked_ids = [i.intent_id for i in ctx.ranked_intents]
    assert ranked_ids, "docs fixture must produce ranked intents"
    assert ranked_ids[0] != "secrets_update"
    assert "secrets_update" not in ranked_ids[:3]

    hostile = _cq.make_commit_plan(
        intent_id="secrets_update",
        gitmoji="🔐",
        cc_type="chore",
        scope="docs",
        description="document review checklist for usage",
        semver_impact="PATCH",
        changelog_group="Miscellaneous",
        construct=True,
    )
    contract, final = _final_plan_from_context(ctx, hostile_plan=hostile)
    assert contract.primary_intent_id != "secrets_update"
    assert contract.cc_type == "docs"
    assert contract.semver_impact == "NONE"
    assert final.primary_intent.intent_id != "secrets_update"
    assert final.primary_intent.cc_type == CommitType.DOCS
    assert final.primary_intent.semver_impact == SemVerImpact.NONE


def test_apc_a_rtk_summarized_diff_is_unsafe_for_analysis() -> None:
    """Characterization: RTK-style summary collapses harvest (root-cause lock)."""
    summary = extract_diff_file_summary(_RTK_DOCS_SUMMARY)
    signals = extract_diff_signals(_RTK_DOCS_SUMMARY)
    assert summary.paths == []
    assert list(signals.files or []) == []
    # Content markers in the summary body can still fire without path evidence.
    assert signals.secrets_management_changed is True
    assert signals.only_docs is False


def test_apc_a_extract_git_diff_never_selects_rtk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Analysis extraction always uses standard git argv (RTK builder unused)."""
    import subprocess

    calls: list[list[str]] = []

    def fake_check_output(cmd, **_kwargs):
        calls.append(list(cmd))
        return "diff --git a/docs/usage.md b/docs/usage.md\n+hello\n"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/rtk")

    out = extract_git_diff(verbose=False, strict=False)
    assert "diff --git" in out
    assert calls and calls[0][0] == "git"
    assert calls[0] == _staged_diff_command(use_rtk=False)
    # pack_prompt_diff remains the only compression boundary for prompts.
    packed, omitted = pack_prompt_diff(out)
    assert packed
    assert omitted == []


# ---------------------------------------------------------------------------
# APC-B — full presentation surface after contract + overlay + lift
# ---------------------------------------------------------------------------


def test_apc_b01_docs_full_surface() -> None:
    diff = _fixture_diff("docs-only")
    ctx = _build_generation_context(diff, enable_semantic=False)
    hostile = _cq.make_commit_plan(
        intent_id="secrets_update",
        gitmoji="🔐",
        cc_type="chore",
        scope="docs",
        description="document review checklist",
        semver_impact="PATCH",
        changelog_group="Miscellaneous",
        construct=True,
    )
    contract, final = _final_plan_from_context(ctx, hostile_plan=hostile)
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_DOCS
    assert "docs_only_force_docs_none" in ctx.presentation_constraints.notes
    assert contract.primary_intent_id == "documentation_update" or contract.cc_type == "docs"
    assert contract.primary_intent_id != "secrets_update"
    assert final.primary_intent.cc_type == CommitType.DOCS
    assert final.primary_intent.semver_impact == SemVerImpact.NONE
    assert final.primary_intent.changelog_group == "Documentation"
    assert final.breaking_change is False


def test_apc_b02_tests_test_none() -> None:
    diff = _fixture_diff("tests-only")
    ctx = _build_generation_context(diff, enable_semantic=False)
    hostile = _cq.make_commit_plan(
        intent_id="breaking_change",
        gitmoji="💥",
        cc_type="feat",
        scope="test",
        description="add edge case tests",
        semver_impact="MAJOR",
        changelog_group="Added",
        breaking_change=True,
        breaking_change_description="new assertions",
        construct=True,
    )
    contract, final = _final_plan_from_context(ctx, hostile_plan=hostile)
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_TESTS
    assert contract.cc_type == "test"
    assert contract.semver_impact == "NONE"
    assert final.primary_intent.cc_type == CommitType.TEST
    assert final.primary_intent.semver_impact == SemVerImpact.NONE
    assert final.primary_intent.intent_id != "breaking_change"
    assert final.breaking_change is False


def test_apc_b03_product_non_breaking_feat_minor() -> None:
    diff = _fixture_diff("product-source")
    ctx = _build_generation_context(diff, enable_semantic=False)
    hostile = _cq.make_commit_plan(
        intent_id="breaking_change",
        gitmoji="💥",
        cc_type="feat",
        scope="greeter",
        description="add excited flag and greet_many",
        semver_impact="MAJOR",
        changelog_group="Changed",
        breaking_change=True,
        breaking_change_description="kw-only excited",
        construct=True,
    )
    contract, final = _final_plan_from_context(ctx, hostile_plan=hostile)
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_PRODUCT
    assert contract.cc_type == "feat"
    assert contract.semver_impact == "MINOR"
    assert contract.primary_intent_id != "breaking_change"
    assert final.primary_intent.cc_type == CommitType.FEAT
    assert final.primary_intent.semver_impact == SemVerImpact.MINOR
    assert final.primary_intent.intent_id != "breaking_change"
    assert final.breaking_change is False


def test_apc_b_gold_trigger_not_forced_major() -> None:
    diff = _fixture_diff("gold-trigger")
    ctx = _build_generation_context(diff, enable_semantic=False)
    hostile = _cq.make_commit_plan(
        intent_id="breaking_change",
        gitmoji="💥",
        cc_type="feat",
        scope="util",
        description="add normalize_or_default",
        semver_impact="MAJOR",
        changelog_group="Changed",
        breaking_change=True,
        breaking_change_description="None fallback",
        construct=True,
    )
    contract, final = _final_plan_from_context(ctx, hostile_plan=hostile)
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_PRODUCT
    assert contract.semver_impact != "MAJOR"
    assert final.primary_intent.semver_impact != SemVerImpact.MAJOR
    assert contract.primary_intent_id != "breaking_change"
    assert final.breaking_change is False


def test_apc_b04_no_sop_rewrite_required_for_docs_fixture() -> None:
    """APC-B04: plain fixture ranking already selects documentation_update."""
    diff = _fixture_diff("docs-only")
    signals = extract_diff_signals(diff)
    assert signals.only_docs is True
    ctx = _build_generation_context(diff, enable_semantic=False)
    assert ctx.ranked_intents[0].intent_id == "documentation_update"
    assert ctx.ranked_intents[0].cc_type == "docs"
    assert ctx.ranked_intents[0].semver_impact == "NONE"


# ---------------------------------------------------------------------------
# Shared fixture pack + informational LMLX parity (Issue #212 NTH)
# ---------------------------------------------------------------------------


def test_acceptpath_pack_integrity_close_gate_and_info() -> None:
    """Canonical pack exposes close-gate + informational cases with required artifacts."""
    assert_pack_integrity(include_info=True)
    assert CLOSE_GATE_CASES == (
        "docs-only",
        "product-source",
        "tests-only",
        "gold-trigger",
    )
    assert INFO_CASES == ("lmlx-docs-compare",)
    assert ALL_CASES == CLOSE_GATE_CASES + INFO_CASES
    assert PACK_ROOT.is_dir()

    for case in iter_close_gate_cases():
        assert case.is_close_gate()
        assert case.staged_diff().startswith("diff --git")
        assert not case.missing_required_files()
        assert case.expected_envelope()["diff_class"]

    for case in iter_info_cases():
        assert not case.is_close_gate()
        assert not case.missing_required_files()


def test_acceptpath_lmlx_docs_compare_is_informational_parity_twin() -> None:
    """LMLX twin mirrors docs-only staged envelope; outcomes stay non-blocking."""
    docs = load_case("docs-only")
    lmlx = load_case("lmlx-docs-compare")

    assert lmlx.staged_diff() == docs.staged_diff()
    assert "docs/usage.md" in lmlx.staged_diff()

    # Parity core artifacts present (informational bakeoff contract).
    for name in (
        "staged.diff",
        "COMMIT_EDITMSG",
        "GIT_CG_OPIK_STATE.json",
        "summary.txt",
        "meta.txt",
        "status.txt",
        "telemetry-extract.txt",
    ):
        assert (lmlx.root / name).is_file(), name

    meta = lmlx.read_text("meta.txt")
    assert "ENGINE=lmlx" in meta
    assert "informational" in meta.lower() or "not a #212 close gate" in meta

    tel = lmlx.read_text("telemetry-extract.txt")
    # Preserve truthful captured LMLX evidence (empty gate / redaction failure).
    assert "engine='lmlx'" in tel or 'engine="lmlx"' in tel or "engine=lmlx" in tel
    assert "path_class_gate" in tel

    # Deterministic recovery still classifies the shared staged.diff as docs_only.
    ctx = _build_generation_context(lmlx.staged_diff(), enable_semantic=False)
    assert ctx.presentation_constraints.diff_class == DIFF_CLASS_DOCS


def test_acceptpath_pack_staged_diff_helper_matches_case_loader() -> None:
    """Bakeoff harnesses can use either staged_diff(name) or load_case(name)."""
    for name in CLOSE_GATE_CASES:
        assert _fixture_diff(name) == load_case(name).staged_diff()


def test_acceptpath_pack_rejects_path_escape() -> None:
    """case_dir/read_text must not resolve outside the committed fixture pack."""
    with pytest.raises(ValueError, match="escapes fixture pack"):
        case_dir("../")
    with pytest.raises(ValueError, match="escapes fixture pack"):
        case_dir("docs-only/../../")

    case = load_case("docs-only")
    with pytest.raises(ValueError, match="escapes case root"):
        case.read_text("../README.md")
    with pytest.raises(ValueError, match="escapes case root"):
        case.optional_text("../../pyproject.toml")


def test_acceptpath_docs_only_post_repair_snapshot_issue_214() -> None:
    """#214 NTH: frozen post-repair COMMIT_EDITMSG snapshot stays craft-clean."""
    assert_docs_only_post_repair_snapshot()
    case = load_case("docs-only")
    # Historical pre-fix capture remains distinct evidence.
    pre = case.read_text("COMMIT_EDITMSG").strip()
    post = case.read_text("COMMIT_EDITMSG.post-repair").strip()
    assert pre != post
    assert "SemVer-Impact: PATCH" in pre or "secrets" in pre.lower() or "chore" in pre.lower()
    assert "SemVer-Impact: NONE" in post
    assert "Change-Types: docs" in post
