"""Slice 6 ``eval promote`` state machine law (Issue #246 / §18.8 / INT-20/44).

* Closed destinations after scrubbed_candidate.
* Required provenance/source/thread/trace/owner/label/destination/redaction/split.
* Explicit denial taxonomy (no silent gold, no popularity gold, no human-sole gold,
  synthetic Expand-with-AI requires quarantine, antipattern ∉ positive).
* split_group_id contamination check.
* Optional dry-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import acceptpath_bundles_dir, atomic_write_json
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.promote import (
    DENY_ANTIPATTERN_POSITIVE,
    DENY_HUMAN_SOLE_GOLD,
    DENY_MISSING_FIELD,
    DENY_POPULARITY_GOLD,
    DENY_SILENT_GOLD,
    DENY_SPLIT_CONTAMINATION,
    DENY_SYNTHETIC_UNQUARANTINED,
    DEST_FIXTURE_LANE_A,
    DEST_HARD_NEGATIVE,
    DEST_OBSERVABILITY_FIXTURE,
    DEST_QUARANTINE,
    PromoteError,
    promote,
)
from git_cg.eval.review_queue import adjudicate, claim, enqueue


def _bundle(**over) -> dict:
    base = {
        "schema_version": "ape_bundle_v1",
        "case_id": "case-src-1",
        "artifact_class": "final_accept",
        "bound": True,
        "session_thread_id": "thread-src-1",
        "final_message": "docs(eval): freeze schema pack\n",
        "provenance_label": "final_accept",
        "redaction_profile": "default_scrub",
        "regime": "A",
        "path_class_gate": "docs_only",
        "generation_task_input": {
            "diff_summary": "docs only",
            "path_class_gate": "docs_only",
            "ranked_intent_id": "documentation_update",
        },
        "failure_ids": ["EVAL_TOPOLOGY"],
        "meta": {
            "binding": {"trace_id": "trace-src-1", "state": "bound"},
            "split_group_id": "sg:thread-src-1",
        },
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
    }
    base.update(over)
    return base


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def _seed(repo: Path, bundle: dict | None = None, stem: str = "thread-src-1") -> Path:
    b = bundle or _bundle()
    path = acceptpath_bundles_dir(repo) / f"{stem}.json"
    atomic_write_json(path, b)
    return path


def _ok_kwargs(**over) -> dict:
    base = {
        "bundle": "thread-src-1",
        "destination": DEST_OBSERVABILITY_FIXTURE,
        "owner": "owner-1",
        "label": "observability_candidate",
        "provenance": "diag_issue",
        "redaction_profile": "default_scrub",
    }
    base.update(over)
    return base


def test_promote_happy_path_writes_decision(repo: Path) -> None:
    _seed(repo)
    result = promote(repo, **_ok_kwargs())
    assert result["accepted"] is True
    decision = result["decision"]
    assert decision["destination"] == DEST_OBSERVABILITY_FIXTURE
    assert decision["split_group_id"] == "sg:thread-src-1"
    assert decision["source"]["trace_id"] == "trace-src-1"
    assert decision["source"]["session_thread_id"] == "thread-src-1"
    assert Path(result["decision_path"]).is_file()
    assert Path(result["artifact_path"]).is_file()
    on_disk = json.loads(Path(result["decision_path"]).read_text(encoding="utf-8"))
    assert on_disk["promotion_id"] == decision["promotion_id"]


def test_promote_dry_run_no_write(repo: Path) -> None:
    _seed(repo)
    result = promote(repo, **_ok_kwargs(dry_run=True))
    assert result["dry_run"] is True
    assert not Path(result["decision_path"]).exists()


def test_promote_missing_required_fields(repo: Path) -> None:
    _seed(repo)
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            bundle="thread-src-1",
            destination=DEST_QUARANTINE,
            owner="",
            label="x",
            provenance="y",
            redaction_profile="default_scrub",
        )
    assert ei.value.denial_reason == DENY_MISSING_FIELD


def test_promote_requires_thread_and_trace(repo: Path) -> None:
    _seed(repo, _bundle(session_thread_id=None, meta={"binding": {}}))
    # Remove session_thread_id key entirely
    path = acceptpath_bundles_dir(repo) / "thread-src-1.json"
    b = _bundle()
    del b["session_thread_id"]
    b["meta"] = {"binding": {}}
    atomic_write_json(path, b)
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs())
    assert ei.value.denial_reason == DENY_MISSING_FIELD


def test_deny_popularity_gold(repo: Path) -> None:
    _seed(repo)
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                label="gold",
                popularity_signal=True,
                destination=DEST_FIXTURE_LANE_A,
            ),
        )
    assert ei.value.denial_reason == DENY_POPULARITY_GOLD


def test_deny_silent_gold_label(repo: Path) -> None:
    _seed(repo)
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(label="golden", destination=DEST_FIXTURE_LANE_A))
    assert ei.value.denial_reason in {DENY_SILENT_GOLD, DENY_HUMAN_SOLE_GOLD}


def test_deny_human_sole_gold_with_review(repo: Path) -> None:
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1")["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="approve_promote")
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                label="gold",
                destination=DEST_FIXTURE_LANE_A,
                review_id=rid,
                provenance="human_review",
            ),
        )
    assert ei.value.denial_reason in {DENY_HUMAN_SOLE_GOLD, DENY_SILENT_GOLD}


def test_deny_synthetic_without_quarantine(repo: Path) -> None:
    b = _bundle()
    b["meta"]["synthetic"] = True
    b["meta"]["expand_with_ai"] = True
    _seed(repo, b)
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(destination=DEST_FIXTURE_LANE_A, label="candidate"))
    assert ei.value.denial_reason == DENY_SYNTHETIC_UNQUARANTINED
    # quarantine allowed
    ok = promote(repo, **_ok_kwargs(destination=DEST_QUARANTINE, label="candidate"))
    assert ok["accepted"] is True


def test_deny_antipattern_positive(repo: Path) -> None:
    _seed(repo)
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(label="antipattern_example", destination=DEST_FIXTURE_LANE_A),
        )
    assert ei.value.denial_reason == DENY_ANTIPATTERN_POSITIVE
    ok = promote(repo, **_ok_kwargs(label="antipattern_example", destination=DEST_HARD_NEGATIVE))
    assert ok["accepted"] is True


def test_split_group_contamination(repo: Path) -> None:
    _seed(repo)
    first = promote(repo, **_ok_kwargs(destination=DEST_OBSERVABILITY_FIXTURE, label="obs-1"))
    assert first["accepted"] is True
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(destination=DEST_HARD_NEGATIVE, label="neg-1"))
    assert ei.value.denial_reason == DENY_SPLIT_CONTAMINATION


def test_invalid_destination(repo: Path) -> None:
    _seed(repo)
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(destination="gold_final"))
    assert ei.value.exit_code == 2
