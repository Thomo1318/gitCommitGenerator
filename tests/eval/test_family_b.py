"""Family B — Hybrid wrap via product parse law."""

from __future__ import annotations

import json
from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_b import score_family_b
from git_cg.eval.scoring.product_bridges import parse_hybrid_header, parse_message_to_plan

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def _bundle_with_message(msg: str) -> dict:
    """
    Create a fixture bundle with the supplied final commit message.
    
    Parameters:
    	msg (str): The final commit message to place in the bundle.
    
    Returns:
    	dict: The bundle with its previous message hash removed for recomputation.
    """
    fx = json.loads(VALID.read_text(encoding="utf-8"))
    enc = encode_fixture(fx)
    b = dict(enc["bundle"])
    b["final_message"] = msg
    # leave sha to be recomputed by context
    b.pop("final_message_sha256", None)
    return b


def test_family_b_valid_hybrid_message() -> None:
    b = _bundle_with_message(
        "📝 docs(eval): add offline fixture seed\n\n"
        "Refs: #223\n"
        "SemVer-Impact: PATCH\n"
        "Change-Types: docs\n"
        "Changelog-Groups: Documentation\n"
    )
    ctx = project_score_context(b)
    by = {s.metric_id: s for s in score_family_b(ctx)}
    assert by["b.header_shape"].passed is True
    assert by["b.gitmoji_present"].passed is True
    assert by["b.cc_type_known"].passed is True
    assert by["b.subject_length"].passed is True
    assert by["b.trailers_parse"].passed is True
    assert by["b.trailers_issue_ref"].passed is True
    assert by["b.trailers_semver"].passed is True
    assert by["b.structured_envelope"].passed is True


def test_family_b_subject_over_72_fails() -> None:
    long_subj = "x" * 80
    msg = f"📝 docs(eval): {long_subj}\n\nRefs: #1\nSemVer-Impact: PATCH\nChange-Types: docs\nChangelog-Groups: Documentation\n"
    ctx = project_score_context(_bundle_with_message(msg))
    by = {s.metric_id: s for s in score_family_b(ctx)}
    assert by["b.subject_length"].passed is False


def test_family_b_missing_trailers_fail() -> None:
    msg = "📝 docs(eval): add seed\n"
    ctx = project_score_context(_bundle_with_message(msg))
    by = {s.metric_id: s for s in score_family_b(ctx)}
    assert by["b.trailers_parse"].passed is False
    assert by["b.trailers_issue_ref"].passed is False


def test_family_b_null_issue_must_be_zero() -> None:
    msg = (
        "📝 docs(eval): add seed\n\n"
        "Null: #7\n"
        "SemVer-Impact: PATCH\n"
        "Change-Types: docs\n"
        "Changelog-Groups: Documentation\n"
    )
    ctx = project_score_context(_bundle_with_message(msg))
    by = {s.metric_id: s for s in score_family_b(ctx)}
    assert by["b.trailers_issue_ref"].passed is False


def test_product_bridges_build_plan() -> None:
    msg = (
        "📝 docs(eval): add offline fixture seed\n\n"
        "Refs: #223\n"
        "SemVer-Impact: PATCH\n"
        "Change-Types: docs\n"
        "Changelog-Groups: Documentation\n"
    )
    assert parse_hybrid_header(msg)["ok"] is True
    plan = parse_message_to_plan(msg)
    assert plan.primary_intent.cc_type.value == "docs"
