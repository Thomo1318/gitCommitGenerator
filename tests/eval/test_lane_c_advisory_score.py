"""S5c Lane C' — advisory score emission (C-ADV / D30)."""

from __future__ import annotations

import pytest

from git_cg.eval.lane_c.advisory import (
    GEVAL_SCALE,
    MAX_RATIONALE_CHARS,
    make_advisory_score,
    make_advisory_skip,
    scrub_rationale,
)
from git_cg.eval.lane_c.taxonomy import EXEC_JUDGE_NOT_INVOKED, EXEC_SCORED
from git_cg.eval.scoring.result_builder import make_score


class TestScrubRationale:
    def test_strips_controls_and_caps(self) -> None:
        dirty = "good\x00craft\nwith\ttabs" + ("x" * 1000)
        cleaned = scrub_rationale(dirty)
        assert cleaned is not None
        assert "\x00" not in cleaned
        assert "\n" not in cleaned
        assert "\t" not in cleaned
        assert len(cleaned) <= MAX_RATIONALE_CHARS

    def test_empty_becomes_none(self) -> None:
        assert scrub_rationale(None) is None
        assert scrub_rationale("   ") is None
        assert scrub_rationale("\x00\x01") is None


class TestMakeAdvisoryScore:
    def test_forces_passed_none_and_scale(self) -> None:
        row = make_advisory_score("cprime.geval_craft", 5, rationale="solid craft")
        assert row.passed is None
        assert row.value == 5
        assert row.reason == EXEC_SCORED
        assert row.evidence["scale"] == GEVAL_SCALE
        assert row.evidence["skipped"] is False
        assert row.evidence["rationale"] == "solid craft"
        assert row.authority.value == "advisory"

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError, match=r"1..5"):
            make_advisory_score("cprime.geval_craft", 0)
        with pytest.raises(ValueError, match=r"1..5"):
            make_advisory_score("cprime.geval_craft", 6)
        with pytest.raises(ValueError, match="number"):
            make_advisory_score("cprime.geval_craft", True)  # type: ignore[arg-type]

    def test_rejects_non_scored_reason(self) -> None:
        with pytest.raises(ValueError, match="scored"):
            make_advisory_score("cprime.geval_craft", 3, reason="parse_error")

    def test_strips_secret_looking_evidence_keys(self) -> None:
        row = make_advisory_score(
            "cprime.geval_relevance",
            4,
            evidence={"api_key": "sk-leak", "ok": 1, "authorization": "Bearer x"},
        )
        assert "api_key" not in row.evidence
        assert "authorization" not in row.evidence
        assert row.evidence["ok"] == 1

    def test_make_score_footgun_still_exists(self) -> None:
        # Documents why C' must not use make_score for continuous rows.
        footgun = make_score("cprime.geval_craft", 5.0, passed=None)
        assert footgun.passed is True


class TestMakeAdvisorySkip:
    def test_neutral_value_no_scale(self) -> None:
        row = make_advisory_skip("cprime.geval_craft", reason=EXEC_JUDGE_NOT_INVOKED)
        assert row.passed is None
        assert row.value == 0.0
        assert row.reason == EXEC_JUDGE_NOT_INVOKED
        assert row.evidence.get("scale") is None
        assert row.evidence["skipped"] is True
        assert row.failure_ids

    def test_rejects_scored_reason(self) -> None:
        with pytest.raises(ValueError, match="scored"):
            make_advisory_skip("cprime.geval_craft", reason=EXEC_SCORED)

    def test_unknown_metric_fails_closed(self) -> None:
        with pytest.raises(KeyError):
            make_advisory_skip("cprime.does_not_exist", reason=EXEC_JUDGE_NOT_INVOKED)
