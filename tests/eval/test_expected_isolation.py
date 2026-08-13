"""S1-D: expected_* / gold isolation — offline only."""

from __future__ import annotations

import pytest

from git_cg.eval.corpus.encoder import CorpusEncodeError, encode_fixture
from git_cg.eval.corpus.fixtures import default_fixture_root, load_fixture_dict
from git_cg.eval.corpus.task_input import TaskInputError, project_generation_task_input

ROOT = default_fixture_root()


def test_s1_d01_fixture_envelope_may_carry_expected_fields() -> None:
    fix = load_fixture_dict(ROOT / "cases/valid/seed-v1-valid-fixture.json")
    out = encode_fixture(fix)
    assert "expected_final_message" in out["bundle"]
    assert out["bundle"]["expected_gold_codes"] == []


def test_s1_d02_generation_task_input_omits_expected_gold() -> None:
    projected = project_generation_task_input(
        {
            "diff_summary": "x",
            "path_class_gate": "docs_only",
            "ranked_intent_id": "documentation_update",
        }
    )
    assert projected == {
        "diff_summary": "x",
        "path_class_gate": "docs_only",
        "ranked_intent_id": "documentation_update",
    }
    assert "expected_final_message" not in projected
    out = encode_fixture(load_fixture_dict(ROOT / "cases/valid/seed-v1-valid-fixture.json"))
    gti = out["bundle"]["generation_task_input"]
    assert all(not k.startswith("expected") and not k.startswith("gold") for k in gti)


def test_s1_d03_seed_i1_expected_leak_rejected() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-i1-expected-in-task-input.json")
    with pytest.raises(CorpusEncodeError, match="expected"):
        encode_fixture(fix)


def test_s1_d03b_seed_i1_gold_prefix_leak_rejected() -> None:
    fix = load_fixture_dict(ROOT / "cases/invalid/seed-i1-gold-prefix-in-task-input.json")
    with pytest.raises((CorpusEncodeError, TaskInputError)):
        encode_fixture(fix)


def test_project_generation_task_input_strict_unknown_key() -> None:
    with pytest.raises(TaskInputError, match="unsupported keys"):
        project_generation_task_input({"diff_summary": "x", "secret_sauce": "nope"})


def test_project_generation_task_input_strip_mode_never_returns_expected() -> None:
    out = project_generation_task_input(
        {
            "diff_summary": "x",
            "expected_final_message": "LEAK",
            "gold_target": "LEAK",
        },
        strict=False,
    )
    assert out == {"diff_summary": "x"}
