"""Reproducible content pins for schema pack and metric catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from git_cg.eval.paths import CATALOG_PATH, schema_files


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(path: Path) -> bytes:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def schema_pack_digest() -> str:
    """SHA-256 over canonical concatenation of all eval schemas."""
    h = hashlib.sha256()
    for path in schema_files():
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(_canonical_json_bytes(path))
        h.update(b"\0")
    return h.hexdigest()


def metric_catalog_digest() -> str:
    return _sha256_bytes(_canonical_json_bytes(CATALOG_PATH))


def schema_pack_pin() -> str:
    return f"schema_pack_v0@{schema_pack_digest()}"


def metric_catalog_pin() -> str:
    return f"metric_catalog_v0@{metric_catalog_digest()}"
