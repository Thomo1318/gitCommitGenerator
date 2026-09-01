"""Acceptpath reuse-scan index.json cache behaviour.

Cache is rebuildable and never sole authority. Corrupt, missing, or stale
index entries must fall back to a linear bundle scan without changing bind
behaviour.

Refs: #257.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding import paths as binding_paths
from git_cg.eval.binding.binder import (
    BindInput,
    _cache_write_through,
    _index_entry_key,
    _load_index,
    _reuse_key,
    _scan_reuse_key,
    _write_index,
    bind_final_accept,
    message_sha256_bytes,
)

FINAL = (
    "✨ feat(eval): cache reuse scan\n\nRefs: #257\nSemVer-Impact: PATCH\nChange-Types: fix\nChangelog-Groups: Fixed\n"
)


@pytest.fixture(autouse=True)
def _capture_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)


def _bind(tmp_path: Path, **overrides):
    kwargs = {
        "final_message": FINAL,
        "accept_event_token": "ae_cache",
    }
    kwargs.update(overrides)
    return bind_final_accept(BindInput(**kwargs), repo_root=tmp_path, write=True)


def _bundles(tmp_path: Path) -> Path:
    return tmp_path / ".eval" / "bundles" / "acceptpath"


def test_cache_hit_returns_cached_id(tmp_path: Path) -> None:
    first = _bind(tmp_path)
    assert first.bound is True
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    assert index_path.is_file()
    entries = _load_index(index_path)
    assert entries is not None
    key = _reuse_key(tmp_path, "ae_cache", message_sha256_bytes(FINAL))
    assert key is not None
    assert entries[_index_entry_key(key)] == session

    # Second bind must reuse via cache-assisted path.
    second = _bind(tmp_path)
    assert second.bundle["session_thread_id"] == session
    files = [p for p in _bundles(tmp_path).glob("*.json") if p.name != "index.json"]
    assert len(files) == 1


def test_cache_miss_falls_back_to_scan(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_miss")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    # Empty valid index → miss → linear scan still finds bundle.
    _write_index(index_path, {})
    second = _bind(tmp_path, accept_event_token="ae_miss")
    assert second.bundle["session_thread_id"] == session


def test_corrupt_index_falls_back_to_scan(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_corrupt")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.write_text("{not-json", encoding="utf-8")
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_corrupt")
    assert second.bundle["session_thread_id"] == session


def test_stale_index_falls_back_to_scan(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_stale")
    session = first.bundle["session_thread_id"]
    key = _reuse_key(tmp_path, "ae_stale", message_sha256_bytes(FINAL))
    assert key is not None
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    # Point cache at a non-existent session id (stale entry).
    _write_index(index_path, {_index_entry_key(key): "sess_does_not_exist"})
    second = _bind(tmp_path, accept_event_token="ae_stale")
    assert second.bundle["session_thread_id"] == session


def test_write_through_after_successful_bind(tmp_path: Path) -> None:
    result = _bind(tmp_path, accept_event_token="ae_wt")
    assert result.bound is True
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    entries = _load_index(index_path)
    assert entries is not None
    key = _reuse_key(tmp_path, "ae_wt", message_sha256_bytes(FINAL))
    assert entries[_index_entry_key(key)] == result.bundle["session_thread_id"]


def test_rebuild_from_bundles_recreates_index(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_rebuild")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.unlink()
    assert not index_path.exists()
    key = _reuse_key(tmp_path, "ae_rebuild", message_sha256_bytes(FINAL))
    assert key is not None
    scanned = _scan_reuse_key(_bundles(tmp_path), key)
    assert scanned is not None
    assert scanned["session_thread_id"] == session
    # Linear scan hit write-through rebuilds the cache.
    entries = _load_index(index_path)
    assert entries is not None
    assert entries[_index_entry_key(key)] == session


def test_no_behaviour_change_when_index_absent(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_absent")
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    if index_path.exists():
        index_path.unlink()
    second = _bind(tmp_path, accept_event_token="ae_absent")
    assert first.bundle["session_thread_id"] == second.bundle["session_thread_id"]
    assert first.bound is True and second.bound is True


def test_wrong_version_index_ignored(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_ver")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.write_text(json.dumps({"version": 99, "entries": {"x": "y"}}), encoding="utf-8")
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_ver")
    assert second.bundle["session_thread_id"] == session


def test_cache_write_failure_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise binding_paths.LayerAPathError("cache write boom")

    # First bind succeeds even if cache write fails after bundle write.
    calls: list[str] = []
    real_atomic = binding_paths.atomic_write_json

    def _wrap(path, payload):
        calls.append(Path(path).name)
        if Path(path).name == "index.json":
            raise binding_paths.LayerAPathError("cache write boom")
        return real_atomic(path, payload)

    monkeypatch.setattr(binding_paths, "atomic_write_json", _wrap)
    result = _bind(tmp_path, accept_event_token="ae_cachefail")
    assert result.bound is True
    assert result.errors == ()
    assert any(name.endswith(".json") and name != "index.json" for name in calls)


def test_load_index_rejects_non_object_and_bad_entries(tmp_path: Path) -> None:
    p = tmp_path / "index.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert _load_index(p) is None
    p.write_text(json.dumps({"version": 1, "entries": "nope"}), encoding="utf-8")
    assert _load_index(p) is None
    p.write_text(
        json.dumps({"version": 1, "entries": {"ok": "sess_x", "blank": "  ", "b": 2}}),
        encoding="utf-8",
    )
    loaded = _load_index(p)
    assert loaded == {"ok": "sess_x"}


def test_cache_write_through_ignores_blank_session(tmp_path: Path) -> None:
    index_path = tmp_path / "index.json"
    key = (str(tmp_path), "tok", "a" * 64)
    _cache_write_through(index_path, key, "   ")
    assert not index_path.exists()
