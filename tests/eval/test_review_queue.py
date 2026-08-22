"""Slice 6 local HITL review queue law (Issue #246 / R4 / §7.2.7).

* Atomic writes under ``.eval/review_queue/``.
* Nested payload validates as frozen ``human_review_v1``.
* Lifecycle: pending → in_review → {adjudicated|dismissed}.
* Authority always advisory; adjudication emits typed outcome_ref.
* Review never writes fixtures/gold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import review_queue_dir
from git_cg.eval.review_queue import (
    STATUS_ADJUDICATED,
    STATUS_DISMISSED,
    STATUS_IN_REVIEW,
    STATUS_PENDING,
    TRANSITIONS,
    ReviewQueueError,
    adjudicate,
    claim,
    dismiss,
    enqueue,
    list_reviews,
    show_review,
)
from git_cg.eval.schema_pack import validate_instance


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_transition_matrix_closed() -> None:
    assert TRANSITIONS[STATUS_PENDING] == frozenset({STATUS_IN_REVIEW, STATUS_DISMISSED})
    assert TRANSITIONS[STATUS_IN_REVIEW] == frozenset({STATUS_ADJUDICATED, STATUS_DISMISSED, STATUS_PENDING})
    assert TRANSITIONS[STATUS_ADJUDICATED] == frozenset()
    assert TRANSITIONS[STATUS_DISMISSED] == frozenset()


def test_enqueue_writes_schema_valid_human_review(repo: Path) -> None:
    result = enqueue(
        repo,
        case_id="case-1",
        bundle_id="bundle-1",
        reviewer="reviewer-opaque-01",
        craft_rating=4,
        gold_dispute=False,
        regime_label="A",
        notes="advisory only",
    )
    item = result["item"]
    assert item["status"] == STATUS_PENDING
    review = item["review"]
    validate_instance("human_review_v1", review)
    assert review["authority"] == "advisory"
    assert review["scores"]["human.craft_rating"] == 4
    assert review["scores"]["human.gold_dispute"] is False
    assert review["scores"]["human.regime_label"] == "A"
    on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert on_disk["review_id"] == item["review_id"]
    assert Path(result["path"]).parent == review_queue_dir(repo)


def test_enqueue_rejects_email_reviewer(repo: Path) -> None:
    with pytest.raises(ReviewQueueError) as ei:
        enqueue(repo, case_id="c1", reviewer="user@example.com")
    assert ei.value.exit_code == 2


def test_claim_adjudicate_lifecycle(repo: Path) -> None:
    created = enqueue(repo, case_id="case-1", reviewer="rev-1")
    rid = created["item"]["review_id"]

    claimed = claim(repo, review_id=rid, reviewer="rev-1")
    assert claimed["item"]["status"] == STATUS_IN_REVIEW
    assert claimed["item"]["claimed_by"] == "rev-1"

    adj = adjudicate(
        repo,
        review_id=rid,
        outcome="approve_promote",
        destination_hint="observability_fixture",
        notes="looks like a good fixture candidate",
    )
    assert adj["item"]["status"] == STATUS_ADJUDICATED
    assert adj["outcome_ref"].startswith(f"review_outcome:{rid}:")
    assert adj["item"]["adjudication"]["authority"] == "advisory"
    # No gold/fixture files written by review itself.
    assert not (repo / ".eval" / "index" / "fixture_lane_a_candidates").exists()


def test_dismiss_from_pending(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-1", reviewer="rev-1")["item"]["review_id"]
    result = dismiss(repo, review_id=rid, reason="duplicate")
    assert result["item"]["status"] == STATUS_DISMISSED


def test_illegal_adjudicate_from_pending(repo: Path) -> None:
    rid = enqueue(repo, case_id="case-1", reviewer="rev-1")["item"]["review_id"]
    with pytest.raises(ReviewQueueError) as ei:
        adjudicate(repo, review_id=rid, outcome="approve_promote")
    assert ei.value.exit_code == 2


def test_list_and_show(repo: Path) -> None:
    a = enqueue(repo, case_id="case-a", reviewer="rev-1")["item"]["review_id"]
    b = enqueue(repo, case_id="case-b", reviewer="rev-2")["item"]["review_id"]
    claim(repo, review_id=b, reviewer="rev-2")
    listed = list_reviews(repo)
    assert listed["review_count"] == 2
    pending = list_reviews(repo, status=STATUS_PENDING)
    assert pending["review_count"] == 1
    assert pending["reviews"][0]["review_id"] == a
    shown = show_review(repo, review_id=a)
    assert shown["item"]["review"]["case_id"] == "case-a"


def test_dry_run_enqueue_no_write(repo: Path) -> None:
    result = enqueue(repo, case_id="case-1", reviewer="rev-1", dry_run=True)
    assert result["dry_run"] is True
    assert not Path(result["path"]).exists()
