"""Meta checks for the frozen schema pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from git_cg.eval import schema_pack as schema_pack_mod
from git_cg.eval.paths import SCHEMA_DIR
from git_cg.eval.schema_pack import (
    SchemaLoadError,
    SchemaPackError,
    clear_schema_cache,
    is_valid,
    list_schema_names,
    load_schema,
    validate_instance,
)

VALID_SCORE_RESULT = {
    "metric_id": "a.final_message_present",
    "polarity": "pass_fail",
    "authority": "law",
    "source": "local_wrapper",
    "value": True,
}


@pytest.fixture(autouse=True)
def _clear_schema_pack_cache() -> None:
    clear_schema_cache()
    yield
    clear_schema_cache()


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


def test_is_valid_returns_true_for_valid_instance() -> None:
    assert is_valid("score_result_v1", VALID_SCORE_RESULT) is True


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


def test_load_schema_returns_draft_document() -> None:
    schema = load_schema("score_result_v1")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("score_result_v1.schema.json")


def test_load_schema_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schema_pack_mod, "SCHEMA_DIR", tmp_path)
    with pytest.raises(SchemaLoadError, match="missing schema"):
        load_schema("nope_v1")


def test_load_schema_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "broken_v1.schema.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(schema_pack_mod, "SCHEMA_DIR", tmp_path)
    with pytest.raises(SchemaLoadError, match="invalid schema JSON"):
        load_schema("broken_v1")


def test_validator_for_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "broken_v1.schema.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(schema_pack_mod, "SCHEMA_DIR", tmp_path)
    with pytest.raises(SchemaLoadError, match="invalid schema JSON"):
        validate_instance("broken_v1", {"id": "x"})


def test_validator_for_invalid_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Valid JSON, invalid Draft 2020-12 meta (type must be string/array, not int).
    path = tmp_path / "bad_meta_v1.schema.json"
    path.write_text(json.dumps({"type": 123}), encoding="utf-8")
    monkeypatch.setattr(schema_pack_mod, "SCHEMA_DIR", tmp_path)
    with pytest.raises(SchemaLoadError, match="invalid schema meta"):
        validate_instance("bad_meta_v1", {"id": "x"})


def test_clear_schema_cache_reloads_validators(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
    }
    path = tmp_path / "cache_probe_v1.schema.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    monkeypatch.setattr(schema_pack_mod, "SCHEMA_DIR", tmp_path)

    validate_instance("cache_probe_v1", {"id": "ok"})
    # Corrupt on disk; cached validator should still succeed until cleared.
    path.write_text("{not-json", encoding="utf-8")
    validate_instance("cache_probe_v1", {"id": "still-cached"})

    clear_schema_cache()
    with pytest.raises(SchemaLoadError, match="invalid schema JSON"):
        validate_instance("cache_probe_v1", {"id": "reload"})
