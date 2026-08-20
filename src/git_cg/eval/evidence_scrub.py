"""Shared evidence sanitization for score/gate persistence (no Lane C deps)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_SECRET_TOKENS = frozenset({"api_key", "secret", "password", "token", "authorization"})


def _looks_like_secret_key(key: object) -> bool:
    """Determine whether a key contains a case-insensitive secret-related term.
    
    Parameters:
    	key (object): The key to inspect.
    
    Returns:
    	`true` if the key is a string containing a configured secret-related term, `false` otherwise.
    """
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(tok in lowered for tok in _SECRET_TOKENS)


def scrub_evidence_mapping(value: Any) -> Any:
    """
    Recursively sanitise evidence by removing secret-looking mapping keys.
    
    Parameters:
        value (Any): Evidence value to sanitise.
    
    Returns:
        Any: Sanitised mappings and sequences, with tuples converted to lists; other values are unchanged.
    """
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
