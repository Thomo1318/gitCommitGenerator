"""Focused S6 foundation patch-coverage locks (Issue #246 / codecov patch 80%).

Targets fail-closed and branch arms that happy-path S6 suites leave cold:
brief loaders / projections, CLI run-result emit, doctor pin/Opik arms,
orchestrator recompute evidence, replay/promote path wrappers, train-export
IO tails, api_map write/print entrypoints, and envelope sketch hygiene.

Production behaviour is exercised as-is — no product logic is relaxed for
coverage. Network-free and offline-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from git_cg.eval.binding.paths import LayerAPathError

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _git_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir(exist_ok=True)
    return tmp_path


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# api_map / envelope_sketches residuals (cheap, high density)
# ---------------------------------------------------------------------------


def test_click_help_prefers_short_and_strips_detail_split() -> None:
    """Lock _click_help short_help preference and brief/detail split arms.

    Codecov patch gate requires coverage of the dual-axis help truncation
    path introduced for operator API map blurbs.
    """
    from types import SimpleNamespace

    from git_cg.eval.api_map import _click_help
    from git_cg.eval.cli import _HELP_DETAIL_MARKER

    short_only = SimpleNamespace(short_help="  brief short  help ", help="ignored long body")
    assert _click_help(short_only) == "brief short help"

    marker_split = SimpleNamespace(
        short_help=None,
        help=f"Operator brief line.\n{_HELP_DETAIL_MARKER}\nDETAIL should not appear",
    )
    assert _click_help(marker_split) == "Operator brief line."

    formfeed_split = SimpleNamespace(
        short_help="",
        help="First brief paragraph.\fHidden form-feed detail",
    )
    assert _click_help(formfeed_split) == "First brief paragraph."

    plain = SimpleNamespace(short_help=None, help="  multi\n  line   help  ")
    assert _click_help(plain) == "multi line help"

    empty = SimpleNamespace(short_help=None, help=None)
    assert _click_help(empty) == ""


def test_api_map_write_and_main_print_write_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from git_cg.eval.api_map import check_map, main, write_map

    target = tmp_path / "nested" / "operator_api_map.md"
    written = write_map(target)
    assert written == target
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "operator" in text.lower() or "eval" in text

    assert main([]) == 0  # default: print map to stdout
    printed = capsys.readouterr().out
    assert printed
    assert "eval" in printed.lower() or "Operator" in printed or "command" in printed.lower()

    assert main(["--write", "--path", str(target)]) == 0
    out = capsys.readouterr().out
    assert "wrote" in out

    missing = tmp_path / "nope.md"
    ok, msg = check_map(missing)
    assert ok is False
    assert "missing" in msg.lower()


def test_envelope_sketch_all_keys_and_command_mismatch() -> None:
    from git_cg.eval.envelope_sketches import (
        ENVELOPE_DATA_SKETCHES,
        DataSketch,
        validate_sketch_registry,
    )

    sample = next(iter(ENVELOPE_DATA_SKETCHES.values()))
    keys = sample.allowed_keys
    assert isinstance(keys, frozenset)
    assert set(sample.required_keys).issubset(keys)

    # Command field mismatch fails closed (registry must still cover the minimum set).
    bad = dict(ENVELOPE_DATA_SKETCHES)
    bad["run"] = DataSketch(
        command="not-run",
        required_keys=sample.required_keys,
        optional_keys=sample.optional_keys,
        enums=dict(sample.enums or {}),
        notes=sample.notes,
    )
    ok, msg = validate_sketch_registry(bad)
    assert ok is False
    assert "mismatch" in msg.lower()


# ---------------------------------------------------------------------------
# brief.py — integrity wrappers, projections, attachments, bundle load
# ---------------------------------------------------------------------------


def test_brief_load_json_os_decode_and_non_object(tmp_path: Path) -> None:
    from git_cg.eval import brief as brief_mod
    from git_cg.eval.brief import AmendBriefError

    missing = tmp_path / "gone.json"
    with pytest.raises(AmendBriefError) as ei:
        brief_mod._load_json(missing)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    assert ei.value.exit_code == 4

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not-json", encoding="utf-8")
    with pytest.raises(AmendBriefError) as ei:
        brief_mod._load_json(bad_json)
    assert "not valid JSON" in str(ei.value)

    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(AmendBriefError) as ei:
        brief_mod._load_json(arr)
    assert "JSON object" in str(ei.value)


def test_brief_path_wrappers_map_layer_a_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import brief as brief_mod
    from git_cg.eval.binding import paths as binding_paths
    from git_cg.eval.brief import AmendBriefError

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise LayerAPathError("path escaped store")

    monkeypatch.setattr(binding_paths, "amend_briefs_dir", boom)
    monkeypatch.setattr(binding_paths, "dogfood_dir", boom)
    monkeypatch.setattr(binding_paths, "atomic_write_json", boom)

    with pytest.raises(AmendBriefError) as ei:
        brief_mod._briefs_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    with pytest.raises(AmendBriefError) as ei:
        brief_mod._dogfood_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    with pytest.raises(AmendBriefError) as ei:
        brief_mod._atomic_write(tmp_path / "x.json", {"a": 1})
    assert ei.value.code == "EVAL_STORE_INTEGRITY"


def test_brief_regime_path_class_bundle_and_case_fallbacks() -> None:
    from git_cg.eval import brief as brief_mod

    assert brief_mod._regime([], None) == "unknown"
    assert brief_mod._regime([], {"regime": "a"}) == "A"
    assert brief_mod._regime([], {"meta": {"regime": "B"}}) == "B"

    cases = [
        {
            "scores": [
                {
                    "metric_id": "i.x",
                    "evidence": {"diag_fingerprint_inputs": {"regime": "A"}},
                }
            ]
        }
    ]
    assert brief_mod._regime(cases, None) == "A"

    assert brief_mod._path_class([], None) == "unknown"
    assert brief_mod._path_class([], {"path_class_gate": "docs"}) == "docs"
    assert brief_mod._path_class([], {"path_class": "tests"}) == "tests"
    assert (
        brief_mod._path_class(
            [],
            {"generation_task_input": {"path_class_gate": "mixed"}},
        )
        == "mixed"
    )
    cases2 = [
        {
            "scores": [
                {
                    "metric_id": "i.x",
                    "evidence": {"diag_fingerprint_inputs": {"path_class_key": "code"}},
                }
            ]
        }
    ]
    assert brief_mod._path_class(cases2, None) == "code"


def test_brief_lane_c_attachments_filters_and_bounds(tmp_path: Path) -> None:
    from git_cg.eval import brief as brief_mod
    from git_cg.eval.binding.paths import dogfood_dir

    repo = _git_repo(tmp_path)
    root = dogfood_dir(repo)
    root.mkdir(parents=True, exist_ok=True)

    _write_json(
        root / "ok.json",
        {
            "schema_version": "dogfood_attachment_v1",
            "run_id": "run-1",
            "judge_id": "j1",
            "pin_ref": "pin@1",
            "mode": "shadow",
            "score": 0.5,
            "polarity": "higher_better",
            "rationale_short": "fine",
        },
    )
    _write_json(root / "wrong_schema.json", {"schema_version": "other", "run_id": "x"})
    _write_json(root / "broken.json", "{nope")

    # last_n <= 0 → empty even when files exist
    assert brief_mod._lane_c_attachments(repo, last_n=0) == []

    rows = brief_mod._lane_c_attachments(repo, last_n=5)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["authority"] == "advisory"
    assert rows[0]["score"] == 0.5
    assert rows[0]["polarity"] == "higher_better"


def test_brief_load_bundle_validation_and_happy(tmp_path: Path) -> None:
    from git_cg.eval import brief as brief_mod
    from git_cg.eval.binding.paths import acceptpath_bundles_dir
    from git_cg.eval.brief import AmendBriefError

    repo = _git_repo(tmp_path)
    assert brief_mod._load_bundle(repo, None) is None

    with pytest.raises(AmendBriefError) as ei:
        brief_mod._load_bundle(repo, "bad id!")
    assert ei.value.code == "EVAL_USAGE"

    with pytest.raises(AmendBriefError) as ei:
        brief_mod._load_bundle(repo, "bundle-missing")
    assert ei.value.code == "EVAL_USAGE"

    root = acceptpath_bundles_dir(repo)
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "bundle-ok.json", {"schema_version": "ape_bundle_v1", "id": "bundle-ok"})
    obj = brief_mod._load_bundle(repo, "bundle-ok")
    assert obj is not None
    assert obj["id"] == "bundle-ok"


def test_brief_resolve_case_rows_edges(tmp_path: Path) -> None:
    from git_cg.eval import brief as brief_mod
    from git_cg.eval.binding.paths import experiments_dir
    from git_cg.eval.brief import AmendBriefError

    repo = _git_repo(tmp_path)

    # empty experiments dir
    experiments_dir(repo).mkdir(parents=True, exist_ok=True)
    with pytest.raises(AmendBriefError) as ei:
        brief_mod._resolve_case_rows(repo, experiment_id=None, case_id=None)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    exp = "rs_cov_exp"
    exp_dir = experiments_dir(repo) / exp
    exp_dir.mkdir(parents=True, exist_ok=True)
    _write_json(exp_dir / "experiment.json", {"schema_version": "experiment_v1", "id": exp})
    # no cases dir → empty list
    got_exp, rows = brief_mod._resolve_case_rows(repo, experiment_id=exp, case_id=None)
    assert got_exp == exp
    assert rows == []

    cases = exp_dir / "cases"
    cases.mkdir()
    _write_json(
        cases / "c1.json",
        {
            "schema_version": "local_case_score_v0",
            "case_id": "c1",
            "deterministic_pass": True,
            "scores": [],
            "gates": [],
            "failed_metric_ids": [],
        },
    )
    _write_json(
        cases / "bad_schema.json",
        {"schema_version": "other", "case_id": "bad"},
    )
    with pytest.raises(AmendBriefError) as ei:
        brief_mod._resolve_case_rows(repo, experiment_id=exp, case_id=None)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    # remove bad schema file; filter missing case_id
    (cases / "bad_schema.json").unlink()
    with pytest.raises(AmendBriefError) as ei:
        brief_mod._resolve_case_rows(repo, experiment_id=exp, case_id="nope")
    assert ei.value.code == "EVAL_USAGE"


def test_brief_build_with_doctor_notes_bundle_and_lane_c(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.binding.paths import acceptpath_bundles_dir, dogfood_dir, experiments_dir
    from git_cg.eval.brief import AmendBriefError, build_amend_brief

    pin = "schema_pack_v1@" + ("a" * 64)
    cat = "metric_catalog_v1@" + ("b" * 64)
    monkeypatch.setattr("git_cg.eval.pins.schema_pack_pin", lambda: pin)
    monkeypatch.setattr("git_cg.eval.pins.metric_catalog_pin", lambda: cat)

    repo = _git_repo(tmp_path)
    exp = "rs_brief_cov"
    exp_dir = experiments_dir(repo) / exp
    exp_dir.mkdir(parents=True)
    _write_json(exp_dir / "experiment.json", {"schema_version": "experiment_v1", "id": exp})
    cases = exp_dir / "cases"
    cases.mkdir()
    _write_json(
        cases / "c1.json",
        {
            "schema_version": "local_case_score_v0",
            "case_id": "c1",
            "deterministic_pass": True,
            "scores": [],
            "gates": [],
            "failed_metric_ids": [],
            "experiment_id": exp,
            "suite_snapshot_pin": "suite_snapshot_v1@" + ("a" * 64),
            "evaluator_errors": [],
        },
    )

    bdir = acceptpath_bundles_dir(repo)
    bdir.mkdir(parents=True)
    _write_json(
        bdir / "b1.json",
        {
            "schema_version": "ape_bundle_v1",
            "id": "b1",
            "regime": "A",
            "path_class": "docs",
        },
    )

    ddir = dogfood_dir(repo)
    ddir.mkdir(parents=True)
    _write_json(
        ddir / "att.json",
        {
            "schema_version": "dogfood_attachment_v1",
            "run_id": "r1",
            "judge_id": "j",
            "mode": "off",
            "pin_ref": "prompt_pack_v1@" + ("c" * 64),
            "authority": "advisory",
        },
    )

    brief = build_amend_brief(
        repo,
        experiment_id=exp,
        case_id="c1",
        bundle_id="b1",
        include_doctor=True,
        doctor_report={
            "green": False,
            "checks": [{"check_id": "pins.x"}],
            "block_failures": ["pins.x"],
        },
        lane_c_last_n=3,
        notes="operator note",
        brief_id="brief-cov-01",
    )
    assert brief["l1"]["regime"] == "A"
    assert brief["l1"]["path_class"] == "docs"
    assert brief["doctor"]["green"] is False
    assert brief["doctor"]["check_ids"] == ["pins.x"]
    assert brief["notes"] == "operator note"
    assert brief["lane_c_attachments"]

    # invalid brief_id
    with pytest.raises(AmendBriefError) as ei:
        build_amend_brief(repo, experiment_id=exp, brief_id="bad id")
    assert ei.value.code == "EVAL_USAGE"

    # include_doctor without report → placeholder notes arm
    brief2 = build_amend_brief(
        repo,
        experiment_id=exp,
        include_doctor=True,
        brief_id="brief-cov-02",
    )
    assert brief2["doctor"]["notes"]


# ---------------------------------------------------------------------------
# cli.py — _emit_run_result dense branches
# ---------------------------------------------------------------------------


def test_cli_emit_run_result_error_and_success_arms(capsys: pytest.CaptureFixture[str]) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.run_orchestrator import CaseSummary, RunOrchestratorError, RunResult

    # Generic error → EVAL_SUITE_FAIL JSON
    with pytest.raises(typer.Exit) as ei:
        cli_mod._emit_run_result("eval run", as_json=True, error=RuntimeError("boom"))
    assert ei.value.exit_code == 1
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "EVAL_SUITE_FAIL"

    # Orchestrator error human path with hint
    with pytest.raises(typer.Exit) as ei:
        cli_mod._emit_run_result(
            "eval run",
            as_json=False,
            error=RunOrchestratorError("blocked", code="EVAL_COMPAT", exit_code=3, hint="reseed"),
        )
    assert ei.value.exit_code == 3
    err = capsys.readouterr().err
    assert "blocked" in err
    assert "reseed" in err

    # Success path human with case rows + checkpoint + pruned
    result = RunResult(
        status="completed",
        mode="fresh_suite_run",
        suite_id="suite",
        experiment_id="exp-1",
        parent_experiment_id="parent-1",
        checkpoint_id="ckpt-1",
        compat_hash="abc123def4567890",
        completed_case_ids=["c1"],
        pending_case_ids=[],
        case_results=[CaseSummary(case_id="c1", deterministic_pass=True, failed_metric_ids=[])],
        all_pass=True,
        keep_last=10,
        pruned_checkpoint_ids=["old-ckpt"],
        exit_code=0,
        notes="ok",
        triage_filter=["t1"],
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod._emit_run_result("eval run", as_json=False, result=result)
    assert ei.value.exit_code == 0
    human = capsys.readouterr()
    combined = human.out + human.err
    assert "status=completed" in combined
    assert "case c1" in combined
    assert "checkpoint=ckpt-1" in combined
    assert "pruned_checkpoints=1" in combined

    # JSON success
    with pytest.raises(typer.Exit) as ei:
        cli_mod._emit_run_result("eval run", as_json=True, result=result)
    assert ei.value.exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["data"]["experiment_id"] == "exp-1"
    assert payload["data"]["parent_experiment_id"] == "parent-1"
    assert payload["data"]["pruned_checkpoint_ids"] == ["old-ckpt"]

    # Type guard
    with pytest.raises(TypeError):
        cli_mod._emit_run_result("eval run", as_json=True, result={"nope": True})


# ---------------------------------------------------------------------------
# doctor.py — pin unreadable + opik doctor arms
# ---------------------------------------------------------------------------


def test_doctor_pin_unreadable_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import doctor as doctor_mod, pins

    repo = _git_repo(tmp_path)

    def boom_schema() -> str:
        raise RuntimeError("schema gone")

    def boom_catalog() -> str:
        raise RuntimeError("catalog gone")

    monkeypatch.setattr(pins, "schema_pack_pin", boom_schema)
    monkeypatch.setattr(pins, "metric_catalog_pin", boom_catalog)

    report = doctor_mod.run_local_doctor(repo_root=repo)
    ids = {c.check_id for c in report.checks}
    assert "pins.schema_pack_resolvable" in ids
    assert "pins.metric_catalog_resolvable" in ids
    assert report.green is False


def test_opik_doctor_config_error_and_queue_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import doctor as doctor_mod
    from git_cg.eval.mirror import config as mirror_config
    from git_cg.eval.mirror.config import OpikConfigError

    repo = _git_repo(tmp_path)

    def boom_config() -> Any:
        raise OpikConfigError("bad mode")

    monkeypatch.setattr(mirror_config, "resolve_opik_config", boom_config)
    report = doctor_mod.run_opik_doctor(repo_root=repo)
    assert report.exit_code == 2
    assert report.green is False
    assert any(c.check_id == "opik.config_resolved" for c in report.checks)

    # Happy config path with queue unreadable + failed rows
    cfg = SimpleNamespace(mode="off")
    monkeypatch.setattr(mirror_config, "resolve_opik_config", lambda: cfg)
    monkeypatch.setattr(mirror_config, "public_config_view", lambda _c: {"mode": "off"})
    monkeypatch.setattr(mirror_config, "operator_config_health", lambda _c: "ok")

    qdir = repo / ".eval" / "export_queue"
    qdir.mkdir(parents=True)
    (qdir / "bad.json").write_text("{nope", encoding="utf-8")
    _write_json(
        qdir / "failed.json",
        {
            "schema_version": "export_queue_item_v1",
            "id": "failed",
            "status": "failed",
            "last_error_class": "Timeout",
        },
    )

    report2 = doctor_mod.run_opik_doctor(repo_root=repo)
    assert report2.exit_code == 0
    assert isinstance(report2.extra.get("queue_counts"), dict)
    counts = report2.extra["queue_counts"]
    assert counts.get("failed") == 1
    assert counts.get("unreadable") == 1


# ---------------------------------------------------------------------------
# run_orchestrator — prior summaries + recompute evidence fallback
# ---------------------------------------------------------------------------


def test_orchestrator_prior_summaries_and_recompute_evidence(tmp_path: Path) -> None:
    from git_cg.eval import run_orchestrator as orch
    from git_cg.eval.binding.paths import acceptpath_bundles_dir, experiments_dir
    from git_cg.eval.run_orchestrator import RunOrchestratorError

    repo = _git_repo(tmp_path)
    exp = "parent-exp"
    cases = experiments_dir(repo) / exp / "cases"
    cases.mkdir(parents=True)
    _write_json(
        cases / "c1.json",
        {
            "case_id": "c1",
            "deterministic_pass": True,
            "failed_metric_ids": ["a.x"],
        },
    )
    (cases / "c2.json").write_text("{broken", encoding="utf-8")

    summaries = orch._load_prior_case_summaries(repo, exp, ["c1", "c2", "c3"])
    by_id = {s.case_id: s for s in summaries}
    assert by_id["c1"].deterministic_pass is True
    assert by_id["c1"].failed_metric_ids == ["a.x"]
    assert by_id["c2"].deterministic_pass is None  # unreadable
    assert by_id["c3"].deterministic_pass is None  # missing

    # Recompute evidence: parent missing → fail closed via helper dependency
    prepared = SimpleNamespace(encoded_pairs=[])
    # Ensure parent experiment record path exists for success-ish fallback path
    parent_dir = experiments_dir(repo) / exp
    _write_json(
        parent_dir / "experiment.json",
        {
            "schema_version": "experiment_v1",
            "id": exp,
            "experiment_name": exp,
            "lane": "suite",
            "git_sha": "deadbeef",
            "catalog_pin": "metric_catalog_v1@" + ("a" * 64),
            "schema_pack": "schema_pack_v1@" + ("b" * 64),
            "metric_catalog": "metric_catalog_v1@" + ("a" * 64),
            "meta": {"pins": {"project_lane": "suite", "environment": "local"}},
        },
    )

    # No fixtures + no acceptpath bundles → EVAL_EVIDENCE_MISSING
    with pytest.raises(RunOrchestratorError) as ei:
        orch._evidence_bundles_for_recompute(repo, prepared, parent_experiment_id=exp)
    assert ei.value.code == "EVAL_EVIDENCE_MISSING"

    # Accept-path fallback fills bundles
    root = acceptpath_bundles_dir(repo)
    root.mkdir(parents=True)
    _write_json(root / "live.json", {"case_id": "live-1", "schema_version": "ape_bundle_v1"})
    _write_json(root / "broken.json", "{nope")
    bundles, parent = orch._evidence_bundles_for_recompute(repo, prepared, parent_experiment_id=exp)
    assert "live-1" in bundles
    assert parent["id"] == exp

    # Fixture path short-circuit
    prepared2 = SimpleNamespace(encoded_pairs=[("fx-1", {"case_id": "fx-1"})])
    bundles2, _ = orch._evidence_bundles_for_recompute(repo, prepared2, parent_experiment_id=exp)
    assert bundles2 == {"fx-1": {"case_id": "fx-1"}}


# ---------------------------------------------------------------------------
# replay / promote integrity wrappers + harness/split helpers
# ---------------------------------------------------------------------------


def test_replay_path_wrappers_and_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import replay as replay_mod
    from git_cg.eval.binding import paths as binding_paths
    from git_cg.eval.replay import ReplayError

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise LayerAPathError("escaped")

    monkeypatch.setattr(binding_paths, "replays_dir", boom)
    monkeypatch.setattr(binding_paths, "acceptpath_bundles_dir", boom)
    monkeypatch.setattr(binding_paths, "atomic_write_json", boom)

    with pytest.raises(ReplayError) as ei:
        replay_mod._replays_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    with pytest.raises(ReplayError) as ei:
        replay_mod._acceptpath_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    with pytest.raises(ReplayError) as ei:
        replay_mod._atomic_write(tmp_path / "x.json", {"a": 1})
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    # load_json arms
    with pytest.raises(ReplayError):
        replay_mod._load_json(tmp_path / "missing.json")
    bad = tmp_path / "b.json"
    bad.write_text("not-json", encoding="utf-8")
    with pytest.raises(ReplayError):
        replay_mod._load_json(bad)
    arr = tmp_path / "a.json"
    arr.write_text("[1]", encoding="utf-8")
    with pytest.raises(ReplayError):
        replay_mod._load_json(arr)

    # harness version never raises
    ver = replay_mod._harness_version()
    assert isinstance(ver, str) and ver

    # split group extraction precedence
    assert replay_mod._extract_split_group({"meta": {"split_group_id": " sg1 "}}) == "sg1"
    assert replay_mod._extract_split_group({"split_group_id": "sg2"}) == "sg2"
    assert replay_mod._extract_split_group({"session_thread_id": "sess1"}) == "sg:sess1"
    assert replay_mod._extract_split_group({"case_id": "c1"}) == "sg:c1"
    assert replay_mod._extract_split_group({}) is None


def test_promote_path_wrappers_and_load_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import promote as promote_mod
    from git_cg.eval.binding import paths as binding_paths
    from git_cg.eval.promote import PromoteError

    def boom_index(*_args: object, **_kwargs: object) -> Path:
        raise LayerAPathError("escaped")

    monkeypatch.setattr(binding_paths, "index_dir", boom_index)
    monkeypatch.setattr(binding_paths, "acceptpath_bundles_dir", boom_index)
    monkeypatch.setattr(binding_paths, "atomic_write_json", boom_index)

    with pytest.raises(PromoteError) as ei:
        promote_mod._promotions_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    with pytest.raises(PromoteError) as ei:
        promote_mod._acceptpath_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    with pytest.raises(PromoteError) as ei:
        promote_mod._atomic_write(tmp_path / "x.json", {"a": 1})
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    with pytest.raises(PromoteError):
        promote_mod._load_json(tmp_path / "missing.json")
    bad = tmp_path / "b.json"
    bad.write_text("{bad", encoding="utf-8")
    with pytest.raises(PromoteError):
        promote_mod._load_json(bad)
    arr = tmp_path / "a.json"
    arr.write_text("[]", encoding="utf-8")
    with pytest.raises(PromoteError):
        promote_mod._load_json(arr)


def test_promote_destination_dir_and_split_scan(tmp_path: Path) -> None:
    from git_cg.eval import promote as promote_mod
    from git_cg.eval.promote import (
        DEST_FIXTURE_LANE_A,
        DEST_HARD_NEGATIVE,
        DEST_OBSERVABILITY_FIXTURE,
        DEST_PREFERENCE_PAIR,
        DEST_QUARANTINE,
        DEST_REJECT,
        PromoteError,
    )

    repo = _git_repo(tmp_path)

    # Touch each destination resolver arm
    for dest in (
        DEST_HARD_NEGATIVE,
        DEST_QUARANTINE,
        DEST_REJECT,
        DEST_PREFERENCE_PAIR,
        DEST_OBSERVABILITY_FIXTURE,
        DEST_FIXTURE_LANE_A,
    ):
        path = promote_mod._destination_dir(repo, dest)
        assert isinstance(path, Path)

    with pytest.raises(PromoteError) as ei:
        promote_mod._destination_dir(repo, "not-a-dest")
    assert ei.value.code == "EVAL_USAGE"

    # split contamination: accepted prior different destination
    root = promote_mod._promotions_dir(repo)
    root.mkdir(parents=True)
    _write_json(
        root / "p1.json",
        {
            "promotion_id": "p1",
            "split_group_id": "sg-x",
            "accepted": True,
            "destination": DEST_OBSERVABILITY_FIXTURE,
        },
    )
    _write_json(root / "broken.json", "{nope")
    conflicts = promote_mod._scan_split_contamination(
        repo,
        split_group_id="sg-x",
        destination=DEST_HARD_NEGATIVE,
        label="neg",
    )
    assert any("p1" in c for c in conflicts)


# ---------------------------------------------------------------------------
# train_export residuals
# ---------------------------------------------------------------------------


def test_train_export_path_wrappers_and_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import train_export as te
    from git_cg.eval.binding import paths as binding_paths
    from git_cg.eval.train_export import TrainExportError

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise LayerAPathError("escaped")

    monkeypatch.setattr(binding_paths, "train_export_dir", boom)
    monkeypatch.setattr(binding_paths, "antipattern_vault_dir", boom)
    monkeypatch.setattr(binding_paths, "atomic_write_json", boom)
    monkeypatch.setattr(binding_paths, "acceptpath_bundles_dir", boom)

    with pytest.raises(TrainExportError) as ei:
        te._train_export_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    with pytest.raises(TrainExportError) as ei:
        te._vault_dir(tmp_path)
    assert ei.value.code == "EVAL_STORE_INTEGRITY"
    with pytest.raises(TrainExportError) as ei:
        te._atomic_write(tmp_path / "x.json", {"a": 1})
    assert ei.value.code == "EVAL_STORE_INTEGRITY"

    with pytest.raises(TrainExportError):
        te._load_json(tmp_path / "missing.json")

    repo = _git_repo(tmp_path)
    monkeypatch.undo()

    from git_cg.eval.binding.paths import acceptpath_bundles_dir

    acceptpath_bundles_dir(repo).mkdir(parents=True, exist_ok=True)
    with pytest.raises(TrainExportError) as ei:
        te._load_bundles(repo, ["bad id"])
    assert ei.value.code == "EVAL_USAGE"
    with pytest.raises(TrainExportError) as ei:
        te._load_bundles(repo, ["no-such-bundle"])
    assert ei.value.code == "EVAL_USAGE"


def test_train_export_write_persists_rows_and_vault(tmp_path: Path) -> None:
    from git_cg.eval.train_export import write_train_export

    repo = _git_repo(tmp_path)
    result = {
        "export": {
            "export_id": "expcov01",
            "schema_version": "train_export_v1",
            "vault_destination": "antipattern_vault",
        },
        "rows": [
            {
                "id": "row-pos",
                "train_label": "positive",
                "schema_version": "train_row_v1",
            },
            {
                "id": "row-neg",
                "train_label": "hard_negative",
                "schema_version": "train_row_v1",
            },
        ],
    }
    out = write_train_export(repo, result)
    assert Path(out["export_path"]).is_file()
    assert out["row_count"] == 2
    assert any("row-neg" in p for p in out["vault_paths"])


# ---------------------------------------------------------------------------
# checkpoint_store residual IO arms
# ---------------------------------------------------------------------------


def test_checkpoint_store_list_and_load_edges(tmp_path: Path) -> None:
    from git_cg.eval.checkpoint_store import (
        CheckpointStoreError,
        list_checkpoint_ids,
        list_index_rows,
        load_checkpoint,
    )

    repo = _git_repo(tmp_path)
    assert list_checkpoint_ids(repo) == []
    assert list_index_rows(repo) == []

    with pytest.raises(CheckpointStoreError) as ei:
        load_checkpoint(repo, "ckpt-missing")
    assert ei.value.code == "EVAL_CHECKPOINT_MISSING"


# ---------------------------------------------------------------------------
# Round 2 — high-yield CLI / export / checkpoint residual arms
# ---------------------------------------------------------------------------


runner = CliRunner()


def test_cli_slice5_error_and_issue_transition_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.diagnose import DiagnoseError

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)

    class _BoomError(Exception):
        def __init__(self) -> None:
            super().__init__("boom")
            self.code = "EVAL_USAGE"
            self.exit_code = 2
            self.hint = "try again"

    with pytest.raises(typer.Exit) as ei:
        cli_mod._emit_slice5_error("eval explain", _BoomError(), as_json=False)
    assert ei.value.exit_code == 2
    err = capsys.readouterr().err
    assert "boom" in err
    assert "try again" in err

    with pytest.raises(typer.Exit) as ei:
        cli_mod._emit_slice5_error("eval explain", _BoomError(), as_json=True)
    assert ei.value.exit_code == 2
    out = capsys.readouterr().out
    assert '"ok": false' in out or '"ok":false' in out.replace(" ", "")

    def boom_transition(*_a: object, **_k: object) -> dict[str, object]:
        raise DiagnoseError("nope", code="EVAL_USAGE", exit_code=2)

    monkeypatch.setattr("git_cg.eval.diagnose.transition_issue", boom_transition)
    with pytest.raises(typer.Exit):
        cli_mod._run_issue_transition(
            "eval issue resolve",
            issue_id="i1",
            target="resolved",
            resolution_evidence=None,
            reason=None,
            as_json=True,
        )

    def ok_transition(*_a: object, **_k: object) -> dict[str, object]:
        return {
            "issue": {"issue_id": "i1"},
            "transitioned": True,
            "from": "open",
            "to": "resolved",
        }

    monkeypatch.setattr("git_cg.eval.diagnose.transition_issue", ok_transition)
    with pytest.raises(typer.Exit) as ei:
        cli_mod._run_issue_transition(
            "eval issue resolve",
            issue_id="i1",
            target="resolved",
            resolution_evidence="fixed",
            reason=None,
            as_json=False,
        )
    assert ei.value.exit_code == 0
    assert "transitioned" in capsys.readouterr().out


def test_cli_status_queue_counts_and_emit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.mirror import queue as mirror_queue

    repo = _git_repo(tmp_path)
    qdir = repo / ".eval" / "export_queue"
    qdir.mkdir(parents=True)
    (qdir / "bad.json").write_text("{", encoding="utf-8")
    (qdir / "good.json").write_text('{"status": "pending"}', encoding="utf-8")

    monkeypatch.setattr(mirror_queue, "export_queue_dir", lambda _repo: qdir)

    def load_item(stem: str, *, repo_root: Path | None = None) -> dict[str, str]:
        if stem == "bad":
            raise ValueError("unreadable")
        return {"status": "pending"}

    monkeypatch.setattr(mirror_queue, "load_queue_item", load_item)
    counts = cli_mod._queue_status_counts(repo)
    assert counts.get("pending") == 1
    assert counts.get("unreadable") == 1
    cli_mod._emit_status(repo)
    out = capsys.readouterr().out
    assert "queue_dir" in out
    assert "pending" in out


def test_cli_explain_compare_error_and_success_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.explain import ExplainError

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)

    def boom_explain(*_a: object, **_k: object) -> dict[str, object]:
        raise ExplainError("missing", code="EVAL_USAGE", exit_code=2)

    monkeypatch.setattr("git_cg.eval.explain.explain", boom_explain)
    with pytest.raises(typer.Exit) as ei:
        cli_mod.explain_cmd(experiment_id=None, case_id=None, as_json=True)
    assert ei.value.exit_code == 2

    monkeypatch.setattr(
        "git_cg.eval.explain.explain",
        lambda *_a, **_k: {
            "cases": [
                {
                    "case_id": "c1",
                    "blame_span": "s",
                    "first_divergent_span": None,
                    "artifact_class": "x",
                    "failure_ids": ["f1"],
                    "prevention_ids": [],
                    "replay_command": "git-cg eval replay",
                }
            ]
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.explain_cmd(experiment_id="e1", case_id="c1", as_json=False)
    assert ei.value.exit_code == 0

    def boom_compare(*_a: object, **_k: object) -> dict[str, object]:
        raise ExplainError("nope", code="EVAL_USAGE", exit_code=2)

    monkeypatch.setattr("git_cg.eval.explain.compare", boom_compare)
    with pytest.raises(typer.Exit):
        cli_mod.compare_cmd(
            a_experiment_id="a",
            a_case_id="c1",
            b_experiment_id="b",
            b_case_id="c2",
            as_json=True,
        )

    monkeypatch.setattr(
        "git_cg.eval.explain.compare",
        lambda *_a, **_k: {
            "compare_source": "structural",
            "lineage_linked": False,
            "metric_delta": [{"metric_id": "m1", "a": {"passed": True}, "b": {"passed": False}}],
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.compare_cmd(
            a_experiment_id="a",
            a_case_id="c1",
            b_experiment_id="b",
            b_case_id="c2",
            as_json=False,
        )
    assert ei.value.exit_code == 0


def test_cli_promote_denial_json_and_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.promote import PromoteError

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)

    def deny(*_a: object, **_k: object) -> dict[str, object]:
        raise PromoteError(
            "denied",
            code="EVAL_USAGE",
            exit_code=2,
            hint="nope",
            denial_reason="silent_gold_mint_forbidden",
            decision={"promotion_id": "p1"},
            decision_path="/tmp/decision.json",
        )

    monkeypatch.setattr("git_cg.eval.promote.promote", deny)
    with pytest.raises(typer.Exit) as ei:
        cli_mod.promote_cmd(
            bundle="b1",
            destination="reject",
            owner="o",
            label="l",
            provenance="p",
            redaction_profile="default_scrub",
            stage="scrubbed_candidate",
            split_group_id=None,
            review_id=None,
            notes=None,
            popularity_signal=False,
            dry_run=True,
            as_json=True,
        )
    assert ei.value.exit_code == 2

    with pytest.raises(typer.Exit) as ei:
        cli_mod.promote_cmd(
            bundle="b1",
            destination="reject",
            owner="o",
            label="l",
            provenance="p",
            redaction_profile="default_scrub",
            stage="scrubbed_candidate",
            split_group_id=None,
            review_id=None,
            notes=None,
            popularity_signal=False,
            dry_run=True,
            as_json=False,
        )
    assert ei.value.exit_code == 2

    def accept(*_a: object, **_k: object) -> dict[str, object]:
        return {
            "decision": {"promotion_id": "p1", "destination": "reject"},
            "decision_path": "/tmp/d.json",
            "artifact_path": "/tmp/a.json",
            "accepted": True,
            "denial_reason": None,
            "dry_run": True,
        }

    monkeypatch.setattr("git_cg.eval.promote.promote", accept)
    with pytest.raises(typer.Exit) as ei:
        cli_mod.promote_cmd(
            bundle="b1",
            destination="reject",
            owner="o",
            label="l",
            provenance="p",
            redaction_profile="default_scrub",
            stage="scrubbed_candidate",
            split_group_id=None,
            review_id=None,
            notes=None,
            popularity_signal=False,
            dry_run=True,
            as_json=False,
        )
    assert ei.value.exit_code == 0


def test_cli_replay_train_export_amend_brief_wrappers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.brief import AmendBriefError
    from git_cg.eval.replay import ReplayError
    from git_cg.eval.train_export import TrainExportError

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)

    monkeypatch.setattr(
        "git_cg.eval.replay.replay",
        lambda *_a, **_k: (_ for _ in ()).throw(ReplayError("x", code="EVAL_USAGE", exit_code=2)),
    )
    with pytest.raises(typer.Exit):
        cli_mod.replay_cmd(
            bundle="b",
            experiment_id=None,
            case_id=None,
            notes=None,
            dry_run=True,
            as_json=True,
        )

    monkeypatch.setattr(
        "git_cg.eval.replay.replay",
        lambda *_a, **_k: {
            "compare": {
                "replay_id": "r1",
                "regression_status": "pass",
                "lineage_ok": True,
                "session_thread_id": "t1",
                "schema_version": "replay_compare_v1",
            },
            "source_path": "s",
            "compare_path": "c",
            "replay_bundle_path": "r",
            "source_bundle_hash": "a" * 64,
            "replay_bundle_hash": "b" * 64,
            "source_mutated": False,
            "dry_run": True,
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.replay_cmd(
            bundle="b",
            experiment_id=None,
            case_id=None,
            notes=None,
            dry_run=True,
            as_json=False,
        )
    assert ei.value.exit_code == 0

    monkeypatch.setattr(
        "git_cg.eval.train_export.train_export",
        lambda *_a, **_k: (_ for _ in ()).throw(TrainExportError("x", code="EVAL_USAGE", exit_code=2)),
    )
    with pytest.raises(typer.Exit):
        cli_mod.train_export_cmd(
            bundle_id=None,
            profile="train_rich",
            capture_on="all",
            split_group_id=None,
            notes=None,
            write=False,
            dry_run=True,
            as_json=True,
        )

    monkeypatch.setattr(
        "git_cg.eval.train_export.train_export",
        lambda *_a, **_k: {
            "export_id": "e1",
            "row_count": 0,
            "dropped_row_ids": [],
            "scrub_report": {"status": "ok"},
            "written": False,
            "dry_run": True,
            "would_write": {"export_path": "e.json", "rows_dir": "rows", "row_count": 0},
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.train_export_cmd(
            bundle_id=None,
            profile="train_rich",
            capture_on="all",
            split_group_id=None,
            notes=None,
            write=False,
            dry_run=True,
            as_json=False,
        )
    assert ei.value.exit_code == 0

    monkeypatch.setattr(
        "git_cg.eval.brief.amend_brief",
        lambda *_a, **_k: (_ for _ in ()).throw(AmendBriefError("x", code="EVAL_USAGE", exit_code=2)),
    )
    with pytest.raises(typer.Exit):
        cli_mod.amend_brief_cmd(
            score_run_id="rs_1",
            session_thread_id=None,
            case_id=None,
            last_dogfood=0,
            doctor=False,
            write=False,
            root=None,
            as_json=True,
        )

    monkeypatch.setattr(
        "git_cg.eval.brief.amend_brief",
        lambda *_a, **_k: {
            "brief": {"id": "b1"},
            "experiment_id": "e1",
            "written": False,
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.amend_brief_cmd(
            score_run_id="e1",
            session_thread_id=None,
            case_id=None,
            last_dogfood=0,
            doctor=False,
            write=False,
            root=None,
            as_json=False,
        )
    assert ei.value.exit_code == 0


def test_cli_amend_brief_case_option_threads_case_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`eval amend-brief --case <id>` is accepted and passed to amend_brief."""
    from git_cg.eval import cli as cli_mod

    captured: dict[str, object] = {}

    def fake_amend_brief(_repo, **_kwargs):
        captured.update(_kwargs)
        return {"brief": {"id": "b1"}, "experiment_id": "e1", "written": False}

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)
    monkeypatch.setattr("git_cg.eval.brief.amend_brief", fake_amend_brief)

    with pytest.raises(typer.Exit) as ei:
        cli_mod.amend_brief_cmd(
            score_run_id="e1",
            session_thread_id=None,
            case_id="case-A1",
            last_dogfood=0,
            doctor=False,
            write=False,
            root=None,
            as_json=True,
        )
    assert ei.value.exit_code == 0
    assert captured.get("case_id") == "case-A1"


def test_cli_review_enqueue_list_rollup_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.review_queue import ReviewQueueError

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)

    # invalid gold_dispute
    with pytest.raises(typer.Exit) as ei:
        cli_mod.review_enqueue_cmd(
            case_id="c1",
            bundle_id=None,
            reviewer="r",
            redaction_profile="default_scrub",
            craft_rating=None,
            gold_dispute="maybe",
            regime_label=None,
            notes=None,
            dry_run=True,
            as_json=True,
        )
    assert ei.value.exit_code == 2

    monkeypatch.setattr(
        "git_cg.eval.review_queue.enqueue",
        lambda *_a, **_k: (_ for _ in ()).throw(ReviewQueueError("x", code="EVAL_USAGE", exit_code=2)),
    )
    with pytest.raises(typer.Exit):
        cli_mod.review_enqueue_cmd(
            case_id="c1",
            bundle_id=None,
            reviewer="r",
            redaction_profile="default_scrub",
            craft_rating=1.0,
            gold_dispute="true",
            regime_label="A",
            notes="n",
            dry_run=True,
            as_json=True,
        )

    monkeypatch.setattr(
        "git_cg.eval.review_queue.enqueue",
        lambda *_a, **_k: {"item": {"review_id": "rv1", "status": "pending"}},
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.review_enqueue_cmd(
            case_id="c1",
            bundle_id=None,
            reviewer="r",
            redaction_profile="default_scrub",
            craft_rating=1.0,
            gold_dispute="false",
            regime_label=None,
            notes=None,
            dry_run=True,
            as_json=False,
        )
    assert ei.value.exit_code == 0

    monkeypatch.setattr(
        "git_cg.eval.review_queue.list_reviews",
        lambda *_a, **_k: {
            "review_count": 1,
            "reviews": [{"review_id": "rv1", "status": "pending", "case_id": "c1", "reviewer": "r"}],
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.review_list_cmd(status=None, as_json=False)
    assert ei.value.exit_code == 0

    monkeypatch.setattr(
        "git_cg.eval.review_queue.rollup_reviews",
        lambda *_a, **_k: {
            "rollup_count": 1,
            "can_sole_promote_gold": False,
            "rollups": [
                {
                    "target_kind": "case",
                    "target_id": "c1",
                    "reviewer_count": 1,
                    "review_count": 1,
                    "dimensions": {
                        "human.craft_rating": {"mean": 1.0, "disagreement": 0.0},
                        "human.gold_dispute": {"majority": False},
                        "human.regime_label": {"majority": "A"},
                    },
                    "outcomes": {"majority": "pending"},
                }
            ],
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.review_rollup_cmd(case_id="c1", bundle_id=None, as_json=False)
    assert ei.value.exit_code == 0


def test_cli_diagnose_success_and_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval import cli as cli_mod
    from git_cg.eval.diagnose import DiagnoseError

    monkeypatch.setattr(cli_mod, "_resolve_repo", lambda _root=None: tmp_path)
    monkeypatch.setattr(
        "git_cg.eval.diagnose.diagnose",
        lambda *_a, **_k: (_ for _ in ()).throw(DiagnoseError("x", code="EVAL_USAGE", exit_code=2)),
    )
    with pytest.raises(typer.Exit):
        cli_mod.diagnose_cmd(
            experiment_id=None,
            case_id="c1",
            code=None,
            title=None,
            product_impact="unknown",
            owner=None,
            notes=None,
            dry_run=True,
            as_json=True,
        )

    monkeypatch.setattr(
        "git_cg.eval.diagnose.diagnose",
        lambda *_a, **_k: {
            "issue": {
                "issue_id": "iss1",
                "status": "open",
                "occurrence_count": 1,
                "fingerprint": "f" * 64,
            },
            "upserted": False,
            "dry_run": True,
            "would_write": {"issue_path": "a", "diagnostics_path": "b"},
        },
    )
    with pytest.raises(typer.Exit) as ei:
        cli_mod.diagnose_cmd(
            experiment_id="e1",
            case_id="c1",
            code="code1",
            title="t",
            product_impact="low",
            owner="o",
            notes="n",
            dry_run=True,
            as_json=False,
        )
    assert ei.value.exit_code == 0


def test_train_export_build_policy_arms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from git_cg.eval.binding.paths import acceptpath_bundles_dir
    from git_cg.eval.mirror.redaction import RedactionError
    from git_cg.eval.train_export import TrainExportError, build_train_export

    repo = _git_repo(tmp_path)
    bdir = acceptpath_bundles_dir(repo)
    bdir.mkdir(parents=True)
    _write_json(
        bdir / "pos.json",
        {
            "id": "pos",
            "train_label": "positive",
            "final_message": "docs: x",
            "gate": {"deterministic_pass": True},
            "meta": {},
        },
    )
    _write_json(
        bdir / "neg.json",
        {
            "id": "neg",
            "train_label": "negative",
            "final_message": "fix: y",
            "gate": {"deterministic_pass": False},
            "meta": {"train_label": "negative"},
        },
    )
    _write_json(
        bdir / "unlab.json",
        {
            "id": "unlab",
            "final_message": "chore: z",
            "gate": {"deterministic_pass": True},
            "meta": {},
        },
    )

    with pytest.raises(TrainExportError) as ei:
        build_train_export(repo, redaction_profile="raw_dev_unsafe")
    assert ei.value.code == "EVAL_USAGE"

    with pytest.raises(TrainExportError) as ei:
        build_train_export(repo, capture_on="weird")
    assert ei.value.code == "EVAL_USAGE"

    def scrub_fail(bundle: dict[str, Any], *, profile: str) -> dict[str, Any]:
        if bundle.get("id") == "neg":
            raise RedactionError("blocked")
        out = dict(bundle)
        out["meta"] = dict(out.get("meta") or {})
        if bundle.get("id") == "pos":
            out["meta"]["redaction_quarantine"] = ["final_message"]
        return out

    # Mixed: unlabeled drop, scrub fail drop, quarantine field, capture_on pass filter
    result = build_train_export(
        repo,
        redaction_profile="train_rich",
        capture_on="pass",
        notes="token=ghp_ABCDEFghijklmnopqrstuvwxyz0123456789",
        split_group_id="sg1",
        export_id="export-cov1",
        redact_bundle=scrub_fail,
    )
    assert result["export"]["export_id"] == "export-cov1"
    assert "scrub_report" in result["export"]
    assert result["export"].get("split_group_id") == "sg1"

    with pytest.raises(TrainExportError):
        build_train_export(repo, export_id="bad id")


def test_checkpoint_store_corrupt_and_build_edges(tmp_path: Path) -> None:
    from git_cg.eval.binding.paths import checkpoints_dir, index_dir
    from git_cg.eval.checkpoint_store import (
        CheckpointStoreError,
        build_checkpoint_record,
        list_index_rows,
        load_checkpoint,
        write_checkpoint,
    )

    repo = _git_repo(tmp_path)
    with pytest.raises(CheckpointStoreError):
        build_checkpoint_record(
            checkpoint_id="bad id",
            experiment_id="e",
            compat_hash="a" * 64,
            completed_case_ids=[],
            pending_case_ids=[],
            mode="fresh_suite_run",
        )
    with pytest.raises(CheckpointStoreError):
        build_checkpoint_record(
            checkpoint_id="ok1",
            experiment_id="",
            compat_hash="a" * 64,
            completed_case_ids=[],
            pending_case_ids=[],
            mode="fresh_suite_run",
        )
    with pytest.raises(CheckpointStoreError):
        build_checkpoint_record(
            checkpoint_id="ok1",
            experiment_id="e1",
            compat_hash="zz",
            completed_case_ids=[],
            pending_case_ids=[],
            mode="fresh_suite_run",
        )

    # corrupt on-disk file
    cdir = checkpoints_dir(repo)
    cdir.mkdir(parents=True)
    (cdir / "broke.json").write_text("{", encoding="utf-8")
    with pytest.raises(CheckpointStoreError):
        load_checkpoint(repo, "broke")
    (cdir / "arr.json").write_text("[]", encoding="utf-8")
    with pytest.raises(CheckpointStoreError):
        load_checkpoint(repo, "arr")

    # index synthesis + status sanitize + suite filter
    rec = build_checkpoint_record(
        checkpoint_id="ck1",
        experiment_id="e1",
        compat_hash="a" * 64,
        completed_case_ids=["c1"],
        pending_case_ids=[],
        mode="fresh_suite_run",
        suite_id="suite-a",
        snapshot_id="snap",
        schema_pack="schema_pack_v0@" + ("a" * 64),
        metric_catalog="metric_catalog_v0@" + ("b" * 64),
        cursor="c1",
        notes="n",
    )
    write_checkpoint(repo, rec, status="completed")
    # orphan checkpoint without index
    rec2 = build_checkpoint_record(
        checkpoint_id="ck2",
        experiment_id="e2",
        compat_hash="b" * 64,
        completed_case_ids=[],
        pending_case_ids=["c2"],
        mode="resume_missing",
        suite_id="suite-b",
        schema_pack="schema_pack_v0@" + ("a" * 64),
        metric_catalog="metric_catalog_v0@" + ("b" * 64),
    )
    # write file only (no index)
    _write_json(cdir / "ck2.json", rec2)
    rows = list_index_rows(repo)
    assert {r.checkpoint_id for r in rows} >= {"ck1", "ck2"}
    rows_a = list_index_rows(repo, suite_id="suite-a")
    assert all(r.suite_id == "suite-a" for r in rows_a)

    # bad index row shapes ignored
    idx = index_dir(repo) / "checkpoints"
    idx.mkdir(parents=True, exist_ok=True)
    (idx / "junk.json").write_text("{", encoding="utf-8")
    (idx / "arr.json").write_text("[]", encoding="utf-8")
    (idx / "weird-status.json").write_text(
        json.dumps(
            {
                "checkpoint_id": "weird",
                "suite_id": "suite-a",
                "experiment_id": "e",
                "started_at": "t",
                "last_progress_at": "t",
                "status": "nope",
                "mode": "m",
                "path": "p",
            }
        ),
        encoding="utf-8",
    )
    list_index_rows(repo, suite_id="suite-a")
