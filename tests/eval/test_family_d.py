"""Family D — single gold call fan-out."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.commit_gold import STRICT_FAIL_CODES, GoldFinding, GoldReport
from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_d import score_family_d
from git_cg.intent import DiffSignals
from git_cg.models import CommitPlan

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def _ctx():
    """Valid-fixture ``ScoreContext`` for Family D unit locks."""
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    enc = encode_fixture(fx)
    return project_score_context(enc["bundle"])


def test_family_d_calls_gold_once_and_maps_codes() -> None:
    calls: list[tuple] = []

    def bridge(plan: CommitPlan, signals: DiffSignals, mode: str):
        """Stub gold bridge: record call + two STRICT_FAIL findings."""
        calls.append((plan, signals, mode))
        findings = (
            GoldFinding(code="GOLD_SKELETON_FALLBACK_FINAL", message="skeleton"),
            GoldFinding(code="GOLD_SUBJECT_TITLE_CASE", message="title"),
        )
        report = GoldReport(findings=findings)
        strict = report.codes() & STRICT_FAIL_CODES
        return report, strict, report.ok_for_mode(mode)

    ctx = _ctx()
    scores = score_family_d(ctx, gold_bridge=bridge, gold_mode="strict")
    assert len(calls) == 1
    by = {s.metric_id: s for s in scores}
    assert by["d.gold_report_ok"].evidence["call_count"] == 1
    assert by["d.skeleton_fallback_final"].passed is False
    assert "GOLD_SKELETON_FALLBACK_FINAL" in (by["d.skeleton_fallback_final"].failure_ids or [])
    assert "d.subject_title_case" in by
    assert by["d.subject_title_case"].passed is False
    assert by["d.gold_report_ok"].passed is False  # strict fail codes present


def test_family_d_empty_message_skips_gold() -> None:
    ctx = _ctx()
    b = dict(ctx.bundle)
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    ctx2 = project_score_context(b)
    called = {"n": 0}

    def bridge(plan, signals, mode):
        called["n"] += 1
        return GoldReport(), frozenset(), True

    scores = score_family_d(ctx2, gold_bridge=bridge)
    assert called["n"] == 0
    by = {s.metric_id: s for s in scores}
    assert by["d.gold_report_ok"].passed is False


def test_family_d_product_gold_on_valid_v1() -> None:
    """Live product gold path on V1 (no monkeypatch)."""
    ctx = _ctx()
    scores = score_family_d(ctx, gold_mode="strict")
    by = {s.metric_id: s for s in scores}
    assert by["d.gold_report_ok"].evidence.get("call_count") == 1
    assert by["d.skeleton_fallback_final"].passed is True


def test_family_d_gold_build_error_preserved_on_strict_fail_set() -> None:
    ctx = _ctx()

    def bridge(plan: CommitPlan, signals: DiffSignals, mode: str):
        """Stub gold bridge that always raises (build-error path)."""
        raise RuntimeError("gold boom")

    scores = score_family_d(ctx, gold_bridge=bridge, gold_mode="strict")
    by = {s.metric_id: s for s in scores}
    assert by["d.gold_report_ok"].passed is False
    assert "EVAL_GOLD_BUILD_ERROR" in (by["d.gold_report_ok"].failure_ids or [])
    strict = by["d.strict_fail_set"]
    assert strict.passed is False
    assert strict.reason == "gold_evaluation_error"
    assert "EVAL_GOLD_BUILD_ERROR" in (strict.failure_ids or [])
    assert (strict.evidence or {}).get("error")
    assert (strict.evidence or {}).get("count") == 0
