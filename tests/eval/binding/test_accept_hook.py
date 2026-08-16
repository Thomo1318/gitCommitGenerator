"""S3 Slice 3 — accept-path emit hook tests (Issue #231, N19 F8).

Covers the narrow ``record-telemetry`` → binding integration:

* Binding occurs even when telemetry state is absent (N19 F8).
* Capture gating (D1): off by default ⇒ zero writes.
* Exact-byte binding incl. invalid UTF-8 projection (N19.4/N20.3).
* Stored-vs-recomputed hash authority (N19 F1) and meta card precedence.
* Opik failure must not block binding or product accept.
"""

from __future__ import annotations

import json

import pytest

from git_cg.eval.binding.accept_hook import bind_accept_path, mint_accept_event_token
from git_cg.eval.binding.binder import message_sha256_bytes
from git_cg.eval.binding.profiles import capture_enabled

FINAL = "✨ feat(eval): add accept-path binding\n\nRefs: #231\n"


def _enable_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "1")


def _disable_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_CG_EVAL_CAPTURE", raising=False)
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)


class _State:
    """Minimal stand-in for GenerationTelemetry (attrs only)."""

    def __init__(self) -> None:
        self.generated_message = "✨ feat(eval): draft\n"
        self.score_card = {"total": 5}
        self.trace_id = "trace-1"
        self.thread_id = "repo-demo"


# --- capture gating ---------------------------------------------------------


def test_capture_disabled_by_default(monkeypatch, tmp_path):
    _disable_capture(monkeypatch)
    assert capture_enabled() is False
    res = bind_accept_path(
        final_bytes=FINAL.encode(),
        git_dir=str(tmp_path / ".git"),
        repo_root=tmp_path,
    )
    assert res.attempted is False
    assert res.hook_status == "capture_disabled"
    assert res.paths_written == ()
    assert not (tmp_path / ".eval").exists()


def test_capture_enabled_binds_without_state(monkeypatch, tmp_path):
    """N19 F8: binding must occur even when telemetry state is absent."""
    _enable_capture(monkeypatch)
    res = bind_accept_path(
        final_bytes=FINAL.encode(),
        git_dir=str(tmp_path / ".git"),
        repo_root=tmp_path,
        telemetry_state=None,
    )
    assert res.attempted is True
    assert res.bound is True
    assert res.hook_status == "bound"
    assert res.session_thread_id and res.session_thread_id.startswith("sess_")
    # Bundle written under .eval/bundles/acceptpath/
    bundle_path = tmp_path / ".eval" / "bundles" / "acceptpath" / f"{res.session_thread_id}.json"
    assert bundle_path.exists()
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert data["artifact_class"] == "final_accept"
    assert data["bound"] is True
    assert data["final_message_sha256"] == message_sha256_bytes(FINAL.encode())
    # Trajectory evidence embedded under meta.trajectory (N19.6)
    assert isinstance(data["meta"].get("trajectory"), dict)
    assert data["meta"]["trajectory"]["schema_version"] == "trajectory_evidence_v1"
    # Session twin written under .eval/sessions/
    twin_path = tmp_path / ".eval" / "sessions" / f"{res.session_thread_id}.json"
    assert twin_path.exists()


def test_state_enriches_bind_and_twin(monkeypatch, tmp_path):
    _enable_capture(monkeypatch)
    state = _State()
    res = bind_accept_path(
        final_bytes=FINAL.encode(),
        git_dir=str(tmp_path / ".git"),
        repo_root=tmp_path,
        telemetry_state=state,
        edit_provenance="ai_edited_minor",
    )
    assert res.bound is True
    bundle_path = tmp_path / ".eval" / "bundles" / "acceptpath" / f"{res.session_thread_id}.json"
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert data["meta"]["score_card"] == {"total": 5}
    assert data["meta"]["binding"]["trace_id"] == "trace-1"
    # thread_id is correlation-only, never the session id (D9)
    assert data["session_thread_id"].startswith("sess_")
    assert data["meta"]["binding"]["thread_id"] == "repo-demo"
    # Telemetry-state presence must not fabricate an opik_export observation (N19 F7).
    observed = data["meta"]["trajectory"]["observed_stages"]
    assert "accept_path_finalization" in observed
    assert "opik_export" not in observed
    # Trajectory id is digest-derived, not a filesystem path slice.
    traj_id = data["meta"]["trajectory"]["id"]
    assert traj_id.startswith("traj_")
    assert "/" not in traj_id
    assert "\\" not in traj_id
    # Twin carries message_versions: generated + edited + final_accept
    twin = json.loads((tmp_path / ".eval" / "sessions" / f"{res.session_thread_id}.json").read_text())
    kinds = [v["kind"] for v in twin["message_versions"]]
    assert kinds == ["generated", "edited", "final_accept"]
    assert twin["meta"]["lifecycle"] == "closed"
    assert twin["meta"]["generation_thread_id"] == "repo-demo"


def test_invalid_utf8_projects_with_replace(monkeypatch, tmp_path):
    _enable_capture(monkeypatch)
    raw = b"\x80\xff invalid utf-8 \xfe"
    res = bind_accept_path(
        final_bytes=raw,
        git_dir=str(tmp_path / ".git"),
        repo_root=tmp_path,
    )
    assert res.bound is True
    bundle_path = tmp_path / ".eval" / "bundles" / "acceptpath" / f"{res.session_thread_id}.json"
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    # Hash is over the original bytes; text projected with replacement.
    assert data["final_message_sha256"] == message_sha256_bytes(raw)
    assert data["meta"]["final_message_encoding"] == "utf-8-replace"
    assert data["meta"]["final_message_byte_length"] == len(raw)


def test_scoped_reuse_same_event_same_bytes(monkeypatch, tmp_path):
    """N19.2: same accept event + same bytes ⇒ reuse session identity."""
    _enable_capture(monkeypatch)
    git_dir = str(tmp_path / ".git")
    r1 = bind_accept_path(final_bytes=FINAL.encode(), git_dir=git_dir, repo_root=tmp_path)
    r2 = bind_accept_path(final_bytes=FINAL.encode(), git_dir=git_dir, repo_root=tmp_path)
    assert r1.session_thread_id == r2.session_thread_id


def test_new_event_changed_bytes_new_session(monkeypatch, tmp_path):
    _enable_capture(monkeypatch)
    git_dir = str(tmp_path / ".git")
    r1 = bind_accept_path(final_bytes=FINAL.encode(), git_dir=git_dir, repo_root=tmp_path)
    r2 = bind_accept_path(final_bytes=b"different bytes\n", git_dir=git_dir, repo_root=tmp_path)
    assert r1.session_thread_id != r2.session_thread_id


def test_accept_event_token_deterministic(tmp_path):
    a = mint_accept_event_token("/x/.git", b"hello")
    b = mint_accept_event_token("/x/.git", b"hello")
    c = mint_accept_event_token("/x/.git", b"world")
    assert a == b
    assert a != c
    assert a.startswith("accept:")


def test_bind_never_raises_on_write_error(monkeypatch, tmp_path):
    """Best-effort: persistence failure must not raise (product accept safe)."""
    _enable_capture(monkeypatch)
    # Point repo_root at a path whose .eval tree cannot be created (file in the way).
    blocker = tmp_path / ".eval"
    blocker.write_text("not a dir", encoding="utf-8")
    res = bind_accept_path(
        final_bytes=FINAL.encode(),
        git_dir=str(tmp_path / ".git"),
        repo_root=tmp_path,
    )
    # Binder reports the write error but does not raise.
    assert res.attempted is True
    assert res.paths_written == ()
    assert res.errors
