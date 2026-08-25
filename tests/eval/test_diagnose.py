"""Slice 5 ``eval diagnose`` + issue store law (Issue #246).

Locks the §18.4 / FIND-021 contract against the frozen ``diag_issue_v1`` schema:

* **Fingerprint law:** stable, canonical, and excludes trace ids / timestamps /
  raw text / URLs / usernames / absolute paths (normative exclusion list).
* **Idempotent upsert:** re-diagnosing the same fingerprint bumps
  ``last_seen_at`` + ``occurrence_count``; never duplicates a row.
* **Closed transition matrix** with required evidence/reason and idempotent
  no-op re-application.
* Every persisted row validates against ``schemas/eval/diag_issue_v1.schema.json``.
* Writes stay contained under ``.eval/`` (N19.3) and are atomic.

All offline against synthetic ``local_case_score_v0`` rows in tmp repos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import atomic_write_json, experiments_dir, issues_dir
from git_cg.eval.diagnose import (
    TRANSITIONS,
    DiagnoseError,
    compute_fingerprint,
    diagnose,
    list_issues,
    show_issue,
    transition_issue,
)
from git_cg.eval.scoring.result_builder import make_score

# --------------------------------------------------------------------------
# Fingerprint law (pure)
# --------------------------------------------------------------------------


def _inputs(**over) -> dict:
    base = {
        "failure_ids": ["EVAL_TOPOLOGY", "EVAL_B"],
        "metric_ids": ["i.b", "i.a"],
        "blame_span": "regeneration",
        "regime": "B",
        "artifact_class": "final_accept",
        "missing_required_spans": ["regeneration"],
        "path_class_key": "code_change",
    }
    base.update(over)
    return base


def test_fingerprint_is_order_stable() -> None:
    a = compute_fingerprint(_inputs())
    # Reversed input lists must produce the identical digest (sorted canonically).
    b = compute_fingerprint(
        _inputs(
            failure_ids=["EVAL_B", "EVAL_TOPOLOGY"],
            metric_ids=["i.a", "i.b"],
        )
    )
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_fingerprint_excludes_ephemeral_and_sensitive_fields() -> None:
    base = compute_fingerprint(_inputs())
    # Fields that MUST NOT enter the preimage (schema normative exclusion list).
    excluded = _inputs()
    excluded.update(
        {
            "trace_id": "trace-999",
            "timestamp": "2026-08-21T00:00:00Z",
            "raw_text": "the actual commit message body",
            "url": "https://example.com/x",
            "username": "operator1",
            "absolute_path": "/Users/admin/secret",
        }
    )
    # compute_fingerprint only reads the inclusion-list keys, so adding excluded
    # keys must not change the digest.
    assert compute_fingerprint(excluded) == base


def test_fingerprint_changes_on_blame_span() -> None:
    assert compute_fingerprint(_inputs()) != compute_fingerprint(_inputs(blame_span="final_render"))


def test_transition_matrix_is_closed_and_matches_spec() -> None:
    assert TRANSITIONS["open"] == frozenset({"acknowledged", "resolved", "suppressed"})
    assert TRANSITIONS["acknowledged"] == frozenset({"resolved", "suppressed", "reopened"})
    assert TRANSITIONS["resolved"] == frozenset({"reopened"})
    assert TRANSITIONS["suppressed"] == frozenset({"reopened"})
    assert TRANSITIONS["reopened"] == frozenset({"acknowledged", "resolved", "suppressed"})
    # Closed: no state may transition to itself implicitly, and no extra states.
    for state, targets in TRANSITIONS.items():
        assert state not in targets
        assert targets <= set(TRANSITIONS)


# --------------------------------------------------------------------------
# Store fixtures
# --------------------------------------------------------------------------


def _fp(**over) -> dict:
    base = {
        "metric_ids": ["i.counter_span_consistent"],
        "failure_ids": ["EVAL_TOPOLOGY"],
        "blame_span": "regeneration",
        "missing_required_spans": ["regeneration"],
        "artifact_class": "final_accept",
        "regime": "B",
        "path_class_key": "code_change",
    }
    base.update(over)
    return base


def _failing_case(experiment_id: str, case_id: str, *, trace_id: str | None = None) -> dict:
    score = make_score(
        "i.counter_span_consistent",
        False,
        passed=False,
        reason="counter_span_mismatch",
        evidence={
            "diag_fingerprint_inputs": _fp(),
            "prevention_ids": ["PREV-001"],
            "severity": "block",
        },
        failure_ids=["EVAL_TOPOLOGY"],
        product_authority="git_cg.eval.scoring.family_i",
    )
    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": experiment_id,
        "case_id": case_id,
        "deterministic_pass": False,
        "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
        "evaluator_errors": [],
        "scores": [score.model_dump(mode="json")],
        "gates": [],
        "failed_metric_ids": ["i.counter_span_consistent"],
    }
    if trace_id:
        payload["trace_id"] = trace_id
    return payload


def _seed_failing(repo: Path, experiment_id: str = "exp-a", case_id: str = "case-fail") -> None:
    _failing = _failing_case(experiment_id, case_id, trace_id="trace-1")
    atomic_write_json(experiments_dir(repo) / experiment_id / "cases" / f"{case_id}.json", _failing)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture()
def failing_repo(repo: Path) -> Path:
    _seed_failing(repo)
    return repo


# --------------------------------------------------------------------------
# diagnose: upsert + schema validation
# --------------------------------------------------------------------------


def test_diagnose_creates_valid_issue_row(failing_repo: Path) -> None:
    result = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")
    issue = result["issue"]
    assert result["upserted"] is False
    assert issue["schema_version"] == "diag_issue_v1"
    assert issue["status"] == "open"
    assert issue["occurrence_count"] == 1
    assert issue["fingerprint"] == compute_fingerprint(_fp())
    assert issue["failure_ids"] == ["EVAL_TOPOLOGY"]
    assert issue["metric_ids"] == ["i.counter_span_consistent"]
    assert issue["blame_span"] == "regeneration"
    assert issue["artifact_class"] == "final_accept"
    assert issue["regime"] == "B"
    assert issue["path_class"] == "code_change"
    assert issue["topology_missing_spans"] == ["regeneration"]
    assert issue["prevention_ids"] == ["PREV-001"]  # surfaced, not fabricated
    assert issue["suggested_surfaces"]  # blame map resolved
    assert issue["product_impact"] == "unknown"
    # Persisted row validates against the frozen schema (diagnose validates on write).
    on_disk = json.loads((issues_dir(failing_repo) / f"{issue['issue_id']}.json").read_text("utf-8"))
    assert on_disk["fingerprint"] == issue["fingerprint"]


def test_diagnose_is_idempotent_upsert_by_fingerprint(failing_repo: Path) -> None:
    first = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")
    second = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")
    assert first["upserted"] is False
    assert second["upserted"] is True
    assert first["issue"]["issue_id"] == second["issue"]["issue_id"]
    assert first["issue"]["fingerprint"] == second["issue"]["fingerprint"]
    assert second["issue"]["occurrence_count"] == 2
    assert second["issue"]["first_seen_at"] == first["issue"]["first_seen_at"]  # never rewritten
    # Only one row on disk (no duplicate by fingerprint).
    rows = list(issues_dir(failing_repo).glob("*.json"))
    assert len(rows) == 1


def test_diagnose_distinct_fingerprints_create_distinct_issues(failing_repo: Path) -> None:
    diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")
    # A second failing case with a different blame span -> different fingerprint.
    other = _failing_case("exp-a", "case-fail-2")
    other["scores"][0]["evidence"]["diag_fingerprint_inputs"] = _fp(blame_span="final_render")
    atomic_write_json(experiments_dir(failing_repo) / "exp-a" / "cases" / "case-fail-2.json", other)
    diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail-2")
    assert len(list(issues_dir(failing_repo).glob("*.json"))) == 2


def test_diagnose_no_failing_cases_fails_closed(repo: Path) -> None:
    score = make_score("i.trace_root_present", True, passed=True)
    payload = {
        "schema_version": "local_case_score_v0",
        "experiment_id": "exp-ok",
        "case_id": "ok",
        "deterministic_pass": True,
        "suite_snapshot_pin": "suite_snapshot_v1@" + "c" * 64,
        "evaluator_errors": [],
        "scores": [score.model_dump(mode="json")],
        "gates": [],
        "failed_metric_ids": [],
    }
    atomic_write_json(experiments_dir(repo) / "exp-ok" / "cases" / "ok.json", payload)
    with pytest.raises(DiagnoseError) as ei:
        diagnose(repo, experiment_id="exp-ok", case_id="ok")
    assert ei.value.exit_code == 2


# --------------------------------------------------------------------------
# issue list / show / transitions
# --------------------------------------------------------------------------


def test_issue_list_and_show(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    listed = list_issues(failing_repo)
    assert listed["issue_count"] == 1
    assert listed["issues"][0]["issue_id"] == created["issue_id"]
    shown = show_issue(failing_repo, issue_id=created["issue_id"])
    assert shown["issue"]["fingerprint"] == created["fingerprint"]


def test_issue_list_status_filter(failing_repo: Path) -> None:
    diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")
    assert list_issues(failing_repo, status="open")["issue_count"] == 1
    assert list_issues(failing_repo, status="resolved")["issue_count"] == 0


def test_show_missing_issue_fails_closed(failing_repo: Path) -> None:
    with pytest.raises(DiagnoseError) as ei:
        show_issue(failing_repo, issue_id="issue-doesnotexist")
    assert ei.value.exit_code == 2


def test_resolve_requires_evidence(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    with pytest.raises(DiagnoseError) as ei:
        transition_issue(failing_repo, issue_id=created["issue_id"], target="resolved")
    assert ei.value.exit_code == 2
    assert "resolution evidence" in str(ei.value).lower()


def test_suppress_requires_reason(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    with pytest.raises(DiagnoseError) as ei:
        transition_issue(failing_repo, issue_id=created["issue_id"], target="suppressed")
    assert ei.value.exit_code == 2


def test_resolve_with_evidence_persists_and_validates(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    result = transition_issue(
        failing_repo,
        issue_id=created["issue_id"],
        target="resolved",
        resolution_evidence="fixed by PR #999; green on re-run",
    )
    assert result["transitioned"] is True
    assert result["from"] == "open"
    assert result["to"] == "resolved"
    assert result["issue"]["status"] == "resolved"
    assert result["issue"]["resolution_evidence"].startswith("fixed by PR")


def test_illegal_transition_fails_closed(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    # open -> reopened is not in the closed matrix.
    with pytest.raises(DiagnoseError) as ei:
        transition_issue(failing_repo, issue_id=created["issue_id"], target="reopened")
    assert ei.value.exit_code == 2
    assert "illegal transition" in str(ei.value).lower()


def test_resolved_then_reopen_then_resolvable(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    iid = created["issue_id"]
    transition_issue(failing_repo, issue_id=iid, target="resolved", resolution_evidence="done")
    reopened = transition_issue(failing_repo, issue_id=iid, target="reopened")
    assert reopened["issue"]["status"] == "reopened"
    # reopened -> resolved is allowed (with fresh evidence).
    again = transition_issue(failing_repo, issue_id=iid, target="resolved", resolution_evidence="re-fixed")
    assert again["issue"]["status"] == "resolved"


def test_transition_is_idempotent_noop(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    iid = created["issue_id"]
    transition_issue(failing_repo, issue_id=iid, target="resolved", resolution_evidence="done")
    # Resolving an already-resolved issue is a no-op success (idempotent).
    noop = transition_issue(failing_repo, issue_id=iid, target="resolved", resolution_evidence="done again")
    assert noop["transitioned"] is False
    assert noop["issue"]["status"] == "resolved"


def test_invalid_issue_id_rejected(failing_repo: Path) -> None:
    with pytest.raises(DiagnoseError) as ei:
        show_issue(failing_repo, issue_id="../escape")
    assert ei.value.exit_code == 2


def test_suppress_records_reason_in_notes(failing_repo: Path) -> None:
    created = diagnose(failing_repo, experiment_id="exp-a", case_id="case-fail")["issue"]
    result = transition_issue(
        failing_repo,
        issue_id=created["issue_id"],
        target="suppressed",
        reason="known flaky fixture; tracked separately",
    )
    assert result["issue"]["status"] == "suppressed"
    assert "suppressed:" in result["issue"]["notes"]


def test_diagnose_masks_secret_bearing_title_notes_and_store_row(failing_repo: Path) -> None:
    """S6-C08: diagnose free-text + store rows never keep raw tokens/prefixes."""
    secret = "sk-test-secret-token-value-0123456789"
    result = diagnose(
        failing_repo,
        experiment_id="exp-a",
        case_id="case-fail",
        title=f"leak title {secret}",
        owner=f"owner-{secret}",
        notes=f"api_key={secret}",
    )
    issue = result["issue"]
    blob = json.dumps(result, ensure_ascii=False)
    assert secret not in blob
    assert "sk-test" not in blob
    assert "•••[len=" in blob

    on_disk = json.loads((issues_dir(failing_repo) / f"{issue['issue_id']}.json").read_text("utf-8"))
    disk_blob = json.dumps(on_disk, ensure_ascii=False)
    assert secret not in disk_blob
    assert "sk-test" not in disk_blob
    assert "•••[len=" in disk_blob
