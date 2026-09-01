"""Slice 6 ``eval promote`` state machine law (Issue #246 / §18.8 / INT-20/44).

* Closed destinations after scrubbed_candidate.
* Required provenance/source/thread/trace/owner/label/destination/redaction/split.
* Explicit denial taxonomy (no silent gold, no popularity gold, no human-sole gold,
  synthetic Expand-with-AI requires quarantine, antipattern ∉ positive,
  unresolved dispute, schema validation failure).
* split_group_id contamination check.
* Denied candidates remain candidate-class with denial audit rows (no fixture mint).
* Optional dry-run.
* ``decision.human_rollup`` is advisory-only evidence (never sole-gold / accept).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.paths import (
    acceptpath_bundles_dir,
    antipattern_vault_dir,
    atomic_write_json,
)
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.promote import (
    DENIAL_REASONS,
    DENY_ANTIPATTERN_POSITIVE,
    DENY_HUMAN_LEG,
    DENY_HUMAN_SOLE_GOLD,
    DENY_MISSING_FIELD,
    DENY_POPULARITY_GOLD,
    DENY_SCHEMA,
    DENY_SILENT_GOLD,
    DENY_SPLIT_CONTAMINATION,
    DENY_SYNTHETIC_UNQUARANTINED,
    DENY_UNRESOLVED_DISPUTE,
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
    assert ei.value.decision is not None
    rollup = ei.value.decision["human_rollup"]
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False


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


def test_explicit_non_synthetic_meta_is_promotable(repo: Path) -> None:
    """meta.synthetic=False must not trip the unquarantined-synthetic denial."""
    b = _bundle()
    b.setdefault("meta", {})
    b["meta"]["synthetic"] = False
    _seed(repo, b)
    ok = promote(repo, **_ok_kwargs(destination=DEST_OBSERVABILITY_FIXTURE, label="obs-non-synth"))
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


def _promotions(repo: Path) -> list[Path]:
    root = repo / ".eval" / "index" / "promotions"
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def _assert_denial_audit(exc: PromoteError, *, reason: str, repo: Path) -> dict:
    assert exc.denial_reason == reason
    assert isinstance(exc.decision, dict)
    assert exc.decision["accepted"] is False
    assert exc.decision["denial_reason"] == reason
    assert exc.decision["candidate_class"] in {"scrubbed_candidate", "quarantine_candidate"}
    assert exc.decision_path is not None
    path = Path(exc.decision_path)
    assert path.is_file()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["accepted"] is False
    assert on_disk["denial_reason"] == reason
    # Denial must not mint destination fixture/gold artifacts.
    index = repo / ".eval" / "index"
    for folder in (
        "fixture_lane_a_candidates",
        "observability_fixtures",
    ):
        d = index / folder
        if d.is_dir():
            assert list(d.glob("*.json")) == []
    hard_neg = antipattern_vault_dir(repo) / "hard_negatives"
    if hard_neg.is_dir():
        assert list(hard_neg.glob("*.json")) == []
    return on_disk


def test_deny_schema_validation_persists_candidate(repo: Path) -> None:
    """Invalid ape_bundle_v1 shape is an explicit schema denial with audit row."""
    bad = {
        "schema_version": "ape_bundle_v1",
        # required fields present but wrong types / illegal enum → schema fail
        "case_id": "case-bad-schema",
        "artifact_class": "not_a_real_class",
        "bound": "yes",
        "session_thread_id": "thread-bad-schema",
        "meta": {"binding": {"trace_id": "trace-bad-schema"}},
    }
    _seed(repo, bad, stem="thread-bad-schema")
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(bundle="thread-bad-schema"))
    _assert_denial_audit(ei.value, reason=DENY_SCHEMA, repo=repo)


def test_deny_unresolved_dispute_pending_review(repo: Path) -> None:
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1", gold_dispute=True)["item"]["review_id"]
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                destination=DEST_OBSERVABILITY_FIXTURE,
                review_id=rid,
                provenance="diag_issue",
            ),
        )
    _assert_denial_audit(ei.value, reason=DENY_UNRESOLVED_DISPUTE, repo=repo)


def test_deny_unresolved_dispute_needs_work_outcome(repo: Path) -> None:
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1", gold_dispute=True)["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="needs_work")
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                destination=DEST_OBSERVABILITY_FIXTURE,
                review_id=rid,
                provenance="diag_issue",
            ),
        )
    _assert_denial_audit(ei.value, reason=DENY_UNRESOLVED_DISPUTE, repo=repo)


def test_deny_unresolved_dispute_allows_quarantine_park(repo: Path) -> None:
    """Park destinations may still retain an open dispute (operator quarantine)."""
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1", gold_dispute=True)["item"]["review_id"]
    ok = promote(
        repo,
        **_ok_kwargs(destination=DEST_QUARANTINE, review_id=rid, provenance="diag_issue", label="parked"),
    )
    assert ok["accepted"] is True
    assert ok["decision"]["destination"] == DEST_QUARANTINE


def test_deny_popularity_gold_persists_audit_not_fixture(repo: Path) -> None:
    _seed(repo)
    before = len(_promotions(repo))
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                label="gold",
                popularity_signal=True,
                destination=DEST_FIXTURE_LANE_A,
            ),
        )
    row = _assert_denial_audit(ei.value, reason=DENY_POPULARITY_GOLD, repo=repo)
    assert len(_promotions(repo)) == before + 1
    assert row["candidate_class"] == "scrubbed_candidate"
    # No fixture_lane_a artifact minted on denial.
    fixture_dir = repo / ".eval" / "index" / "fixture_lane_a_candidates"
    assert not fixture_dir.exists() or list(fixture_dir.glob("*.json")) == []


def test_dry_run_denial_does_not_write_audit(repo: Path) -> None:
    _seed(repo)
    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                label="gold",
                popularity_signal=True,
                destination=DEST_FIXTURE_LANE_A,
                dry_run=True,
            ),
        )
    assert ei.value.denial_reason == DENY_POPULARITY_GOLD
    assert ei.value.decision is not None
    assert ei.value.decision["dry_run"] is True
    assert ei.value.decision_path is None
    assert _promotions(repo) == []


def test_s6_e09_denial_reason_set_is_closed() -> None:
    """Guard the closed named-denial taxonomy (S6-E09 + human leg)."""
    expected = {
        "missing_required_field",
        "invalid_destination",
        "invalid_stage_transition",
        "split_group_contamination",
        "silent_gold_mint_forbidden",
        "popularity_promotion_forbidden",
        "human_review_cannot_sole_promote_golden",
        "synthetic_expand_requires_quarantine",
        "antipattern_cannot_enter_positive_train",
        "schema_validation_failed",
        "source_bundle_missing",
        "provenance_invalid",
        "unresolved_dispute",
        "human_leg_not_satisfied",
    }
    assert expected == DENIAL_REASONS


def test_human_leg_approve_promote_binds_on_non_park(repo: Path) -> None:
    """adjudicate(approve_promote) satisfies the human leg on non-park promote."""
    _seed(repo)
    rid = enqueue(
        repo,
        case_id="case-src-1",
        reviewer="rev-1",
        craft_rating=4.0,
        gold_dispute=False,
        regime_label="A",
    )["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adj = adjudicate(repo, review_id=rid, outcome="approve_promote")
    result = promote(repo, **_ok_kwargs(review_id=rid, provenance="diag_issue"))
    assert result["accepted"] is True
    decision = result["decision"]
    leg = decision["human_leg"]
    assert leg["satisfied"] is True
    assert leg["review_id"] == rid
    assert leg["outcome"] == "approve_promote"
    assert leg["outcome_ref"] == adj["outcome_ref"]
    assert leg["authority"] == "advisory"
    assert leg["can_sole_promote_gold"] is False
    assert leg["scores_are_accept_authority"] is False
    assert set(leg["score_names"]) == {
        "human.craft_rating",
        "human.gold_dispute",
        "human.regime_label",
    }
    assert decision["review_id"] == rid
    assert decision["review_authority"] == "advisory"
    assert decision["review_outcome_ref"] == adj["outcome_ref"]


def test_human_leg_reject_blocks_non_park(repo: Path) -> None:
    """reject adjudication does not satisfy the human leg on non-park destinations."""
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1")["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="reject")
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(review_id=rid, provenance="diag_issue"))
    _assert_denial_audit(ei.value, reason=DENY_HUMAN_LEG, repo=repo)
    leg = ei.value.decision["human_leg"]
    assert leg["satisfied"] is False
    assert leg["outcome"] == "reject"
    assert leg["can_sole_promote_gold"] is False


def test_human_leg_needs_work_blocks_non_park(repo: Path) -> None:
    """needs_work is defer/override, not the accept leg."""
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1")["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="needs_work")
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(review_id=rid))
    assert ei.value.denial_reason == DENY_HUMAN_LEG


def test_human_leg_pending_still_unresolved_before_leg(repo: Path) -> None:
    """Open lifecycle remains unresolved_dispute (pre-leg) on non-park destinations."""
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1")["item"]["review_id"]
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(review_id=rid))
    assert ei.value.denial_reason == DENY_UNRESOLVED_DISPUTE


def test_human_leg_not_required_without_review_id(repo: Path) -> None:
    """Promote without --review-id does not invent a human-leg requirement."""
    _seed(repo)
    result = promote(repo, **_ok_kwargs())
    assert result["accepted"] is True
    assert "human_leg" not in result["decision"]


def test_human_leg_park_allows_non_approve(repo: Path) -> None:
    """Park destinations may retain non-approve reviews (operator quarantine)."""
    _seed(repo)
    rid = enqueue(repo, case_id="case-src-1", reviewer="rev-1")["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="reject")
    ok = promote(
        repo,
        **_ok_kwargs(destination=DEST_QUARANTINE, review_id=rid, label="parked"),
    )
    assert ok["accepted"] is True
    assert ok["decision"]["human_leg"]["satisfied"] is False
    assert ok["decision"]["human_leg"]["outcome"] == "reject"


def test_human_sole_gold_still_denied_with_satisfied_leg(repo: Path) -> None:
    """Satisfied human leg never escalates into sole-gold authority."""
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
    assert ei.value.decision is not None
    assert ei.value.decision["human_leg"]["satisfied"] is True
    assert ei.value.decision["human_leg"]["can_sole_promote_gold"] is False
    rollup = ei.value.decision["human_rollup"]
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False
    assert rollup["scores_are_accept_authority"] is False


def test_human_rollup_attached_on_accept_case_keyed(repo: Path) -> None:
    """Promote attaches case-keyed rollup_reviews as decision.human_rollup."""
    _seed(repo)
    a = enqueue(
        repo,
        case_id="case-src-1",
        reviewer="rev-1",
        craft_rating=4.0,
        gold_dispute=False,
        regime_label="A",
    )
    b = enqueue(
        repo,
        case_id="case-src-1",
        reviewer="rev-2",
        craft_rating=5.0,
        gold_dispute=False,
        regime_label="A",
    )
    rid = a["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="approve_promote", adjudicator="rev-1")
    claim(repo, review_id=b["item"]["review_id"], reviewer="rev-2")
    adjudicate(
        repo,
        review_id=b["item"]["review_id"],
        outcome="approve_promote",
        adjudicator="rev-2",
    )

    result = promote(repo, **_ok_kwargs(review_id=rid, provenance="diag_issue"))
    assert result["accepted"] is True
    rollup = result["decision"]["human_rollup"]
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False
    assert rollup["scores_are_accept_authority"] is False
    assert rollup["source_case_id"] == "case-src-1"
    assert rollup["filters"]["case_id"] == "case-src-1"
    assert rollup["filters"]["bundle_id"] is None
    assert rollup["rollup_count"] == 1
    row = rollup["rollups"][0]
    assert row["target_kind"] == "case_id"
    assert row["target_id"] == "case-src-1"
    assert row["reviewer_count"] == 2
    assert row["authority"] == "advisory"
    assert row["can_sole_promote_gold"] is False
    assert row["outcomes"]["majority"] == "approve_promote"
    on_disk = json.loads(Path(result["decision_path"]).read_text(encoding="utf-8"))
    assert on_disk["human_rollup"]["authority"] == "advisory"
    assert on_disk["human_rollup"]["can_sole_promote_gold"] is False


def test_human_rollup_bundle_keyed_fallback(repo: Path) -> None:
    """Bundle-only queue rows still attach via session_thread_id fallback."""
    _seed(repo)
    rid = enqueue(
        repo,
        bundle_id="thread-src-1",
        reviewer="rev-1",
        craft_rating=3.0,
        gold_dispute=False,
        regime_label="B",
    )["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="approve_promote")

    result = promote(repo, **_ok_kwargs(review_id=rid, provenance="diag_issue"))
    assert result["accepted"] is True
    rollup = result["decision"]["human_rollup"]
    assert rollup["source_case_id"] == "case-src-1"
    assert rollup["source_bundle_id"] == "thread-src-1"
    assert rollup["filters"]["case_id"] is None
    assert rollup["filters"]["bundle_id"] == "thread-src-1"
    assert rollup["rollup_count"] == 1
    row = rollup["rollups"][0]
    assert row["target_kind"] == "bundle_id"
    assert row["target_id"] == "thread-src-1"
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False


def test_human_rollup_empty_queue_still_advisory(repo: Path) -> None:
    """No queue rows → empty advisory rollup evidence, never missing authority stamps."""
    _seed(repo)
    result = promote(repo, **_ok_kwargs())
    assert result["accepted"] is True
    rollup = result["decision"]["human_rollup"]
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False
    assert rollup["scores_are_accept_authority"] is False
    assert rollup["rollup_count"] == 0
    assert rollup["rollups"] == []
    assert rollup["source_case_id"] == "case-src-1"


def test_majority_approve_promote_rollup_cannot_sole_promote_gold(repo: Path) -> None:
    """Majority approve_promote rollup still cannot sole-promote golden."""
    _seed(repo)
    reviews = []
    for i, rating in enumerate((4.0, 5.0, 4.5), start=1):
        item = enqueue(
            repo,
            case_id="case-src-1",
            reviewer=f"rev-{i}",
            craft_rating=rating,
            gold_dispute=False,
            regime_label="A",
        )
        rid = item["item"]["review_id"]
        claim(repo, review_id=rid, reviewer=f"rev-{i}")
        adjudicate(repo, review_id=rid, outcome="approve_promote", adjudicator=f"rev-{i}")
        reviews.append(rid)

    with pytest.raises(PromoteError) as ei:
        promote(
            repo,
            **_ok_kwargs(
                label="gold",
                destination=DEST_FIXTURE_LANE_A,
                review_id=reviews[0],
                provenance="human_review",
            ),
        )
    assert ei.value.denial_reason == DENY_HUMAN_SOLE_GOLD
    decision = ei.value.decision
    assert decision is not None
    assert decision["human_leg"]["satisfied"] is True
    assert decision["human_leg"]["can_sole_promote_gold"] is False
    rollup = decision["human_rollup"]
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False
    assert rollup["scores_are_accept_authority"] is False
    assert rollup["rollup_count"] == 1
    row = rollup["rollups"][0]
    assert row["outcomes"]["majority"] == "approve_promote"
    assert row["reviewer_count"] == 3
    assert row["can_sole_promote_gold"] is False
    _assert_denial_audit(ei.value, reason=DENY_HUMAN_SOLE_GOLD, repo=repo)


def test_human_rollup_never_overrides_unresolved_dispute_guard(repo: Path) -> None:
    """Rollup evidence cannot bypass the unresolved-dispute deny path."""
    _seed(repo)
    done = enqueue(
        repo,
        case_id="case-src-1",
        reviewer="rev-1",
        craft_rating=5.0,
        gold_dispute=False,
        regime_label="A",
    )
    pending = enqueue(
        repo,
        case_id="case-src-1",
        reviewer="rev-2",
        craft_rating=2.0,
        gold_dispute=True,
        regime_label="B",
    )
    rid = done["item"]["review_id"]
    claim(repo, review_id=rid, reviewer="rev-1")
    adjudicate(repo, review_id=rid, outcome="approve_promote", adjudicator="rev-1")
    with pytest.raises(PromoteError) as ei:
        promote(repo, **_ok_kwargs(review_id=pending["item"]["review_id"]))
    assert ei.value.denial_reason == DENY_UNRESOLVED_DISPUTE
    rollup = ei.value.decision["human_rollup"]
    assert rollup["authority"] == "advisory"
    assert rollup["can_sole_promote_gold"] is False
    assert rollup["rollup_count"] == 1
    assert rollup["rollups"][0]["reviewer_count"] == 2


def test_promote_notes_mask_secrets_before_persist(repo: Path) -> None:
    """Promote decision notes never persist raw secret-shaped text."""
    _seed(repo)
    token = "sk-live-H65probeTokenABCDEFGHIJKLMNOP"
    short_jwt = "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature"
    result = promote(
        repo,
        **_ok_kwargs(notes=f"operator note with {token} and {short_jwt}"),
    )
    decision = result["decision"]
    notes = decision["notes"]
    assert token not in notes
    assert short_jwt not in notes
    assert "•••" in notes
    on_disk = json.loads(Path(result["decision_path"]).read_text(encoding="utf-8"))
    dumped = json.dumps(on_disk)
    assert token not in dumped
    assert short_jwt not in dumped
    assert on_disk["notes"] == notes


def test_promote_notes_mask_to_empty_never_restores_raw(repo: Path, monkeypatch) -> None:
    """Falsy mask result persists redacted empty, never raw notes."""
    from git_cg.eval import promote as promote_mod

    monkeypatch.setattr(promote_mod, "mask_optional_operator_text", lambda _value: "")
    _seed(repo)
    raw = "sk-live-H65probeTokenABCDEFGHIJKLMNOP"
    result = promote(repo, **_ok_kwargs(notes=raw))
    decision = result["decision"]
    assert decision["notes"] == ""
    on_disk = json.loads(Path(result["decision_path"]).read_text(encoding="utf-8"))
    assert on_disk["notes"] == ""
    assert raw not in json.dumps(on_disk)


def test_promote_notes_masked_on_dry_run_stdout_path(repo: Path) -> None:
    """Dry-run promote decisions mask notes before emit (no persist required)."""
    _seed(repo)
    token = "sk-live-H65probeTokenABCDEFGHIJKLMNOP"
    short_jwt = "Bearer eyJhbGciOiJIUzI1NiJ9.h65probe.signature"
    result = promote(
        repo,
        **_ok_kwargs(
            notes=f"operator note with {token} and {short_jwt}",
            dry_run=True,
        ),
    )
    assert result["dry_run"] is True
    notes = result["decision"]["notes"]
    assert token not in notes
    assert short_jwt not in notes
    assert "•••" in notes
    dumped = json.dumps(result["decision"])
    assert token not in dumped
    assert short_jwt not in dumped


def test_notes_masked_no_raw_fallback(repo: Path, monkeypatch) -> None:
    """Mask-to-empty promote notes never restore raw operator text."""
    test_promote_notes_mask_to_empty_never_restores_raw(repo, monkeypatch)


def test_hitl_enqueue_claim_adjudicate_rollup_promote_denied(repo: Path) -> None:
    """HITL composition: enqueue→claim→adjudicate→rollup cannot sole-promote gold."""
    test_majority_approve_promote_rollup_cannot_sole_promote_gold(repo)
