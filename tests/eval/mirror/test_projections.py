"""S4b projections: bundle→trace, session→thread, score_card→feedback."""

from __future__ import annotations

from git_cg.eval.mirror.projections import (
    project_bundle_to_trace,
    project_score_card_to_feedback,
    project_session_thread,
)

BUNDLE = {
    "schema_version": "ape_bundle_v1",
    "id": "bundle_1",
    "attempts": [
        {"final_message": "first", "scored_target": "final_message"},
        {"final_message": "✨ feat: final", "scored_target": "final_message"},
    ],
    "gate": {"deterministic_pass": True},
    "score_card": {"format_compliance": 1.0, "subject_length": 0.9, "label": "good"},
    "meta": {"redaction_profile": "default_scrub"},
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


class TestProjectScoreCardToFeedback:
    def test_numeric_entries_become_feedback(self) -> None:
        feedback = project_score_card_to_feedback(BUNDLE, experiment_name="exp")
        names = {f["name"] for f in feedback}
        assert "format_compliance" in names
        assert "subject_length" in names
        # Non-numeric entries are excluded.
        assert "label" not in names

    def test_feedback_values_are_floats(self) -> None:
        feedback = project_score_card_to_feedback(BUNDLE, experiment_name="exp")
        for f in feedback:
            assert isinstance(f["value"], float)
            assert f["source"] == "deterministic_score_card"
            assert f["experiment_name"] == "exp"

    def test_empty_score_card_returns_empty(self) -> None:
        assert project_score_card_to_feedback({}, experiment_name="exp") == []

    def test_bool_excluded(self) -> None:
        bundle = {"score_card": {"flag": True, "real": 0.5}}
        feedback = project_score_card_to_feedback(bundle, experiment_name="exp")
        assert [f["name"] for f in feedback] == ["real"]
