"""Meta checks for the frozen schema pack."""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from git_cg.eval.paths import SCHEMA_DIR
from git_cg.eval.schema_pack import list_schema_names


def test_all_schema_files_are_valid_draft_2020_12() -> None:
    files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    assert files
    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_schema_pack_excludes_underscore_helpers() -> None:
    names = list_schema_names()
    assert all(not n.startswith("_") for n in names)
    assert (SCHEMA_DIR / "_enums.schema.json").is_file()
    assert "_enums" not in names
