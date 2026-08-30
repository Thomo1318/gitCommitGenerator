"""S7-B: Feedback Definition vocabulary map — data-shape + drift guard.

The map (``config/feedback_definitions.json``) must stay 1:1 with the score
vocabulary actually emitted by the product (``main.py``) and the human-review
score builder (``review_queue._build_scores``). The guard asserts by importing
the shared registry and the real emitter/score-builder loci — never by grep.
"""

from __future__ import annotations

import inspect

import pytest

from git_cg.eval import review_queue
from git_cg.eval.feedback_definitions import (
    DATA_PATH,
    FEEDBACK_DEFINITION_REGISTRY,
    HUMAN_SCORES,
    PRODUCT_SCORES,
    FeedbackDefinitionError,
    defined_score_names,
    load_feedback_definitions,
)
from git_cg.eval.schema_pack import list_schema_names, validate_instance


def test_map_loads_and_validates() -> None:
    """The committed data map loads and validates against its schema."""
    data = load_feedback_definitions()
    assert data["schema_version"] == "feedback_definition_v1"
    assert isinstance(data["definitions"], dict)
    # Round-trip: the loaded instance must independently satisfy the schema.
    validate_instance("feedback_definition_v1", data)


def test_map_matches_emitted_vocabulary() -> None:
    """Map definitions are exactly the emitted product + human score names."""
    names = set(defined_score_names())
    expected = set(PRODUCT_SCORES) | set(HUMAN_SCORES)
    assert names == expected, (
        f"FD map / emitted vocabulary drift: extra={sorted(names - expected)} missing={sorted(expected - names)}"
    )


def test_registry_is_single_source() -> None:
    """The shared registry equals the union of product and human score names."""
    assert set(FEEDBACK_DEFINITION_REGISTRY) == set(PRODUCT_SCORES) | set(HUMAN_SCORES)


def test_human_scores_match_review_queue_builder() -> None:
    """The registry's human.* names match review_queue._build_scores output keys."""
    src = inspect.getsource(review_queue._build_scores)
    for name in HUMAN_SCORES:
        assert name in src, f"review_queue._build_scores no longer emits {name!r}"


def test_product_scores_emitted_from_main() -> None:
    """The registry's product score names are emitted by the main.py emitter."""
    import git_cg.main as main_module

    src = inspect.getsource(main_module)
    for name in PRODUCT_SCORES:
        assert f'"name": "{name}"' in src, f"main.py emitter no longer emits {name!r}"


def test_notes_present_not_a_minted_fd() -> None:
    """human.notes_present is derived metadata — never in the map or registry."""
    names = defined_score_names()
    assert "human.notes_present" not in names
    assert "human.notes_present" not in FEEDBACK_DEFINITION_REGISTRY
    assert not any("notes_present" in n for n in names)


def test_final_accept_not_a_review_score() -> None:
    """final_accept is a provenance enum, never a Tier-1 review-outcome FD."""
    assert "final_accept" not in defined_score_names()
    assert "final_accept" not in FEEDBACK_DEFINITION_REGISTRY


def test_schema_pack_membership() -> None:
    """feedback_definition_v1 passes schema_files() filtering (no '_' prefix)."""
    assert "feedback_definition_v1" in list_schema_names()


def test_missing_data_file_is_fail_open(tmp_path) -> None:
    """Absent data file loads an empty map (offline-first), never raises."""
    data = load_feedback_definitions(path=tmp_path / "absent.json")
    assert data == {"schema_version": "feedback_definition_v1", "definitions": {}}


def test_malformed_json_fails_closed(tmp_path) -> None:
    """Malformed JSON is an authoring defect and must fail closed."""
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(FeedbackDefinitionError):
        load_feedback_definitions(path=bad)


def test_schema_invalid_content_fails_closed(tmp_path) -> None:
    """Schema-invalid content (unknown score / extra prop) must fail closed."""
    bad = tmp_path / "invalid.json"
    bad.write_text(
        '{"schema_version": "feedback_definition_v1",'
        ' "definitions": {"not_a_real_score": {"type": "numerical", "emitter": "x"}}}',
        encoding="utf-8",
    )
    with pytest.raises(FeedbackDefinitionError):
        load_feedback_definitions(path=bad)


def test_data_path_is_config_root() -> None:
    """The data map lives at the config/ root, not a config/eval/ subdir."""
    assert DATA_PATH.name == "feedback_definitions.json"
    assert DATA_PATH.parent.name == "config"
