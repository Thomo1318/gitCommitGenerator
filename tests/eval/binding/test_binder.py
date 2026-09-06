"""S3 Slice 1 — accept-path binder package (Issue #231, S3-contract-v1.4).

Covers the locked binder-core contract surface (D1-D6, N2/N6/N19):

* capture gating (D1): off by default; ``GIT_CG_EVAL_CAPTURE``/profile law;
  capture-off ⇒ no writes + ``unbound_reason="capture_disabled"``;
* happy bind (N2/D4): schema-valid ``ape_bundle_v1`` with
  ``artifact_class=final_accept``, ``bound=true``, stored full-64
  ``final_message_sha256`` over the exact bytes;
* bytes-aware hashing (N19.4/N20.3): ``bytes | str``; invalid UTF-8 projects
  with ``utf-8-replace`` while the hash stays over the original bytes;
* scoped idempotency (N19.2/N20.1): same event+bytes ⇒ reuse; new event+same
  bytes ⇒ new session; missing token ⇒ new session;
* atomic persist + containment (N19.3): bundle written under
  ``.eval/bundles/acceptpath/`` with restrictive mode; path escape refused;
* honest unbound (N6): blank reason / ``final_accept`` class fail closed.

Synthetic case ids (D5, greppable): ``synth-s3-bind-happy``,
``synth-s3-capture-off``, ``synth-s3-scoped-reuse-same-event``,
``synth-s3-scoped-reuse-new-event``, ``synth-s3-fake-final-accept``,
``synth-s3-unbind-reason-missing``, ``synth-s3-draft-vs-final``.

No network. No Opik import on the bind path. No credentials required.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from git_cg.eval.binding import (
    BindInput,
    BindResult,
    bind_final_accept,
    bind_unbound,
    capture_enabled,
    message_sha256_bytes,
    paths as binding_paths,
)
from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.schema_pack import validate_instance

GENERATED = (
    "✨ feat(eval): add accept-path binder\n\n"
    "Body line.\n\n"
    "Refs: #231\n"
    "SemVer-Impact: MINOR\n"
    "Change-Types: feat\n"
    "Changelog-Groups: Added\n"
)
FINAL_ACCEPTED = GENERATED
FINAL_EDITED = GENERATED.replace("add accept-path binder", "add accept path binder")

CAPTURE_ON = {"GIT_CG_EVAL_CAPTURE": "on"}
CAPTURE_OFF = {"GIT_CG_EVAL_CAPTURE": "off"}


@pytest.fixture(autouse=True)
def _capture_env(monkeypatch: pytest.MonkeyPatch):
    """Default every test to capture ON unless it overrides the env.

    The binder reads ``os.environ`` via ``capture_enabled()``; tests control it
    through monkeypatch so no real environment leaks in.
    """
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "on")
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)
    yield


def _bind(tmp_path, **overrides) -> BindResult:
    kwargs = {
        "final_message": FINAL_ACCEPTED,
        "generated_message": GENERATED,
        "trace_id": "trace-abc123",
        "thread_id": "repo-gitCommitGenerator",
        "accept_event_token": "ae_testtoken",
    }
    kwargs.update(overrides)
    return bind_final_accept(BindInput(**kwargs), repo_root=tmp_path, write=True)


# ---------------------------------------------------------------------------
# D1 — capture enablement law (fail-closed parse)
# ---------------------------------------------------------------------------


def test_capture_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_CG_EVAL_CAPTURE", raising=False)
    monkeypatch.delenv("GIT_CG_EVAL_PROFILE", raising=False)
    assert capture_enabled() is False


@pytest.mark.parametrize("token", ["1", "true", "on", "yes", "TRUE", " On "])
def test_capture_truthy_tokens(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", token)
    assert capture_enabled() is True


@pytest.mark.parametrize("token", ["0", "false", "off", "no", "", "garbage", "2"])
def test_capture_falsy_and_unknown_fail_closed(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", token)
    assert capture_enabled() is False


def test_capture_profile_alias_only_when_canonical_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_CG_EVAL_CAPTURE", raising=False)
    monkeypatch.setenv("GIT_CG_EVAL_PROFILE", "maintainer")
    assert capture_enabled() is True
    # Canonical switch wins when set.
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "off")
    assert capture_enabled() is False


def test_capture_profile_basic_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_CG_EVAL_CAPTURE", raising=False)
    monkeypatch.setenv("GIT_CG_EVAL_PROFILE", "basic")
    assert capture_enabled() is False


def test_capture_enabled_accepts_explicit_env_mapping() -> None:
    assert capture_enabled(CAPTURE_ON) is True
    assert capture_enabled(CAPTURE_OFF) is False
    assert capture_enabled({}) is False


# ---------------------------------------------------------------------------
# synth-s3-capture-off — capture off ⇒ no writes, honest unbound
# ---------------------------------------------------------------------------


def test_synth_s3_capture_off(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """synth-s3-capture-off: env off → no writes; unbound_reason=capture_disabled."""
    monkeypatch.setenv("GIT_CG_EVAL_CAPTURE", "off")
    result = _bind(tmp_path)
    assert result.bound is False
    assert result.unbound_reason == "capture_disabled"
    assert result.bundle is None
    assert result.paths_written == ()
    # Zero creates under .eval/**
    assert not (tmp_path / ".eval").exists()


# ---------------------------------------------------------------------------
# synth-s3-bind-happy — schema-valid final_accept bundle + stable hash
# ---------------------------------------------------------------------------


def test_synth_s3_bind_happy(tmp_path) -> None:
    """synth-s3-bind-happy: exact bytes → final_accept, sha stable, schema-valid."""
    result = _bind(tmp_path)
    assert result.bound is True
    assert result.unbound_reason is None
    bundle = result.bundle
    assert bundle is not None

    # Schema-valid against the frozen pin.
    validate_instance("ape_bundle_v1", bundle)

    assert bundle["schema_version"] == "ape_bundle_v1"
    assert bundle["artifact_class"] == "final_accept"
    assert bundle["bound"] is True
    assert bundle["final_message"] == FINAL_ACCEPTED
    # Full 64-hex stored hash of the exact bytes (not truncated).
    assert bundle["final_message_sha256"] == message_sha256(FINAL_ACCEPTED)
    assert len(bundle["final_message_sha256"]) == 64
    # sess_ session id minted; thread_id is correlation-only, never the session id.
    assert bundle["session_thread_id"].startswith("sess_")
    assert bundle["session_thread_id"] != "repo-gitCommitGenerator"
    assert bundle["provenance_label"] == "final_accept"
    assert bundle["redaction_profile"] == "default_scrub"
    # Cards/correlation under meta (no illegal top-level score_card).
    assert "score_card" not in bundle
    assert bundle["meta"]["producer"] == "acceptpath_binder"
    assert bundle["meta"]["binding"]["state"] == "bound"
    assert bundle["meta"]["binding"]["trace_id"] == "trace-abc123"
    assert bundle["meta"]["binding"]["thread_id"] == "repo-gitCommitGenerator"
    assert bundle["meta"]["accept_event"]["token"] == "ae_testtoken"


def test_bind_persists_bundle_atomically_with_restrictive_mode(tmp_path) -> None:
    result = _bind(tmp_path)
    assert result.paths_written
    rel = result.paths_written[0]
    assert rel.startswith(".eval/bundles/acceptpath/")
    written = tmp_path / rel
    assert written.is_file()
    # Restrictive file mode 0600 (N19.3).
    mode = stat.S_IMODE(os.stat(written).st_mode)
    assert mode == 0o600
    # On-disk content is the authoritative schema-valid bundle.
    on_disk = json.loads(written.read_text(encoding="utf-8"))
    validate_instance("ape_bundle_v1", on_disk)
    assert on_disk["final_message_sha256"] == result.bundle["final_message_sha256"]


def test_bind_score_card_lives_under_meta(tmp_path) -> None:
    card = {"contract_compliant": True, "semver_impact": "MINOR"}
    result = _bind(tmp_path, score_card=card)
    assert result.bundle["meta"]["score_card"] == card
    assert "score_card" not in result.bundle  # M5: no illegal top-level card


def test_caller_meta_cannot_overwrite_authority_keys(tmp_path) -> None:
    """BindInput.meta is additive only; accept_event/binding/producer stay authoritative."""
    result = _bind(
        tmp_path,
        meta={
            "producer": "attacker",
            "accept_event": {"token": "forged"},
            "binding": {"state": "unbound"},
            "trajectory": {"schema_version": "trajectory_evidence_v1"},
        },
    )
    assert result.bound is True
    meta = result.bundle["meta"]
    assert meta["producer"] == "acceptpath_binder"
    assert meta["accept_event"]["token"] == "ae_testtoken"
    assert meta["binding"]["state"] == "bound"
    assert meta["trajectory"]["schema_version"] == "trajectory_evidence_v1"


# ---------------------------------------------------------------------------
# N19.4 / N20.3 — bytes-aware binding
# ---------------------------------------------------------------------------


def test_message_sha256_bytes_matches_text_helper_for_str() -> None:
    assert message_sha256_bytes(FINAL_ACCEPTED) == message_sha256(FINAL_ACCEPTED)


def test_bind_accepts_exact_bytes(tmp_path) -> None:
    raw = FINAL_ACCEPTED.encode("utf-8")
    result = _bind(tmp_path, final_message=raw)
    assert result.bound is True
    assert result.bundle["final_message"] == FINAL_ACCEPTED
    assert result.bundle["final_message_sha256"] == message_sha256_bytes(raw)


def test_bind_invalid_utf8_projects_replace_and_hashes_original(tmp_path) -> None:
    """AC22 / N20.3: invalid UTF-8 → utf-8-replace projection, hash over original bytes."""
    raw = b"\xff\xfe invalid \x80 bytes\n"
    result = _bind(tmp_path, final_message=raw)
    assert result.bound is True
    bundle = result.bundle
    # Hash authority is the ORIGINAL bytes, not the replaced text.
    assert bundle["final_message_sha256"] == message_sha256_bytes(raw)
    assert bundle["final_message_sha256"] != message_sha256(raw.decode("utf-8", errors="replace"))
    # Projection metadata recorded.
    assert bundle["meta"]["final_message_encoding"] == "utf-8-replace"
    assert bundle["meta"]["final_message_byte_length"] == len(raw)
    # Schema still valid (final_message is a string).
    validate_instance("ape_bundle_v1", bundle)


def test_bind_empty_final_message_unbound(tmp_path) -> None:
    result = _bind(tmp_path, final_message="   \n  ")
    assert result.bound is False
    assert result.unbound_reason == "final_message_absent"
    assert result.paths_written == ()


# ---------------------------------------------------------------------------
# N19.2 / N20.1 — scoped idempotency
# ---------------------------------------------------------------------------


def test_synth_s3_scoped_reuse_same_event(tmp_path) -> None:
    """synth-s3-scoped-reuse-same-event: same token + same bytes ⇒ reuse session/bundle."""
    first = _bind(tmp_path, accept_event_token="ae_same")
    second = _bind(tmp_path, accept_event_token="ae_same")
    assert first.bound and second.bound
    # Identity reused — no new sess_ minted.
    assert first.bundle["session_thread_id"] == second.bundle["session_thread_id"]
    assert first.bundle["case_id"] == second.bundle["case_id"]
    # Only one authoritative bundle file on disk.
    files = list((tmp_path / ".eval" / "bundles" / "acceptpath").glob("*.json"))
    assert len([f for f in files if f.name != "index.json"]) == 1


def test_synth_s3_scoped_reuse_new_event(tmp_path) -> None:
    """synth-s3-scoped-reuse-new-event: new token + same bytes ⇒ new session."""
    first = _bind(tmp_path, accept_event_token="ae_event_one")
    second = _bind(tmp_path, accept_event_token="ae_event_two")
    assert first.bound and second.bound
    assert first.bundle["session_thread_id"] != second.bundle["session_thread_id"]
    files = [f for f in (tmp_path / ".eval" / "bundles" / "acceptpath").glob("*.json") if f.name != "index.json"]
    assert len(files) == 2


def test_scoped_reuse_missing_token_fails_closed_to_new_session(tmp_path) -> None:
    """N19.2: no reliable accept_event_token ⇒ new session; never silently reuse."""
    first = _bind(tmp_path, accept_event_token=None)
    second = _bind(tmp_path, accept_event_token=None)
    assert first.bound and second.bound
    assert first.bundle["session_thread_id"] != second.bundle["session_thread_id"]


def test_scoped_reuse_same_event_changed_bytes_new_bundle(tmp_path) -> None:
    """N19.2: same event + changed bytes ⇒ new bundle (no silent identity overwrite)."""
    first = _bind(tmp_path, accept_event_token="ae_same", final_message=FINAL_ACCEPTED)
    second = _bind(tmp_path, accept_event_token="ae_same", final_message=FINAL_EDITED)
    assert first.bound and second.bound
    # Changed bytes ⇒ different hash ⇒ different reuse_key ⇒ new identity.
    assert first.bundle["final_message_sha256"] != second.bundle["final_message_sha256"]
    assert first.bundle["session_thread_id"] != second.bundle["session_thread_id"]


# ---------------------------------------------------------------------------
# synth-s3-draft-vs-final — final bytes are the scored artifact (FIND-027)
# ---------------------------------------------------------------------------


def test_synth_s3_draft_vs_final(tmp_path) -> None:
    """synth-s3-draft-vs-final: generated ≠ final; final remains the scored artifact."""
    result = _bind(tmp_path, generated_message=GENERATED, final_message=FINAL_EDITED)
    bundle = result.bundle
    assert bundle["final_message"] == FINAL_EDITED
    assert bundle["final_message_sha256"] == message_sha256(FINAL_EDITED)
    # Draft is evidence only; it is never relabeled into the final field.
    assert bundle["final_message"] != GENERATED


# ---------------------------------------------------------------------------
# N6 — honest unbound (fail closed)
# ---------------------------------------------------------------------------


def test_synth_s3_fake_final_accept() -> None:
    """synth-s3-fake-final-accept: bound=false + final_accept ⇒ fail closed."""
    with pytest.raises(ValueError, match="EVAL_FAKE_BOUND"):
        bind_unbound(reason="capture_disabled", artifact_class="final_accept")


def test_synth_s3_unbind_reason_missing() -> None:
    """synth-s3-unbind-reason-missing: bound=false without reason ⇒ fail closed."""
    with pytest.raises(ValueError, match="EVAL_FAKE_BOUND"):
        bind_unbound(reason="   ")


def test_bind_unbound_happy_produces_schema_valid_non_final_accept() -> None:
    result = bind_unbound(reason="capture_disabled", final_message=FINAL_ACCEPTED)
    assert result.bound is False
    assert result.unbound_reason == "capture_disabled"
    assert result.bundle["artifact_class"] == "Opik-unbound"
    assert result.bundle["bound"] is False
    validate_instance("ape_bundle_v1", result.bundle)


def test_bind_unbound_rejects_unknown_class() -> None:
    with pytest.raises(ValueError, match="artifact_class"):
        bind_unbound(reason="x", artifact_class="not_a_class")


# ---------------------------------------------------------------------------
# N19.3 — containment / persistence hardening
# ---------------------------------------------------------------------------


def test_containment_refuses_escape(tmp_path) -> None:
    with pytest.raises(binding_paths.LayerAPathError):
        binding_paths._contained(tmp_path, tmp_path / ".eval" / ".." / "outside")


def test_containment_refuses_symlink_escape(tmp_path) -> None:
    """N19.3: a symlink under .eval that points outside the repo must fail closed."""
    outside = tmp_path / "outside_target"
    outside.mkdir()
    eval_root = tmp_path / ".eval"
    eval_root.mkdir()
    link = eval_root / "escape_link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(binding_paths.LayerAPathError):
        binding_paths._contained(tmp_path, Path("escape_link") / "bundle.json")


def test_repo_root_unresolved_returns_unbound_not_raise(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC23 / N20.5: unresolvable repo root ⇒ no writes, no product fail."""

    def _boom(start=None):
        raise binding_paths.RepoRootUnresolvedError("repo_root_unresolved")

    monkeypatch.setattr(binding_paths, "resolve_repo_root", _boom)
    # Force the binder to use its own resolution (repo_root=None).
    result = bind_final_accept(BindInput(final_message=FINAL_ACCEPTED), repo_root=None, write=True)
    assert result.bound is False
    assert result.unbound_reason == "repo_root_unresolved"


def test_write_disabled_produces_bundle_without_persist(tmp_path) -> None:
    result = bind_final_accept(
        BindInput(final_message=FINAL_ACCEPTED, accept_event_token="ae_x"),
        repo_root=tmp_path,
        write=False,
    )
    assert result.bound is True
    assert result.paths_written == ()
    assert not (tmp_path / ".eval").exists()
    validate_instance("ape_bundle_v1", result.bundle)


def test_scan_reuse_skips_index_and_corrupt_files(tmp_path) -> None:
    """Bundle JSON is authority; index.json + corrupt files must never be reused."""
    from git_cg.eval.binding.binder import _scan_reuse_key

    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    bundles.mkdir(parents=True)
    # Cache-only index must be ignored even if it looks matching.
    (bundles / "index.json").write_text(
        json.dumps(
            {
                "final_message_sha256": message_sha256(FINAL_ACCEPTED),
                "meta": {"accept_event": {"token": "ae_scan", "repo_root": str(tmp_path.resolve())}},
                "session_thread_id": "sess_from_index",
            }
        ),
        encoding="utf-8",
    )
    (bundles / "corrupt.json").write_text("{not-json", encoding="utf-8")
    (bundles / "not-object.json").write_text(json.dumps(["list"]), encoding="utf-8")
    (bundles / "no-meta.json").write_text(
        json.dumps({"final_message_sha256": message_sha256(FINAL_ACCEPTED), "meta": "x"}),
        encoding="utf-8",
    )
    (bundles / "wrong-token.json").write_text(
        json.dumps(
            {
                "final_message_sha256": message_sha256(FINAL_ACCEPTED),
                "meta": {"accept_event": {"token": "other", "repo_root": str(tmp_path.resolve())}},
            }
        ),
        encoding="utf-8",
    )
    (bundles / "wrong-root.json").write_text(
        json.dumps(
            {
                "final_message_sha256": message_sha256(FINAL_ACCEPTED),
                "meta": {"accept_event": {"token": "ae_scan", "repo_root": "/not/this/repo"}},
                "session_thread_id": "sess_wrong_root",
            }
        ),
        encoding="utf-8",
    )
    key = (str(tmp_path.resolve()), "ae_scan", message_sha256(FINAL_ACCEPTED))
    assert _scan_reuse_key(bundles, key) is None
    assert _scan_reuse_key(tmp_path / "missing", key) is None

    # Schema-valid candidate is adoptable.
    good = {
        "schema_version": "ape_bundle_v1",
        "case_id": "acceptpath:sess_good",
        "artifact_class": "final_accept",
        "bound": True,
        "final_message_sha256": message_sha256(FINAL_ACCEPTED),
        "session_thread_id": "sess_good",
        "meta": {"accept_event": {"token": "ae_scan", "repo_root": str(tmp_path.resolve())}},
    }
    (bundles / "sess_good.json").write_text(json.dumps(good), encoding="utf-8")
    assert _scan_reuse_key(bundles, key)["session_thread_id"] == "sess_good"


def test_scan_skips_symlinked_bundle_files(tmp_path) -> None:
    """Matching *.json symlink must not donate reuse identity (F-12)."""
    from git_cg.eval.binding.binder import _scan_reuse_key

    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    bundles.mkdir(parents=True)
    repo_root = str(tmp_path.resolve())
    token = "ae_scan_symlink"
    sha = message_sha256(FINAL_ACCEPTED)

    def _candidate(session_id: str) -> dict:
        return {
            "schema_version": "ape_bundle_v1",
            "case_id": f"acceptpath:{session_id}",
            "artifact_class": "final_accept",
            "bound": True,
            "final_message_sha256": sha,
            "session_thread_id": session_id,
            "meta": {"accept_event": {"token": token, "repo_root": repo_root}},
        }

    good = _candidate("sess_good")
    (bundles / "sess_good.json").write_text(json.dumps(good), encoding="utf-8")

    # Name sorts before sess_good.json so a followed symlink would be adopted first.
    poison = _candidate("sess_alink")
    outside = tmp_path / "outside_payload.json"
    outside.write_text(json.dumps(poison), encoding="utf-8")
    link = bundles / "sess_alink.json"
    link.symlink_to(outside)
    assert link.is_symlink()

    key = (repo_root, token, sha)
    scanned = _scan_reuse_key(bundles, key)
    assert scanned is not None
    assert scanned["session_thread_id"] == "sess_good"


def test_scan_skips_non_regular_files(tmp_path) -> None:
    """Matching *.json directory is skipped without raising (F-12)."""
    from git_cg.eval.binding.binder import _scan_reuse_key

    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    bundles.mkdir(parents=True)
    repo_root = str(tmp_path.resolve())
    token = "ae_scan_nonregular"
    sha = message_sha256(FINAL_ACCEPTED)
    good = {
        "schema_version": "ape_bundle_v1",
        "case_id": "acceptpath:sess_good",
        "artifact_class": "final_accept",
        "bound": True,
        "final_message_sha256": sha,
        "session_thread_id": "sess_good",
        "meta": {"accept_event": {"token": token, "repo_root": repo_root}},
    }
    (bundles / "sess_good.json").write_text(json.dumps(good), encoding="utf-8")
    # Directory named *.json sorts first; skip it and still adopt the regular file.
    (bundles / "aaa.json").mkdir()

    key = (repo_root, token, sha)
    scanned = _scan_reuse_key(bundles, key)
    assert scanned is not None
    assert scanned["session_thread_id"] == "sess_good"


def test_bind_write_error_reports_without_raising(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise binding_paths.LayerAPathError("containment boom")

    monkeypatch.setattr(binding_paths, "atomic_write_json", _boom)
    result = _bind(tmp_path)
    assert result.bound is True
    assert result.paths_written == ()
    assert result.errors and result.errors[0].startswith("bind_write_error:")


def test_schema_invalid_meta_returns_unbound(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import schema_pack
    from git_cg.eval.schema_pack import SchemaPackError

    def _boom(name, instance):
        raise SchemaPackError("forced schema invalid")

    monkeypatch.setattr(schema_pack, "validate_instance", _boom)
    # binder imports validate_instance into its module namespace
    monkeypatch.setattr("git_cg.eval.binding.binder.validate_instance", _boom)
    result = _bind(tmp_path)
    assert result.bound is False
    assert result.unbound_reason == "schema_invalid"
    assert result.errors


def test_reuse_ignores_blank_session_and_case_ids(tmp_path) -> None:
    """Blank session/case strings in a matching bundle must not be reused."""
    from git_cg.eval.binding.binder import _scan_reuse_key

    first = _bind(tmp_path, accept_event_token="ae_blankish")
    assert first.bound is True
    bundles = tmp_path / ".eval" / "bundles" / "acceptpath"
    # Overwrite the authoritative file with blank identity fields.
    blank = {
        "final_message_sha256": first.bundle["final_message_sha256"],
        "session_thread_id": "   ",
        "case_id": "",
        "meta": {
            "accept_event": {
                "token": "ae_blankish",
                "repo_root": str(tmp_path.resolve()),
            }
        },
    }
    target = bundles / f"{first.bundle['session_thread_id']}.json"
    target.write_text(json.dumps(blank), encoding="utf-8")
    key = (str(tmp_path.resolve()), "ae_blankish", first.bundle["final_message_sha256"])
    scanned = _scan_reuse_key(bundles, key)
    assert scanned is None
    # Re-bind mints a fresh session because blank ids are not adoptable.
    second = _bind(tmp_path, accept_event_token="ae_blankish")
    assert second.bound is True
    assert second.bundle["session_thread_id"].startswith("sess_")
    assert second.bundle["session_thread_id"].strip()
    assert second.bundle["case_id"].startswith("acceptpath:")


def test_bind_unbound_with_final_message_hashes() -> None:
    result = bind_unbound(reason="fixture_only", final_message=FINAL_ACCEPTED, case_id="acceptpath:unbound-x")
    assert result.bound is False
    assert result.bundle["final_message"] == FINAL_ACCEPTED
    assert result.bundle["final_message_sha256"] == message_sha256(FINAL_ACCEPTED)
    assert result.bundle["case_id"] == "acceptpath:unbound-x"


def test_bind_unbound_without_final_message() -> None:
    """Cover bind_unbound path that omits final_message hashing (347->350)."""
    from git_cg.eval.binding.binder import bind_unbound

    result = bind_unbound(reason="no-message-path", artifact_class="fixture")
    assert result.bound is False
    assert result.unbound_reason == "no-message-path"
    assert "final_message" not in result.bundle
    assert "final_message_sha256" not in result.bundle


# ---------------------------------------------------------------------------
# Isolation — bind path must not require Opik
# ---------------------------------------------------------------------------


def test_bind_path_does_not_import_opik(tmp_path) -> None:
    """The binder's own import graph must not require Opik (offline authority).

    Other eval modules in the session may legitimately import ``opik``; the
    contract here is that importing ``git_cg.eval.binding`` and running a bind
    does not itself pull Opik into the process. Assert against a fresh import
    of the binding package's own modules rather than global interpreter state.
    """
    import importlib
    import subprocess

    # A clean interpreter must not gain ``opik`` from importing the binding package.
    probe = (
        "import sys; import git_cg.eval.binding; "
        "sys.exit(1 if any(m == 'opik' or m.startswith('opik.') for m in sys.modules) else 0)"
    )
    assert subprocess.run([sys.executable, "-c", probe], check=False).returncode == 0, (
        "importing git_cg.eval.binding must not import opik"
    )
    binding_modules = [m for m in sys.modules if m.startswith("git_cg.eval.binding")]
    assert binding_modules, "binding package should be imported by this test"
    for name in binding_modules:
        mod = importlib.import_module(name)
        # No binding module may hold a hard reference to a live opik module.
        assert not any(isinstance(v, type(sys)) and getattr(v, "__name__", "") == "opik" for v in vars(mod).values()), (
            f"{name} must not import opik"
        )
    # And the bind itself must succeed without opik being a binder dependency.
    result = _bind(tmp_path)
    assert result.bound is True
