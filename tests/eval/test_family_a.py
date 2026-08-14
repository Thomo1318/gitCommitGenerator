"""Family A — artifact/binding."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_a import score_family_a

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def _ctx_from_fixture(path: Path = VALID):
    fx = json.loads(path.read_text(encoding="utf-8"))
    enc = encode_fixture(fx)
    return project_score_context(enc["bundle"])


def test_family_a_valid_fixture_passes_core() -> None:
    ctx = _ctx_from_fixture()
    scores = score_family_a(ctx)
    by = {s.metric_id: s for s in scores}
    assert by["a.bundle_schema_valid"].passed is True
    assert by["a.artifact_class_known"].passed is True
    assert by["a.final_message_present"].passed is True
    assert by["a.binding_unbound_explicit"].passed is True
    assert by["a.binding_complete"].passed is True
    assert by["a.final_bytes_stable"].passed is True
    assert by["a.scored_target_order_ok"].passed is True


def test_family_a_missing_final_fails_presence() -> None:
    ctx = _ctx_from_fixture()
    # Rebuild with empty final
    b = dict(ctx.bundle)
    b["final_message"] = ""
    b.pop("final_message_sha256", None)
    ctx2 = project_score_context(b)
    by = {s.metric_id: s for s in score_family_a(ctx2)}
    assert by["a.final_message_present"].passed is False
    assert by["a.final_bytes_stable"].passed is False


def test_family_a_unknown_artifact_class() -> None:
    ctx = _ctx_from_fixture()
    b = dict(ctx.bundle)
    b["artifact_class"] = "not_a_real_class"
    # schema may fail; still check class known metric
    ctx2 = project_score_context(b)
    by = {s.metric_id: s for s in score_family_a(ctx2)}
    assert by["a.artifact_class_known"].passed is False


def test_family_a_unbound_without_reason_fails() -> None:
    ctx = _ctx_from_fixture()
    b = dict(ctx.bundle)
    b["bound"] = False
    b["unbound_reason"] = None
    # drop key entirely
    b.pop("unbound_reason", None)
    ctx2 = project_score_context(b)
    by = {s.metric_id: s for s in score_family_a(ctx2)}
    assert by["a.binding_unbound_explicit"].passed is False
