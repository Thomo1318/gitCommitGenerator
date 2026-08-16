"""S2a offline score runner — core suite + API surface."""

from __future__ import annotations

from pathlib import Path

from git_cg.eval.corpus.encoder import encode_fixture
from git_cg.eval.scoring import (
    S2A_REQUIRE_BLOCK,
    score_bundle,
    score_case,
    score_suite,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "eval"
VALID = FIXTURE_ROOT / "cases" / "valid" / "seed-v1-valid-fixture.json"


def test_package_exports() -> None:
    import git_cg.eval.scoring as s

    assert callable(s.score_bundle)
    assert callable(s.score_case)
    assert callable(s.score_suite)
    assert callable(s.compose_gates)
    assert isinstance(s.S2A_REQUIRE_BLOCK, tuple)
    assert "gate.deterministic_pass" not in s.S2A_REQUIRE_BLOCK
    assert "a.final_message_present" in s.S2A_REQUIRE_BLOCK
    # S2c surface
    assert isinstance(s.S2C_TOPOLOGY_BLOCK, tuple)
    assert callable(s.score_family_i)
    assert len(s.FAMILY_I_METRIC_IDS) == 16


def test_score_case_valid_fixture() -> None:
    result = score_case(VALID, suite_snapshot_pin="test-pin@abc")
    assert result.case_id == "seed-v1-valid-fixture"
    assert result.short_circuit is False
    assert result.evaluator_errors == []
    by = result.by_id()
    assert by["a.final_message_present"].passed is True
    assert by["b.header_shape"].passed is True
    assert by["h.eval_input_nonempty"].passed is True
    assert by["h.suite_snapshot_pinned"].passed is True
    assert by["gate.deterministic_pass"].passed is True


def test_score_suite_core_offline() -> None:
    suite = score_suite("cm-eval-fixtures-core", fixture_root=FIXTURE_ROOT)
    assert suite.suite_id == "cm-eval-fixtures-core"
    assert suite.suite_snapshot_pin
    assert len(suite.cases) == 3
    ids = {c.case_id for c in suite.cases}
    assert ids == {
        "seed-v1-valid-fixture",
        "seed-a1-session12-regime-a",
        "seed-b1-session12-regime-b",
    }
    # V1 + B1 are Hybrid-shaped gold targets; A1 is historical non-standard header
    by_case = {c.case_id: c for c in suite.cases}
    assert by_case["seed-v1-valid-fixture"].deterministic_pass is True
    assert by_case["seed-b1-session12-regime-b"].deterministic_pass is True
    # A1 may fail Hybrid header shape — still must score offline without errors
    assert by_case["seed-a1-session12-regime-a"].evaluator_errors == []
    assert by_case["seed-a1-session12-regime-a"].by_id()["h.offline_complete"].passed is True


def test_score_bundle_preserves_context() -> None:
    import json

    fx = json.loads(VALID.read_text(encoding="utf-8"))
    enc = encode_fixture(fx)
    result = score_bundle(enc["bundle"], suite_snapshot_pin="pin@1")
    assert result.context is not None
    assert result.context.scored_target == "final_message"
    assert result.context.bound is False
    assert result.context.unbound_reason


def test_all_emitted_scores_are_valid_envelopes() -> None:
    result = score_case(VALID, suite_snapshot_pin="pin@1")
    from git_cg.eval.score_result import ScoreResultV1

    for s in result.all_results:
        ScoreResultV1.model_validate(s.model_dump(mode="json"))


def test_require_block_list_nonempty() -> None:
    assert len(S2A_REQUIRE_BLOCK) >= 20
    # No C-prime metrics in S2a require block
    assert not any(m.startswith("c.") for m in S2A_REQUIRE_BLOCK)


def test_score_suite_rejects_divergent_suite_path(tmp_path: Path) -> None:
    """suite_path with same suite_id but different case_ids must not pin the wrong corpus."""
    import json

    import pytest

    core = json.loads((FIXTURE_ROOT / "suites" / "cm-eval-fixtures-core.json").read_text(encoding="utf-8"))
    divergent = dict(core)
    divergent["case_ids"] = ["seed-v1-valid-fixture"]
    if "case_paths" in divergent:
        divergent["case_paths"] = {
            "seed-v1-valid-fixture": divergent["case_paths"].get("seed-v1-valid-fixture")
            or "cases/valid/seed-v1-valid-fixture.json"
        }
    path = tmp_path / "divergent-core.json"
    path.write_text(json.dumps(divergent, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="suite_path case_ids diverge"):
        score_suite(
            "cm-eval-fixtures-core",
            fixture_root=FIXTURE_ROOT,
            suite_path=path,
        )
