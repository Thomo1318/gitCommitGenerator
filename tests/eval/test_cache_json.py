"""Bounded rebuildable-cache JSON loader.

The helper is for rebuildable ``.eval/`` cache files only. Defects map to
``None`` and must never become product authority. Refs: #257.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.cache_json import (
    DEFAULT_CACHE_MAX_BYTES,
    object_pairs_reject_duplicates,
    read_bounded_json,
)


def test_object_pairs_reject_duplicates_builds_and_rejects() -> None:
    assert object_pairs_reject_duplicates([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}
    with pytest.raises(ValueError, match="duplicate json object key"):
        object_pairs_reject_duplicates([("ok", 1), ("ok", 2)])


def test_read_bounded_json_missing_file(tmp_path: Path) -> None:
    assert read_bounded_json(tmp_path / "missing.json") is None


def test_read_bounded_json_non_file(tmp_path: Path) -> None:
    target = tmp_path / "not-a-file"
    target.mkdir()
    assert read_bounded_json(target) is None


def test_read_bounded_json_malformed(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert read_bounded_json(path) is None


def test_read_bounded_json_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_bytes(b"{\xff}")
    assert read_bounded_json(path) is None


def test_read_bounded_json_oversize(tmp_path: Path) -> None:
    path = tmp_path / "big.json"
    path.write_bytes(b"{" + (b"x" * DEFAULT_CACHE_MAX_BYTES) + b"}")
    assert read_bounded_json(path) is None


def test_read_bounded_json_stale_stat_oversize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "big.json"
    path.write_bytes(b"{" + (b"x" * DEFAULT_CACHE_MAX_BYTES) + b"}")
    original_stat = Path.stat

    class _StaleStat:
        def __init__(self, inner: object) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

        @property
        def st_size(self) -> int:
            return 64

    def _stale_stat(self: Path, *args: object, **kwargs: object):
        result = original_stat(self, *args, **kwargs)
        if self == path:
            return _StaleStat(result)
        return result

    monkeypatch.setattr(Path, "stat", _stale_stat)
    assert read_bounded_json(path) is None


def test_read_bounded_json_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "dup.json"
    path.write_text('{"ok": 1, "ok": 2}', encoding="utf-8")
    assert read_bounded_json(path) is None


def test_read_bounded_json_require_mapping(tmp_path: Path) -> None:
    path = tmp_path / "arr.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert read_bounded_json(path) == [1, 2, 3]
    assert read_bounded_json(path, require_mapping=True) is None


def test_read_bounded_json_valid_object(tmp_path: Path) -> None:
    path = tmp_path / "ok.json"
    path.write_text(json.dumps({"checkpoint_id": "ckpt-1", "status": "completed"}), encoding="utf-8")
    assert read_bounded_json(path, require_mapping=True) == {
        "checkpoint_id": "ckpt-1",
        "status": "completed",
    }
