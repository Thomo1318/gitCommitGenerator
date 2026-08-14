"""FIND-026 — empty/oversize input short-circuit + bounded fan-out."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring import score_bundle

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def _empty_bundle() -> dict:
    """Valid bundle mutated to empty final message (FIND-026 empty path)."""
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    b.pop("product_card", None)
    b.pop("score_card", None)
    return b


def test_empty_input_short_circuits_message_families() -> None:
    result = score_bundle(_empty_bundle(), suite_snapshot_pin="pin@1")
    assert result.short_circuit is True
    by = result.by_id()
    assert by["h.eval_input_nonempty"].passed is False
    assert "FIND-026" in (by["h.eval_input_nonempty"].failure_ids or [])
    # Family B must not run
    assert "b.header_shape" not in by
    assert "b.trailers_parse" not in by
    # Family D must not run gold path with message metrics... D is skipped entirely
    assert "d.gold_report_ok" not in by
    # Fanout bounded
    assert by["h.eval_error_fanout_bounded"].passed is True
    # Exactly one FIND-026 owner among scores (H input metric)
    find026_owners = [s.metric_id for s in result.scores if s.failure_ids and "FIND-026" in s.failure_ids]
    assert find026_owners == ["h.eval_input_nonempty"]


def test_oversize_input_short_circuits() -> None:
    b = _empty_bundle()
    b["final_message"] = "📝 docs(eval): x\n" + ("body\n" * 200_000)
    result = score_bundle(b, suite_snapshot_pin="pin@1", max_eval_bytes=1000)
    assert result.short_circuit is True
    by = result.by_id()
    assert by["h.eval_input_size_ok"].passed is False
    assert "b.header_shape" not in by
    assert by["h.eval_error_fanout_bounded"].passed is True


def test_no_family_b_clone_of_empty_failure() -> None:
    result = score_bundle(_empty_bundle(), suite_snapshot_pin="pin@1")
    leaked = [
        s
        for s in result.scores
        if s.metric_id.startswith("b.")
        and s.failure_ids
        and any(str(f).startswith("EVAL_INPUT") or f == "FIND-026" for f in s.failure_ids)
    ]
    assert leaked == []


def test_oversize_product_card_when_final_empty() -> None:
    """Empty final_message must not hide an oversize product_card (FIND-026)."""
    b = _empty_bundle()
    b["final_message"] = ""
    b["product_card"] = {"blob": "x" * 5000, "nested": {"k": "v" * 100}}
    result = score_bundle(b, suite_snapshot_pin="pin@1", max_eval_bytes=64)
    assert result.short_circuit is True
    by = result.by_id()
    assert result.context is not None
    assert result.context.scored_target == "product_card"
    assert result.context.input_size_bytes > 64
    assert by["h.eval_input_nonempty"].passed is True
    assert by["h.eval_input_size_ok"].passed is False
    assert "FIND-026" in (by["h.eval_input_size_ok"].failure_ids or [])
    assert "b.header_shape" not in by
    assert by["h.eval_error_fanout_bounded"].passed is True
