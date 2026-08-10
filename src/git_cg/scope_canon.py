"""Producer-side canonical scope normalisation (Issue #204 · Phase 7.30 · Slice 1).

Pure module: no git/LLM/TUI I/O, no ranker mutation, no gold steers, no #201
ontology allowlist. Gold may *consume* ``normalize_scope``; this module must
not import ``commit_quality`` or grow policy algorithms beyond alias mapping.

Dependency rule (D22): leaf-adjacent — stdlib only. ``commit_quality`` may
import this module; this module imports neither ``commit_quality`` nor
``models``.
"""

from __future__ import annotations

import re

# Minimum canonical map (Issue #204 Slice 1 table). Extend only via PR + test.
# Keys are lower-cased lookup tokens; values are the emitted canonical slug.
CANONICAL_SCOPE_ALIASES: dict[str, str] = {
    # scoped-history family (TIP-G7/G9/G11)
    "scoped_history": "scoped-history",
    "scoped-hist": "scoped-history",
    "scoped_hist": "scoped-history",
    "scoped-history": "scoped-history",
    # main / package-qualified main
    "main": "main",
    "main.py": "main",
    "git_cg.main": "main",
    # intent
    "intent": "intent",
    "intent.py": "intent",
    # telemetry
    "telemetry": "telemetry",
    "telemetry.py": "telemetry",
    # sentry
    "sentry": "sentry",
    "sentry_config": "sentry",
    "sentry_config.py": "sentry",
    # docs / ADR / usage
    "adr": "adr",
    "adrs": "adr",
    "docs": "docs",
    "usage": "usage",
    "usage.md": "usage",
    # tests / fixtures
    "test": "test",
    "tests": "test",
    "fixtures": "fixtures",
    # optional phase rollup
    "phase9": "phase9",
}

# Path-ish / filename-ish cleanup (defense in depth with gold F5-light).
_PATH_SEP_RE = re.compile(r"[/\\]+")
_PY_SUFFIX_RE = re.compile(r"\.py$", re.IGNORECASE)
# Known basename → scope for path tails (docs/ADRs/..., docs/usage.md, ...).
_BASENAME_ALIASES: dict[str, str] = {
    "main.py": "main",
    "main": "main",
    "intent.py": "intent",
    "intent": "intent",
    "telemetry.py": "telemetry",
    "telemetry": "telemetry",
    "sentry_config.py": "sentry",
    "sentry_config": "sentry",
    "sentry.py": "sentry",
    "usage.md": "usage",
    "usage": "usage",
}


def _strip_accidental_path(raw: str) -> str:
    """Reduce accidental path/filename forms to a bare token before alias lookup."""
    text = raw.strip()
    if not text:
        return text

    # Normalise separators, then take the final path component.
    if "/" in text or "\\" in text:
        parts = [p for p in _PATH_SEP_RE.split(text) if p]
        lower_parts = [p.lower() for p in parts]

        # ADR path under docs/ADRs/ → adr
        if any(p in {"adrs", "adr"} for p in lower_parts):
            return "adr"
        # fixtures path → fixtures
        if "fixtures" in lower_parts:
            return "fixtures"
        # pure docs path (non-ADR) → docs, unless basename is a known alias
        basename = parts[-1]
        basename_key = basename.lower()
        if basename_key in _BASENAME_ALIASES:
            return _BASENAME_ALIASES[basename_key]
        if "docs" in lower_parts:
            return "docs"
        text = basename

    return text


def normalize_scope(scope: str | None) -> str | None:
    """Return the canonical presentation scope slug for *scope*.

    Rules (Issue #204 §J / Slice 1):
    * ``None`` / blank → ``None``
    * strip accidental path separators and ``.py`` suffixes (F5-light defense)
    * map known aliases → canonical hyphen/slug form
    * unknown but already-clean tokens pass through unchanged (no crash)
    * never emit path separators or bare ``*.py`` filenames when a canon entry
      exists; unknown ``*.py`` tokens are stripped to their stem
    """
    if scope is None:
        return None

    raw = scope.strip()
    if not raw:
        return None

    cleaned = _strip_accidental_path(raw)
    if not cleaned:
        return None

    key = cleaned.lower()

    # Direct alias hit (including dotted package forms like git_cg.main).
    if key in CANONICAL_SCOPE_ALIASES:
        return CANONICAL_SCOPE_ALIASES[key]

    # Strip a trailing .py and retry (main.py, intent.py, ...).
    stem = _PY_SUFFIX_RE.sub("", key)
    if stem != key and stem in CANONICAL_SCOPE_ALIASES:
        return CANONICAL_SCOPE_ALIASES[stem]

    # Dotted module path: git_cg.main → try full, then final segment.
    if "." in key:
        if key in CANONICAL_SCOPE_ALIASES:
            return CANONICAL_SCOPE_ALIASES[key]
        tail = key.rsplit(".", 1)[-1]
        tail_stem = _PY_SUFFIX_RE.sub("", tail)
        if tail_stem in CANONICAL_SCOPE_ALIASES:
            return CANONICAL_SCOPE_ALIASES[tail_stem]
        if tail_stem:
            return tail_stem

    # Unknown clean token: pass through stem if it looked like a filename.
    if stem != key:
        return stem or None

    return cleaned


def resolve_scope_normalisation(scope: str | None) -> tuple[str | None, str]:
    """Return ``(canonical_scope, scope_normalised_from)`` for telemetry (RF-1).

    ``scope_normalised_from`` is a key of ``CANONICAL_SCOPE_ALIASES`` when an
    actual alias / path-tail normalisation fired, otherwise the closed default
    ``"none"``. Identity inputs that are already canonical (for example
    ``main`` or ``scoped-history``) report ``"none"`` — no transformation
    occurred. Never returns a filesystem path, raw free token, or empty string
    as the source key.
    """
    if scope is None:
        return None, "none"

    raw = scope.strip()
    if not raw:
        return None, "none"

    simple = raw.lower()
    cleaned = _strip_accidental_path(raw)
    if not cleaned:
        return None, "none"

    key = cleaned.lower()
    matched_key = "none"
    canon: str | None

    if key in CANONICAL_SCOPE_ALIASES:
        canon = CANONICAL_SCOPE_ALIASES[key]
        matched_key = key
    else:
        stem = _PY_SUFFIX_RE.sub("", key)
        if stem != key and stem in CANONICAL_SCOPE_ALIASES:
            canon = CANONICAL_SCOPE_ALIASES[stem]
            matched_key = stem
        elif "." in key:
            if key in CANONICAL_SCOPE_ALIASES:
                canon = CANONICAL_SCOPE_ALIASES[key]
                matched_key = key
            else:
                tail = key.rsplit(".", 1)[-1]
                tail_stem = _PY_SUFFIX_RE.sub("", tail)
                if tail_stem in CANONICAL_SCOPE_ALIASES:
                    canon = CANONICAL_SCOPE_ALIASES[tail_stem]
                    matched_key = tail_stem
                elif tail_stem:
                    return tail_stem, "none"
                else:
                    return None, "none"
        elif stem != key:
            return (stem or None), "none"
        else:
            return cleaned, "none"

    # Identity canonical inputs report no transformation (RF-1 polish).
    # Path/basename reductions still report the alias key that fired even when
    # that key equals the canon value (e.g. docs/usage.md → usage).
    if matched_key != "none" and matched_key == canon and simple == canon:
        return canon, "none"
    return canon, matched_key


def coerce_scope_normalised_from(value: object) -> str:
    """Coerce ``scope_normalised_from`` to a closed alias key or ``none`` (RF-1)."""
    if value is None:
        return "none"
    text = str(value).strip().lower()
    if not text or text == "none":
        return "none"
    if text in CANONICAL_SCOPE_ALIASES:
        return text
    return "none"


# ---------------------------------------------------------------------------
# Stable shared export surface (Issue #204 NTH · future #201 allowlist consumers)
# ---------------------------------------------------------------------------
# Keep this module leaf-adjacent (stdlib only). Downstream allowlists should
# import these helpers rather than copy CANONICAL_SCOPE_ALIASES tables.


def iter_canonical_scope_aliases() -> tuple[tuple[str, str], ...]:
    """Return a stable ``(alias, canonical)`` snapshot of the closed alias map.

    Intended for #201 / ontology allowlist consumers that need the producer-side
    canon without importing presentation policy from ``commit_quality``.
    """
    return tuple(sorted(CANONICAL_SCOPE_ALIASES.items(), key=lambda item: item[0]))


def canonical_scope_values() -> frozenset[str]:
    """Return the closed set of canonical scope slugs (unique values)."""
    return frozenset(CANONICAL_SCOPE_ALIASES.values())


def is_canonical_scope(scope: str | None) -> bool:
    """Return whether *scope* normalises to a known canonical slug value."""
    if scope is None:
        return False
    normalised = normalize_scope(scope)
    if normalised is None:
        return False
    return normalised in canonical_scope_values()


def export_scope_canon() -> dict[str, object]:
    """JSON-serialisable canon snapshot for shared allowlist importers.

    Shape is intentionally small and stable:
    ``{"aliases": {alias: canon}, "canonical_values": [..sorted..]}``.
    """
    return {
        "aliases": dict(sorted(CANONICAL_SCOPE_ALIASES.items())),
        "canonical_values": sorted(canonical_scope_values()),
    }
