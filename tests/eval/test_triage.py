"""Slice 8 offline ``eval triage`` service contract (Issue #246 / D27).

Locks:

* ``eval_triage_v0`` projection shape + advisory authority.
* Library-engine composition (doctor / failures / explain) — no Typer nesting.
* Explain auto-select rules (0 / 1 / many failures + explicit ``--case``).
* Exit precedence: usage 2 → store 4 → doctor compat 3 → doctor red 1 → 0.
* No Opik / ``user_acceptance`` dual score law on the triage path.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import atomic_write_json, experiments_dir
from git_cg.eval.explain import ExplainError
from git_cg.eval.scoring.result_builder import make_score
from git_cg.eval.triage import (
    AUTHORITY,
    REPLACEMENTS_FOR_LEGACY_SCRIPT,
    SCHEMA_VERSION,
    TriageError,
    run_triage,
)

REPO = Path(__file__).resolve().parents[2]
TRIAGE_SRC = REPO / "src" / "git_cg" / "eval" / "triage.py"


def _fp() -> dict:
    return {
        "metric_ids": ["i.counter_span_consistent"],
        "failure_ids": ["EVAL_TOPOLOGY"],
        "blame_span": "regeneration",
        "first_divergent_span": "regeneration",
        "missing_required_spans": ["regeneration"],
        "artifact_class": "final_accept",
        "regime": "B",
        "path_class_key": "code_change",
    }


def _write_experiment(repo: Path, experiment_id: str) -> None:
    atomic_write_json(
        experiments_dir(repo) / experiment_id / "experiment.json",
        {
            "schema_version": "experiment_v1",
            "id": experiment_id,
            "experiment_name": experiment_id,
            "lane": "suite",
            "git_sha": "deadbeef",
            "catalog_pin": "metric_catalog_v1@" + "a" * 64,
            "schema_pack": "schema_pack_v1@" + "b" * 64,
            "metric_catalog": "metric_catalog_v1@" + "a" * 64,
            "meta": {"pins": {"project_lane": "suite", "environment": "local"}},
        },
    )


def _write_case(repo: Path, experiment_id: str, case_id: str, *, passed: bool) -> None:
    score = make_score(
        "i.counter_span_consistent",
        passed,
        passed=passed,
        reason=None if passed else "counter_span_mismatch",
        evidence={
            "diag_fingerprint_inputs": _fp(),
            "prevention_ids": ["PREV-001"],
            "severity": "block",
        },
        failure_ids=None if passed else ["EVAL_TOPOLOGY"],
        product_authority="git_cg.eval.scoring.family_i",
    )
    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": experiment_id,
        "case_id": case_id,
        "deterministic_pass": passed,
        "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
        "evaluator_errors": [],
        "scores": [score.model_dump(mode="json")],
        "gates": [],
        "failed_metric_ids": [] if passed else ["i.counter_span_consistent"],
        "trace_id": "trace-1",
        "session_thread_id": "thread-9",
    }
    atomic_write_json(
        experiments_dir(repo) / experiment_id / "cases" / f"{case_id}.json",
        payload,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_all_sections_skipped_is_usage_error(repo: Path) -> None:
    with pytest.raises(TriageError) as ei:
        run_triage(
            repo,
            skip_doctor=True,
            skip_failures=True,
            skip_explain=True,
        )
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_projection_shape_and_authority(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:

    doctor = make_doctor_double(suite_id="cm-eval-fixtures-core")
    # Patch the symbols resolved by lazy import inside run_triage.
    import git_cg.eval.doctor as doctor_mod
    import git_cg.eval.explain as explain_mod

    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)
    monkeypatch.setattr(
        explain_mod,
        "list_failures",
        lambda *_a, **_k: {"experiment_id": None, "failing_cases": [], "case_count": 0},
    )

    report = run_triage(repo, skip_explain=True)
    data = report.to_data()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["authority"] == AUTHORITY
    assert data["not_score_law"] is True
    assert data["doctor"]["green"] is True
    assert data["failures"]["case_count"] == 0
    assert data["explain"] is None
    assert data["sections_run"] == ["doctor", "failures"]
    assert "explain" in data["sections_skipped"]
    assert data["replacements_for_legacy_script"] == list(REPLACEMENTS_FOR_LEGACY_SCRIPT)
    assert report.exit_code == 0
    assert report.ok is True


def test_explain_auto_selects_single_failure(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod

    _write_experiment(repo, "exp-a")
    _write_case(repo, "exp-a", "case-fail", passed=False)

    doctor = make_doctor_double()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    report = run_triage(repo, experiment_id="exp-a")
    data = report.to_data()
    assert data["explain"] is not None
    assert data["explain"]["cases"][0]["case_id"] == "case-fail"
    assert any("auto-selected" in n for n in data["notes"])
    assert report.exit_code == 0  # failures alone do not force non-zero


def test_explain_omitted_when_multiple_failures(
    repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double
) -> None:
    import git_cg.eval.doctor as doctor_mod

    _write_experiment(repo, "exp-a")
    _write_case(repo, "exp-a", "case-a", passed=False)
    _write_case(repo, "exp-a", "case-b", passed=False)

    doctor = make_doctor_double()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    report = run_triage(repo, experiment_id="exp-a")
    data = report.to_data()
    assert data["explain"] is None
    assert "explain" in data["sections_skipped"]
    assert any("pass --case" in n for n in data["notes"])
    assert data["failures"]["case_count"] == 2
    assert report.exit_code == 0


def test_explicit_case_explain(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod

    _write_experiment(repo, "exp-a")
    _write_case(repo, "exp-a", "case-a", passed=False)
    _write_case(repo, "exp-a", "case-b", passed=False)

    doctor = make_doctor_double()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    report = run_triage(repo, experiment_id="exp-a", case_id="case-b")
    data = report.to_data()
    assert data["explain"] is not None
    assert data["explain"]["cases"][0]["case_id"] == "case-b"


def test_invalid_case_propagates_usage(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod

    _write_experiment(repo, "exp-a")
    _write_case(repo, "exp-a", "case-a", passed=False)
    doctor = make_doctor_double()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    with pytest.raises(ExplainError) as ei:
        run_triage(repo, experiment_id="exp-a", case_id="missing")
    assert ei.value.exit_code == 2
    assert ei.value.code == "EVAL_USAGE"


def test_doctor_red_exit_1(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod
    import git_cg.eval.explain as explain_mod

    doctor = make_doctor_double(green=False, exit_code=1, block_failures=["pin_floating"])
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)
    monkeypatch.setattr(
        explain_mod,
        "list_failures",
        lambda *_a, **_k: {"experiment_id": "e", "failing_cases": [], "case_count": 0},
    )
    report = run_triage(repo, skip_explain=True)
    assert report.exit_code == 1
    assert report.ok is False


def test_doctor_compat_exit_3_outranks_red(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod
    import git_cg.eval.explain as explain_mod

    doctor = make_doctor_double(green=False, exit_code=3)
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)
    monkeypatch.setattr(
        explain_mod,
        "list_failures",
        lambda *_a, **_k: {"experiment_id": "e", "failing_cases": [], "case_count": 0},
    )
    report = run_triage(repo, skip_explain=True)
    assert report.exit_code == 3


def test_corrupt_case_store_integrity(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod

    _write_experiment(repo, "exp-a")
    bad = experiments_dir(repo) / "exp-a" / "cases" / "broken.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not-json", encoding="utf-8")

    doctor = make_doctor_double()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)

    with pytest.raises(ExplainError) as ei:
        run_triage(repo, experiment_id="exp-a", skip_explain=True)
    assert ei.value.exit_code == 4
    assert ei.value.code == "EVAL_STORE_INTEGRITY"


def test_source_has_no_banned_imports_or_thresholds() -> None:
    src = TRIAGE_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(TRIAGE_SRC))
    banned = {"opik", "requests", "httpx", "openai", "anthropic"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            assert root not in banned
    # Docstrings may name the banned dual-law surface; executable code must not
    # implement search_traces / threshold filters / acceptance ranking.
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            chunk = ast.get_source_segment(src, node) or ""
            # Allow-list only assignment/ann-assign nodes that define the constants.
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and (
                "REPLACEMENTS_FOR_LEGACY_SCRIPT" in chunk or "SCHEMA_VERSION" in chunk
            ):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body_src = "\n".join(
                    (ast.get_source_segment(src, child) or "")
                    for child in node.body
                    if not isinstance(child, ast.Expr)  # skip docstrings
                )
                lowered = body_src.lower()
                assert "search_traces" not in lowered
                assert "feedback_scores.user_acceptance" not in lowered
                assert "> 0.8" not in body_src and "< 0.2" not in body_src


def test_projection_serialisable(repo: Path, monkeypatch: pytest.MonkeyPatch, make_doctor_double) -> None:
    import git_cg.eval.doctor as doctor_mod
    import git_cg.eval.explain as explain_mod

    doctor = make_doctor_double()
    monkeypatch.setattr(doctor_mod, "run_local_doctor", lambda **_k: doctor)
    monkeypatch.setattr(
        explain_mod,
        "list_failures",
        lambda *_a, **_k: {"experiment_id": None, "failing_cases": [], "case_count": 0},
    )
    report = run_triage(repo, skip_explain=True)
    blob = json.dumps(report.to_data())
    assert SCHEMA_VERSION in blob
    assert "user_acceptance" not in blob.lower()
