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


def test_bound_human_score_names_match_feedback_definitions() -> None:
    """Review UX human.* names stay 1:1 with the Tier-1 Feedback Definition map."""
    from git_cg.eval.feedback_definitions import HUMAN_SCORES
    from git_cg.eval.review_queue import BOUND_HUMAN_SCORE_NAMES

    assert set(BOUND_HUMAN_SCORE_NAMES) == set(HUMAN_SCORES)


def test_enqueue_rejects_raw_diff_annotation_keys(repo: Path) -> None:
    """Malformed annotation: raw diff bodies are rejected (metadata/reference only)."""
    from git_cg.eval.review_queue import _reject_raw_annotation_payload

    with pytest.raises(ReviewQueueError) as ei:
        _reject_raw_annotation_payload(
            {"notes": "ok", "diff_body": "@@ -1 +1 @@\n-secret patch"},
            where="enqueue",
        )
    assert ei.value.exit_code == 2
    assert "diff_body" in str(ei.value)


def test_enqueue_schema_rejects_unknown_annotation_fields(repo: Path) -> None:
    """human_review_v1 additionalProperties=false rejects raw diff smuggling."""
    from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
    from git_cg.eval.review_queue import SCHEMA_VERSION, _validate_human_review

    bad = {
        "schema_version": SCHEMA_VERSION,
        "id": "hr-malformed01",
        "review_id": "hr-malformed01",
        "authority": "advisory",
        "redaction_profile": "meta_eval_scrub",
        "scores": {"human.craft_rating": 3},
        "schema_pack": schema_pack_pin(),
        "metric_catalog": metric_catalog_pin(),
        "diff_body": "@@ raw diff not allowed @@",
    }
    with pytest.raises(ReviewQueueError) as ei:
        _validate_human_review(bad)
    assert ei.value.exit_code == 4


def test_claim_rejects_duplicate_overclaim(repo: Path) -> None:
    """Second operator cannot over-claim an already in_review row."""
    rid = enqueue(repo, case_id="case-1", reviewer="rev-1")["item"]["review_id"]
    first = claim(repo, review_id=rid, reviewer="rev-1")
    assert first["changed"] is True
    again = claim(repo, review_id=rid, reviewer="rev-1")
    assert again["changed"] is False
    with pytest.raises(ReviewQueueError) as ei:
        claim(repo, review_id=rid, reviewer="rev-2")
    assert ei.value.exit_code == 2
    assert "illegal claim" in str(ei.value)


def test_claim_contention_lock_rejects_concurrent_second_writer(repo: Path) -> None:
    """Held .claim lock fails closed for a concurrent second claim attempt."""
    from git_cg.eval.review_queue import _acquire_claim_lock, _claim_lock_path, _release_claim_lock

    rid = enqueue(repo, case_id="case-lock", reviewer="rev-1")["item"]["review_id"]
    lock = _acquire_claim_lock(repo, rid, "rev-1")
    try:
        assert lock == _claim_lock_path(repo, rid)
        assert lock.is_file()
        with pytest.raises(ReviewQueueError) as ei:
            claim(repo, review_id=rid, reviewer="rev-2")
        assert ei.value.exit_code == 2
        assert "contention" in str(ei.value).lower()
        shown = show_review(repo, review_id=rid)
        assert shown["item"]["status"] == STATUS_PENDING
    finally:
        _release_claim_lock(lock)
    claimed = claim(repo, review_id=rid, reviewer="rev-1")
    assert claimed["item"]["status"] == STATUS_IN_REVIEW
    assert claimed["item"]["claimed_by"] == "rev-1"
    assert not _claim_lock_path(repo, rid).exists()


def test_atomic_queue_row_write_is_replace_based(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Queue row persistence goes through atomic_write_json (temp + os.replace)."""
    import git_cg.eval.binding.paths as paths

    calls: list[Path] = []
    original = paths.atomic_write_json

    def _spy(path: Path, payload: dict) -> Path:
        calls.append(Path(path))
        return original(path, payload)

    monkeypatch.setattr(paths, "atomic_write_json", _spy)
    result = enqueue(repo, case_id="case-atomic", reviewer="rev-1")
    rid = result["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="approve_promote")
    assert calls, "expected atomic_write_json to be used for queue row writes"
    assert all(p.suffix == ".json" for p in calls)
    on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert on_disk["status"] == STATUS_ADJUDICATED
    validate_instance("human_review_v1", on_disk["review"])


# --- H65: mask-before-persist law (never restore raw after masking) -----------


def test_enqueue_notes_never_store_raw_secret_shapes(repo: Path) -> None:
    """H65: enqueue notes mask known secret shapes before persist."""
    tokens = [
        "sk-live-H65probeTokenABCDEFGHIJKLMNOP",
        "ghp_H65probeTokenABCDEFGHIJKLMNOPQRSTUVWXYZ12",
        "Bearer eyJhbGciOiJIUzI1NiJ9.aGVsbG93b3JsZA.signature1234",
        "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature",
        "api_key=h65secretvalue",
    ]
    for i, token in enumerate(tokens):
        result = enqueue(repo, case_id=f"case-mask-{i}", reviewer="rev-1", notes=f"found {token} here")
        notes = result["item"]["review"]["notes"]
        assert "•••" in notes, f"expected masked sentinel in notes for token shape {i}"
        assert token not in notes, f"raw token must not appear in persisted notes (shape {i})"
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


def test_mask_optional_operator_text_never_restores_raw_on_falsy_mask(monkeypatch) -> None:
    """H65: if masking returns falsy, persist redacted empty — never raw input."""
    from git_cg.eval import evidence_scrub

    monkeypatch.setattr(evidence_scrub, "mask_secrets_in_text", lambda _value: "")
    raw = "sk-live-H65probeTokenABCDEFGHIJKLMNOP"
    masked = evidence_scrub.mask_optional_operator_text(raw)
    assert masked == ""


def test_mask_secrets_in_text_returns_nonempty_for_nonempty_secret_input() -> None:
    """H65: mask_secrets_in_text returns a non-empty projection for secret input."""
    from git_cg.eval.evidence_scrub import mask_secrets_in_text

    secret_inputs = [
        "sk-live-H65probeTokenABCDEFGHIJKLMNOP",
        "ghp_H65probeTokenABCDEFGHIJKLMNOPQRSTUVWXYZ12",
        "Bearer eyJhbGciOiJIUzI1NiJ9.aGVsbG93b3JsZA.signature1234",
        "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature",
        "api_key=h65secretvalue",
        "password=supersecretpassword123",
        "token: abcdefgh12345678",
    ]
    for value in secret_inputs:
        masked = mask_secrets_in_text(value)
        assert masked, f"mask_secrets_in_text returned falsy for non-empty secret input: {value!r}"
        assert value not in masked, f"raw secret must not survive masking: {value!r}"


def test_bearer_jwt_short_segment_is_masked(repo: Path) -> None:
    """H65: short-segment Bearer JWTs are masked before persist."""
    from git_cg.eval.evidence_scrub import mask_secrets_in_text

    short_jwt = "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature"
    masked = mask_secrets_in_text(short_jwt)
    assert short_jwt not in (masked or "")
    assert "•••" in (masked or "")

    result = enqueue(
        repo,
        case_id="case-short-jwt",
        reviewer="rev-1",
        notes=f"token={short_jwt}",
    )
    notes = result["item"]["review"]["notes"]
    assert short_jwt not in notes
    assert "•••" in notes
    on_disk = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert short_jwt not in json.dumps(on_disk)
