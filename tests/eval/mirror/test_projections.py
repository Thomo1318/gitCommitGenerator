"""S4b/S5 projections: bundle→trace, session→thread, score_card→feedback."""

from __future__ import annotations

import pytest

from git_cg.eval.enums import Source
from git_cg.eval.mirror.projections import (
    FEEDBACK_SOURCE,
    ProjectionError,
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
    select_final_attempt,
)

BUNDLE = {
    "schema_version": "ape_bundle_v1",
    "id": "bundle_1",
    "artifact_class": "final_accept",
    "attempts": [
        {"final_message": "first", "scored_target": "final_message"},
        {
            "final_message": "✨ feat: final",
            "scored_target": "final_message",
            "artifact_class": "final_accept",
        },
    ],
    "gate": {"deterministic_pass": True},
    "score_card": {"format_compliance": 1.0, "subject_length": 0.9, "label": "good"},
    "meta": {"redaction_profile": "default_scrub", "train_label": "positive", "split_group_id": "sg1"},
}

SESSION_THREAD = {
    "schema_version": "commit_session_thread_v1",
    "id": "sessmeta_sess_1",
    "session_thread_id": "sess_1",
    "redaction_profile": "default_scrub",
    "attempt_ids": ["att_1", "att_2"],
    "message_versions": [{"v": 1}, {"v": 2}],
    "meta": {
        "lifecycle": "closed",
        "trace_id": "trace_1",
        "generation_thread_id": "gen_1",
    },
}


class TestSelectFinalAttempt:
    def test_explicit_final_accept_wins_over_list_order(self) -> None:
        bundle = {
            "artifact_class": "final_accept",
            "attempts": [
                {
                    "final_message": "✨ feat: final",
                    "scored_target": "final_message",
                    "artifact_class": "final_accept",
                },
                {"final_message": "later draft", "scored_target": "final_message"},
            ],
        }
        final = select_final_attempt(bundle)
        assert final is not None
        assert final["final_message"] == "✨ feat: final"

    def test_message_identity_when_no_attempt_class(self) -> None:
        bundle = {
            "artifact_class": "final_accept",
            "final_message": "✨ feat: bound",
            "attempts": [
                {"final_message": "draft", "scored_target": "final_message"},
                {"final_message": "✨ feat: bound", "scored_target": "final_message"},
            ],
        }
        final = select_final_attempt(bundle)
        assert final is not None
        assert final["final_message"] == "✨ feat: bound"

    def test_multiple_unbound_attempts_fail_closed(self) -> None:
        bundle = {
            "artifact_class": "final_accept",
            "attempts": [
                {"final_message": "a", "scored_target": "final_message"},
                {"final_message": "b", "scored_target": "final_message"},
            ],
        }
        with pytest.raises(ProjectionError, match="final_accept binding"):
            select_final_attempt(bundle)

    def test_empty_returns_none(self) -> None:
        assert select_final_attempt({}) is None


class TestProjectBundleToTrace:
    def test_uses_final_attempt(self) -> None:
        trace = project_bundle_to_trace(BUNDLE, experiment_name="exp")
        assert trace["output"]["final_message"] == "✨ feat: final"
        assert trace["input"]["attempt_count"] == 2

    def test_carries_gate_and_score_card(self) -> None:
        trace = project_bundle_to_trace(BUNDLE, experiment_name="exp")
        assert trace["metadata"]["deterministic_pass"] is True
        assert trace["metadata"]["score_card"]["format_compliance"] == 1.0
        assert trace["metadata"]["experiment_name"] == "exp"

    def test_authority_annotations_present(self) -> None:
        trace = project_bundle_to_trace(BUNDLE, experiment_name="exp")
        auth = trace["metadata"]["authority"]
        assert auth["source"] == Source.LOCAL_WRAPPER.value
        assert auth["cloud_rescore_forbidden"] is True
        assert auth["schema_pack"] and "@" in auth["schema_pack"]
        assert auth["metric_catalog"] and "@" in auth["metric_catalog"]
        assert auth["train_label"] == "positive"
        assert auth["split_group_id"] == "sg1"

    def test_empty_bundle_does_not_raise(self) -> None:
        trace = project_bundle_to_trace({}, experiment_name="exp")
        assert trace["output"]["final_message"] is None
        assert trace["input"]["attempt_count"] == 0


class TestProjectSessionThread:
    def test_preserves_session_id_and_lifecycle(self) -> None:
        thread = project_session_thread(SESSION_THREAD, experiment_name="exp")
        assert thread["thread_id"] == "sess_1"
        assert thread["lifecycle"] == "closed"
        assert thread["experiment_name"] == "exp"

    def test_carries_messages_and_attempt_ids(self) -> None:
        thread = project_session_thread(SESSION_THREAD, experiment_name="exp")
        assert thread["messages"] == [{"v": 1}, {"v": 2}]
        assert thread["metadata"]["attempt_ids"] == ["att_1", "att_2"]
        assert thread["metadata"]["trace_id"] == "trace_1"
        assert thread["metadata"]["source"] == FEEDBACK_SOURCE


class TestProjectScoreCardToFeedback:
    def test_numeric_entries_become_feedback(self) -> None:
        feedback = project_score_card_to_feedback(BUNDLE, experiment_name="exp")
        names = {f["name"] for f in feedback}
        assert "format_compliance" in names or "b.header_shape" in names or any("format" in n for n in names)
        assert any(n.endswith("subject_length") or n == "subject_length" or n == "b.subject_length" for n in names)
        # Non-numeric entries are excluded.
        assert "label" not in names
        assert "good" not in names

    def test_feedback_values_are_floats_with_closed_source(self) -> None:
        feedback = project_score_card_to_feedback(BUNDLE, experiment_name="exp")
        for f in feedback:
            assert isinstance(f["value"], float)
            assert f["source"] == FEEDBACK_SOURCE == "local_wrapper"
            assert f["experiment_name"] == "exp"
            assert f["authority"]["product_score_authority"] is True
            assert f["polarity"]

    def test_empty_score_card_returns_empty(self) -> None:
        assert project_score_card_to_feedback({}, experiment_name="exp") == []

    def test_bool_projected_as_pass_fail(self) -> None:
        bundle = {
            "artifact_class": "final_accept",
            "score_card": {"flag": True, "real": 0.5, "off": False},
            "attempts": [{"final_message": "x", "scored_target": "final_message"}],
        }
        feedback = project_score_card_to_feedback(bundle, experiment_name="exp")
        by_name = {f["name"]: f for f in feedback}
        assert "flag" in by_name
        assert by_name["flag"]["value"] == 1.0
        assert by_name["flag"]["polarity"] == "pass_fail"
        assert by_name["off"]["value"] == 0.0
        assert by_name["off"]["polarity"] == "pass_fail"
        assert by_name["real"]["value"] == 0.5
        assert all(f["source"] == "local_wrapper" for f in feedback)
