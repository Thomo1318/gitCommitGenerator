"""Acceptpath reuse-scan index.json cache behaviour.

Cache is rebuildable and never sole authority. Corrupt, missing, stale,
oversized, or malformed index data must fall back to a miss-scan without
changing bind behaviour.

Miss-scan is hybrid-bounded: at most K recent regular ``*.json``
bundles, default 512, mtime descending / filename ascending. Truncation
sets ``meta.scan_bounded=true`` only on that miss-scan. Cache hits and
``GIT_CG_EVAL_ACCEPTPATH_FULL_SCAN=1`` never set the marker.

The 1k/10k harness (``-k benchmark``) records bounded-scan and lock-hold
timings. It does not ratify K or the lock budget.

Refs: #257.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from git_cg.eval.binding import paths as binding_paths
from git_cg.eval.binding.binder import (
    _DEFAULT_SCAN_WINDOW,
    _FULL_SCAN_ENV,
    _INDEX_MAX_BYTES,
    _INDEX_MAX_ENTRIES,
    _INDEX_MAX_KEY_BYTES,
    _INDEX_MAX_SESSION_ID_BYTES,
    _INDEX_VERSION,
    _SCAN_WINDOW_ENV,
    BindInput,
    _acceptpath_full_scan,
    _acceptpath_scan_window,
    _cache_write_through,
    _index_entry_admissible,
    _index_entry_key,
    _index_object_pairs,
    _load_bundle_for_session,
    _load_index,
    _reuse_key,
    _scan_reuse_key,
    _write_index,
    bind_final_accept,
    message_sha256_bytes,
)
from git_cg.eval.binding.lock import acquire_bind_lock
from git_cg.eval.schema_pack import is_valid

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


def _authoritative_bundle_path(tmp_path: Path) -> Path:
    files = [path for path in _bundles(tmp_path).glob("*.json") if path.name != "index.json"]
    assert len(files) == 1
    return files[0]


def _rewrite_authoritative_bundle(tmp_path: Path, mutate) -> dict:
    path = _authoritative_bundle_path(tmp_path)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    mutate(bundle)
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return bundle


def _poison_cache(tmp_path: Path, token: str, session_id: str) -> tuple[str, str, str]:
    key = _reuse_key(tmp_path, token, message_sha256_bytes(FINAL))
    assert key is not None
    _write_index(binding_paths.acceptpath_index_file(tmp_path), {_index_entry_key(key): session_id})
    return key


def _assert_loader_skips_fs(monkeypatch: pytest.MonkeyPatch, bundles_dir: Path, session_id: str) -> None:
    seen: list[str] = []
    original_is_file = Path.is_file

    def spy_is_file(self: Path) -> bool:
        seen.append(str(self))
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", spy_is_file)
    assert _load_bundle_for_session(bundles_dir, session_id) is None
    assert seen == []


def _assert_scan_skips_join(monkeypatch: pytest.MonkeyPatch, session_id: str) -> None:
    original_truediv = Path.__truediv__
    forbidden = f"{session_id}.json"

    def spy_truediv(self: Path, other: object):
        if str(other) == forbidden:
            raise AssertionError(f"malformed session id must not be joined onto a path: {session_id!r}")
        return original_truediv(self, other)

    monkeypatch.setattr(Path, "__truediv__", spy_truediv)


def _bind_rejects_cached_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    bad_id: str,
) -> str:
    first = _bind(tmp_path, accept_event_token=token)
    session = first.bundle["session_thread_id"]
    _assert_loader_skips_fs(monkeypatch, _bundles(tmp_path), bad_id)
    _poison_cache(tmp_path, token, bad_id)

    loaded_ids: list[str] = []
    real_loader = _load_bundle_for_session

    def spy_loader(bundles_dir: Path, session_id: str):
        loaded_ids.append(session_id)
        return real_loader(bundles_dir, session_id)

    monkeypatch.setattr(
        "git_cg.eval.binding.binder._load_bundle_for_session",
        spy_loader,
    )
    _assert_scan_skips_join(monkeypatch, bad_id)
    second = _bind(tmp_path, accept_event_token=token)
    assert bad_id not in loaded_ids
    assert second.bound is True
    assert second.errors == ()
    assert second.bundle["session_thread_id"] == session
    return session


def test_index_entry_key_is_injective_for_separator_collisions() -> None:
    final_sha = "a" * 64
    first = ("/tmp/repo", "accept::token", final_sha)
    second = ("/tmp/repo::accept", "token", final_sha)

    first_key = _index_entry_key(first)
    second_key = _index_entry_key(second)

    assert first_key != second_key
    assert json.loads(first_key) == list(first)
    assert json.loads(second_key) == list(second)


def test_index_entry_key_uses_canonical_json_array_encoding() -> None:
    key = ("/tmp/répô", "accept_unicode", "b" * 64)

    assert _index_entry_key(key) == json.dumps(
        list(key),
        ensure_ascii=False,
        separators=(",", ":"),
    )


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


def test_binder_uses_acceptpath_index_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind consults acceptpath_index_file(root) for cache lookup and write-through."""
    index_calls: list[Path] = []
    relocated = tmp_path / ".eval" / "relocated-index.json"

    def relocated_index(repo_root: Path) -> Path:
        index_calls.append(Path(repo_root).resolve())
        return relocated

    monkeypatch.setattr(binding_paths, "acceptpath_index_file", relocated_index)

    first = _bind(tmp_path, accept_event_token="ae_index_path")
    assert first.bound is True
    session = first.bundle["session_thread_id"]
    assert index_calls
    assert all(path == tmp_path.resolve() for path in index_calls)
    assert relocated.is_file()
    assert not (_bundles(tmp_path) / "index.json").exists()
    entries = _load_index(relocated)
    assert entries is not None
    key = _reuse_key(tmp_path, "ae_index_path", message_sha256_bytes(FINAL))
    assert key is not None
    assert entries[_index_entry_key(key)] == session

    second = _bind(tmp_path, accept_event_token="ae_index_path")
    assert second.bundle["session_thread_id"] == session
    assert index_calls
    assert all(path == tmp_path.resolve() for path in index_calls)
    assert relocated.is_file()
    assert not (_bundles(tmp_path) / "index.json").exists()


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


def test_v1_index_is_ignored_then_rebuilt_as_v2(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_v1")
    key = _reuse_key(tmp_path, "ae_v1", message_sha256_bytes(FINAL))
    assert key is not None
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    legacy_key = "::".join(key)
    index_path.write_text(
        json.dumps({"version": 1, "entries": {legacy_key: first.bundle["session_thread_id"]}}),
        encoding="utf-8",
    )

    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_v1")

    assert second.bundle["session_thread_id"] == first.bundle["session_thread_id"]
    loaded = _load_index(index_path)
    assert loaded is not None
    assert loaded[_index_entry_key(key)] == first.bundle["session_thread_id"]
    assert json.loads(index_path.read_text(encoding="utf-8"))["version"] == _INDEX_VERSION


def test_wrong_version_index_ignored(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_ver")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.write_text(json.dumps({"version": 99, "entries": {"x": "y"}}), encoding="utf-8")
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_ver")
    assert second.bundle["session_thread_id"] == session


def test_cache_write_failure_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real_atomic = binding_paths.atomic_write_json

    def _fail_index_write(path, payload, **kwargs):
        calls.append(Path(path).name)
        if Path(path).name == "index.json":
            raise binding_paths.LayerAPathError("cache write failed")
        return real_atomic(path, payload, **kwargs)

    monkeypatch.setattr(binding_paths, "atomic_write_json", _fail_index_write)
    result = _bind(tmp_path, accept_event_token="ae_cachefail")
    assert result.bound is True
    assert result.errors == ()
    assert any(name.endswith(".json") and name != "index.json" for name in calls)


def test_load_index_rejects_non_object_and_bad_entries(tmp_path: Path) -> None:
    p = tmp_path / "index.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert _load_index(p) is None
    p.write_text(json.dumps({"version": _INDEX_VERSION, "entries": "nope"}), encoding="utf-8")
    assert _load_index(p) is None
    p.write_text(
        json.dumps({"version": _INDEX_VERSION, "entries": {"ok": "sess_x", "blank": "  "}}),
        encoding="utf-8",
    )
    assert _load_index(p) is None
    p.write_text(
        json.dumps({"version": _INDEX_VERSION, "entries": {"": "sess_x"}}),
        encoding="utf-8",
    )
    assert _load_index(p) is None


def test_oversized_index_treated_as_miss(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_oversize")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.write_bytes(b"{" + (b"x" * _INDEX_MAX_BYTES) + b"}")
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_oversize")
    assert second.bound is True
    assert second.errors == ()
    assert second.bundle["session_thread_id"] == session


def test_index_size_cap_after_stale_stat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    index_path = tmp_path / "index.json"
    index_path.write_bytes(b"{" + (b"x" * _INDEX_MAX_BYTES) + b"}")
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
        if self == index_path:
            return _StaleStat(result)
        return result

    monkeypatch.setattr(Path, "stat", _stale_stat)
    assert _load_index(index_path) is None


def test_index_entry_rejects_unencodable_key_or_value() -> None:
    assert _index_entry_admissible("\ud800", "sess_x") is False
    assert _index_entry_admissible("ok", "\ud800") is False


def test_index_entry_count_cap_miss(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_count_cap")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    too_many = {str(i): "sess_x" for i in range(_INDEX_MAX_ENTRIES + 1)}
    index_path.write_text(
        json.dumps({"version": _INDEX_VERSION, "entries": too_many}),
        encoding="utf-8",
    )
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_count_cap")
    assert second.bundle["session_thread_id"] == session


def test_index_non_string_entry_miss(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_non_string")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.write_text(
        json.dumps({"version": _INDEX_VERSION, "entries": {"ok": "sess_x", "b": 2}}),
        encoding="utf-8",
    )
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_non_string")
    assert second.bundle["session_thread_id"] == session


def test_index_object_pairs_builds_objects_and_rejects_duplicates() -> None:
    assert _index_object_pairs([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}
    with pytest.raises(ValueError, match="duplicate json object key"):
        _index_object_pairs([("a", 1), ("a", 2)])


def test_index_duplicate_keys_miss(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_dup_keys")
    session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.write_text(
        f'{{"version": {_INDEX_VERSION}, "entries": {{"ok": "sess_a", "ok": "sess_b"}}}}',
        encoding="utf-8",
    )
    assert _load_index(index_path) is None
    second = _bind(tmp_path, accept_event_token="ae_dup_keys")
    assert second.bundle["session_thread_id"] == session


def test_load_index_rejects_oversized_key_or_session_value(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_oversize_fields")
    session = first.bundle["session_thread_id"]
    p = binding_paths.acceptpath_index_file(tmp_path)
    p.write_text(
        json.dumps({"version": _INDEX_VERSION, "entries": {"x" * (_INDEX_MAX_KEY_BYTES + 1): "sess_x"}}),
        encoding="utf-8",
    )
    assert _load_index(p) is None
    second = _bind(tmp_path, accept_event_token="ae_oversize_fields")
    assert second.bundle["session_thread_id"] == session
    p.write_text(
        json.dumps({"version": _INDEX_VERSION, "entries": {"ok": "s" * (_INDEX_MAX_SESSION_ID_BYTES + 1)}}),
        encoding="utf-8",
    )
    assert _load_index(p) is None
    third = _bind(tmp_path, accept_event_token="ae_oversize_fields")
    assert third.bundle["session_thread_id"] == session


def test_write_index_refuses_oversized_entry_count(tmp_path: Path) -> None:
    p = tmp_path / "index.json"
    p.write_text("keep-me", encoding="utf-8")
    too_many = {str(i): "sess_x" for i in range(_INDEX_MAX_ENTRIES + 1)}
    _write_index(p, too_many)
    assert p.read_text(encoding="utf-8") == "keep-me"


def test_write_index_refuses_oversized_key_or_session_value(tmp_path: Path) -> None:
    p = tmp_path / "index.json"
    p.write_text("keep-me", encoding="utf-8")
    _write_index(p, {"x" * (_INDEX_MAX_KEY_BYTES + 1): "sess_x"})
    assert p.read_text(encoding="utf-8") == "keep-me"
    _write_index(p, {"ok": "s" * (_INDEX_MAX_SESSION_ID_BYTES + 1)})
    assert p.read_text(encoding="utf-8") == "keep-me"
    _write_index(p, {"": "sess_x"})
    assert p.read_text(encoding="utf-8") == "keep-me"


def test_write_index_refuses_oversized_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "index.json"
    p.write_text("keep-me", encoding="utf-8")
    monkeypatch.setattr(
        "git_cg.eval.binding.binder.json.dumps",
        lambda *_args, **_kwargs: "x" * _INDEX_MAX_BYTES,
    )
    _write_index(p, {"ok": "sess_x"})
    assert p.read_text(encoding="utf-8") == "keep-me"


def test_write_index_swallows_serialize_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "index.json"
    p.write_text("keep-me", encoding="utf-8")

    def _boom(*_args: object, **_kwargs: object) -> str:
        raise TypeError("cannot serialize")

    monkeypatch.setattr("git_cg.eval.binding.binder.json.dumps", _boom)
    _write_index(p, {"ok": "sess_x"})
    assert p.read_text(encoding="utf-8") == "keep-me"


def test_cache_write_through_ignores_blank_session(tmp_path: Path) -> None:
    index_path = tmp_path / "index.json"
    key = (str(tmp_path), "tok", "a" * 64)
    _cache_write_through(index_path, key, "   ")
    assert not index_path.exists()


def test_cache_hit_session_mismatch_not_reused(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_identity_session")
    original_session = first.bundle["session_thread_id"]

    def mutate(bundle: dict) -> None:
        bundle["session_thread_id"] = "sess_" + ("b" * 32)

    _rewrite_authoritative_bundle(tmp_path, mutate)
    second = _bind(tmp_path, accept_event_token="ae_identity_session")

    assert second.bound is True
    assert second.bundle["session_thread_id"] != original_session


@pytest.mark.parametrize(
    "stored_root",
    ["/other/repo", "", None],
    ids=["cross_root", "empty", "missing"],
)
def test_cache_hit_repo_root_mismatch_not_reused(tmp_path: Path, stored_root: str | None) -> None:
    first = _bind(tmp_path, accept_event_token="ae_identity_root")
    original_session = first.bundle["session_thread_id"]

    def mutate(bundle: dict) -> None:
        accept_event = bundle["meta"]["accept_event"]
        if stored_root is None:
            accept_event.pop("repo_root", None)
        else:
            accept_event["repo_root"] = stored_root

    _rewrite_authoritative_bundle(tmp_path, mutate)
    second = _bind(tmp_path, accept_event_token="ae_identity_root")

    assert second.bound is True
    assert second.bundle["session_thread_id"] != original_session


def test_reuse_adoption_requires_valid_schema(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_identity_schema")
    original_session = first.bundle["session_thread_id"]
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    index_path.unlink()

    def mutate(bundle: dict) -> None:
        bundle["schema_version"] = "ape_bundle_v0"

    _rewrite_authoritative_bundle(tmp_path, mutate)
    second = _bind(tmp_path, accept_event_token="ae_identity_schema")

    assert second.bound is True
    assert second.bundle["session_thread_id"] != original_session


@pytest.mark.parametrize(
    ("field", "value"),
    [("bound", False), ("artifact_class", "fixture")],
)
def test_reuse_adoption_requires_bound_final_accept(tmp_path: Path, field: str, value: object) -> None:
    first = _bind(tmp_path, accept_event_token=f"ae_identity_{field}")
    original_session = first.bundle["session_thread_id"]

    def mutate(bundle: dict) -> None:
        bundle[field] = value

    _rewrite_authoritative_bundle(tmp_path, mutate)
    second = _bind(tmp_path, accept_event_token=f"ae_identity_{field}")

    assert second.bound is True
    assert second.bundle["session_thread_id"] != original_session


def test_cache_id_rejected_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _bind(tmp_path, accept_event_token="ae_empty_id")
    session = first.bundle["session_thread_id"]
    _assert_loader_skips_fs(monkeypatch, _bundles(tmp_path), "")

    monkeypatch.setattr(
        "git_cg.eval.binding.binder._cache_lookup_session",
        lambda *_args, **_kwargs: "",
    )
    _assert_scan_skips_join(monkeypatch, "")
    second = _bind(tmp_path, accept_event_token="ae_empty_id")
    assert second.bound is True
    assert second.errors == ()
    assert second.bundle["session_thread_id"] == session


@pytest.mark.parametrize(
    "bad_id",
    ["sess_../../x", "sess_..%2F", "sess_/abs"],
)
def test_cache_id_rejected_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_id: str,
) -> None:
    _bind_rejects_cached_id(tmp_path, monkeypatch, f"ae_trav_{bad_id}", bad_id)
    assert not (_bundles(tmp_path).parent / "x.json").exists()
    assert not (_bundles(tmp_path) / "sess_" / "abs.json").exists()


@pytest.mark.parametrize(
    "bad_id",
    [
        "sess_" + ("A" * 32),
        "sess_" + ("a" * 31),
        "sess_" + ("g" * 32),
        "sess_01234567-89ab-cdef-0123-456789abcdef",
    ],
)
def test_cache_id_rejected_malformed_grammar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_id: str,
) -> None:
    _bind_rejects_cached_id(tmp_path, monkeypatch, "ae_malformed", bad_id)


def test_cache_id_rejected_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trap = tmp_path / "escaped.json"
    trap.write_text("{}", encoding="utf-8")
    _bind_rejects_cached_id(tmp_path, monkeypatch, "ae_abs_id", str(trap.with_suffix("")))
    assert trap.read_text(encoding="utf-8") == "{}"


def test_cache_id_rejected_whitespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    padded = f"  sess_{'a' * 32}  "
    _assert_loader_skips_fs(monkeypatch, _bundles(tmp_path), " \t ")
    _bind_rejects_cached_id(tmp_path, monkeypatch, "ae_ws_id", padded)


def test_valid_id_still_hits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _bind(tmp_path, accept_event_token="ae_valid_id")
    session = first.bundle["session_thread_id"]
    assert binding_paths.SESSION_ID_RE.fullmatch(session) is not None
    key = _reuse_key(tmp_path, "ae_valid_id", message_sha256_bytes(FINAL))
    assert key is not None
    scanned_without_glob = _scan_reuse_key(_bundles(tmp_path), key)
    assert scanned_without_glob is not None
    assert scanned_without_glob["session_thread_id"] == session

    def boom_glob(self, pattern):
        raise AssertionError(f"miss-scan glob should not run on a valid cache hit: {pattern!r}")

    monkeypatch.setattr(Path, "glob", boom_glob)
    second = _bind(tmp_path, accept_event_token="ae_valid_id")
    assert second.bound is True
    assert second.bundle["session_thread_id"] == session
    files = [path for path in _bundles(tmp_path).iterdir() if path.suffix == ".json" and path.name != "index.json"]
    assert len(files) == 1


def test_cache_id_symlink_escape_falls_back_to_scan(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_symlink_escape")
    session = first.bundle["session_thread_id"]
    bundles = _bundles(tmp_path)
    decoy = "sess_" + ("c" * 32)
    trap = tmp_path / "escaped.json"
    trap.write_text('{"poison": true}', encoding="utf-8")
    (bundles / f"{decoy}.json").symlink_to(trap)
    _poison_cache(tmp_path, "ae_symlink_escape", decoy)

    second = _bind(tmp_path, accept_event_token="ae_symlink_escape")
    assert second.bound is True
    assert second.errors == ()
    assert second.bundle["session_thread_id"] == session
    assert json.loads(trap.read_text(encoding="utf-8")) == {"poison": True}


def _clone_acceptpath_bundle(
    template: dict[str, Any],
    *,
    session_id: str,
    token: str,
    final_sha: str,
    repo_root: str,
) -> dict[str, Any]:
    bundle = json.loads(json.dumps(template))
    bundle["session_thread_id"] = session_id
    bundle["case_id"] = f"acceptpath:{session_id}"
    bundle["final_message_sha256"] = final_sha
    meta = dict(bundle.get("meta") or {})
    accept_event = dict(meta.get("accept_event") or {})
    accept_event["token"] = token
    accept_event["repo_root"] = repo_root
    meta["accept_event"] = accept_event
    bundle["meta"] = meta
    bundle["bound"] = True
    bundle["artifact_class"] = "final_accept"
    return bundle


# Bounded miss-scan window and truncation marker. Refs: #257.


def _unlink_acceptpath_index(tmp_path: Path) -> None:
    index_path = binding_paths.acceptpath_index_file(tmp_path)
    if index_path.exists():
        index_path.unlink()


def _plant_window_bundles(
    tmp_path: Path,
    specs: list[tuple[str, str, float]],
) -> tuple[Path, dict[str, Any], str]:
    """Write ``(session_id, token, mtime)`` twins and return ``(dir, template, sha)``."""
    template_result = _bind(tmp_path, accept_event_token="ae_window_template")
    assert template_result.bound is True
    template = template_result.bundle
    assert template is not None
    assert is_valid("ape_bundle_v1", template)

    bundles = _bundles(tmp_path)
    for path in bundles.glob("*.json"):
        path.unlink()

    repo_root = str(tmp_path.resolve())
    final_sha = message_sha256_bytes(FINAL)
    for session_id, token, mtime in specs:
        bundle = _clone_acceptpath_bundle(
            template,
            session_id=session_id,
            token=token,
            final_sha=final_sha,
            repo_root=repo_root,
        )
        path = bundles / f"{session_id}.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.utime(path, (mtime, mtime))
    return bundles, template, final_sha


def test_scan_window_env_fails_closed_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_SCAN_WINDOW_ENV, raising=False)
    assert _acceptpath_scan_window() == _DEFAULT_SCAN_WINDOW
    assert _DEFAULT_SCAN_WINDOW == 512

    for token in ("0", "-1", "+0", "abc", "1.5", " ", "512.0", "0x20"):
        monkeypatch.setenv(_SCAN_WINDOW_ENV, token)
        assert _acceptpath_scan_window() == _DEFAULT_SCAN_WINDOW

    monkeypatch.setenv(_SCAN_WINDOW_ENV, "4")
    assert _acceptpath_scan_window() == 4
    monkeypatch.setenv(_SCAN_WINDOW_ENV, " 8 ")
    assert _acceptpath_scan_window() == 8


def test_full_scan_env_is_token_one_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_FULL_SCAN_ENV, raising=False)
    assert _acceptpath_full_scan() is False
    for token in ("", "0", "2", "true", "TRUE", "yes", "on", "full"):
        monkeypatch.setenv(_FULL_SCAN_ENV, token)
        assert _acceptpath_full_scan() is False
    monkeypatch.setenv(_FULL_SCAN_ENV, "1")
    assert _acceptpath_full_scan() is True
    monkeypatch.setenv(_FULL_SCAN_ENV, " 1 ")
    assert _acceptpath_full_scan() is True


def test_mtime_desc_filename_asc_picks_first_duplicate(tmp_path: Path) -> None:
    older = "sess_" + ("a" * 32)
    newer = "sess_" + ("b" * 32)
    token = "ae_mtime_order"
    bundles, _, sha = _plant_window_bundles(
        tmp_path,
        [
            (older, token, 100.0),
            (newer, token, 200.0),
        ],
    )
    key = _reuse_key(tmp_path, token, sha)
    assert key is not None
    _unlink_acceptpath_index(tmp_path)
    found = _scan_reuse_key(bundles, key)
    assert found is not None
    assert found["session_thread_id"] == newer

    # Equal mtimes: filename ascending wins.
    os.utime(bundles / f"{older}.json", (50.0, 50.0))
    os.utime(bundles / f"{newer}.json", (50.0, 50.0))
    _unlink_acceptpath_index(tmp_path)
    tied = _scan_reuse_key(bundles, key)
    assert tied is not None
    assert tied["session_thread_id"] == older


def test_bounded_scan_misses_old_twin_and_sets_scan_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "2")
    inside = "sess_" + ("1" * 32)
    filler = "sess_" + ("2" * 32)
    outside = "sess_" + ("0" * 32)
    _plant_window_bundles(
        tmp_path,
        [
            (outside, "ae_bounded_old", 10.0),
            (filler, "ae_bounded_fill", 20.0),
            (inside, "ae_bounded_new", 30.0),
        ],
    )
    _unlink_acceptpath_index(tmp_path)

    missed = _bind(tmp_path, accept_event_token="ae_bounded_old")
    assert missed.bound is True
    assert missed.bundle is not None
    assert missed.bundle["session_thread_id"] != outside
    assert missed.bundle["meta"].get("scan_bounded") is True

    _unlink_acceptpath_index(tmp_path)
    reused = _bind(tmp_path, accept_event_token="ae_bounded_new")
    assert reused.bound is True
    assert reused.bundle is not None
    assert reused.bundle["session_thread_id"] == inside
    assert reused.bundle["meta"].get("scan_bounded") is True


def test_non_truncated_and_exact_window_omit_scan_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "2")
    first = "sess_" + ("a" * 32)
    second = "sess_" + ("b" * 32)
    _plant_window_bundles(
        tmp_path,
        [
            (first, "ae_exact_a", 10.0),
            (second, "ae_exact_b", 20.0),
        ],
    )
    _unlink_acceptpath_index(tmp_path)
    result = _bind(tmp_path, accept_event_token="ae_exact_a")
    assert result.bound is True
    assert result.bundle is not None
    assert result.bundle["session_thread_id"] == first
    assert "scan_bounded" not in result.bundle["meta"]


def test_ineligible_files_do_not_count_toward_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "2")
    first = "sess_" + ("c" * 32)
    second = "sess_" + ("d" * 32)
    bundles, _, _ = _plant_window_bundles(
        tmp_path,
        [
            (first, "ae_ineligible_a", 10.0),
            (second, "ae_ineligible_b", 20.0),
        ],
    )
    (bundles / "index.json").write_text("{}", encoding="utf-8")
    (bundles / "aaa.json").mkdir()
    poison = tmp_path / "outside_symlink.json"
    poison.write_text("{}", encoding="utf-8")
    (bundles / "sess_alink.json").symlink_to(poison)
    result = _bind(tmp_path, accept_event_token="ae_ineligible_a")
    assert result.bound is True
    assert result.bundle is not None
    assert result.bundle["session_thread_id"] == first
    assert "scan_bounded" not in result.bundle["meta"]


def test_full_scan_override_finds_old_twin_without_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "1")
    monkeypatch.setenv(_FULL_SCAN_ENV, "1")
    old = "sess_" + ("0" * 32)
    new = "sess_" + ("1" * 32)
    _plant_window_bundles(
        tmp_path,
        [
            (old, "ae_full_old", 10.0),
            (new, "ae_full_new", 20.0),
        ],
    )
    _unlink_acceptpath_index(tmp_path)
    result = _bind(tmp_path, accept_event_token="ae_full_old")
    assert result.bound is True
    assert result.bundle is not None
    assert result.bundle["session_thread_id"] == old
    assert "scan_bounded" not in result.bundle["meta"]


def test_cache_hit_never_sets_scan_bounded_or_globs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "1")
    first = _bind(tmp_path, accept_event_token="ae_cache_hit_flag")
    assert first.bound is True
    assert first.bundle is not None
    assert "scan_bounded" not in first.bundle["meta"]

    def boom_glob(self, pattern):
        raise AssertionError(f"cache hit must not miss-scan: {pattern!r}")

    monkeypatch.setattr(Path, "glob", boom_glob)
    second = _bind(tmp_path, accept_event_token="ae_cache_hit_flag")
    assert second.bound is True
    assert second.bundle is not None
    assert second.bundle["session_thread_id"] == first.bundle["session_thread_id"]
    assert "scan_bounded" not in second.bundle["meta"]


def test_caller_meta_cannot_inject_scan_bounded(tmp_path: Path) -> None:
    result = _bind(tmp_path, accept_event_token="ae_inject_flag", meta={"scan_bounded": True})
    assert result.bound is True
    assert result.bundle is not None
    assert "scan_bounded" not in result.bundle["meta"]


def test_bounded_scan_does_not_backfill_outside_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "1")
    old = "sess_" + ("0" * 32)
    newest = "sess_" + ("f" * 32)
    bundles, template, sha = _plant_window_bundles(
        tmp_path,
        [
            (old, "ae_nobackfill", 10.0),
            (newest, "ae_nobackfill_other", 20.0),
        ],
    )
    # Newest file occupies the window but is not adoptable for this key.
    corrupt = dict(template)
    corrupt["bound"] = False
    (bundles / f"{newest}.json").write_text(json.dumps(corrupt), encoding="utf-8")
    os.utime(bundles / f"{newest}.json", (20.0, 20.0))
    _unlink_acceptpath_index(tmp_path)
    state: dict[str, bool] = {}
    key = _reuse_key(tmp_path, "ae_nobackfill", sha)
    assert key is not None
    found = _scan_reuse_key(bundles, key, scan_state=state)
    assert found is None
    assert state.get("truncated") is True


def test_positive_window_hit_still_requires_adoptable_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SCAN_WINDOW_ENV, "2")
    session = "sess_" + ("e" * 32)
    bundles, template, sha = _plant_window_bundles(
        tmp_path,
        [(session, "ae_gate", 10.0)],
    )
    bad = _clone_acceptpath_bundle(
        template,
        session_id=session,
        token="ae_gate",
        final_sha=sha,
        repo_root=str(tmp_path.resolve()),
    )
    bad["artifact_class"] = "fixture"
    (bundles / f"{session}.json").write_text(json.dumps(bad), encoding="utf-8")
    os.utime(bundles / f"{session}.json", (10.0, 10.0))
    _unlink_acceptpath_index(tmp_path)
    key = _reuse_key(tmp_path, "ae_gate", sha)
    assert key is not None
    assert _scan_reuse_key(bundles, key) is None
    result = _bind(tmp_path, accept_event_token="ae_gate")
    assert result.bound is True
    assert result.bundle is not None
    assert result.bundle["session_thread_id"] != session
    assert result.bundle["artifact_class"] == "final_accept"


# Measurement-only miss-scan timings. Do not ratify K. Refs: #257.

# Recency cut used only to place twins inside vs outside the window.
# Aliased to the product default so placement cannot drift; still not ratification.
_PLACEMENT_WINDOW = _DEFAULT_SCAN_WINDOW


def _session_id_for_index(index: int) -> str:
    return f"sess_{index:032x}"


def _measure_locked_scan(bundles_dir: Path, key: tuple[str, str, str]) -> tuple[dict[str, Any] | None, float, float]:
    """Return ``(bundle, scan_ms, lock_hold_ms)`` for the in-lock miss-scan.

    ``lock_hold_ms`` stops immediately before ``release()``.
    """
    held = acquire_bind_lock(bundles_dir)
    assert held is not None
    started = time.perf_counter()
    try:
        found = _scan_reuse_key(bundles_dir, key)
        scan_ms = (time.perf_counter() - started) * 1000.0
    finally:
        lock_hold_ms = (time.perf_counter() - started) * 1000.0
        held.release()
    return found, scan_ms, lock_hold_ms


def _seed_benchmark_bundles(tmp_path: Path, bundle_count: int) -> dict[str, Any]:
    """Populate ``bundle_count`` schema-valid bundles with in/out-placement twins."""
    assert bundle_count > _PLACEMENT_WINDOW

    template_result = _bind(tmp_path, accept_event_token="ae_bench_template")
    assert template_result.bound is True
    template = template_result.bundle
    assert template is not None
    assert is_valid("ape_bundle_v1", template)

    bundles = _bundles(tmp_path)
    for path in bundles.glob("*.json"):
        path.unlink()

    repo_root = str(tmp_path.resolve())
    target_sha = message_sha256_bytes(FINAL)
    inside_index = bundle_count - 1
    outside_index = 0
    inside_session = _session_id_for_index(inside_index)
    outside_session = _session_id_for_index(outside_index)
    inside_token = "ae_bench_inside"
    outside_token = "ae_bench_outside"
    inside_key = _reuse_key(tmp_path, inside_token, target_sha)
    outside_key = _reuse_key(tmp_path, outside_token, target_sha)
    miss_key = _reuse_key(tmp_path, "ae_bench_nomatch", target_sha)
    assert inside_key is not None and outside_key is not None and miss_key is not None

    for index in range(bundle_count):
        session_id = _session_id_for_index(index)
        if index == inside_index:
            token = inside_token
        elif index == outside_index:
            token = outside_token
        else:
            token = f"ae_bench_fill_{index}"
        bundle = _clone_acceptpath_bundle(
            template,
            session_id=session_id,
            token=token,
            final_sha=target_sha,
            repo_root=repo_root,
        )
        (bundles / f"{session_id}.json").write_text(
            json.dumps(bundle, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    base = time.time()
    for index in range(bundle_count):
        path = bundles / f"{_session_id_for_index(index)}.json"
        stamp = base + index
        os.utime(path, (stamp, stamp))

    inside_bundle = json.loads((bundles / f"{inside_session}.json").read_text(encoding="utf-8"))
    outside_bundle = json.loads((bundles / f"{outside_session}.json").read_text(encoding="utf-8"))
    filler_bundle = json.loads((bundles / f"{_session_id_for_index(1)}.json").read_text(encoding="utf-8"))
    assert is_valid("ape_bundle_v1", inside_bundle)
    assert is_valid("ape_bundle_v1", outside_bundle)
    assert is_valid("ape_bundle_v1", filler_bundle)
    assert _reuse_key(tmp_path, inside_token, target_sha) == inside_key
    assert _reuse_key(tmp_path, outside_token, target_sha) == outside_key

    newest_cutoff = bundle_count - _PLACEMENT_WINDOW
    assert inside_index >= newest_cutoff
    assert outside_index < newest_cutoff

    return {
        "bundles": bundles,
        "inside_key": inside_key,
        "outside_key": outside_key,
        "miss_key": miss_key,
        "inside_session": inside_session,
        "outside_session": outside_session,
        "index_path": binding_paths.acceptpath_index_file(tmp_path),
    }


@pytest.mark.parametrize("bundle_count", [1_000, 10_000])
def test_benchmark_acceptpath_miss_scan_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bundle_count: int,
) -> None:
    """Measure bounded miss-scan cost; do not ratify K or lock budget.

    Cases: cache hit, twin inside the 512 window, twin outside it (bounded
    miss), bounded no-match, and full-scan override for the outside twin.
    """
    seeded = _seed_benchmark_bundles(tmp_path, bundle_count)
    bundles = seeded["bundles"]
    index_path = seeded["index_path"]

    _unlink_acceptpath_index(tmp_path)
    outside, outside_scan_ms, outside_lock_ms = _measure_locked_scan(bundles, seeded["outside_key"])
    assert outside is None

    _unlink_acceptpath_index(tmp_path)
    inside, inside_scan_ms, inside_lock_ms = _measure_locked_scan(bundles, seeded["inside_key"])
    assert inside is not None
    assert inside["session_thread_id"] == seeded["inside_session"]

    _unlink_acceptpath_index(tmp_path)
    missing, miss_scan_ms, miss_lock_ms = _measure_locked_scan(bundles, seeded["miss_key"])
    assert missing is None

    monkeypatch.setenv(_FULL_SCAN_ENV, "1")
    _unlink_acceptpath_index(tmp_path)
    outside_full, outside_full_scan_ms, outside_full_lock_ms = _measure_locked_scan(bundles, seeded["outside_key"])
    monkeypatch.delenv(_FULL_SCAN_ENV, raising=False)
    assert outside_full is not None
    assert outside_full["session_thread_id"] == seeded["outside_session"]

    _write_index(index_path, {_index_entry_key(seeded["inside_key"]): seeded["inside_session"]})
    glob_calls: list[str] = []
    real_glob = Path.glob

    def spy_glob(self: Path, pattern: str, *args, **kwargs):
        glob_calls.append(pattern)
        return real_glob(self, pattern, *args, **kwargs)

    monkeypatch.setattr(Path, "glob", spy_glob)
    cached, cache_scan_ms, cache_lock_ms = _measure_locked_scan(bundles, seeded["inside_key"])
    monkeypatch.setattr(Path, "glob", real_glob)
    assert cached is not None
    assert cached["session_thread_id"] == seeded["inside_session"]
    assert glob_calls == []

    for scan_ms, lock_ms in (
        (outside_scan_ms, outside_lock_ms),
        (inside_scan_ms, inside_lock_ms),
        (miss_scan_ms, miss_lock_ms),
        (cache_scan_ms, cache_lock_ms),
        (outside_full_scan_ms, outside_full_lock_ms),
    ):
        assert scan_ms >= 0.0
        assert lock_ms >= 0.0
        assert lock_ms >= scan_ms

    record = {
        "bundle_count": bundle_count,
        "placement_window": _PLACEMENT_WINDOW,
        "scan_implementation": "mtime_desc_filename_asc_k_window",
        "k_ratified": False,
        "lock_budget_ratified": False,
        "cases": {
            "cache_hit": {
                "scan_ms": round(cache_scan_ms, 3),
                "lock_hold_ms": round(cache_lock_ms, 3),
                "hit": True,
                "glob_entered": False,
            },
            "inside_placement": {
                "scan_ms": round(inside_scan_ms, 3),
                "lock_hold_ms": round(inside_lock_ms, 3),
                "hit": True,
                "session": seeded["inside_session"],
            },
            "outside_placement": {
                "scan_ms": round(outside_scan_ms, 3),
                "lock_hold_ms": round(outside_lock_ms, 3),
                "hit": False,
                "session": seeded["outside_session"],
            },
            "bounded_no_match": {
                "scan_ms": round(miss_scan_ms, 3),
                "lock_hold_ms": round(miss_lock_ms, 3),
                "hit": False,
            },
            "full_scan_outside": {
                "scan_ms": round(outside_full_scan_ms, 3),
                "lock_hold_ms": round(outside_full_lock_ms, 3),
                "hit": True,
                "session": seeded["outside_session"],
            },
        },
    }
    print("MISS_SCAN_MEASUREMENT " + json.dumps(record, ensure_ascii=False), flush=True)
