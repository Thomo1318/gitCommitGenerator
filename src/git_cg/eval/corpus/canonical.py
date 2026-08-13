"""Canonical JSON serialization helpers (S0 pin style)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(obj: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes (sorted keys, compact separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json_text(obj: Any) -> str:
    return canonical_json_bytes(obj).decode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_sha256(obj: Any) -> str:
    return sha256_hex(canonical_json_bytes(obj))


def message_sha256(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))
