"""Broader #204 archive ramp (S1 optional suite) — offline only."""

from __future__ import annotations

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_fixture_dict, load_suite_fixtures
from git_cg.eval.corpus.snapshots import build_snapshot
from git_cg.eval.corpus.suites import load_suite
from git_cg.eval.schema_pack import validate_instance

ROOT = default_fixture_root()


def test_archive_suite_loads_via_alias() -> None:
    suite = load_suite("cm-eval-204-archive")
    assert suite["suite_id"] == "204-archive"
    assert suite["meta"].get("archive_ramp") is True
    assert len(suite["case_ids"]) == 6


def test_archive_suite_encodes_all_cases_offline() -> None:
    suite = load_suite("204-archive")
    pairs = load_suite_fixtures(suite)
    assert [c for c, _ in pairs] == suite["case_ids"]
    regimes = set()
    for case_id, fixture in pairs:
        out = encode_fixture(fixture, case_id=case_id, suite_id=suite["suite_id"])
        validate_instance("ape_bundle_v1", out["bundle"])
        validate_instance("eval_case_v1", out["case"])
        b = out["bundle"]
        assert b["bound"] is False
        assert b["provenance_label"] == "Opik-unbound"
        assert b.get("failure_ids") is not None
        assert b.get("regime") in {"A", "B"}
        regimes.add(b["regime"])
        # archive-shaped meta preserved
        assert (
            out["bundle"]["meta"].get("corpus_source") == "204_archive"
            or fixture.get("meta", {}).get("corpus_source") == "204_archive"
        )
    assert regimes == {"A", "B"}


def test_archive_snapshot_deterministic() -> None:
    a = build_snapshot("204-archive")
    b = build_snapshot("204-archive")
    assert a["snapshot_hash"] == b["snapshot_hash"]
    assert a["snapshot"]["item_count"] == 6
    validate_instance("dataset_snapshot_v1", a["snapshot"])


def test_archive_ramp_seeds_preserve_ids() -> None:
    for rel, fail, prev in (
        ("cases/204-archive/seed-b2-session12-g3.json", "F76", "P-S12-4"),
        ("cases/204-archive/seed-b3-session12-g4.json", "F77", "P-S12-7"),
        ("cases/204-archive/seed-b4-quality-package-dogfood.json", "F81", "P-S12-10"),
        ("cases/204-archive/seed-a2-instance-a-precursor.json", "F72", "P-S12-1"),
    ):
        fix = load_fixture_dict(ROOT / rel)
        out = encode_fixture(fix)
        assert fail in out["bundle"]["failure_ids"]
        assert prev in out["bundle"]["prevention_ids"]
