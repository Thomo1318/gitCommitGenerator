"""S1-A / S1-F: corpus encoder — offline only."""

from __future__ import annotations

import pytest

from git_cg.eval.corpus.encoder import CorpusEncodeError, encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_fixture_dict
from git_cg.eval.corpus.suites import load_suite
from git_cg.eval.pins import metric_catalog_pin, schema_pack_pin
from git_cg.eval.schema_pack import validate_instance

ROOT = default_fixture_root()


def test_s1_a01_known_good_encodes_valid_ape_bundle() -> None:
    fix = load_fixture_dict(ROOT / "cases/valid/seed-v1-valid-fixture.json")
    out = encode_fixture(fix)
    validate_instance("ape_bundle_v1", out["bundle"])
    assert out["bundle"]["schema_version"] == "ape_bundle_v1"
    assert out["bundle"]["case_id"] == "seed-v1-valid-fixture"
    assert out["bundle"]["schema_pack"] == schema_pack_pin()
    assert out["bundle"]["metric_catalog"] == metric_catalog_pin()


def test_s1_a02_eval_case_has_bundle_ref() -> None:
    fix = load_fixture_dict(ROOT / "cases/valid/seed-v1-valid-fixture.json")
    out = encode_fixture(fix)
    validate_instance("eval_case_v1", out["case"])
    assert out["case"]["bundle_ref"] == out["bundle_ref"]
    assert out["bundle_ref"].startswith("bundle:seed-v1-valid-fixture@")
    assert len(out["bundle_hash"]) == 64


def test_s1_a03_core_suite_loads_and_references_valid_cases() -> None:
    suite = load_suite("cm-eval-fixtures-core")
    assert suite["suite_id"] == "cm-eval-fixtures-core"
    assert suite["schema_pack_pin"] == schema_pack_pin()
    assert suite["metric_catalog_pin"] == metric_catalog_pin()
    assert suite["case_ids"] == [
        "seed-v1-valid-fixture",
        "seed-a1-session12-regime-a",
        "seed-b1-session12-regime-b",
    ]
    for case_id, rel in suite["case_paths"].items():
        path = ROOT / rel
        assert path.is_file(), path
        out = encode_fixture(load_fixture_dict(path), case_id=case_id, suite_id=suite["suite_id"])
        validate_instance("ape_bundle_v1", out["bundle"])
        validate_instance("eval_case_v1", out["case"])


def test_s1_a04_known_bad_missing_case_id() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n1-missing-case-id.json")
    with pytest.raises(CorpusEncodeError, match="case_id"):
        encode_fixture(fix)


def test_s1_a05_unknown_artifact_class_fails_closed() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n1-unknown-artifact-class.json")
    with pytest.raises(CorpusEncodeError, match="artifact_class"):
        encode_fixture(fix)


def test_s1_f01_empty_unbound_reason_fails() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n1-bound-false-missing-reason.json")
    with pytest.raises(CorpusEncodeError, match="unbound_reason"):
        encode_fixture(fix)


def test_s1_f02_unbound_final_accept_coercion_rejected() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n1-unbound-final-accept-coercion.json")
    with pytest.raises(CorpusEncodeError, match="final_accept"):
        encode_fixture(fix)


def test_s1_g01_encoder_consumes_live_s0_pins() -> None:
    fix = load_fixture_dict(ROOT / "cases/valid/seed-v1-valid-fixture.json")
    out = encode_fixture(fix)
    assert out["bundle"]["schema_pack"].startswith("schema_pack_v0@")
    assert out["bundle"]["metric_catalog"].startswith("metric_catalog_v0@")
    # Frozen S0 identities unless an explicit pin-bump PR changes them.
    assert out["bundle"]["schema_pack"] == (
        "schema_pack_v0@2584b00da059d676c49f5a923cb266ecf9968a41560184d94ebdaf5cb9ca93ec"
    )
    assert out["bundle"]["metric_catalog"] == (
        "metric_catalog_v0@430a62c1d7971e1145cfffd41e608a5f6bd39d284a3d050f991b8537f817eb75"
    )
