"""eval_suite_v1 load + pin binding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from git_cg.eval.corpus.aliases import DatasetAliasError, resolve_dataset_id
from git_cg.eval.corpus.fixtures import FixtureLoadError, default_fixture_root, load_fixture_dict
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import SchemaPackError, validate_instance


class SuiteLoadError(ValueError):
    """Suite load / pin / alias failure."""


def load_suite(
    suite_id: str = "cm-eval-fixtures-core",
    *,
    fixture_root: Path | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Load a committed suite definition and bind live S0 pins."""
    root = fixture_root or default_fixture_root()
    try:
        stable = resolve_dataset_id(suite_id)
    except DatasetAliasError as exc:
        raise SuiteLoadError(str(exc)) from exc

    suite_path = path or (root / "suites" / f"{stable}.json")
    if not suite_path.is_file():
        # allow alias filename
        alt = root / "suites" / f"{suite_id}.json"
        if alt.is_file():
            suite_path = alt
        else:
            raise SuiteLoadError(f"missing suite definition: {suite_path}")

    try:
        data = load_fixture_dict(suite_path)
    except FixtureLoadError as exc:
        raise SuiteLoadError(str(exc)) from exc

    # Identity checks
    file_suite_id = data.get("suite_id") or data.get("id")
    if isinstance(file_suite_id, str):
        try:
            file_stable = resolve_dataset_id(file_suite_id)
        except DatasetAliasError as exc:
            raise SuiteLoadError(str(exc)) from exc
        if file_stable != stable:
            raise SuiteLoadError(f"suite file id {file_suite_id!r} does not match requested {suite_id!r}")

    pack = schema_pack_pin()
    catalog = metric_catalog_pin()

    suite: dict[str, Any] = {
        "schema_version": "eval_suite_v1",
        "id": f"suite:{stable}",
        "suite_id": stable,
        "schema_pack_pin": pack,
        "metric_catalog_pin": catalog,
        "schema_pack": pack,
        "metric_catalog": catalog,
    }
    if "case_ids" in data:
        suite["case_ids"] = data["case_ids"]
    if "case_paths" in data:
        suite["case_paths"] = data["case_paths"]
    if "notes" in data:
        suite["notes"] = data["notes"]
    if "meta" in data and isinstance(data["meta"], dict):
        suite["meta"] = dict(data["meta"])
    else:
        suite["meta"] = {}
    suite["meta"].setdefault("producer", "fixture_encoder_s1")
    suite["meta"]["network_policy"] = "offline_required"
    suite["meta"]["mode_default"] = "fixture_offline"

    # Validate schema-visible subset (case_paths is encoder-only; strip before schema check)
    schema_view = {k: v for k, v in suite.items() if k != "case_paths"}
    try:
        validate_instance("eval_suite_v1", schema_view)
    except SchemaPackError as exc:
        raise SuiteLoadError(str(exc)) from exc

    # Keep case_paths on returned object for loaders
    return suite


def materialize_suite(
    suite_id: str = "cm-eval-fixtures-core",
    *,
    fixture_root: Path | None = None,
) -> dict[str, Any]:
    """Load suite JSON without live pin overwrite (for raw inspection)."""
    root = fixture_root or default_fixture_root()
    stable = resolve_dataset_id(suite_id)
    path = root / "suites" / f"{stable}.json"
    if not path.is_file():
        raise SuiteLoadError(f"missing suite definition: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
