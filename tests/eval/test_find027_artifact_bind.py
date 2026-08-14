"""FIND-027 — final message / product card bind order; never raw model dumps."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring import score_bundle
from git_cg.eval.scoring.context import project_score_context

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def test_final_message_is_primary_target() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b["raw_model_output"] = '{"not":"the target"}'
    b["generation_json"] = {"nope": True}
    ctx = project_score_context(b)
    assert ctx.scored_target == "final_message"
    assert any(w.startswith("ignored_wrong_artifact_key:") for w in ctx.warnings) or ctx.final_message


def test_missing_final_falls_back_to_product_card() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    b["product_card"] = {"header_ok": True}
    ctx = project_score_context(b)
    assert ctx.scored_target == "product_card"
    assert "scored_target_fell_back_to_product_card" in ctx.warnings


def test_wrong_artifact_only_is_missing_target() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    b["raw_model_output"] = "RAW"
    b.pop("product_card", None)
    b.pop("score_card", None)
    ctx = project_score_context(b)
    assert ctx.scored_target == "missing"
    assert any("ignored_wrong_artifact_key:raw_model_output" in w for w in ctx.warnings)
    result = score_bundle(b, suite_snapshot_pin="pin@1")
    by = result.by_id()
    assert by["a.scored_target_order_ok"].passed is True  # missing is order-ok
    assert by["h.eval_input_nonempty"].passed is False


def test_score_runner_uses_final_message_bytes() -> None:
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    b = dict(encode_fixture(fx)["bundle"])
    # inject noise keys that must not become the target
    b["llm_raw"] = b["final_message"]
    b["trace_blob"] = "TRACE"
    result = score_bundle(b, suite_snapshot_pin="pin@1")
    assert result.context is not None
    assert result.context.scored_target == "final_message"
    assert result.by_id()["a.scored_target_order_ok"].passed is True
