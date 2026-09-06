"""Acceptpath bind lock contention, stale reclaim, and recovery paths.

Refs: #257.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from git_cg.eval.binding import paths as binding_paths
from git_cg.eval.binding.binder import BindInput, bind_final_accept, message_sha256_bytes
from git_cg.eval.binding.lock import (
    BIND_LOCK_NAME,
    STALE_LOCK_SECONDS,
    acquire_bind_lock,
)

FINAL = (
    "✨ feat(eval): bind lock recovery\n\n"
    "Refs: #257\n"
    "SemVer-Impact: PATCH\n"
    "Change-Types: fix\n"
    "Changelog-Groups: Fixed\n"
)


@pytest.fixture(autouse=True)
def _capture_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)


def _bind(tmp_path: Path, **overrides):
    kwargs = {
        "final_message": FINAL,
        "accept_event_token": "ae_lock",
    }
    kwargs.update(overrides)
    return bind_final_accept(BindInput(**kwargs), repo_root=tmp_path, write=True)


def test_simultaneous_binds_same_acceptpath(tmp_path: Path) -> None:
    results: list = []
    errors: list[BaseException] = []

    def worker(token: str) -> None:
        try:
            results.append(_bind(tmp_path, accept_event_token=token))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(f"ae_conc_{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(results) == 8
    assert all(r.bound for r in results)
    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    files = [p for p in bundles.glob("*.json") if p.name != "index.json"]
    # Distinct tokens ⇒ distinct sessions; no corruption.
    assert len(files) == 8
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["bound"] is True
        assert data["final_message_sha256"] == message_sha256_bytes(FINAL)


def test_lock_failure_falls_back_to_unlocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("git_cg.eval.binding.binder.acquire_bind_lock", lambda *_a, **_k: None)
    result = _bind(tmp_path, accept_event_token="ae_fallback")
    assert result.bound is True
    assert result.paths_written


def test_stale_lock_recovery(tmp_path: Path) -> None:
    bundles = binding_paths.acceptpath_bundles_dir(tmp_path)
    bundles.mkdir(parents=True, exist_ok=True)
    lock_path = bundles / BIND_LOCK_NAME
    lock_path.write_text("stale", encoding="utf-8")
    stale_mtime = time.time() - (STALE_LOCK_SECONDS + 5)
    os.utime(lock_path, (stale_mtime, stale_mtime))
    result = _bind(tmp_path, accept_event_token="ae_stale_lock")
    assert result.bound is True
    assert result.paths_written


def test_default_bind_lock_budget_is_bounded(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    held = acquire_bind_lock(bundles, timeout=1.0)
    assert held is not None
    try:
        started = time.monotonic()
        assert acquire_bind_lock(bundles) is None
        elapsed = time.monotonic() - started
        # Default wait must stay under 1 s; poll jitter is not asserted.
        assert elapsed < 1.0
    finally:
        held.release()


def test_bind_completes_under_default_lock_budget(tmp_path: Path) -> None:
    bundles = binding_paths.acceptpath_bundles_dir(tmp_path)
    bundles.mkdir(parents=True, exist_ok=True)
    held = acquire_bind_lock(bundles, timeout=1.0)
    assert held is not None
    try:
        started = time.monotonic()
        result = _bind(tmp_path, accept_event_token="ae_budget")
        elapsed = time.monotonic() - started
        assert result.bound is True
        assert result.paths_written
        # Binder uses the default lock timeout; wait must stay under 1 s.
        assert elapsed < 1.0
    finally:
        held.release()


def test_acquire_bind_lock_timeout_returns_none(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    held = acquire_bind_lock(bundles, timeout=0.2)
    assert held is not None
    try:
        # Live lock held elsewhere → timeout → None (never raises).
        other = acquire_bind_lock(bundles, timeout=0.15)
        assert other is None
    finally:
        held.release()


def test_duplicate_valid_bundles_same_key(tmp_path: Path) -> None:
    """Conflict policy: first sorted authoritative match wins; bind still succeeds."""
    first = _bind(tmp_path, accept_event_token="ae_dup")
    session = first.bundle["session_thread_id"]
    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    # Plant a second valid bundle with same key but different session id.
    dup = dict(first.bundle)
    dup["session_thread_id"] = "sess_duplicate_zzzz"
    dup["case_id"] = "acceptpath:sess_duplicate_zzzz"
    (bundles / "sess_duplicate_zzzz.json").write_text(json.dumps(dup), encoding="utf-8")
    second = _bind(tmp_path, accept_event_token="ae_dup")
    assert second.bound is True
    # Sorted scan: sess_duplicate_zzzz comes after original sess_* typically;
    # either way identity is one of the authoritative matches, never crash.
    assert second.bundle["session_thread_id"] in {session, "sess_duplicate_zzzz"}


def test_interrupted_temp_write_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Atomic-replace guarantees: failed write leaves no partial final bundle."""
    real_replace = os.replace
    calls = {"n": 0}

    def _flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1 and str(dst).endswith(".json") and not str(dst).endswith("index.json"):
            # Simulate crash before replace completes.
            raise OSError("simulated interrupt")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _flaky_replace)
    result = _bind(tmp_path, accept_event_token="ae_interrupt")
    # Bind reports write error without raising; no partial final authoritative file
    # for the new session should remain as valid JSON under final name if replace failed.
    assert result.bound is True
    assert result.errors and result.errors[0].startswith("bind_write_error:")
    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    if bundles.exists():
        for path in bundles.glob("*.json"):
            if path.name == "index.json":
                continue
            # Any surviving final path must be valid JSON (atomic replace law).
            json.loads(path.read_text(encoding="utf-8"))
        assert list(bundles.glob(".*.tmp")) == []


def test_symlink_escape_cases(tmp_path: Path) -> None:
    outside = tmp_path / "outside_target"
    outside.mkdir()
    eval_root = tmp_path / ".eval"
    eval_root.mkdir()
    link = eval_root / "escape_link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(binding_paths.LayerAPathError):
        binding_paths._contained(tmp_path, Path("escape_link") / "bundle.json")
    with pytest.raises(binding_paths.LayerAPathError):
        binding_paths._contained(tmp_path, Path("escape_link") / "index.json")


def test_dotdot_escape_cases(tmp_path: Path) -> None:
    with pytest.raises(binding_paths.LayerAPathError):
        binding_paths._contained(tmp_path, tmp_path / ".eval" / ".." / "outside" / "x.json")
    # Normal index path stays contained.
    index = binding_paths.acceptpath_index_file(tmp_path)
    assert ".eval" in index.parts
    assert index.name == "index.json"


def test_corrupt_index_recovery_matrix(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_matrix")
    session = first.bundle["session_thread_id"]
    index = binding_paths.acceptpath_index_file(tmp_path)

    # missing
    index.unlink(missing_ok=True)
    assert _bind(tmp_path, accept_event_token="ae_matrix").bundle["session_thread_id"] == session

    # corrupt
    index.write_text("{{", encoding="utf-8")
    assert _bind(tmp_path, accept_event_token="ae_matrix").bundle["session_thread_id"] == session

    # wrong version
    index.write_text(json.dumps({"version": 0, "entries": {}}), encoding="utf-8")
    assert _bind(tmp_path, accept_event_token="ae_matrix").bundle["session_thread_id"] == session

    # stale entry
    index.write_text(
        json.dumps({"version": 1, "entries": {"not-a-real-key": "sess_missing"}}),
        encoding="utf-8",
    )
    assert _bind(tmp_path, accept_event_token="ae_matrix").bundle["session_thread_id"] == session


def test_bind_lock_context_manager_and_double_release(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    with lock:
        assert lock.path.exists()
    assert not lock.path.exists()
    lock.release()


def test_acquire_bind_lock_mkdir_failure_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "nope"

    def _fail_mkdir(*_a, **_k):
        raise OSError("mkdir failed")

    monkeypatch.setattr(Path, "mkdir", _fail_mkdir)
    assert acquire_bind_lock(target, timeout=0.1) is None


def test_try_create_lock_write_failure_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.binding import lock as lock_mod

    bundles = tmp_path / "bundles"
    bundles.mkdir()
    real_write = os.write

    def _fail_write(fd, data):
        raise OSError("write failed")

    monkeypatch.setattr(os, "write", _fail_write)
    assert lock_mod._try_create_lock(bundles / BIND_LOCK_NAME) is None
    assert not (bundles / BIND_LOCK_NAME).exists()
    monkeypatch.setattr(os, "write", real_write)


def test_lock_mtime_age_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.binding.lock import _lock_mtime_age

    path = tmp_path / "x.lock"
    path.write_text("x", encoding="utf-8")

    def _fail_stat(self):
        raise OSError("stat failed")

    monkeypatch.setattr(Path, "stat", _fail_stat)
    assert _lock_mtime_age(path) is None


def test_lock_payload_carries_ownership_nonce(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    try:
        payload = lock.path.read_text(encoding="utf-8")
        assert lock.nonce
        assert len(lock.nonce) == 32
        int(lock.nonce, 16)
        assert "pid=" in payload
        assert "t=" in payload
        assert f"nonce={lock.nonce}" in payload
    finally:
        lock.release()


def test_sequential_owners_hold_distinct_nonces(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    first = acquire_bind_lock(bundles, timeout=1.0)
    assert first is not None
    first_nonce = first.nonce
    first.release()
    assert not first.path.exists()
    second = acquire_bind_lock(bundles, timeout=1.0)
    assert second is not None
    try:
        assert second.nonce != first_nonce
        assert f"nonce={second.nonce}" in second.path.read_text(encoding="utf-8")
    finally:
        second.release()
    assert not second.path.exists()


def test_release_does_not_remove_reclaimed_lock(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    old = acquire_bind_lock(bundles, timeout=1.0)
    assert old is not None
    stale_mtime = time.time() - (STALE_LOCK_SECONDS + 5)
    os.utime(old.path, (stale_mtime, stale_mtime))
    new = acquire_bind_lock(bundles, timeout=1.0)
    assert new is not None
    try:
        assert new.nonce != old.nonce
        old.release()
        assert new.path.exists()
        assert f"nonce={new.nonce}" in new.path.read_text(encoding="utf-8")
    finally:
        new.release()


def test_release_after_timeout_does_not_remove_new_owner_lock(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    old = acquire_bind_lock(bundles, timeout=0.2)
    assert old is not None
    timed_out = acquire_bind_lock(bundles, timeout=0.15)
    assert timed_out is None
    old.path.unlink()
    new = acquire_bind_lock(bundles, timeout=1.0)
    assert new is not None
    try:
        old.release()
        assert new.path.exists()
        assert f"nonce={new.nonce}" in new.path.read_text(encoding="utf-8")
    finally:
        new.release()


def test_release_after_replacement_does_not_remove_new_lock(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    old = acquire_bind_lock(bundles, timeout=1.0)
    assert old is not None
    old.path.unlink()
    new = acquire_bind_lock(bundles, timeout=1.0)
    assert new is not None
    try:
        old.release()
        assert new.path.exists()
        assert f"nonce={new.nonce}" in new.path.read_text(encoding="utf-8")
    finally:
        new.release()


def test_mismatched_nonce_release_is_noop(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    lock.path.write_text("pid=1 t=1.000000 nonce=deadbeefdeadbeefdeadbeefdeadbeef\n", encoding="utf-8")
    lock.release()
    assert lock.path.exists()
    lock.path.unlink()


def test_legacy_non_nonce_payload_release_is_noop(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    lock.path.write_text(f"pid=1 t={time.time():.6f}\n", encoding="utf-8")
    lock.release()
    assert lock.path.exists()
    lock.path.unlink()


def test_malformed_payload_release_is_noop(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    lock.path.write_bytes(b"\xff\xfe not a lock\n")
    lock.release()
    assert lock.path.exists()
    lock.path.unlink()


def test_unreadable_payload_release_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    target = lock.path
    real_read = Path.read_bytes

    def _fail_read(self: Path) -> bytes:
        if self == target:
            raise OSError("unreadable")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", _fail_read)
    lock.release()
    assert target.exists()
    monkeypatch.undo()
    target.unlink()


def test_matching_nonce_release_removes_lock(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    lock = acquire_bind_lock(bundles, timeout=1.0)
    assert lock is not None
    lock.release()
    assert not lock.path.exists()
    lock.release()
