"""S0 catalog loader integrity — offline only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval import catalog as catalog_mod
from git_cg.eval.catalog import CatalogError, clear_catalog_cache, load_metric_catalog
from git_cg.eval.paths import SchemaPathError, schema_files


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_catalog_cache()
    yield
    clear_catalog_cache()


def _write_catalog(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "metric_catalog_v0.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_metric_catalog_returns_defensive_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    first = load_metric_catalog()
    first["metrics"].clear()
    second = load_metric_catalog()
    assert second["metrics"], "cached catalog must not be caller-mutable"


def test_catalog_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", missing)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="missing catalog"):
        load_metric_catalog()


def test_catalog_wrong_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "catalog_id": "other",
            "metrics": [{"metric_id": "x", "polarity": "pass_fail", "authority": "law"}],
            "laws": [{"law_id": "M10"}, {"law_id": "M11"}],
        },
    )
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="catalog_id"):
        load_metric_catalog()


def test_catalog_empty_metrics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path, {"catalog_id": "metric_catalog_v0", "metrics": [], "laws": [{"law_id": "M10"}, {"law_id": "M11"}]}
    )
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="non-empty"):
        load_metric_catalog()


def test_catalog_missing_polarity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "catalog_id": "metric_catalog_v0",
            "metrics": [{"metric_id": "a.x", "authority": "law"}],
            "laws": [{"law_id": "M10"}, {"law_id": "M11"}],
        },
    )
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="polarity"):
        load_metric_catalog()


def test_catalog_invalid_polarity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "catalog_id": "metric_catalog_v0",
            "metrics": [
                {
                    "metric_id": "a.x",
                    "polarity": "higher_is_worse",
                    "authority": "law",
                }
            ],
            "laws": [{"law_id": "M10"}, {"law_id": "M11"}],
        },
    )
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="invalid polarity"):
        load_metric_catalog()


def test_catalog_duplicate_metric_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    row = {"metric_id": "a.x", "polarity": "pass_fail", "authority": "law"}
    path = _write_catalog(
        tmp_path,
        {
            "catalog_id": "metric_catalog_v0",
            "metrics": [row, dict(row)],
            "laws": [{"law_id": "M10"}, {"law_id": "M11"}],
        },
    )
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="duplicate metric_id"):
        load_metric_catalog()


def test_catalog_missing_m11(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "catalog_id": "metric_catalog_v0",
            "metrics": [{"metric_id": "a.x", "polarity": "pass_fail", "authority": "law"}],
            "laws": [{"law_id": "M10"}],
        },
    )
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", path)
    clear_catalog_cache()
    with pytest.raises(CatalogError, match="M11"):
        load_metric_catalog()


def test_schema_files_fail_closed_missing_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from git_cg.eval import paths as paths_mod

    monkeypatch.setattr(paths_mod, "SCHEMA_DIR", tmp_path / "missing")
    with pytest.raises(SchemaPathError, match="missing schema pack directory"):
        schema_files()


def test_schema_files_fail_closed_empty_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from git_cg.eval import paths as paths_mod

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(paths_mod, "SCHEMA_DIR", empty)
    with pytest.raises(SchemaPathError, match="empty schema pack directory"):
        schema_files()
