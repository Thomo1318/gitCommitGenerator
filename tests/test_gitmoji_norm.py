"""Tests for D8 gitmoji confusable / variation-selector normalisation (#204 NTH)."""

from __future__ import annotations

from git_cg.gitmoji_norm import (
    GITMOJI_CONFUSABLES,
    gitmojis_equivalent,
    is_security_gitmoji,
    iter_gitmoji_confusables,
    normalize_gitmoji,
    strip_gitmoji_variation_selectors,
)
from git_cg.models import CommitIntent, CommitType, SemVerImpact
from git_cg.sop import get_gitmoji_matrix


def test_strip_variation_selectors_removes_vs16_and_vs15() -> None:
    assert strip_gitmoji_variation_selectors("⚡️") == "⚡"
    assert strip_gitmoji_variation_selectors("⚡\ufe0e") == "⚡"
    assert strip_gitmoji_variation_selectors("✨") == "✨"


def test_normalize_gitmoji_is_selector_insensitive() -> None:
    assert normalize_gitmoji("⚡️") == normalize_gitmoji("⚡")
    assert normalize_gitmoji("🔒️") == normalize_gitmoji("🔒")
    assert normalize_gitmoji("♻️") == normalize_gitmoji("♻")
    assert normalize_gitmoji("⏪️") == normalize_gitmoji("⏪")


def test_normalize_gitmoji_unknown_passthrough() -> None:
    weird = "🧩"
    assert normalize_gitmoji(weird) == weird
    assert normalize_gitmoji("") == ""


def test_gitmojis_equivalent_for_matrix_vs_variants() -> None:
    assert gitmojis_equivalent("⚡️", "⚡")
    assert gitmojis_equivalent("🔐", "🔐")
    assert not gitmojis_equivalent("🔐", "🔒")  # distinct matrix intents


def test_is_security_gitmoji_covers_lock_family() -> None:
    assert is_security_gitmoji("🔐")
    assert is_security_gitmoji("🔒️")
    assert is_security_gitmoji("🔒")
    assert not is_security_gitmoji("✨")
    assert not is_security_gitmoji("🐛")


def test_confusable_map_is_explicit_and_stable() -> None:
    # Empty map is legal: VS stripping alone covers current SOP instability.
    assert isinstance(GITMOJI_CONFUSABLES, dict)
    snap = iter_gitmoji_confusables()
    assert snap == tuple(sorted(GITMOJI_CONFUSABLES.items(), key=lambda kv: kv[0]))
    for src, preferred in snap:
        assert "\ufe0f" not in src and "\ufe0e" not in src
        assert "\ufe0f" not in preferred and "\ufe0e" not in preferred
        assert normalize_gitmoji(src) == preferred


def test_commit_intent_matches_matrix_emoji_with_vs_variant() -> None:
    """VS-stripped / VS-decorated LLM emoji still resolves to the matrix row (D8)."""
    matrix = get_gitmoji_matrix()
    row = next(r for r in matrix if r.get("intent_id") == "performance_improvement")
    matrix_emoji = row["emoji"]
    bare = strip_gitmoji_variation_selectors(matrix_emoji)
    assert bare
    # Prefer the opposite VS form from whatever the matrix ships.
    candidate = bare if bare != matrix_emoji else f"{bare}\ufe0f"

    intent = CommitIntent(
        intent_id="not_a_real_intent",
        gitmoji=candidate,
        cc_type=CommitType.FEAT,
        scope=None,
        description="speed up path class lookup",
        semver_impact=SemVerImpact.PATCH,
        changelog_group="Changed",
    )
    assert intent.intent_id == "performance_improvement"
    assert intent.gitmoji == matrix_emoji
    assert intent.cc_type == CommitType(row["cc_type"])


def test_commit_gold_norm_delegates_to_shared_helper() -> None:
    from git_cg.commit_gold import _norm_gitmoji

    assert _norm_gitmoji("⚡️") == normalize_gitmoji("⚡️")
    assert _norm_gitmoji("🔒️") == normalize_gitmoji("🔒️")
