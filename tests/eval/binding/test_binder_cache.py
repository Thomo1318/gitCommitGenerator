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
    _INDEX_VERSION,
    BindInput,
    _cache_write_through,
    _index_entry_key,
    _load_bundle_for_session,
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

    def _fail_index_write(path, payload):
        calls.append(Path(path).name)
        if Path(path).name == "index.json":
            raise binding_paths.LayerAPathError("cache write failed")
        return real_atomic(path, payload)

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
        json.dumps(
            {
                "version": _INDEX_VERSION,
                "entries": {"ok": "sess_x", "blank": "  ", "b": 2},
            }
        ),
        encoding="utf-8",
    )
    loaded = _load_index(p)
    assert loaded == {"ok": "sess_x"}


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
