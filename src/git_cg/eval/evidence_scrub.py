"""Shared evidence sanitization for score/gate persistence (no Lane C deps).

Also hosts the S6-C08 secret-safe projection helpers used by operator surfaces
(explain / diagnose / train-export free-text) so secret-bearing values route
through S4 ``mask_secret()`` rather than inventing a second masking law.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from git_cg.eval.mirror.config import mask_secret

_SECRET_TOKENS = frozenset({"api_key", "secret", "password", "token", "authorization"})

# Deterministic secret-shape detectors for free-text projection (offline).
# Whole-value matches are replaced with ``mask_secret(value)``; embedded
# matches are replaced with ``mask_secret(match)`` so raw tokens/prefixes never
# reach stdout, JSON envelopes, or store rows (S6-C08).
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(
        r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\."
        r"[A-Za-z0-9_-]{1,}\."
        r"[A-Za-z0-9_-]{5,}(?![A-Za-z0-9_-])"
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token|authorization)\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?"),
)


def _looks_like_secret_key(key: object) -> bool:
    """True when ``key`` is a str containing a secret-ish token (case-insensitive)."""
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(tok in lowered for tok in _SECRET_TOKENS)


def scrub_evidence_mapping(value: Any) -> Any:
    """Recursively drop secret-looking keys from mappings/lists before persist."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _looks_like_secret_key(key):
                continue
            out[str(key)] = scrub_evidence_mapping(item)
        return out
    if isinstance(value, list):
        return [scrub_evidence_mapping(item) for item in value]
    if isinstance(value, tuple):
        return [scrub_evidence_mapping(item) for item in value]
    return value


def mask_secrets_in_text(value: str | None) -> str | None:
    """Project free text through S4 ``mask_secret`` for secret-shaped content.

    * ``None`` stays ``None``.
    * When the entire string matches a secret shape, return ``mask_secret(value)``.
    * When secret-shaped substrings are embedded, replace each match with
      ``mask_secret(match)`` (never value, never prefix).
    * Non-secret text is returned unchanged.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value  # type: ignore[return-value]
    if not value:
        return value

    # Whole-value secret → single mask form (preferred for pure token fields).
    # Assignment-shaped whole values fall through so the key= prefix is retained.
    stripped = value.strip()
    assignment_pat = _SECRET_VALUE_PATTERNS[-1]
    for pat in _SECRET_VALUE_PATTERNS:
        if pat is assignment_pat:
            continue
        m = pat.fullmatch(stripped)
        if m is not None:
            return mask_secret(stripped)

    # Embedded secrets → replace each matched span with mask_secret(span).
    out = value
    for pat in _SECRET_VALUE_PATTERNS:

        def _repl(match: re.Match[str], _pat: re.Pattern[str] = pat) -> str:
            """Internal helper: repl."""
            # Prefer the captured secret group when present (assignment forms).
            secret = match.group(1) if match.lastindex else match.group(0)
            if not secret:
                secret = match.group(0)
            masked = mask_secret(secret) or ""
            # Keep a stable assignment prefix when the pattern captured a value.
            full = match.group(0)
            if match.lastindex and secret in full:
                return full.replace(secret, masked, 1)
            return masked

        out = pat.sub(_repl, out)
    return out


def mask_optional_operator_text(value: str | None) -> str | None:
    """Mask free-text before persist/export; never restore raw after masking.

    H65 law:
    * ``None`` / blank → ``None``
    * otherwise run ``mask_secrets_in_text`` on the stripped value
    * if masking returns falsy, persist ``""`` (redacted empty) — never the raw input
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    masked = mask_secrets_in_text(stripped)
    if not masked:
        return ""
    return masked


def project_secret_safe(value: Any) -> Any:
    """Recursively project operator payloads so secrets never leave cleartext.

    * Secret-looking mapping keys are dropped (same law as ``scrub_evidence_mapping``).
    * String leaves pass through ``mask_secrets_in_text`` (S4 ``mask_secret``).
    * Lists/tuples are projected element-wise.
    """
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _looks_like_secret_key(key):
                continue
            out[str(key)] = project_secret_safe(item)
        return out
    if isinstance(value, list):
        return [project_secret_safe(item) for item in value]
    if isinstance(value, tuple):
        return [project_secret_safe(item) for item in value]
    if isinstance(value, str):
        return mask_secrets_in_text(value)
    return value


__all__ = [
    "mask_optional_operator_text",
    "mask_secrets_in_text",
    "project_secret_safe",
    "scrub_evidence_mapping",
]
