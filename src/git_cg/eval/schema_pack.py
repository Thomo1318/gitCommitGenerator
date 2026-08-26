"""Load and validate the offline schema pack."""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from git_cg.eval.paths import SCHEMA_DIR, schema_files


class SchemaPackError(ValueError):
    """Schema pack instance-validation failure."""


class SchemaLoadError(SchemaPackError):
    """Schema pack load / discovery failure (missing/invalid schema file)."""


@cache
def _validator_for(schema_name: str) -> Draft202012Validator:
    """Return the schema validator for a named schema-pack document."""
    path = SCHEMA_DIR / f"{schema_name}.schema.json"
    if not path.is_file():
        raise SchemaLoadError(f"missing schema: {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaLoadError(f"invalid schema JSON: {path}: {exc}") from exc
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaLoadError(f"invalid schema meta: {path}: {exc}") from exc
    return Draft202012Validator(schema)


def load_schema(name: str) -> dict[str, Any]:
    """Load one schema-pack document by name from the frozen pack."""
    path = SCHEMA_DIR / f"{name}.schema.json"
    if not path.is_file():
        raise SchemaLoadError(f"missing schema: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaLoadError(f"invalid schema JSON: {path}: {exc}") from exc


def validate_instance(schema_name: str, instance: dict[str, Any]) -> None:
    """Validate ``instance`` against a named schema-pack document (fail closed)."""
    try:
        validator = _validator_for(schema_name)
    except SchemaLoadError:
        raise
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = "; ".join(e.message for e in errors[:8])
        raise SchemaPackError(f"{schema_name} validation failed: {msgs}")


def is_valid(schema_name: str, instance: dict[str, Any]) -> bool:
    """Return False only for invalid instances.

    Load failures (missing/invalid schema) propagate so callers cannot treat a
    packaging/typo problem as a soft validation miss.
    """
    try:
        validate_instance(schema_name, instance)
        return True
    except SchemaLoadError:
        raise
    except SchemaPackError, ValidationError:
        return False


def list_schema_names() -> list[str]:
    """List schema document names available in the frozen pack."""
    return [p.name.removesuffix(".schema.json") for p in schema_files()]


def clear_schema_cache() -> None:
    """Test helper: drop cached Draft202012 validators."""
    _validator_for.cache_clear()
