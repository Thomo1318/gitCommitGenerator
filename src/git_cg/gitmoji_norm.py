"""Gitmoji variant / confusable normalisation (Issue #204 · D8 NTH).

Presentation, gold lookup, and matrix matching must treat known emoji
presentation variants as the same glyph without inventing a parallel gitmoji
policy. The SOP matrix remains the sole authority for which emoji belongs to
which ``intent_id``.

Normalisation steps (locked):
1. Strip Unicode variation selectors U+FE0F / U+FE0E (emoji vs text presentation).
2. Apply the explicit ``GITMOJI_CONFUSABLES`` map for non-VS confusable bases.
3. Unknown glyphs pass through unchanged — never invent matrix rows.
"""

from __future__ import annotations

# Variation selectors that flip emoji/text presentation without changing identity.
_VARIATION_SELECTORS: tuple[str, ...] = ("\ufe0f", "\ufe0e")

# Explicit confusable map: VS-stripped source base → preferred VS-stripped base.
# Only list true confusables that survive variation-selector stripping (D8).
# Do NOT collapse distinct matrix intents (e.g. 🔐 secrets_update must not map
# onto 🔒 security_privacy_fix — those remain separate identity rows).
GITMOJI_CONFUSABLES: dict[str, str] = {
    # Reserved for non-VS confusables. VS-only variants are handled solely by
    # strip_gitmoji_variation_selectors. Extend only via issue amendment.
}

# Security-framing bases used by presentation forbid checks (D13). Distinct
# matrix intents may share this presentation class without identity merge.
_SECURITY_GITMOJI_BASES: frozenset[str] = frozenset(
    {
        "\U0001f512",  # 🔒 lock / security_privacy_fix (matrix often ships with VS16)
        "\U0001f510",  # 🔐 closed_lock_with_key / secrets_update
    }
)


def strip_gitmoji_variation_selectors(emoji: str) -> str:
    """Strip emoji/text variation selectors from *emoji*.

    The SOP matrix encodes some glyphs both with and without U+FE0F (e.g.
    ``⚡`` vs ``⚡️``). Stripping makes selector-insensitive comparison safe.
    """
    if not emoji:
        return ""
    out = str(emoji)
    for vs in _VARIATION_SELECTORS:
        out = out.replace(vs, "")
    return out


def normalize_gitmoji(emoji: str) -> str:
    """Return the stable lookup key for a gitmoji glyph.

    1. Strip VS15/VS16.
    2. Apply explicit confusable map (D8).
    Unknown glyphs pass through unchanged (no invention / no parallel policy).
    """
    base = strip_gitmoji_variation_selectors(emoji or "")
    if not base:
        return ""
    return GITMOJI_CONFUSABLES.get(base, base)


def gitmojis_equivalent(left: str, right: str) -> bool:
    """True when *left* and *right* normalise to the same non-empty confusable base.

    Empty or selector-only input never matches. An absent matrix ``emoji`` value
    must not bind an intent to a row via the empty-string fallback path.
    """
    left_base = normalize_gitmoji(left)
    if not left_base:
        return False
    right_base = normalize_gitmoji(right)
    if not right_base:
        return False
    return left_base == right_base


def is_security_gitmoji(emoji: str) -> bool:
    """True when *emoji* is a security-framing glyph (D13 presentation class)."""
    return normalize_gitmoji(emoji) in _SECURITY_GITMOJI_BASES


def iter_gitmoji_confusables() -> tuple[tuple[str, str], ...]:
    """Stable snapshot of explicit confusable pairs ``(source, preferred)``."""
    return tuple(sorted(GITMOJI_CONFUSABLES.items(), key=lambda kv: kv[0]))
