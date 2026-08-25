"""S6 Slice 7 contract tests (Issue #246).

Covers:
* dogfood deterministic sample reproducibility (schema pin + membership hash).
* async structural seam: async mode never awaits the judge (never blocks).
* train-export row scrub-failure policy: drop + report + continue; no
  .eval/quarantine/; hard_negative never enters positive_gold.
* sessions reader identity contract (S6-F06/F07): happy-path local twin show,
  sess_ + open|closed lifecycle, fail-closed missing/escape, show/map-only
  surface (no chat timeline / graph browser), optional opik_thread_ref.
* CLI envelope shape for the five Slice 7 commands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Dogfood: deterministic sample reproducibility
# ---------------------------------------------------------------------------


def test_dogfood_sample_deterministic_membership() -> None:
    from git_cg.eval.dogfood.capture import select_sample_members

    pop = ["a", "b", "c", "d"]
    a = select_sample_members(pop, rate=0.5, seed="seed-fixed-1")
    b = select_sample_members(pop, rate=0.5, seed="seed-fixed-1")
    assert a == b  # stable across runs
    assert len(a) == 2  # rate*N
    assert set(a) <= set(pop)  # membership within population


def test_dogfood_sample_schema_requires_repro_fields() -> None:
    import hashlib

    from git_cg.eval.dogfood.capture import DOGFoodError, build_attachment

    sha = hashlib.sha256(b"m").hexdigest()
    with pytest.raises(DOGFoodError):
        build_attachment(message_sha256=sha, mode="sample")  # missing seed/rate/population


def test_dogfood_async_never_awaits_judge() -> None:
    """Structural seam: async mode marks never-await; product never blocks."""
    import hashlib

    from git_cg.eval.dogfood.capture import capture_dogfood

    sha = hashlib.sha256(b"feat: x").hexdigest()
    data = capture_dogfood(
        Path.cwd(),
        message_sha256=sha,
        mode="async",
        write=False,
    )
    assert data["product_block"] is False
    assert data["async_never_awaits_judge"] is True
    assert data["authority"] == "advisory"


def test_dogfood_attachment_reproduces_membership() -> None:
    from git_cg.eval.dogfood.capture import attachment_reproduces_membership

    att = {
        "mode": "sample",
        "sample_seed": "s",
        "sample_rate": 0.5,
        "population_id": "pop",
        "selected_ids": ["a"],
        "selected_set_hash": "0" * 64,
    }
    # Current helper verifies recorded metadata/hash consistency only.
    assert attachment_reproduces_membership(att) is False  # hash is fake → mismatch


# ---------------------------------------------------------------------------
# Train export: row scrub-failure policy
# ---------------------------------------------------------------------------


def _write_bundle(root: Path, bid: str, label: str, message: str) -> None:
    bundles = root / ".eval" / "bundles" / "acceptpath"
    bundles.mkdir(parents=True, exist_ok=True)
    (bundles / f"{bid}.json").write_text(
        json.dumps(
            {
                "schema_version": "acceptpath_bundle_v1",
                "id": bid,
                "train_label": label,
                "final_message": message,
                "gate": {"deterministic_pass": label == "positive"},
                "meta": {"train_label": label},
            }
        )
    )


def test_train_export_empty_repo_ok(tmp_path: Path) -> None:
    from git_cg.eval.train_export import build_train_export

    result = build_train_export(tmp_path, redaction_profile="train_rich")
    assert result["export"]["schema_version"] == "train_export_v1"
    assert result["row_ids"] == []
    assert result["dropped_row_ids"] == []


def test_train_export_unlabeled_dropped_not_positive(tmp_path: Path) -> None:
    from git_cg.eval.train_export import build_train_export

    _write_bundle(tmp_path, "b-unlabeled", "", "feat: no label")
    result = build_train_export(tmp_path, redaction_profile="train_rich")
    # Unlabeled rows are excluded from export rows (never silent positive).
    assert result["positive_gold_count"] == 0
    assert "b-unlabeled" in result["dropped_row_ids"]


def test_train_export_no_quarantine_store(tmp_path: Path) -> None:
    from git_cg.eval.train_export import train_export

    _write_bundle(tmp_path, "b-pos", "positive", "feat: ok")
    train_export(tmp_path, redaction_profile="train_rich")
    assert not (tmp_path / ".eval" / "quarantine").exists()


def test_train_export_rejects_raw_dev_unsafe(tmp_path: Path) -> None:
    from git_cg.eval.train_export import TrainExportError, train_export

    with pytest.raises(TrainExportError) as ei:
        train_export(tmp_path, redaction_profile="raw_dev_unsafe", write=False)
    assert ei.value.exit_code == 2


# ---------------------------------------------------------------------------
# Sessions reader: S6-F06 / S6-F07 identity + happy-path contract
# ---------------------------------------------------------------------------

_SESS_ID = "sess_0123456789abcdef0123456789abcdef"


def _write_session_twin(
    root: Path,
    *,
    session_id: str = _SESS_ID,
    lifecycle: str = "closed",
    message_versions: list[dict] | None = None,
    opik_thread_ref: str | dict | None = "opik-thread-demo",
    filename: str | None = None,
    mutate=None,
) -> Path:
    """Persist a schema-valid local twin under ``.eval/sessions/``."""
    from git_cg.eval.binding.session_thread import build_session_twin

    twin = build_session_twin(
        session_id,
        lifecycle=lifecycle,
        attempt_ids=["a1"],
        message_versions=message_versions
        or [
            {
                "kind": "draft",
                "message": "feat: draft",
                "message_sha256": "a" * 64,
                "source": "commit_editmsg",
            },
            {
                "kind": "final_accept",
                "message": "feat: final",
                "message_sha256": "b" * 64,
                "source": "commit_editmsg",
            },
        ],
        opened_at="2026-08-25T00:00:00Z",
        closed_at="2026-08-25T00:01:00Z" if lifecycle == "closed" else None,
        generation_thread_id="repo-gitCommitGenerator",
        notes="fixture twin for sessions reader",
    )
    if opik_thread_ref is not None:
        twin["opik_thread_ref"] = opik_thread_ref
    if mutate is not None:
        mutate(twin)
    sessions = root / ".eval" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    path = sessions / (filename or f"{session_id}.json")
    path.write_text(json.dumps(twin, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def test_session_not_found_is_usage(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, "sess_missing")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_session_invalid_id_is_usage(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, "not-a-sess-id")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_session_repo_generation_thread_id_rejected(tmp_path: Path) -> None:
    """D9: repo-… correlation threads are never session ids on the reader."""
    from git_cg.eval.sessions import SessionsError, show_session

    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, "repo-gitCommitGenerator")
    assert ei.value.exit_code == 2
    assert "sess_" in str(ei.value)


def test_session_show_happy_path_offline(tmp_path: Path) -> None:
    """S6-F06: session show reads local twin without Opik/network."""
    from git_cg.eval.sessions import show_session

    _write_session_twin(tmp_path)
    data = show_session(tmp_path, _SESS_ID)

    assert data["network"] is False
    assert data["authority"] == "local_layer_a"
    assert data["surface"] == "show_map_only"
    assert data["session_thread_id"] == _SESS_ID
    assert data["lifecycle"] == "closed"
    assert data["message_version_count"] == 2
    assert data["opik_thread_ref"] == "opik-thread-demo"

    sess = data["session"]
    assert sess["schema_version"] == "commit_session_thread_v1"
    assert sess["session_thread_id"] == _SESS_ID
    assert sess["id"] == f"sessmeta_{_SESS_ID}"
    assert sess["meta"]["lifecycle"] == "closed"
    assert sess["meta"]["generation_thread_id"] == "repo-gitCommitGenerator"
    assert len(sess["message_versions"]) == 2
    # Show/map only — never promote chat-timeline / graph-browser fields.
    for banned in ("messages", "graph", "timeline", "nodes", "edges", "chat"):
        assert banned not in data
        assert banned not in sess


def test_thread_show_maps_message_versions_not_chat_timeline(tmp_path: Path) -> None:
    """S6-F06/F07: thread show is the same sess_ twin, store fields only."""
    from git_cg.eval.sessions import show_thread

    _write_session_twin(tmp_path)
    data = show_thread(tmp_path, _SESS_ID)

    assert data["network"] is False
    assert data["surface"] == "show_map_only"
    thread = data["thread"]
    assert thread["session_thread_id"] == _SESS_ID
    assert thread["message_version_count"] == 2
    assert len(thread["message_versions"]) == 2
    assert "messages" not in thread  # not a chat timeline
    for banned in ("graph", "timeline", "nodes", "edges", "chat"):
        assert banned not in data
        assert banned not in thread


def test_session_show_accepts_sessmeta_alias(tmp_path: Path) -> None:
    from git_cg.eval.sessions import show_session

    _write_session_twin(tmp_path)
    data = show_session(tmp_path, f"sessmeta_{_SESS_ID}")
    assert data["session_thread_id"] == _SESS_ID
    assert data["session"]["id"] == f"sessmeta_{_SESS_ID}"


def test_session_open_and_closed_lifecycle_accepted(tmp_path: Path) -> None:
    from git_cg.eval.sessions import show_session

    _write_session_twin(tmp_path, lifecycle="open")
    open_data = show_session(tmp_path, _SESS_ID)
    assert open_data["lifecycle"] == "open"

    # overwrite with closed
    _write_session_twin(tmp_path, lifecycle="closed")
    closed_data = show_session(tmp_path, _SESS_ID)
    assert closed_data["lifecycle"] == "closed"


def test_session_invalid_lifecycle_is_integrity(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    def _bad_lifecycle(twin: dict) -> None:
        twin["meta"]["lifecycle"] = "archived"

    _write_session_twin(tmp_path, mutate=_bad_lifecycle)
    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, _SESS_ID)
    assert ei.value.exit_code == 4
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    assert "lifecycle" in str(ei.value)


def test_session_missing_lifecycle_is_integrity(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    def _drop_lifecycle(twin: dict) -> None:
        twin["meta"].pop("lifecycle", None)

    _write_session_twin(tmp_path, mutate=_drop_lifecycle)
    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, _SESS_ID)
    assert ei.value.exit_code == 4
    assert ei.value.code == "EVAL_STORE_INTEGRITY"


def test_session_id_mismatch_is_integrity(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    other = "sess_ffffffffffffffffffffffffffffffff"

    def _mismatch(twin: dict) -> None:
        twin["session_thread_id"] = other
        twin["id"] = f"sessmeta_{other}"

    # File is named for requested id, but body claims another id.
    _write_session_twin(tmp_path, filename=f"{_SESS_ID}.json", mutate=_mismatch)
    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, _SESS_ID)
    assert ei.value.exit_code == 4
    assert "mismatch" in str(ei.value)


def test_session_path_escape_is_integrity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Containment: resolved twin path must stay under .eval/sessions/."""
    from git_cg.eval import sessions as sessions_mod
    from git_cg.eval.sessions import SessionsError, show_session

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    root = tmp_path / ".eval" / "sessions"
    root.mkdir(parents=True, exist_ok=True)

    real_dir = sessions_mod._sessions_dir

    def _fake_sessions_dir(repo: Path) -> Path:
        return real_dir(repo)

    monkeypatch.setattr(sessions_mod, "_sessions_dir", _fake_sessions_dir)

    # Force path construction to a file outside sessions via symlink when possible.
    target = root / f"{_SESS_ID}.json"
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")

    # Even if symlink exists, reader must fail closed on schema/content or containment.
    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, _SESS_ID)
    assert ei.value.exit_code in {2, 4}


def test_session_corrupt_json_is_integrity(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    sessions = tmp_path / ".eval" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{_SESS_ID}.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, _SESS_ID)
    assert ei.value.exit_code == 4
    assert ei.value.code == "EVAL_STORE_INTEGRITY"


def test_session_wrong_schema_version_is_integrity(tmp_path: Path) -> None:
    from git_cg.eval.sessions import SessionsError, show_session

    def _bad_schema(twin: dict) -> None:
        twin["schema_version"] = "commit_session_thread_v0"

    _write_session_twin(tmp_path, mutate=_bad_schema)
    with pytest.raises(SessionsError) as ei:
        show_session(tmp_path, _SESS_ID)
    assert ei.value.exit_code == 4


def test_cli_session_and_thread_show_happy_path(tmp_path: Path) -> None:
    """CLI JSON envelopes for happy-path session/thread show (offline)."""
    _write_session_twin(tmp_path)
    sess_payload, sess_code = _cli(["eval", "session", "show", "--id", _SESS_ID, "--root", str(tmp_path), "--json"])
    assert sess_code == 0
    assert sess_payload["ok"] is True
    assert sess_payload["command"] == "eval session show"
    assert sess_payload["data"]["network"] is False
    assert sess_payload["data"]["surface"] == "show_map_only"
    assert sess_payload["data"]["session"]["session_thread_id"] == _SESS_ID
    assert sess_payload["data"]["lifecycle"] == "closed"

    thread_payload, thread_code = _cli(["eval", "thread", "show", "--id", _SESS_ID, "--root", str(tmp_path), "--json"])
    assert thread_code == 0
    assert thread_payload["ok"] is True
    assert thread_payload["command"] == "eval thread show"
    assert thread_payload["data"]["thread"]["message_version_count"] == 2
    assert "messages" not in thread_payload["data"]["thread"]


# ---------------------------------------------------------------------------
# CLI envelope: five Slice 7 commands emit cli_output_envelope_v1
# ---------------------------------------------------------------------------


def _cli(args: list[str]) -> dict:
    from typer.testing import CliRunner

    from git_cg.main import app

    r = CliRunner().invoke(app, args)
    return json.loads(r.stdout), r.exit_code


def test_cli_dogfood_envelope() -> None:
    payload, code = _cli(["eval", "dogfood", "--commit-message", "feat: x", "--mode", "always", "--no-write", "--json"])
    assert code == 0
    assert payload["schema_version"] == "cli_output_envelope_v1"
    assert payload["command"] == "eval dogfood"
    assert payload["ok"] is True
    assert payload["data"]["product_block"] is False


def test_cli_train_export_envelope_empty() -> None:
    payload, code = _cli(["eval", "train-export", "--no-write", "--json"])
    assert code == 0
    assert payload["command"] == "eval train-export"
    assert payload["data"]["scrub_report"]["status"] == "ok"


def test_cli_session_show_missing_usage() -> None:
    payload, code = _cli(["eval", "session", "show", "--id", "sess_missing", "--json"])
    assert code == 2
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_USAGE"


def test_cli_thread_show_missing_usage() -> None:
    payload, code = _cli(["eval", "thread", "show", "--id", "sess_missing", "--json"])
    assert code == 2
    assert payload["ok"] is False


def test_cli_amend_brief_missing_run_is_usage() -> None:
    # Repo experiments store exists but run id is absent → usage (exit 2).
    payload, code = _cli(["eval", "amend-brief", "rs_missing", "--no-write", "--json"])
    assert code in (2, 4)  # 2 when store exists, 4 when store missing (fail-closed)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] in {"EVAL_USAGE", "EVAL_STORE_INTEGRITY"}


def test_train_export_row_scrub_failure_drops_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S6-G05: row scrub fail ⇒ drop + scrub_report + continue; no quarantine store."""
    from git_cg.eval.mirror.redaction import RedactionError
    from git_cg.eval.train_export import build_train_export

    secret = "sk-test-secret-token-value-0123456789"
    _write_bundle(tmp_path, "b-ok", "positive", "feat: keep me")
    _write_bundle(tmp_path, "b-bad", "positive", f"feat: drop me {secret}")

    def _fake_redact(bundle, profile="train_rich"):
        bid = str(bundle.get("id") or "")
        if bid == "b-bad":
            raise RedactionError(f"injected scrub failure for {bid}")
        # Pass-through for the good row (still secret-safe via projection).
        return dict(bundle)

    monkeypatch.setattr(
        "git_cg.eval.mirror.redaction.redact_bundle_for_export",
        _fake_redact,
    )

    result = build_train_export(tmp_path, redaction_profile="train_rich")
    assert "b-bad" in result["dropped_row_ids"]
    assert "b-ok" in result["row_ids"] or any(r.get("id") == "b-ok" for r in result["rows"])
    assert result["scrub_report"]["status"] == "quarantined"
    report_blob = json.dumps(result["scrub_report"])
    assert "b-bad" in report_blob
    # No cleartext secret and no .eval/quarantine/ store.
    full = json.dumps(result)
    assert secret not in full
    assert "sk-test" not in full
    assert not (tmp_path / ".eval" / "quarantine").exists()


def test_train_export_masks_secret_in_retained_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S6-C08/G05: retained train rows never keep raw secret tokens/prefixes."""
    from git_cg.eval.train_export import build_train_export

    secret = "sk-test-secret-token-value-0123456789"
    _write_bundle(tmp_path, "b-secret", "positive", f"feat: key {secret}")

    # Force betterleaks path to a no-op so the local mask_secret floor is proven.
    monkeypatch.setattr(
        "git_cg.eval.mirror.redaction.redact_payload",
        lambda v: v,
    )

    result = build_train_export(tmp_path, redaction_profile="train_rich")
    blob = json.dumps(result, ensure_ascii=False)
    assert secret not in blob
    assert "sk-test" not in blob
    assert "•••[len=" in blob
    assert result["row_ids"], "secret-bearing but scrubbed row should still export"
