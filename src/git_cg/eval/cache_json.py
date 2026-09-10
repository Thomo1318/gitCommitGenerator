"""Bounded JSON loader for rebuildable ``.eval/`` cache files.

Cache files are never sole authority. Missing paths, oversize input, invalid
UTF-8, malformed JSON, duplicate keys, or a non-object (when required) map to
``None``. Do not use this helper for authoritative checkpoints, bundles,
catalogs, or schema payloads.

No network. Refs: #257.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_CACHE_MAX_BYTES",
    "object_pairs_reject_duplicates",
    "read_bounded_json",
]

# Rebuildable cache document cap (1 MiB).
DEFAULT_CACHE_MAX_BYTES = 1_048_576


def object_pairs_reject_duplicates(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    """Build a JSON object, rejecting duplicate keys fail-closed."""
    out: dict[Any, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate json object key")
        out[key] = value
    return out


def read_bounded_json(
    path: Path,
    *,
    max_bytes: int = DEFAULT_CACHE_MAX_BYTES,
    object_pairs_hook: Callable[[list[tuple[Any, Any]]], Any] = object_pairs_reject_duplicates,
    require_mapping: bool = False,
) -> Any | None:
    """Load JSON from ``path`` with a byte cap.

    Returns ``None`` for a missing or non-file path, an oversize document
    (including a stale-stat race), invalid UTF-8, malformed JSON, a hook
    failure such as duplicate keys, or a non-mapping when ``require_mapping``
    is true. Never raises for those defects.
    """
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None
        with path.open("rb") as fh:
            blob = fh.read(max_bytes + 1)
        if len(blob) > max_bytes:
            return None
        raw = blob.decode("utf-8")
        data = json.loads(raw, object_pairs_hook=object_pairs_hook)
    except OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError:
        return None
    if require_mapping and not isinstance(data, dict):
        return None
    return data
