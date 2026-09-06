"""Session-thread twin tests (R13 / N8 / D12).

Covers the D12 twin shape (``sessmeta_<id>`` id, ``meta.lifecycle``, correlation
ids under ``meta`` only), D9 session-id law (``sess_`` only; ``repo-…`` is
correlation, never the id), fail-closed validation, additive no-invention of
span ids, schema conformance, and capture-gated atomic persistence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.profiles import capture_enabled
from git_cg.eval.binding.session_thread import (
    SESSION_LIFECYCLE_STATES,
    SessionTwinError,
    build_session_twin,
    write_session_twin,
)
from git_cg.eval.schema_pack import validate_instance

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "eval" / "commit_session_thread_v1.schema.json"

SESS = "sess_0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def _capture_on(monkeypatch: pytest.MonkeyPatch):
    """Autouse fixture: force capture on and clear profile overrides."""
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)


# ---------------------------------------------------------------------------
# D12 — twin shape
# ---------------------------------------------------------------------------


def test_build_minimal_closed_twin() -> None:
    twin = build_session_twin(SESS, lifecycle="closed")
    assert twin["schema_version"] == "commit_session_thread_v1"
    assert twin["id"] == f"sessmeta_{SESS}"
    assert twin["session_thread_id"] == SESS
    assert twin["redaction_profile"] == "default_scrub"
    assert twin["meta"]["lifecycle"] == "closed"
    # No top-level open/closed enum (D12)
    assert "lifecycle" not in twin
    assert twin["attempt_ids"] == []
    assert twin["message_versions"] == []


def test_lifecycle_open_and_closed_both_valid() -> None:
    assert build_session_twin(SESS, lifecycle="open")["meta"]["lifecycle"] == "open"
    assert build_session_twin(SESS, lifecycle="closed")["meta"]["lifecycle"] == "closed"
    assert frozenset({"open", "closed"}) == SESSION_LIFECYCLE_STATES


def test_correlation_ids_live_under_meta_only() -> None:
    twin = build_session_twin(
        SESS,
        lifecycle="closed",
        trace_id="trace-abc",
        generation_thread_id="repo-gitCommitGenerator",
        existing_trace_span_ids=["span-1", "span-2"],
        opened_at="2026-08-16T01:00:00Z",
        closed_at="2026-08-16T01:00:05Z",
    )
    meta = twin["meta"]
    assert meta["trace_id"] == "trace-abc"
    assert meta["generation_thread_id"] == "repo-gitCommitGenerator"
    assert meta["existing_trace_span_ids"] == ["span-1", "span-2"]
    assert meta["opened_at"] == "2026-08-16T01:00:00Z"
    assert meta["closed_at"] == "2026-08-16T01:00:05Z"
    # correlation ids never become the session id (D9)
    assert twin["session_thread_id"] == SESS
    assert "trace_id" not in twin
    assert "thread_id" not in twin


def test_empty_span_ids_omitted_not_invented() -> None:
    twin = build_session_twin(SESS, lifecycle="closed", existing_trace_span_ids=[])
    assert "existing_trace_span_ids" not in twin["meta"]


def test_attempt_ids_and_message_versions_passthrough() -> None:
    mv = [{"kind": "final_accept", "message": "m", "message_sha256": "x", "source": "commit_editmsg"}]
    twin = build_session_twin(SESS, lifecycle="closed", attempt_ids=["a1"], message_versions=mv)
    assert twin["attempt_ids"] == ["a1"]
    assert twin["message_versions"] == mv


# ---------------------------------------------------------------------------
# Fail-closed validation
# ---------------------------------------------------------------------------


def test_non_sess_id_fails_closed() -> None:
    with pytest.raises(SessionTwinError, match="sess_"):
        build_session_twin("repo-gitCommitGenerator", lifecycle="closed")


@pytest.mark.parametrize(
    "bad_id",
    [
        "sess_not_a_real_id",
        "sess_" + ("A" * 32),
        "sess_../../x",
        "sess_01234567-89ab-cdef-0123-456789abcdef",
    ],
)
def test_session_id_must_match_capture_grammar(bad_id: str) -> None:
    with pytest.raises(SessionTwinError, match="sess_"):
        build_session_twin(bad_id, lifecycle="closed")


def test_blank_id_fails_closed() -> None:
    with pytest.raises(SessionTwinError, match="non-empty"):
        build_session_twin("   ", lifecycle="closed")


def test_invalid_lifecycle_fails_closed() -> None:
    with pytest.raises(SessionTwinError, match="lifecycle must be one of"):
        build_session_twin(SESS, lifecycle="archived")


def test_blank_span_id_fails_closed() -> None:
    with pytest.raises(SessionTwinError, match="non-empty strings"):
        build_session_twin(SESS, lifecycle="closed", existing_trace_span_ids=["  "])


# ---------------------------------------------------------------------------
# Schema conformance (frozen commit_session_thread_v1)
# ---------------------------------------------------------------------------


def test_twin_conforms_to_frozen_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    twin = build_session_twin(
        SESS,
        lifecycle="closed",
        trace_id="trace-abc",
        existing_trace_span_ids=["span-1"],
        notes="schema-check",
    )
    jsonschema.validate(instance=twin, schema=schema)
    # internal validator agrees
    validate_instance("commit_session_thread_v1", twin)


def test_twin_has_no_unknown_top_level_keys() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    allowed = set(schema["properties"].keys())
    twin = build_session_twin(SESS, lifecycle="closed")
    assert set(twin.keys()) <= allowed


# ---------------------------------------------------------------------------
# Persistence (capture-gated, atomic, contained)
# ---------------------------------------------------------------------------


def test_write_session_twin_persists_under_sessions(tmp_path: Path) -> None:
    res = write_session_twin(SESS, lifecycle="closed", repo_root=tmp_path)
    assert res.written is True
    assert res.path_written == f".eval/sessions/{SESS}.json"
    on_disk = json.loads((tmp_path / res.path_written).read_text(encoding="utf-8"))
    assert on_disk["session_thread_id"] == SESS
    validate_instance("commit_session_thread_v1", on_disk)


def test_write_disabled_by_capture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "off")
    assert capture_enabled() is False
    res = write_session_twin(SESS, lifecycle="closed", repo_root=tmp_path)
    assert res.written is False
    assert res.reason == "capture_disabled"
    assert not (tmp_path / ".eval").exists()


def test_write_false_builds_without_io(tmp_path: Path) -> None:
    res = write_session_twin(SESS, lifecycle="closed", repo_root=tmp_path, write=False)
    assert res.written is False
    assert res.reason == "write_disabled"
    assert res.session_thread is not None
    assert not (tmp_path / ".eval").exists()


def test_invalid_twin_write_reports_not_raises(tmp_path: Path) -> None:
    res = write_session_twin("repo-bad", lifecycle="closed", repo_root=tmp_path)
    assert res.written is False
    assert res.reason == "invalid_twin"
    assert res.errors


def test_blank_attempt_id_fails_closed() -> None:
    with pytest.raises(SessionTwinError, match="non-empty strings"):
        build_session_twin(SESS, lifecycle="closed", attempt_ids=["ok", "  "])


def test_write_repo_root_unresolved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from git_cg.eval.binding import paths as binding_paths

    def _boom(start=None):
        raise binding_paths.RepoRootUnresolvedError("repo_root_unresolved")

    monkeypatch.setattr(binding_paths, "resolve_repo_root", _boom)
    res = write_session_twin(SESS, lifecycle="closed", repo_root=None, write=True)
    assert res.written is False
    assert res.reason == "repo_root_unresolved"
    assert res.session_thread is not None


def test_write_persistence_error_is_non_blocking(tmp_path: Path) -> None:
    blocker = tmp_path / ".eval"
    blocker.write_text("not a dir", encoding="utf-8")
    res = write_session_twin(SESS, lifecycle="closed", repo_root=tmp_path)
    assert res.written is False
    assert res.reason == "write_error"
    assert res.errors and res.errors[0].startswith("session_write_error:")
    assert res.session_thread is not None


def test_optional_fields_and_additive_meta_merge() -> None:
    """Cover notes/metric_catalog/schema_pack + additive meta.setdefault path."""
    twin = build_session_twin(
        SESS,
        lifecycle="closed",
        notes="optional-note",
        metric_catalog="metric_catalog_v0@" + ("a" * 64),
        schema_pack="schema_pack_v0@" + ("b" * 64),
        meta={
            "lifecycle": "open",  # must not overwrite authority lifecycle
            "custom_note": "kept",
            "trace_id": "should-not-overwrite",
        },
        trace_id="trace-authority",
    )
    assert twin["notes"] == "optional-note"
    assert twin["metric_catalog"] == "metric_catalog_v0@" + ("a" * 64)
    assert twin["schema_pack"] == "schema_pack_v0@" + ("b" * 64)
    assert twin["meta"]["lifecycle"] == "closed"
    assert twin["meta"]["custom_note"] == "kept"
    assert twin["meta"]["trace_id"] == "trace-authority"
    validate_instance("commit_session_thread_v1", twin)
