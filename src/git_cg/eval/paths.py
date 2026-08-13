"""Path helpers for schema pack and catalog assets."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas" / "eval"
CATALOG_PATH = PACKAGE_ROOT / "data" / "metric_catalog_v0.json"


class SchemaPathError(FileNotFoundError):
    """Schema pack path/discovery failure."""


def schema_files() -> list[Path]:
    """Return committed evaluation schemas (exclude underscore helpers).

    Fails closed when the pack directory is missing or empty so pin digests
    cannot silently hash the empty set.
    """
    if not SCHEMA_DIR.is_dir():
        raise SchemaPathError(f"missing schema pack directory: {SCHEMA_DIR}")
    files = sorted(p for p in SCHEMA_DIR.glob("*.schema.json") if not p.name.startswith("_"))
    if not files:
        raise SchemaPathError(f"empty schema pack directory: {SCHEMA_DIR}")
    return files
