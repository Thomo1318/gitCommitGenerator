"""Best-effort acceptpath binder diagnostics.

Counters are optional inspection state under
``.eval/diagnostics/binder_counters.json``. They must never become a
product gate: corrupt, missing, unwritable, or exploding diagnostics
must not change ``BindResult`` or block persist.

No network. No Opik. Refs: #257.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.binder import BindInput, BindResult, bind_final_accept
from git_cg.eval.binding.diagnostics import COUNTER_NAMES, binder_counters_path

FINAL = (
    "✨ feat(eval): binder diagnostics\n\n"
    "Refs: #257\n"
    "SemVer-Impact: PATCH\n"
    "Change-Types: feat\n"
    "Changelog-Groups: Added\n"
)


@pytest.fixture(autouse=True)
def _capture_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)


def _bind(tmp_path: Path, **overrides) -> BindResult:
    kwargs = {
        "final_message": FINAL,
        "accept_event_token": "ae_diag",
    }
    kwargs.update(overrides)
    return bind_final_accept(BindInput(**kwargs), repo_root=tmp_path, write=True)


def _counters(tmp_path: Path) -> dict[str, int]:
    path = binder_counters_path(tmp_path)
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == set(COUNTER_NAMES)
    return payload


def test_counters_written_to_diagnostics(tmp_path: Path) -> None:
    first = _bind(tmp_path, accept_event_token="ae_diag_a")
    assert first.bound is True
    counters = _counters(tmp_path)
    assert counters["bind_attempts"] == 1
    assert counters["bind_success"] == 1
    assert counters["cache_misses"] >= 1
    assert counters["cache_hits"] == 0
    assert counters["lock_fallbacks"] == 0

    reused = _bind(tmp_path, accept_event_token="ae_diag_a")
    assert reused.bound is True
    assert reused.bundle is not None
    assert first.bundle is not None
    assert reused.bundle["session_thread_id"] == first.bundle["session_thread_id"]
    counters = _counters(tmp_path)
    assert counters["bind_attempts"] == 2
    assert counters["bind_success"] == 2
    assert counters["cache_hits"] >= 1


def test_counters_never_block_bind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):
        raise RuntimeError("diagnostics exploded")

    monkeypatch.setattr(
        "git_cg.eval.binding.diagnostics.increment_binder_counters",
        _boom,
    )
    result = _bind(tmp_path, accept_event_token="ae_diag_failopen")
    assert result.bound is True
    assert result.paths_written
    assert not binder_counters_path(tmp_path).exists()


def test_lock_fallback_increments_counter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("git_cg.eval.binding.binder.acquire_bind_lock", lambda *_a, **_k: None)
    result = _bind(tmp_path, accept_event_token="ae_diag_lock")
    assert result.bound is True
    counters = _counters(tmp_path)
    assert counters["lock_fallbacks"] == 1
    assert counters["bind_success"] == 1


def test_schema_invalid_does_not_write_counters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.schema_pack import SchemaPackError

    def _boom(_name: str, _instance: object) -> None:
        raise SchemaPackError("forced schema invalid")

    monkeypatch.setattr("git_cg.eval.binding.binder.validate_instance", _boom)
    result = _bind(tmp_path)
    assert result.bound is False
    assert result.unbound_reason == "schema_invalid"
    assert not binder_counters_path(tmp_path).exists()


def test_increment_recovers_from_corrupt_file(tmp_path: Path) -> None:
    from git_cg.eval.binding import paths as binding_paths
    from git_cg.eval.binding.diagnostics import increment_binder_counters

    path = binder_counters_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    increment_binder_counters(tmp_path, bind_success=2, unknown=9)
    payload = _counters(tmp_path)
    assert payload["bind_success"] == 2
    assert payload["bind_attempts"] == 0
    assert binding_paths.diagnostics_dir(tmp_path) in path.parents


def test_increment_swallows_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.binding.diagnostics import increment_binder_counters

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("git_cg.eval.binding.paths.atomic_write_json", _boom)
    increment_binder_counters(tmp_path, bind_attempts=1)
    increment_binder_counters(None, bind_attempts=1)
    increment_binder_counters(tmp_path)
    increment_binder_counters(tmp_path, bind_attempts=0, cache_hits=True)  # type: ignore[arg-type]
