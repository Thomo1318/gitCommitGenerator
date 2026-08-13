"""Load and validate the offline schema pack."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from git_cg.eval.paths import SCHEMA_DIR, schema_files


class SchemaPackError(ValueError):
    """Schema pack load/validation failure."""


def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    if not path.is_file():
        raise SchemaPackError(f"missing schema: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_instance(schema_name: str, instance: dict[str, Any]) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = "; ".join(e.message for e in errors[:8])
        raise SchemaPackError(f"{schema_name} validation failed: {msgs}")


def is_valid(schema_name: str, instance: dict[str, Any]) -> bool:
    try:
        validate_instance(schema_name, instance)
        return True
    except SchemaPackError, ValidationError, json.JSONDecodeError:
        return False


def list_schema_names() -> list[str]:
    return [p.name.removesuffix(".schema.json") for p in schema_files()]
