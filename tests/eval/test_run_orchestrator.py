"""Suite run orchestrator mode tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.checkpoint_store import build_checkpoint_record, load_checkpoint, write_checkpoint
from git_cg.eval.compat import compute_compat_hash
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.run_orchestrator import RunOrchestratorError, RunRequest, run_evaluation
from git_cg.eval.scoring.runner import prepare_suite_cases

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"


def _req(**kwargs):
    base = dict(
        suite_id="cm-eval-fixtures-core",
        fixture_root=FIXTURE_ROOT,
        keep_last=10,
        keep_checkpoint=True,
        offline=True,
    )
    base.update(kwargs)
    return RunRequest(**base)


def test_fresh_suite_run_writes_checkpoint_and_case_scores(tmp_path: Path) -> None:
    result = run_evaluation(_req(mode="fresh_suite_run", repo_root=tmp_path, case_ids=("seed-v1-valid-fixture",)))
    assert result.mode == "fresh_suite_run"
    assert result.experiment_id
    assert result.checkpoint_id
    assert result.compat_hash
    assert "seed-v1-valid-fixture" in result.completed_case_ids
    assert result.pending_case_ids == []
    case_path = tmp_path / ".eval" / "experiments" / result.experiment_id / "cases"
    assert any(case_path.glob("*.json"))
    exp_path = tmp_path / ".eval" / "experiments" / result.experiment_id / "experiment.json"
    exp = json.loads(exp_path.read_text(encoding="utf-8"))
    assert exp["resume_mode"] == "fresh_suite_run"
    assert exp["compat_hash"] == result.compat_hash
    ckpt = load_checkpoint(tmp_path, result.checkpoint_id)
    assert ckpt["compat_hash"] == result.compat_hash
    assert "seed-v1-valid-fixture" in ckpt["completed_case_ids"]


def test_resume_compat_mismatch_exit_3_preserves_bytes(tmp_path: Path) -> None:
    # Seed a checkpoint with a wrong hash.
    prepared = prepare_suite_cases("cm-eval-fixtures-core", fixture_root=FIXTURE_ROOT)
    live = compute_compat_hash(
        schema_pack_pin=schema_pack_pin(),
        metric_catalog_pin=metric_catalog_pin(),
        suite_id=prepared.suite_id,
        snapshot_hash=prepared.suite_snapshot_pin,
        gold_mode="strict",
        network_policy="offline_required",
        judge_pack_pin_or_none=None,
    )
    wrong = "f" * 64
    assert wrong != live
    rec = build_checkpoint_record(
        checkpoint_id="ckpt-mismatch",
        experiment_id="exp-mismatch",
        compat_hash=wrong,
        completed_case_ids=[],
        pending_case_ids=["seed-v1-valid-fixture"],
        mode="resume_missing",
        suite_id=prepared.suite_id,
        snapshot_id=prepared.suite_snapshot_pin,
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    path = write_checkpoint(tmp_path, rec, status="running")
    before = path.read_bytes()
    with pytest.raises(RunOrchestratorError) as ei:
        run_evaluation(
            _req(
                mode="resume_missing",
                repo_root=tmp_path,
                checkpoint_id="ckpt-mismatch",
            )
        )
    err = ei.value
    assert err.exit_code == 3
    assert err.code == "EVAL_COMPAT_HASH_MISMATCH"
    assert path.read_bytes() == before


def test_resume_missing_scores_only_pending(tmp_path: Path) -> None:
    first = run_evaluation(
        _req(
            mode="fresh_suite_run",
            repo_root=tmp_path,
            case_ids=("seed-v1-valid-fixture", "seed-b1-session12-regime-b"),
            keep_checkpoint=True,
        )
    )
    # Manually mark one case pending again to simulate partial progress.
    ckpt = load_checkpoint(tmp_path, first.checkpoint_id)
    # Build a mid-run checkpoint: one done, one pending.
    mid = build_checkpoint_record(
        checkpoint_id="ckpt-mid",
        experiment_id=first.experiment_id,
        compat_hash=first.compat_hash,
        completed_case_ids=["seed-v1-valid-fixture"],
        pending_case_ids=["seed-b1-session12-regime-b"],
        mode="resume_missing",
        suite_id=first.suite_id,
        snapshot_id=ckpt.get("snapshot_id"),
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
    )
    write_checkpoint(tmp_path, mid, status="running")
    resumed = run_evaluation(
        _req(
            mode="resume_missing",
            repo_root=tmp_path,
            checkpoint_id="ckpt-mid",
            keep_checkpoint=True,
        )
    )
    assert resumed.experiment_id == first.experiment_id
    assert "seed-b1-session12-regime-b" in resumed.completed_case_ids
    assert resumed.pending_case_ids == []


def test_recompute_mints_child_and_preserves_parent(tmp_path: Path) -> None:
    parent = run_evaluation(
        _req(
            mode="fresh_suite_run",
            repo_root=tmp_path,
            case_ids=("seed-v1-valid-fixture",),
            keep_checkpoint=True,
        )
    )
    parent_ckpt = parent.checkpoint_id
    parent_exp = tmp_path / ".eval" / "experiments" / parent.experiment_id / "experiment.json"
    parent_bytes = parent_exp.read_bytes()
    child = run_evaluation(
        _req(
            mode="recompute_scores",
            repo_root=tmp_path,
            experiment_id=parent.experiment_id,
            case_ids=("seed-v1-valid-fixture",),
            keep_checkpoint=True,
        )
    )
    assert child.experiment_id != parent.experiment_id
    assert child.parent_experiment_id == parent.experiment_id
    assert child.checkpoint_id != parent_ckpt
    assert parent_exp.read_bytes() == parent_bytes
    # parent checkpoint still loadable
    load_checkpoint(tmp_path, parent_ckpt)
    child_exp = json.loads(
        (tmp_path / ".eval" / "experiments" / child.experiment_id / "experiment.json").read_text(encoding="utf-8")
    )
    assert child_exp["meta"]["parent_experiment_id"] == parent.experiment_id
    assert child_exp["resume_mode"] == "recompute_scores"


def test_export_only_no_checkpoint_no_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded = run_evaluation(
        _req(
            mode="fresh_suite_run",
            repo_root=tmp_path,
            case_ids=("seed-v1-valid-fixture",),
            keep_checkpoint=True,
        )
    )
    calls: list[str] = []

    def boom(*_a, **_k):  # pragma: no cover - must not be called
        calls.append("score")
        raise AssertionError("score_bundle must not run in export_only")

    monkeypatch.setattr("git_cg.eval.run_orchestrator.score_bundle", boom)
    out = run_evaluation(
        _req(
            mode="export_only",
            repo_root=tmp_path,
            experiment_id=seeded.experiment_id,
        )
    )
    assert calls == []
    assert out.checkpoint_id is None
    assert out.mode == "export_only"
    assert "seed-v1-valid-fixture" in out.completed_case_ids


def test_replay_generation_refused_by_default(tmp_path: Path) -> None:
    with pytest.raises(RunOrchestratorError) as ei:
        run_evaluation(_req(mode="replay_generation", repo_root=tmp_path))
    assert ei.value.exit_code == 2


def test_recompute_missing_parent_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RunOrchestratorError) as ei:
        run_evaluation(
            _req(
                mode="recompute_scores",
                repo_root=tmp_path,
                experiment_id="exp-does-not-exist",
                case_ids=("seed-v1-valid-fixture",),
            )
        )
    err = ei.value
    assert err.exit_code == 4
    assert err.code == "EVAL_EVIDENCE_MISSING"


def test_recompute_score_history_append_only(tmp_path: Path) -> None:
    parent = run_evaluation(
        _req(
            mode="fresh_suite_run",
            repo_root=tmp_path,
            case_ids=("seed-v1-valid-fixture",),
            keep_checkpoint=True,
        )
    )
    parent_case = tmp_path / ".eval" / "experiments" / parent.experiment_id / "cases"
    parent_case_files = sorted(parent_case.glob("*.json"))
    assert parent_case_files
    parent_case_bytes = {p.name: p.read_bytes() for p in parent_case_files}

    child = run_evaluation(
        _req(
            mode="recompute_scores",
            repo_root=tmp_path,
            experiment_id=parent.experiment_id,
            case_ids=("seed-v1-valid-fixture",),
            keep_checkpoint=True,
        )
    )
    # Parent case artifacts untouched (append-only).
    for name, before in parent_case_bytes.items():
        assert (parent_case / name).read_bytes() == before

    child_exp = json.loads(
        (tmp_path / ".eval" / "experiments" / child.experiment_id / "experiment.json").read_text(encoding="utf-8")
    )
    history = child_exp["meta"]["score_history"]
    assert isinstance(history, list)
    assert history[-1]["experiment_id"] == child.experiment_id
    assert any(h.get("experiment_id") == parent.experiment_id for h in history)
    assert child_exp["meta"]["score_history_policy"] == "append_only"
    # Child has its own case scores under a different experiment id.
    child_cases = tmp_path / ".eval" / "experiments" / child.experiment_id / "cases"
    assert any(child_cases.glob("*.json"))


def test_b11_per_case_checkpoint_cadence_at_most_one_case_loss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Orchestrator checkpoints per case (≤1-case-loss on crash).

    After each successful case write, completed/pending checkpoint cursors advance
    so a crash loses at most the in-flight case — never the whole scored prefix.
    """
    from git_cg.eval import run_orchestrator as orch

    persist_calls: list[tuple[tuple[str, ...], tuple[str, ...], str]] = []
    real_persist = orch._persist_checkpoint

    def spy_persist(repo, **kwargs):  # type: ignore[no-untyped-def]
        completed = tuple(kwargs.get("completed") or [])
        pending = tuple(kwargs.get("pending") or [])
        status = str(kwargs.get("status") or "")
        persist_calls.append((completed, pending, status))
        return real_persist(repo, **kwargs)

    monkeypatch.setattr(orch, "_persist_checkpoint", spy_persist)

    case_ids = ("seed-v1-valid-fixture", "seed-b1-session12-regime-b")
    result = run_evaluation(
        _req(
            mode="fresh_suite_run",
            repo_root=tmp_path,
            case_ids=case_ids,
            keep_checkpoint=True,
        )
    )
    assert result.pending_case_ids == []
    assert set(result.completed_case_ids) >= set(case_ids)

    # Initial running checkpoint (before any case) + one persist after each case + final.
    running = [c for c in persist_calls if c[2] == "running"]
    assert len(running) >= 1 + len(case_ids)

    # After first case completes, checkpoint must already record that case and
    # keep the second case pending (proves per-case cadence, not end-only flush).
    mid = None
    for completed, pending, status in running:
        if "seed-v1-valid-fixture" in completed and "seed-b1-session12-regime-b" in pending:
            mid = (completed, pending, status)
            break
    assert mid is not None, f"missing mid-run checkpoint cadence; saw={running!r}"

    # Final completed set includes both cases with empty pending.
    final_running_or_done = persist_calls[-1]
    assert "seed-v1-valid-fixture" in final_running_or_done[0]
    assert "seed-b1-session12-regime-b" in final_running_or_done[0]


def test_failed_run_persists_terminal_status_durably(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Failure path must leave durable terminal status on the authoritative payload."""
    from git_cg.eval import run_orchestrator as orch

    real_score = orch.score_bundle
    calls = {"n": 0}

    def boom(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            # Let the first case succeed so a checkpoint exists, then fail.
            return real_score(*args, **kwargs)
        raise RuntimeError("injected suite failure")

    monkeypatch.setattr(orch, "score_bundle", boom)
    with pytest.raises(RunOrchestratorError) as ei:
        run_evaluation(
            _req(
                mode="fresh_suite_run",
                repo_root=tmp_path,
                case_ids=("seed-v1-valid-fixture", "seed-b1-session12-regime-b"),
                keep_checkpoint=True,
            )
        )
    assert ei.value.code == "EVAL_SUITE_FAIL"

    # Find the checkpoint written for this run.
    ckpt_dir = tmp_path / ".eval" / "checkpoints"
    files = list(ckpt_dir.glob("*.json"))
    assert files, "expected a durable checkpoint after failure"
    # Prefer the one marked failed.
    failed = None
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("status") == "failed":
            failed = raw
            break
    assert failed is not None, f"no failed checkpoint among {[p.name for p in files]}"
    assert "started_at" in failed
    assert failed["started_at"].endswith("Z")

    # Delete index and confirm reconstruction still reports failed.
    idx_dir = tmp_path / ".eval" / "index" / "checkpoints"
    for idx in idx_dir.glob("*.json"):
        idx.unlink()
    from git_cg.eval.checkpoint_store import list_index_rows

    rows = list_index_rows(tmp_path, suite_id=failed.get("suite_id") or "cm-eval-fixtures-core")
    by_id = {r.checkpoint_id: r for r in rows}
    assert failed["checkpoint_id"] in by_id
    assert by_id[failed["checkpoint_id"]].status == "failed"


def test_rotated_schema_pack_makes_legacy_checkpoint_resume_terminal(tmp_path: Path) -> None:
    """Legacy schema-pack checkpoints must fail closed on resume with recovery_hint guidance."""
    from git_cg.eval.compat import recovery_hint

    prepared = prepare_suite_cases("cm-eval-fixtures-core", fixture_root=FIXTURE_ROOT)
    # Simulate a pre-rotation checkpoint: valid shape, wrong/stale compat_hash.
    stale_hash = "a" * 64
    rec = build_checkpoint_record(
        checkpoint_id="ckpt-legacy-schema-pack",
        experiment_id="exp-legacy-schema-pack",
        compat_hash=stale_hash,
        completed_case_ids=[],
        pending_case_ids=["seed-v1-valid-fixture"],
        mode="resume_missing",
        suite_id=prepared.suite_id,
        snapshot_id=prepared.suite_snapshot_pin,
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
        status="running",
        started_at="2026-08-20T12:00:00Z",
    )
    path = write_checkpoint(tmp_path, rec, status="running", started_at="2026-08-20T12:00:00Z")
    before = path.read_bytes()

    with pytest.raises(RunOrchestratorError) as ei:
        run_evaluation(
            _req(
                mode="resume_missing",
                repo_root=tmp_path,
                checkpoint_id="ckpt-legacy-schema-pack",
            )
        )
    err = ei.value
    assert err.exit_code == 3
    assert err.code == "EVAL_COMPAT_HASH_MISMATCH"
    assert path.read_bytes() == before
    hint = err.hint or ""
    expected_hint = recovery_hint(checkpoint_id="ckpt-legacy-schema-pack")
    assert "git-cg eval run" in hint
    assert "recompute-scores" in hint
    assert hint == expected_hint or "Checkpoint preserved read-only" in hint


def test_finalize_gc_protects_live_checkpoint_from_reclamation(tmp_path: Path) -> None:
    """Non-completed live checkpoint stays protected when reclaim is enabled."""
    from git_cg.eval.checkpoint_store import list_checkpoint_ids
    from git_cg.eval.run_orchestrator import _finalize_gc

    suite = "cm-eval-fixtures-core"
    old = "2026-08-01T00:00:00Z"

    stale = build_checkpoint_record(
        checkpoint_id="ckpt-foreign-stale",
        experiment_id="exp-foreign-stale",
        compat_hash="a" * 64,
        completed_case_ids=[],
        pending_case_ids=["c1"],
        mode="fresh_suite_run",
        suite_id=suite,
        snapshot_id="snap-1",
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
        status="running",
        started_at=old,
    )
    write_checkpoint(tmp_path, stale, status="running", started_at=old)

    live_id = "ckpt-live-run"
    live = build_checkpoint_record(
        checkpoint_id=live_id,
        experiment_id="exp-live-run",
        compat_hash="b" * 64,
        completed_case_ids=[],
        pending_case_ids=["c1"],
        mode="fresh_suite_run",
        suite_id=suite,
        snapshot_id="snap-1",
        schema_pack=schema_pack_pin(),
        metric_catalog=metric_catalog_pin(),
        status="running",
        started_at=old,
    )
    write_checkpoint(tmp_path, live, status="running", started_at=old)

    pruned = _finalize_gc(
        tmp_path,
        suite_id=suite,
        keep_last=10,
        keep_checkpoint=False,
        checkpoint_id=live_id,
        status="running",
        stale_running_after_seconds=3600,
    )
    ids = set(list_checkpoint_ids(tmp_path))
    assert live_id in ids
    assert "ckpt-foreign-stale" not in ids
    assert "ckpt-foreign-stale" in pruned
    assert live_id not in pruned
