"""Shared evidence sanitization for score/gate persistence (no Lane C deps)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_SECRET_TOKENS = frozenset({"api_key", "secret", "password", "token", "authorization"})


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
