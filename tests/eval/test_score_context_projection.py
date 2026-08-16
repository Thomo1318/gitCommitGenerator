"""Score context projection fixes (Issue #231 Slice 3).

* N19 F1 — stored ``final_message_sha256`` is the authority; a mismatch against
  the recomputed text hash must surface as a warning and must NOT be clobbered
  (tamper detection is not tautological).
* D10/D44 — card precedence: explicit kwargs → ``bundle.meta`` cards →
  top-level compat keys (fixtures only).
"""

from __future__ import annotations

from git_cg.eval.corpus.canonical import message_sha256
from git_cg.eval.scoring.context import project_score_context
from git_cg.eval.scoring.family_a import score_family_a

MSG = "✨ feat(eval): accept-path binding\n"


def _base() -> dict:
    """
    Create the minimal bound final-accept bundle used by the regression tests.
    
    Returns:
    	dict: A bundle containing the case identifier, final message, bound status, and artifact class.
    """
    return {
        "case_id": "c1",
        "final_message": MSG,
        "bound": True,
        "artifact_class": "final_accept",
    }


def test_stored_hash_preserved_when_matching() -> None:
    ctx = project_score_context({**_base(), "final_message_sha256": message_sha256(MSG)})
    assert ctx.final_message_sha256 == message_sha256(MSG)
    assert "final_message_sha256_mismatch" not in ctx.warnings


def test_stored_hash_preserved_on_mismatch_and_flagged() -> None:
    """Tampered stored hash must be preserved (not recomputed) + flagged."""
    tampered = "0" * 64
    ctx = project_score_context({**_base(), "final_message_sha256": tampered})
    assert ctx.final_message_sha256 == tampered  # stored authority preserved
    assert "final_message_sha256_mismatch" in ctx.warnings
    # Family A detects the mismatch: recomputed(text) != stored ⇒ unstable.
    by = {s.metric_id: s for s in score_family_a(ctx)}
    assert by["a.final_bytes_stable"].passed is False


def test_missing_stored_hash_falls_back_to_computed_with_warning() -> None:
    ctx = project_score_context(_base())
    assert ctx.final_message_sha256 == message_sha256(MSG)
    assert "final_message_sha256_computed_fallback" in ctx.warnings
    by = {s.metric_id: s for s in score_family_a(ctx)}
    assert by["a.final_bytes_stable"].passed is True


def test_meta_score_card_precedence_over_toplevel() -> None:
    bundle = _base()
    bundle["final_message_sha256"] = message_sha256(MSG)
    bundle["meta"] = {"score_card": {"total": 9}}
    bundle["score_card"] = {"total": 1}  # compat fallback only
    ctx = project_score_context(bundle)
    assert ctx.score_card == {"total": 9}


def test_meta_product_card_precedence_over_toplevel() -> None:
    bundle = _base()
    bundle["final_message_sha256"] = message_sha256(MSG)
    bundle["meta"] = {"product_card": {"a": 2}}
    bundle["product_card"] = {"a": 1}
    ctx = project_score_context(bundle)
    assert ctx.product_card == {"a": 2}


def test_explicit_kwargs_outrank_meta_cards() -> None:
    bundle = _base()
    bundle["final_message_sha256"] = message_sha256(MSG)
    bundle["meta"] = {"score_card": {"total": 9}, "product_card": {"a": 2}}
    ctx = project_score_context(bundle, score_card={"total": 5}, product_card={"a": 7})
    assert ctx.score_card == {"total": 5}
    assert ctx.product_card == {"a": 7}


def test_toplevel_compat_used_when_meta_absent() -> None:
    bundle = _base()
    bundle["final_message_sha256"] = message_sha256(MSG)
    bundle["score_card"] = {"total": 3}
    ctx = project_score_context(bundle)
    assert ctx.score_card == {"total": 3}
