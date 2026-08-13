"""Meta checks for the frozen schema pack."""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from git_cg.eval.paths import SCHEMA_DIR
from git_cg.eval.schema_pack import (
    SchemaLoadError,
    SchemaPackError,
    is_valid,
    list_schema_names,
    validate_instance,
)


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


def test_is_valid_returns_false_only_for_invalid_instance() -> None:
    bad = {
        "metric_id": "a.final_message_present",
        "polarity": "pass_fail",
        "authority": "law",
        "source": "local_wrapper",
        "value": 1,
    }
    assert is_valid("score_result_v1", bad) is False


def test_is_valid_propagates_missing_schema() -> None:
    with pytest.raises(SchemaLoadError, match="missing schema"):
        is_valid("definitely_missing_schema_v1", {"id": "x"})


def test_validate_instance_missing_schema_is_load_error() -> None:
    with pytest.raises(SchemaLoadError):
        validate_instance("definitely_missing_schema_v1", {"id": "x"})
    with pytest.raises(SchemaPackError):
        validate_instance(
            "score_result_v1",
            {
                "metric_id": "a.final_message_present",
                "polarity": "pass_fail",
                "authority": "law",
                "source": "local_wrapper",
                "value": 1,
            },
        )
