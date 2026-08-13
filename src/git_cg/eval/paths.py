"""Path helpers for schema pack and catalog assets."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas" / "eval"
CATALOG_PATH = PACKAGE_ROOT / "data" / "metric_catalog_v0.json"


def schema_files() -> list[Path]:
    """Return committed evaluation schemas (exclude underscore helpers)."""
    if not SCHEMA_DIR.is_dir():
        return []
    return sorted(p for p in SCHEMA_DIR.glob("*.schema.json") if not p.name.startswith("_"))
