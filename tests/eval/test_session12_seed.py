"""S1-C: Session-12 Regime A/B seed corpus law — offline only."""

from __future__ import annotations

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_fixture_dict
from git_cg.eval.corpus.snapshots import build_snapshot
from git_cg.eval.schema_pack import validate_instance

ROOT = default_fixture_root()


def test_s1_c01_seed_a1_regime_a_session12() -> None:
    fix = load_fixture_dict(ROOT / "cases/session-12/seed-a1-session12-regime-a.json")
    out = encode_fixture(fix, suite_id="cm-eval-fixtures-core")
    b = out["bundle"]
    validate_instance("ape_bundle_v1", b)
    assert b["regime"] == "A"
    assert b["bound"] is False
    assert b["provenance_label"] == "Opik-unbound"
    assert "session-12-seed" in (out["case"].get("tags") or [])
    assert "F72" in b["failure_ids"]
    assert "P-S12-1" in b["prevention_ids"]
    assert b["instance_kind"] == "A"
    # expected stays on envelope
    assert "expected_final_message" in b
    assert "expected_final_message" not in b.get("generation_task_input", {})


def test_s1_c02_seed_b1_regime_b_session12() -> None:
    fix = load_fixture_dict(ROOT / "cases/session-12/seed-b1-session12-regime-b.json")
    out = encode_fixture(fix, suite_id="cm-eval-fixtures-core")
    b = out["bundle"]
    validate_instance("ape_bundle_v1", b)
    assert b["regime"] == "B"
    assert b["bound"] is False
    assert b["provenance_label"] == "Opik-unbound"
    assert "session-12-seed" in (out["case"].get("tags") or [])
    assert "F76" in b["failure_ids"]
    assert "P-S12-4" in b["prevention_ids"]
    assert b["instance_kind"] == "B"


def test_s1_c03_failure_prevention_ids_round_trip() -> None:
    for rel in (
        "cases/session-12/seed-a1-session12-regime-a.json",
        "cases/session-12/seed-b1-session12-regime-b.json",
    ):
        fix = load_fixture_dict(ROOT / rel)
        out = encode_fixture(fix)
        assert out["bundle"]["failure_ids"] == fix["failure_ids"]
        assert out["bundle"]["prevention_ids"] == fix["prevention_ids"]


def test_s1_c05_unbound_historical_seeds_not_coerced() -> None:
    result = build_snapshot("cm-eval-fixtures-core")
    by_id = {b["case_id"]: b for b in result["bundles"]}
    for case_id in ("seed-a1-session12-regime-a", "seed-b1-session12-regime-b"):
        b = by_id[case_id]
        assert b["bound"] is False
        assert b["provenance_label"] == "Opik-unbound"
        assert b["artifact_class"] != "final_accept" or b["bound"] is True


def test_core_snapshot_includes_both_regimes() -> None:
    result = build_snapshot("cm-eval-fixtures-core")
    regimes = {b.get("regime") for b in result["bundles"]}
    assert "A" in regimes
    assert "B" in regimes
    assert result["snapshot"]["item_count"] == 3
