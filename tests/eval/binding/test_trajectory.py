"""Trajectory evidence emitter tests (R7 / D3 / D10).

Covers the D3 closed declared-stage vocabulary, D10 emission shape (plain
``string[]`` observed stages, ``meta.complete`` / ``meta.observed_stage_details``
under ``meta`` only), fail-closed validation, and schema conformance against the
frozen ``trajectory_evidence_v1`` schema. No fabricated stage success (N19 F7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from git_cg.eval.binding.trajectory import (
    DECLARED_STAGES,
    OBSERVED_STAGE_STATUSES,
    REQUIRED_CORE_STAGES,
    TrajectoryError,
    build_trajectory_evidence,
    is_complete,
    validate_observed_stages,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "eval" / "trajectory_evidence_v1.schema.json"

HAPPY_OBSERVED = (
    "diff_extraction",
    "path_classification",
    "intent_ranking",
    "contract_resolution",
    "llm_generation",
    "plan_normalisation",
    "gold_evaluation",
    "presentation_guard",
    "final_render",
    "accept_path_finalization",
)


# ---------------------------------------------------------------------------
# D3 — declared vocabulary
# ---------------------------------------------------------------------------


def test_declared_stages_full_ordered_list() -> None:
    assert list(DECLARED_STAGES) == [
        "diff_extraction",
        "path_classification",
        "intent_ranking",
        "contract_resolution",
        "llm_generation",
        "plan_normalisation",
        "gold_evaluation",
        "presentation_guard",
        "regeneration",
        "fallback",
        "final_render",
        "accept_path_finalization",
        "opik_export",
    ]


def test_required_core_excludes_conditional_stages() -> None:
    # llm_generation / plan_normalisation / regeneration / fallback / opik_export
    # are conditional; they are NOT required for the minimal happy-path core.
    assert "accept_path_finalization" in REQUIRED_CORE_STAGES
    assert "final_render" in REQUIRED_CORE_STAGES
    for conditional in (
        "llm_generation",
        "plan_normalisation",
        "regeneration",
        "fallback",
        "opik_export",
    ):
        assert conditional not in REQUIRED_CORE_STAGES


# ---------------------------------------------------------------------------
# D10 — emission shape
# ---------------------------------------------------------------------------


def test_build_minimal_shape_and_complete() -> None:
    ev = build_trajectory_evidence("ev-1", HAPPY_OBSERVED)
    assert ev["schema_version"] == "trajectory_evidence_v1"
    assert ev["id"] == "ev-1"
    assert ev["declared_stages"] == list(DECLARED_STAGES)
    # observed emitted as plain strings in declared order
    assert all(isinstance(s, str) for s in ev["observed_stages"])
    assert ev["observed_stages"] == list(HAPPY_OBSERVED)
    # meta.complete present; no top-level complete key (schema forbids it)
    assert "complete" not in ev
    assert ev["meta"]["complete"] is True


def test_observed_stages_reordered_to_declared_order() -> None:
    ev = build_trajectory_evidence(
        "ev-2",
        ("accept_path_finalization", "diff_extraction", "final_render"),
    )
    assert ev["observed_stages"] == [
        "diff_extraction",
        "final_render",
        "accept_path_finalization",
    ]


def test_missing_finalization_is_incomplete() -> None:
    observed = tuple(s for s in HAPPY_OBSERVED if s != "accept_path_finalization")
    ev = build_trajectory_evidence("ev-3", observed)
    assert ev["meta"]["complete"] is False


def test_final_render_without_accept_finalization_is_incomplete() -> None:
    # final_render (pre-editor pipeline output) is NOT accept-path finalization.
    ev = build_trajectory_evidence(
        "ev-4",
        (
            "diff_extraction",
            "path_classification",
            "intent_ranking",
            "contract_resolution",
            "gold_evaluation",
            "presentation_guard",
            "final_render",
        ),
    )
    assert "final_render" in ev["observed_stages"]
    assert "accept_path_finalization" not in ev["observed_stages"]
    assert ev["meta"]["complete"] is False


def test_missing_core_stage_is_incomplete_even_with_finalization() -> None:
    ev = build_trajectory_evidence(
        "ev-5",
        ("diff_extraction", "final_render", "accept_path_finalization"),
    )
    assert ev["meta"]["complete"] is False


def test_no_fabricated_success_on_empty_observed() -> None:
    ev = build_trajectory_evidence("ev-6", ())
    assert ev["observed_stages"] == []
    assert ev["meta"]["complete"] is False


def test_optional_observed_stage_details_under_meta() -> None:
    ev = build_trajectory_evidence(
        "ev-7",
        HAPPY_OBSERVED,
        observed_stage_details=[
            {"name": "fallback", "status": "skipped"},
            {"name": "diff_extraction", "status": "observed"},
        ],
    )
    details = ev["meta"]["observed_stage_details"]
    assert details == [
        {"name": "fallback", "status": "skipped"},
        {"name": "diff_extraction", "status": "observed"},
    ]
    # detail is additive; observed_stages stays plain strings
    assert all(isinstance(s, str) for s in ev["observed_stages"])


def test_optional_notes_and_pins() -> None:
    ev = build_trajectory_evidence(
        "ev-8",
        HAPPY_OBSERVED,
        notes="core-goldens",
        metric_catalog="metric_catalog_v1@deadbeef",
        schema_pack="schema_pack_v1@deadbeef",
    )
    assert ev["notes"] == "core-goldens"
    assert ev["metric_catalog"] == "metric_catalog_v1@deadbeef"
    assert ev["schema_pack"] == "schema_pack_v1@deadbeef"


# ---------------------------------------------------------------------------
# Fail-closed validation
# ---------------------------------------------------------------------------


def test_unknown_stage_fails_closed() -> None:
    with pytest.raises(TrajectoryError, match="unknown observed stage"):
        build_trajectory_evidence("ev-bad-1", ("diff_extraction", "not_a_stage"))


def test_duplicate_stage_fails_closed() -> None:
    with pytest.raises(TrajectoryError, match="duplicate observed stage"):
        build_trajectory_evidence("ev-bad-2", ("diff_extraction", "diff_extraction"))


def test_non_string_stage_fails_closed() -> None:
    with pytest.raises(TrajectoryError, match="stage-name string"):
        build_trajectory_evidence("ev-bad-3", ({"name": "diff_extraction"},))  # type: ignore[arg-type]


def test_empty_id_fails_closed() -> None:
    with pytest.raises(TrajectoryError, match="non-empty string"):
        build_trajectory_evidence("   ", HAPPY_OBSERVED)


def test_invalid_detail_status_fails_closed() -> None:
    with pytest.raises(TrajectoryError, match="status must be one of"):
        build_trajectory_evidence(
            "ev-bad-4",
            HAPPY_OBSERVED,
            observed_stage_details=[{"name": "diff_extraction", "status": "bogus"}],
        )


def test_invalid_detail_name_fails_closed() -> None:
    with pytest.raises(TrajectoryError, match="declared stage"):
        build_trajectory_evidence(
            "ev-bad-5",
            HAPPY_OBSERVED,
            observed_stage_details=[{"name": "not_a_stage", "status": "observed"}],
        )


def test_validate_observed_stages_helpers() -> None:
    assert validate_observed_stages(("final_render", "diff_extraction")) == [
        "diff_extraction",
        "final_render",
    ]
    assert is_complete(HAPPY_OBSERVED) is True
    assert is_complete(("diff_extraction",)) is False
    assert "observed" in OBSERVED_STAGE_STATUSES


# ---------------------------------------------------------------------------
# Schema conformance (frozen trajectory_evidence_v1)
# ---------------------------------------------------------------------------


def test_emitted_object_conforms_to_frozen_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    ev = build_trajectory_evidence(
        "ev-schema",
        HAPPY_OBSERVED,
        observed_stage_details=[{"name": "fallback", "status": "skipped"}],
        notes="schema-check",
    )
    jsonschema.validate(instance=ev, schema=schema)


def test_emitted_object_has_no_unknown_top_level_keys() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    allowed = set(schema["properties"].keys())
    ev = build_trajectory_evidence("ev-keys", HAPPY_OBSERVED)
    assert set(ev.keys()) <= allowed
