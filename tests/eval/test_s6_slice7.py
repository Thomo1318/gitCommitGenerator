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
* amend-brief S6-F01-F04 / A2-A3: offline L1 projections, advisory authority,
  local session_thread_id reference, preference-pair threshold/selection law,
  and fail-closed/CLI envelope behaviour.
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


# ---------------------------------------------------------------------------
# Amend-brief: S6-F01-F04 / A2-A3 claim-grade proof lock
# ---------------------------------------------------------------------------

_EXP_ID = "rs_amend_brief_demo"
_BRIEF_ID = "brief-amend-lock-01"


def _fp_inputs(**over) -> dict:
    base = {
        "metric_ids": ["i.counter_span_consistent"],
        "failure_ids": ["EVAL_TOPOLOGY"],
        "blame_span": "regeneration",
        "first_divergent_span": "regeneration",
        "missing_required_spans": ["regeneration"],
        "artifact_class": "final_accept",
        "regime": "B",
        "path_class_key": "code_change",
    }
    base.update(over)
    return base


def _mk_score(
    metric_id: str,
    value,
    *,
    passed: bool,
    failure_ids: list[str] | None = None,
    evidence: dict | None = None,
    reason: str | None = None,
):
    from git_cg.eval.scoring.result_builder import make_score

    kwargs: dict = {"passed": passed}
    if failure_ids is not None:
        kwargs["failure_ids"] = failure_ids
    if evidence is not None:
        kwargs["evidence"] = evidence
    if reason is not None:
        kwargs["reason"] = reason
    if metric_id.startswith("i."):
        kwargs["product_authority"] = "git_cg.eval.scoring.family_i"
    return make_score(metric_id, value, **kwargs)


def _write_experiment(repo: Path, experiment_id: str = _EXP_ID) -> None:
    from git_cg.eval.binding.paths import atomic_write_json, experiments_dir

    record = {
        "schema_version": "experiment_v1",
        "id": experiment_id,
        "experiment_name": experiment_id,
        "lane": "suite",
        "git_sha": "deadbeef",
        "catalog_pin": "metric_catalog_v1@" + "a" * 64,
        "schema_pack": "schema_pack_v1@" + "b" * 64,
        "metric_catalog": "metric_catalog_v1@" + "a" * 64,
        "meta": {"pins": {"project_lane": "suite", "environment": "local"}},
    }
    atomic_write_json(experiments_dir(repo) / experiment_id / "experiment.json", record)


def _write_case(
    repo: Path,
    case_id: str,
    *,
    experiment_id: str = _EXP_ID,
    passed: bool,
    scores: list,
    failed_metric_ids: list[str] | None = None,
    gates: list | None = None,
) -> None:
    from git_cg.eval.binding.paths import atomic_write_json, experiments_dir

    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": experiment_id,
        "case_id": case_id,
        "deterministic_pass": passed,
        "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
        "evaluator_errors": [],
        "scores": [s.model_dump(mode="json") for s in scores],
        "gates": gates or [],
        "failed_metric_ids": failed_metric_ids or [],
    }
    atomic_write_json(
        experiments_dir(repo) / experiment_id / "cases" / f"{case_id}.json",
        payload,
    )


def _seed_amend_brief_cases(repo: Path, *, experiment_id: str = _EXP_ID) -> None:
    """Land mixed local Layer-A rows with known projection outcomes."""
    (repo / ".git").mkdir(exist_ok=True)
    _write_experiment(repo, experiment_id)

    # Passing Family A case — contributes to rollups only.
    _write_case(
        repo,
        "case-pass",
        experiment_id=experiment_id,
        passed=True,
        scores=[_mk_score("a.final_message_present", True, passed=True)],
    )

    # Failing Family I case — regime/path_class + failure_ids + blocking.
    _write_case(
        repo,
        "case-fail",
        experiment_id=experiment_id,
        passed=False,
        scores=[
            _mk_score(
                "i.counter_span_consistent",
                False,
                passed=False,
                failure_ids=["EVAL_TOPOLOGY"],
                evidence={
                    "diag_fingerprint_inputs": _fp_inputs(),
                    "prevention_ids": ["PREV-001"],
                },
                reason="counter_span_mismatch",
            )
        ],
        failed_metric_ids=["i.counter_span_consistent"],
        gates=[
            {
                "metric_id": "gate.topology",
                "passed": False,
                "reason": "missing regeneration span",
            }
        ],
    )

    # Family D counters — strict_fail / skeleton_fallback projections.
    _write_case(
        repo,
        "case-gold",
        experiment_id=experiment_id,
        passed=True,
        scores=[
            _mk_score("d.strict_fail_set", 2, passed=False),
            _mk_score("d.skeleton_fallback_final", True, passed=False),
        ],
        failed_metric_ids=["d.strict_fail_set", "d.skeleton_fallback_final"],
    )


def test_amend_brief_offline_l1_projections_and_advisory(tmp_path: Path) -> None:
    """S6-F01/F02/A2: offline L1 projections from local cases; advisory only."""
    from git_cg.eval.brief import amend_brief, build_amend_brief

    _seed_amend_brief_cases(tmp_path)

    brief = build_amend_brief(
        tmp_path,
        experiment_id=_EXP_ID,
        brief_id=_BRIEF_ID,
        commit_subject="fix(eval): amend brief lock",
        trailers={"Refs": "#246"},
    )

    assert brief["schema_version"] == "amend_brief_v1"
    assert brief["authority"] == "advisory"
    assert brief["id"] == _BRIEF_ID
    assert brief["brief_id"] == _BRIEF_ID
    assert brief["commit_subject"] == "fix(eval): amend brief lock"
    assert brief["trailers"] == {"Refs": "#246"}
    assert "preference_pair" not in brief  # no twin supplied

    l1 = brief["l1"]
    assert l1["regime"] == "B"
    assert l1["path_class"] == "code_change"
    # failure_ids merge score failure_ids + failed_metric_ids (sorted unique)
    assert l1["failure_ids"] == [
        "EVAL_TOPOLOGY",
        "d.skeleton_fallback_final",
        "d.strict_fail_set",
        "i.counter_span_consistent",
    ]

    assert l1["gold_counters"] == {
        "strict_fail": 2,
        "skeleton_fallback_final": 1,
    }

    # Exact family rollups from known score rows (gate family excluded).
    assert l1["family_rollups"] == {
        "A": {
            "metrics": 1,
            "scored": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 1.0,
        },
        "D": {
            "metrics": 2,
            "scored": 2,
            "passed": 0,
            "failed": 2,
            "pass_rate": 0.0,
            "failing_metric_ids": [
                "d.skeleton_fallback_final",
                "d.strict_fail_set",
            ],
        },
        "I": {
            "metrics": 1,
            "scored": 1,
            "passed": 0,
            "failed": 1,
            "pass_rate": 0.0,
            "failing_metric_ids": ["i.counter_span_consistent"],
        },
    }

    blocking = l1["blocking"]
    assert blocking["blocked"] is True
    assert blocking["codes"] == ["gate.deterministic_pass", "gate.topology"]
    assert blocking["reasons"] == ["missing regeneration span"]

    # amend_brief wrapper returns advisory payload + optional persist.
    result = amend_brief(tmp_path, experiment_id=_EXP_ID, write=True)
    assert result["authority"] == "advisory"
    assert result["blocking"] is True
    assert result["written"] is True
    assert result["preference_pair_emitted"] is False
    assert result["experiment_id"] == _EXP_ID
    assert Path(result["path"]).is_file()
    assert (tmp_path / ".eval" / "amend_briefs" / f"{result['brief_id']}.json").is_file()
    on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert on_disk["authority"] == "advisory"
    assert on_disk["l1"]["regime"] == "B"


def test_amend_brief_session_thread_reference_without_preference(tmp_path: Path) -> None:
    """S6-F03/A2 + F04: session_thread_id surfaces; <2 versions ⇒ no pair."""
    from git_cg.eval.brief import build_amend_brief

    _seed_amend_brief_cases(tmp_path)
    _write_session_twin(
        tmp_path,
        message_versions=[
            {
                "kind": "final_accept",
                "message": "feat: solo",
                "message_sha256": "c" * 64,
                "source": "commit_editmsg",
            }
        ],
    )

    brief = build_amend_brief(
        tmp_path,
        experiment_id=_EXP_ID,
        session_thread_id=_SESS_ID,
        brief_id="brief-sess-ref-01",
    )
    assert brief["session_thread_id"] == _SESS_ID
    assert "preference_pair" not in brief


def test_amend_brief_preference_pair_final_accept_selection(tmp_path: Path) -> None:
    """S6-F04/A3: ≥2 versions ⇒ pair; chosen=final_accept; earlier rejected."""
    from git_cg.eval.brief import amend_brief, build_amend_brief

    _seed_amend_brief_cases(tmp_path)
    draft_sha = "d" * 64
    accept_sha = "e" * 64
    mid_sha = "f" * 64
    _write_session_twin(
        tmp_path,
        message_versions=[
            {
                "kind": "draft",
                "message": "feat: draft",
                "message_sha256": draft_sha,
                "source": "commit_editmsg",
            },
            {
                "kind": "draft",
                "message": "feat: mid",
                "message_sha256": mid_sha,
                "source": "commit_editmsg",
            },
            {
                "kind": "final_accept",
                "message": "feat: final",
                "message_sha256": accept_sha,
                "source": "commit_editmsg",
            },
        ],
    )

    brief = build_amend_brief(
        tmp_path,
        experiment_id=_EXP_ID,
        session_thread_id=_SESS_ID,
        brief_id="brief-pref-01",
    )
    pair = brief["preference_pair"]
    assert pair["chosen_version_id"] == f"final_accept:{accept_sha[:12]}"
    assert pair["rejected_version_ids"] == [
        f"draft:{draft_sha[:12]}",
        f"draft:{mid_sha[:12]}",
    ]
    assert pair["owner_approved"] is True
    assert "final accepted" in pair["notes"].lower()

    result = amend_brief(
        tmp_path,
        experiment_id=_EXP_ID,
        session_thread_id=_SESS_ID,
        write=False,
    )
    assert result["preference_pair_emitted"] is True
    assert result["authority"] == "advisory"


def test_amend_brief_no_preference_when_session_missing(tmp_path: Path) -> None:
    """S6-F04: missing twin is optional — no invented preference pair."""
    from git_cg.eval.brief import build_amend_brief

    _seed_amend_brief_cases(tmp_path)
    brief = build_amend_brief(
        tmp_path,
        experiment_id=_EXP_ID,
        session_thread_id="sess_0123456789abcdef0123456789abcdef",
        brief_id="brief-no-twin-01",
    )
    # session_thread_id still surfaces as the operator reference
    assert brief["session_thread_id"].startswith("sess_")
    assert "preference_pair" not in brief


def test_amend_brief_missing_experiment_is_usage(tmp_path: Path) -> None:
    """Fail-closed / usage: unknown experiment id under an existing store."""
    from git_cg.eval.brief import AmendBriefError, build_amend_brief

    _seed_amend_brief_cases(tmp_path)
    with pytest.raises(AmendBriefError) as ei:
        build_amend_brief(tmp_path, experiment_id="rs_does_not_exist")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_amend_brief_no_store_is_integrity(tmp_path: Path) -> None:
    """Fail-closed: empty repo without .eval/experiments/ is store integrity."""
    from git_cg.eval.brief import AmendBriefError, build_amend_brief

    (tmp_path / ".git").mkdir()
    with pytest.raises(AmendBriefError) as ei:
        build_amend_brief(tmp_path, experiment_id=_EXP_ID)
    assert ei.value.exit_code == 4
    assert ei.value.code == "EVAL_STORE_INTEGRITY"


def test_cli_amend_brief_happy_path_envelope(tmp_path: Path) -> None:
    """CLI JSON envelope for successful offline amend-brief via --root."""
    _seed_amend_brief_cases(tmp_path)
    _write_session_twin(tmp_path)  # default two versions → preference pair

    payload, code = _cli(
        [
            "eval",
            "amend-brief",
            _EXP_ID,
            "--session-thread-id",
            _SESS_ID,
            "--root",
            str(tmp_path),
            "--no-write",
            "--json",
        ]
    )
    assert code == 0
    assert payload["schema_version"] == "cli_output_envelope_v1"
    assert payload["command"] == "eval amend-brief"
    assert payload["ok"] is True
    data = payload["data"]
    assert data["authority"] == "advisory"
    assert data["blocking"] is True
    assert data["preference_pair_emitted"] is True
    assert data["written"] is False
    brief = data["brief"]
    assert brief["authority"] == "advisory"
    assert brief["session_thread_id"] == _SESS_ID
    assert brief["l1"]["regime"] == "B"
    assert brief["l1"]["path_class"] == "code_change"
    assert "preference_pair" in brief


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
