"""Topology / counter / split / judge / replay negatives — offline only."""

from __future__ import annotations

import pytest

from git_cg.eval.corpus.encoder import CorpusEncodeError, encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_fixture_dict

ROOT = default_fixture_root()


def test_valid_topology_control_encodes() -> None:
    fix = load_fixture_dict(ROOT / "cases/valid/seed-v-topology-complete.json")
    out = encode_fixture(fix)
    assert out["bundle"]["case_id"] == "seed-v-topology-complete"
    topo = out["bundle"]["meta"]["topology"]
    assert topo["status"] == "complete"
    assert topo["missing_spans"] == []


def test_incomplete_topology_fails_closed() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n-topology-incomplete.json")
    with pytest.raises(CorpusEncodeError, match="topology incomplete"):
        encode_fixture(fix)


def test_counter_span_mismatch_fails_closed() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n-counter-mismatch.json")
    with pytest.raises(CorpusEncodeError, match="counter/span mismatch"):
        encode_fixture(fix)


def test_split_contamination_fails_closed() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n-split-contamination.json")
    with pytest.raises(CorpusEncodeError, match="split contamination"):
        encode_fixture(fix)


def test_judge_input_leak_fails_closed() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n-judge-input-leak.json")
    with pytest.raises(CorpusEncodeError, match=r"unsupported keys|judge"):
        encode_fixture(fix)


def test_replay_lineage_missing_fails_closed() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-n-replay-lineage-missing.json")
    with pytest.raises(CorpusEncodeError, match="replay lineage"):
        encode_fixture(fix)
