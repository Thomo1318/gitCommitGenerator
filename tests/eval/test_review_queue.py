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
    rollup_reviews,
    show_review,
)
from git_cg.eval.schema_pack import validate_instance


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Return a tmp dir seeded with a ``.git`` marker so queue paths resolve."""
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_transition_matrix_closed() -> None:
    """Assert the review lifecycle transition map is closed and matches §7.2.7 law."""
    assert TRANSITIONS[STATUS_PENDING] == frozenset({STATUS_IN_REVIEW, STATUS_DISMISSED})
    assert TRANSITIONS[STATUS_IN_REVIEW] == frozenset({STATUS_ADJUDICATED, STATUS_DISMISSED, STATUS_PENDING})
    assert TRANSITIONS[STATUS_ADJUDICATED] == frozenset()
    assert TRANSITIONS[STATUS_DISMISSED] == frozenset()


def test_enqueue_writes_schema_valid_human_review(repo: Path) -> None:
    """Enqueue persists a frozen ``human_review_v1`` payload with advisory authority."""
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
    """Reviewer identifiers must be opaque: an email raises ``ReviewQueueError`` (exit 2)."""
    with pytest.raises(ReviewQueueError) as ei:
        enqueue(repo, case_id="c1", reviewer="user@example.com")
    assert ei.value.exit_code == 2


def test_claim_adjudicate_lifecycle(repo: Path) -> None:
    """Full pending→in_review→adjudicated path emits typed outcome_ref and never writes fixtures."""
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
    """Dismissing straight from pending is a legal terminal transition."""
    rid = enqueue(repo, case_id="case-1", reviewer="rev-1")["item"]["review_id"]
    result = dismiss(repo, review_id=rid, reason="duplicate")
    assert result["item"]["status"] == STATUS_DISMISSED


def test_illegal_adjudicate_from_pending(repo: Path) -> None:
    """Adjudicating from pending (skipping claim) is rejected with exit 2."""
    rid = enqueue(repo, case_id="case-1", reviewer="rev-1")["item"]["review_id"]
    with pytest.raises(ReviewQueueError) as ei:
        adjudicate(repo, review_id=rid, outcome="approve_promote")
    assert ei.value.exit_code == 2


def test_list_and_show(repo: Path) -> None:
    """List honours status filters and show returns the full stored review item."""
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
    """``dry_run=True`` returns the would-be item without touching the queue on disk."""
    result = enqueue(repo, case_id="case-1", reviewer="rev-1", dry_run=True)
    assert result["dry_run"] is True
    assert not Path(result["path"]).exists()


def test_rollup_multi_rater_dimensions_and_disagreement(repo: Path) -> None:
    """Multi-rater rollup aggregates dimensions, flags disagreement, and stays non-sole-promote."""
    a = enqueue(
        repo,
        case_id="case-1",
        reviewer="r1",
        craft_rating=2.0,
        gold_dispute=True,
        regime_label="A",
    )
    b = enqueue(
        repo,
        case_id="case-1",
        reviewer="r2",
        craft_rating=5.0,
        gold_dispute=False,
        regime_label="B",
    )
    # third reviewer tilts dispute majority true + regime split remains if 1 each then third
    enqueue(
        repo,
        case_id="case-1",
        reviewer="r3",
        craft_rating=4.0,
        gold_dispute=True,
        regime_label="A",
    )
    claim(repo, review_id=a["item"]["review_id"], reviewer="r1")
    adjudicate(repo, review_id=a["item"]["review_id"], outcome="approve_promote", adjudicator="r1")
    claim(repo, review_id=b["item"]["review_id"], reviewer="r2")
    adjudicate(repo, review_id=b["item"]["review_id"], outcome="reject", adjudicator="r2")

    data = rollup_reviews(repo, case_id="case-1")
    assert data["authority"] == "advisory"
    assert data["can_sole_promote_gold"] is False
    assert data["rollup_count"] == 1
    row = data["rollups"][0]
    assert row["target_kind"] == "case_id"
    assert row["target_id"] == "case-1"
    assert row["reviewer_count"] == 3
    assert row["can_sole_promote_gold"] is False
    craft = row["dimensions"]["human.craft_rating"]
    assert craft["disagreement"] is True
    assert craft["min"] == 2.0
    assert craft["max"] == 5.0
    assert row["dimensions"]["human.gold_dispute"]["majority"] == "true"
    assert row["dimensions"]["human.regime_label"]["majority"] == "A"
    assert row["outcomes"]["majority"] == "split"


def test_rollup_empty_queue(repo: Path) -> None:
    """An empty queue rolls up to a zero-count, empty-list advisory result."""
    data = rollup_reviews(repo)
    assert data["rollup_count"] == 0
    assert data["rollups"] == []


# --- H65: secret-mask fallback law (mask_secrets_in_text(...) or raw) ---------


def test_enqueue_notes_never_store_raw_when_mask_returns_nonempty(repo: Path) -> None:
    """H65: mask_secrets_in_text fallback must never store raw for known secret shapes.

    The ``or notes.strip()`` fallback in enqueue/adjudicate fires only when the
    mask returns a falsy value. For every probed secret shape the mask returns
    ``•••[len=N]`` (non-empty), so the fallback never stores raw. This test
    pins that contract against regression.

    NOTE: Bearer JWT uses a long-segment payload (>=10 chars) to match the
    current ``_SECRET_VALUE_PATTERNS`` regex. Short-segment JWTs (e.g.
    ``eyJ…h65probe.signature`` with a 4-char middle) are NOT masked — see
    ``test_bearer_jwt_short_segment_gap_finding`` below.
    """
    tokens = [
        "sk-live-H65probeTokenABCDEFGHIJKLMNOP",
        "ghp_H65probeTokenABCDEFGHIJKLMNOPQRSTUVWXYZ12",
        "Bearer eyJhbGciOiJIUzI1NiJ9.aGVsbG93b3JsZA.signature1234",
        "api_key=h65secretvalue",
    ]
    for i, token in enumerate(tokens):
        result = enqueue(repo, case_id=f"case-mask-{i}", reviewer="rev-1", notes=f"found {token} here")
        notes = result["item"]["review"]["notes"]
        assert "•••" in notes, f"expected masked sentinel in notes for token shape {i}"
        assert token not in notes, f"raw token must not appear in persisted notes (shape {i})"
        # persisted on disk must also be masked
        on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
        assert token not in json.dumps(on_disk), f"raw token must not appear anywhere in persisted JSON (shape {i})"


def test_adjudicate_notes_and_destination_hint_masked(repo: Path) -> None:
    """H65: adjudicate notes and destination_hint are masked before persist."""
    token = "sk-live-H65probeTokenABCDEFGHIJKLMNOP"
    ghp = "ghp_H65probeTokenABCDEFGHIJKLMNOPQRSTUVWXYZ12"
    rid = enqueue(repo, case_id="case-adj-mask", reviewer="rev-1")["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    result = adjudicate(
        repo,
        review_id=rid,
        outcome="approve_promote",
        notes=f"approved with {token}",
        destination_hint=f"hard_negative {ghp}",
    )
    on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    adj = on_disk["adjudication"]
    assert token not in adj["notes"]
    assert "•••" in adj["notes"]
    assert ghp not in adj["destination_hint"]
    assert "•••" in adj["destination_hint"]


def test_mask_secrets_in_text_returns_nonempty_for_nonempty_secret_input() -> None:
    """H65: mask_secrets_in_text must never return a falsy value for non-empty secret input.

    If it ever does, the ``or notes.strip()`` fallback in review_queue would
    store the raw secret. Pin the non-empty contract directly.

    NOTE: Bearer JWT uses long-segment payload (>=10 chars per segment) to
    match the current regex. See short-segment gap test below.
    """
    from git_cg.eval.evidence_scrub import mask_secrets_in_text

    secret_inputs = [
        "sk-live-H65probeTokenABCDEFGHIJKLMNOP",
        "ghp_H65probeTokenABCDEFGHIJKLMNOPQRSTUVWXYZ12",
        "Bearer eyJhbGciOiJIUzI1NiJ9.aGVsbG93b3JsZA.signature1234",
        "api_key=h65secretvalue",
        "password=supersecretpassword123",
        "token: abcdefgh12345678",
    ]
    for value in secret_inputs:
        masked = mask_secrets_in_text(value)
        assert masked, f"mask_secrets_in_text returned falsy for non-empty secret input: {value!r}"
        assert value not in masked, f"raw secret must not survive masking: {value!r}"


def test_bearer_jwt_short_segment_gap_finding(repo: Path) -> None:
    """H65 FIND: Bearer JWT with short middle segment (<10 chars) is NOT masked.

    The JWT pattern ``eyJ[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}``
    requires >=10 chars per segment. Real-world JWTs (e.g. Firebase custom tokens,
    some OIDC id_tokens) can have payload segments shorter than 10 chars. These
    pass through ``mask_secrets_in_text`` unmasked and are stored raw in review
    notes — a secret-safety gap in the evidence scrub layer.

    This test documents the gap as a known FIND. It should be converted to a
    PASS assertion once the pattern is widened (e.g. ``{1,}`` on middle segment).
    """
    from git_cg.eval.evidence_scrub import mask_secrets_in_text

    short_jwt = "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature"
    masked = mask_secrets_in_text(short_jwt)
    # Document current (gap) behaviour: raw survives
    assert short_jwt in (masked or ""), (
        "H65 FIND: short-segment Bearer JWT should be masked but is not. "
        "If this assertion fails, the gap has been fixed — update this test."
    )
