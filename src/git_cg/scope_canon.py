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
