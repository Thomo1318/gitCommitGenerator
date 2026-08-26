"""Reproducible content pins for schema pack and metric catalog."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from git_cg.eval.paths import CATALOG_PATH, schema_files


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 digest bytes for ``data``."""
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(path: Path) -> bytes:
    """Encode ``payload`` as canonical JSON bytes for hashing."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@lru_cache(maxsize=1)
def schema_pack_digest() -> str:
    """SHA-256 over canonical concatenation of all eval schemas."""
    h = hashlib.sha256()
    nul = bytes([0])
    for path in schema_files():
        h.update(path.name.encode("utf-8"))
        h.update(nul)
        h.update(_canonical_json_bytes(path))
        h.update(nul)
    return h.hexdigest()


@lru_cache(maxsize=1)
def metric_catalog_digest() -> str:
    """Digest the pinned metric catalog contents for pin integrity checks."""
    return _sha256_bytes(_canonical_json_bytes(CATALOG_PATH))


def schema_pack_pin() -> str:
    """Return the frozen schema-pack content pin used by fail-closed stores."""
    return f"schema_pack_v0@{schema_pack_digest()}"


def metric_catalog_pin() -> str:
    """Return the frozen metric-catalog content pin used by fail-closed stores."""
    return f"metric_catalog_v0@{metric_catalog_digest()}"


def clear_pin_cache() -> None:
    """Test helper: drop cached digests after on-disk edits."""
    schema_pack_digest.cache_clear()
    metric_catalog_digest.cache_clear()
