"""Slice 5 ``eval failures`` / ``eval explain`` / ``eval compare`` (Issue #246).

Locks the §18.3 deterministic projection contract over landed Slice 3 Layer-A
``local_case_score_v0`` rows:

* ``failures`` lists failing cases with ``metric_ids`` + ``failure_ids``.
* ``explain`` emits the full §18.3 field set with **no** opaque LLM RCA.
* ``compare`` derives structural + metric delta; replay lineage when linked.
* The fingerprint substrate surfaces the sanitised Family I inputs verbatim —
  never raw span names, trace ids, timestamps, URLs, or absolute paths.

All offline: case-result rows are built with the real ``make_score`` builder
(catalog-validated) and written via the governed Layer-A helpers into tmp repos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import atomic_write_json, experiments_dir
from git_cg.eval.explain import (
    BLAME_SPAN_SURFACES,
    ExplainError,
    compare,
    explain,
    list_failures,
)
from git_cg.eval.scoring.result_builder import make_score

# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


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


def _score(metric_id: str, passed: bool, *, fp: dict | None = None, failure_ids=None, extra_evd=None):
    evidence: dict = {}
    if fp is not None:
        evidence["diag_fingerprint_inputs"] = fp
    if extra_evd:
        evidence.update(extra_evd)
    return make_score(
        metric_id,
        bool(passed),
        passed=passed,
        reason=None if passed else "counter_span_mismatch",
        evidence=evidence or None,
        failure_ids=failure_ids,
        product_authority="git_cg.eval.scoring.family_i",
    )


def _write_experiment(repo: Path, experiment_id: str, *, meta: dict | None = None) -> None:
    record = {
        "schema_version": "experiment_v1",
        "id": experiment_id,
        "experiment_name": experiment_id,
        "lane": "suite",
        "git_sha": "deadbeef",
        "catalog_pin": "metric_catalog_v1@" + "a" * 64,
        "schema_pack": "schema_pack_v1@" + "b" * 64,
        "metric_catalog": "metric_catalog_v1@" + "a" * 64,
        "meta": meta or {},
    }
    atomic_write_json(experiments_dir(repo) / experiment_id / "experiment.json", record)


def _write_case(
    repo: Path,
    experiment_id: str,
    case_id: str,
    *,
    passed: bool,
    scores: list,
    failed_metric_ids: list[str] | None = None,
    trace_id: str | None = None,
    session_thread_id: str | None = None,
) -> None:
    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": experiment_id,
        "case_id": case_id,
        "deterministic_pass": passed,
        "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
        "evaluator_errors": [],
        "scores": [s.model_dump(mode="json") for s in scores],
        "gates": [],
        "failed_metric_ids": failed_metric_ids or [],
    }
    if trace_id:
        payload["trace_id"] = trace_id
    if session_thread_id:
        payload["session_thread_id"] = session_thread_id
    atomic_write_json(experiments_dir(repo) / experiment_id / "cases" / f"{case_id}.json", payload)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture()
def failing_repo(repo: Path) -> Path:
    """One experiment with one passing + one failing case (Family I blame)."""
    exp = "exp-a"
    _write_experiment(repo, exp, meta={"pins": {"project_lane": "suite", "environment": "local"}})
    _write_case(
        repo,
        exp,
        "case-pass",
        passed=True,
        scores=[_score("i.trace_root_present", True)],
    )
    _write_case(
        repo,
        exp,
        "case-fail",
        passed=False,
        scores=[
            _score(
                "i.counter_span_consistent",
                False,
                fp=_fp_inputs(),
                failure_ids=["EVAL_TOPOLOGY"],
                extra_evd={"prevention_ids": ["PREV-001"]},
            )
        ],
        failed_metric_ids=["i.counter_span_consistent"],
        trace_id="trace-123",
        session_thread_id="thread-9",
    )
    return repo


# --------------------------------------------------------------------------
# failures
# --------------------------------------------------------------------------


def test_failures_lists_metric_and_failure_ids(failing_repo: Path) -> None:
    data = list_failures(failing_repo, experiment_id="exp-a")
    assert data["experiment_id"] == "exp-a"
    assert data["case_count"] == 1
    case = data["failing_cases"][0]
    assert case["case_id"] == "case-fail"
    assert case["metric_ids"] == ["i.counter_span_consistent"]
    assert case["failure_ids"] == ["EVAL_TOPOLOGY"]
    assert case["deterministic_pass"] is False


def test_failures_empty_when_no_experiments(repo: Path) -> None:
    data = list_failures(repo)
    assert data["experiment_id"] is None
    assert data["failing_cases"] == []


def test_failures_defaults_to_latest_experiment(failing_repo: Path) -> None:
    data = list_failures(failing_repo)
    assert data["experiment_id"] == "exp-a"


def test_failures_corrupt_case_row_fails_closed(failing_repo: Path) -> None:
    bad = experiments_dir(failing_repo) / "exp-a" / "cases" / "broken.json"
    atomic_write_json(bad, {"schema_version": "not_a_case"})
    with pytest.raises(ExplainError) as ei:
        list_failures(failing_repo, experiment_id="exp-a")
    assert ei.value.exit_code == 4
    assert ei.value.code == "EVAL_STORE_INTEGRITY"


# --------------------------------------------------------------------------
# explain
# --------------------------------------------------------------------------


def test_explain_full_contract_no_llm_rca(failing_repo: Path) -> None:
    data = explain(failing_repo, experiment_id="exp-a", case_id="case-fail")
    assert data["case_count"] == 1
    case = data["cases"][0]
    # §18.3 required fields.
    assert case["case_id"] == "case-fail"
    assert case["experiment_id"] == "exp-a"
    assert case["trace_id"] == "trace-123"
    assert case["thread_id"] == "thread-9"
    assert case["artifact_class"] == "final_accept"
    assert case["blame_span"] == "regeneration"
    assert case["first_divergent_span"] == "regeneration"
    assert case["metric_ids"] == ["i.counter_span_consistent"]
    assert case["failure_ids"] == ["EVAL_TOPOLOGY"]
    assert case["prevention_ids"] == ["PREV-001"]  # surfaced, not fabricated
    assert case["topology_missing_spans"] == ["regeneration"]
    assert case["counter_span_consistent"] is False
    assert case["suggested_surfaces"] == list(BLAME_SPAN_SURFACES["regeneration"])
    assert "git-cg eval replay" in case["replay_command"]
    assert case["bundle_path"] == "case-fail"
    # INT-29 headers present.
    headers = case["headers"]
    for key in (
        "project_lane",
        "environment",
        "export_status",
        "redaction_profile",
        "schema_pack_hash",
        "metric_catalog_hash",
        "harness_version",
    ):
        assert key in headers
    # Forbidden: no opaque LLM RCA keys leak into the deterministic contract.
    blob = json.dumps(case).lower()
    for forbidden in ("ollie", "llm_rca", "root_cause_analysis", "gpt", "claude"):
        assert forbidden not in blob


def test_explain_prevention_ids_never_fabricated(repo: Path) -> None:
    _write_experiment(repo, "exp-x")
    _write_case(
        repo,
        "exp-x",
        "c1",
        passed=False,
        scores=[_score("i.counter_span_consistent", False, fp=_fp_inputs(), failure_ids=["EVAL_TOPOLOGY"])],
        failed_metric_ids=["i.counter_span_consistent"],
    )
    data = explain(repo, experiment_id="exp-x", case_id="c1")
    assert data["cases"][0]["prevention_ids"] == []  # not invented from metric_ids


def test_explain_unknown_blame_span_maps_to_empty_surfaces(repo: Path) -> None:
    _write_experiment(repo, "exp-y")
    _write_case(
        repo,
        "exp-y",
        "c1",
        passed=False,
        scores=[
            _score(
                "i.counter_span_consistent",
                False,
                fp=_fp_inputs(blame_span="unknown:abc123def456"),
                failure_ids=["EVAL_TOPOLOGY"],
            )
        ],
        failed_metric_ids=["i.counter_span_consistent"],
    )
    data = explain(repo, experiment_id="exp-y", case_id="c1")
    case = data["cases"][0]
    assert case["blame_span"] == "unknown:abc123def456"
    assert case["suggested_surfaces"] == []  # never guess surfaces for digested spans


def test_explain_missing_case_fails_closed_usage(repo: Path) -> None:
    _write_experiment(repo, "exp-z")
    _write_case(repo, "exp-z", "c1", passed=True, scores=[_score("i.trace_root_present", True)])
    with pytest.raises(ExplainError) as ei:
        explain(repo, experiment_id="exp-z", case_id="nope")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_explain_no_experiments_fails_closed(repo: Path) -> None:
    with pytest.raises(ExplainError) as ei:
        explain(repo)
    assert ei.value.exit_code == 2


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------


def test_compare_metric_and_structural_delta(failing_repo: Path) -> None:
    # Second experiment where the same case now passes.
    exp_b = "exp-b"
    _write_experiment(failing_repo, exp_b)
    _write_case(
        failing_repo,
        exp_b,
        "case-fail",
        passed=True,
        scores=[_score("i.counter_span_consistent", True)],
    )
    data = compare(
        failing_repo,
        a_experiment_id="exp-a",
        a_case_id="case-fail",
        b_experiment_id=exp_b,
        b_case_id="case-fail",
    )
    assert data["compare_source"] == "case_result_delta"  # not lineage-linked
    assert data["lineage_linked"] is False
    delta = {d["metric_id"]: d for d in data["metric_delta"]}
    assert "i.counter_span_consistent" in delta
    assert delta["i.counter_span_consistent"]["a"]["passed"] is False
    assert delta["i.counter_span_consistent"]["b"]["passed"] is True
    assert data["structural_delta"]["deterministic_pass"]["changed"] is True


def test_compare_detects_lineage_link(failing_repo: Path) -> None:
    # Child experiment whose meta.parent_experiment_id points at exp-a.
    _write_experiment(failing_repo, "exp-child", meta={"parent_experiment_id": "exp-a"})
    _write_case(
        failing_repo,
        "exp-child",
        "case-fail",
        passed=True,
        scores=[_score("i.counter_span_consistent", True)],
    )
    data = compare(
        failing_repo,
        a_experiment_id="exp-a",
        a_case_id="case-fail",
        b_experiment_id="exp-child",
        b_case_id="case-fail",
    )
    assert data["lineage_linked"] is True
    assert data["compare_source"] == "case_result_delta"  # lineage orthogonal to delta source


def test_explain_masks_secret_shaped_evaluator_errors(failing_repo: Path) -> None:
    """S6-C08: explain projections never emit raw secret tokens/prefixes."""
    secret = "sk-" + "test-fixture-token-value-0123456789"
    case_path = experiments_dir(failing_repo) / "exp-a" / "cases" / "case-fail.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["evaluator_errors"] = [f"upstream api_key={secret}"]
    payload["trace_id"] = secret
    case_path.write_text(json.dumps(payload), encoding="utf-8")

    data = explain(failing_repo, experiment_id="exp-a", case_id="case-fail")
    # Walk parsed values (json.dumps may escape the bullet mask form).
    flat = json.dumps(data, ensure_ascii=False)
    assert secret not in flat
    assert "sk-test" not in flat
    assert "•••[len=" in flat


# --------------------------------------------------------------------------
# failures filters (NTH-02)
# --------------------------------------------------------------------------


def test_failures_filters_and_combine(repo: Path) -> None:
    exp = "exp-filt"
    _write_experiment(repo, exp)
    # Family I / regime B / block / EVAL_TOPOLOGY
    _write_case(
        repo,
        exp,
        "case-i-b",
        passed=False,
        scores=[
            _score(
                "i.counter_span_consistent",
                False,
                fp=_fp_inputs(regime="B"),
                failure_ids=["EVAL_TOPOLOGY"],
            )
        ],
        failed_metric_ids=["i.counter_span_consistent"],
    )
    # Family H / regime A / warn-ish via second metric path
    h_score = make_score(
        "h.doctor_green",
        False,
        passed=False,
        reason="warn_path",
        evidence={
            "diag_fingerprint_inputs": _fp_inputs(regime="A", metric_ids=["h.doctor_green"], failure_ids=["EVAL_DOC"])
        },
        failure_ids=["EVAL_DOC"],
        product_authority="git_cg.eval.doctor",
        severity="warn",
    )
    _write_case(
        repo,
        exp,
        "case-h-a",
        passed=False,
        scores=[h_score],
        failed_metric_ids=["h.doctor_green"],
    )

    all_rows = list_failures(repo, experiment_id=exp)
    assert all_rows["case_count"] == 2
    assert all_rows["filters"]["regime"] is None

    only_i = list_failures(repo, experiment_id=exp, family="I")
    assert only_i["case_count"] == 1
    assert only_i["failing_cases"][0]["case_id"] == "case-i-b"
    assert only_i["filters"]["family"] == "I"

    only_b = list_failures(repo, experiment_id=exp, regime="B")
    assert only_b["case_count"] == 1
    assert only_b["failing_cases"][0]["case_id"] == "case-i-b"

    by_fid = list_failures(repo, experiment_id=exp, failure_id="EVAL_DOC")
    assert by_fid["case_count"] == 1
    assert by_fid["failing_cases"][0]["case_id"] == "case-h-a"

    by_sev = list_failures(repo, experiment_id=exp, severity="block")
    assert by_sev["case_count"] == 1
    assert by_sev["failing_cases"][0]["case_id"] == "case-i-b"

    none = list_failures(repo, experiment_id=exp, family="I", regime="A")
    assert none["case_count"] == 0


def test_failures_invalid_severity_fails_closed(failing_repo: Path) -> None:
    with pytest.raises(ExplainError) as ei:
        list_failures(failing_repo, severity="critical")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"
