"""
Tests for scripts/sync_promptfoo_to_opik.py

Covers:
  - parse_iso_timestamp: ISO 8601 variants, Z suffix, fallback on invalid input
  - sync_results: file-not-found, invalid JSON, empty results, v1/v2 structures,
    success/failure feedback scores, grading component scores, timestamp/latency math
"""

import datetime
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from sync_promptfoo_to_opik import parse_iso_timestamp, sync_results  # noqa: E402

# ===========================================================================
# parse_iso_timestamp tests
# ===========================================================================


class TestParseIsoTimestamp:
    def test_z_suffix_converted_to_utc_offset(self):
        """'Z' suffix must be converted to '+00:00' before parsing."""
        result = parse_iso_timestamp("2026-06-22T10:00:00Z")
        assert result.tzinfo is not None
        assert result.year == 2026
        assert result.month == 6
        assert result.day == 22
        assert result.hour == 10

    def test_z_suffix_with_fractional_seconds(self):
        """'Z' suffix with fractional seconds must parse correctly."""
        result = parse_iso_timestamp("2026-06-22T10:00:00.123Z")
        assert result.microsecond == 123000
        assert result.tzinfo is not None

    def test_standard_iso_with_offset(self):
        """Standard ISO 8601 with explicit timezone offset must parse."""
        result = parse_iso_timestamp("2026-06-22T10:00:00+10:00")
        assert result.year == 2026
        assert result.hour == 10
        assert result.tzinfo is not None

    def test_returns_datetime_object(self):
        """Return type must always be datetime.datetime."""
        result = parse_iso_timestamp("2026-01-01T00:00:00Z")
        assert isinstance(result, datetime.datetime)

    def test_invalid_timestamp_returns_now(self):
        """A completely invalid timestamp must fall back to datetime.now(UTC)."""
        before = datetime.datetime.now(datetime.UTC)
        result = parse_iso_timestamp("not-a-timestamp")
        after = datetime.datetime.now(datetime.UTC)
        assert before <= result <= after

    def test_empty_string_falls_back_to_now(self):
        """An empty string is invalid and must fall back to datetime.now(UTC)."""
        before = datetime.datetime.now(datetime.UTC)
        result = parse_iso_timestamp("")
        after = datetime.datetime.now(datetime.UTC)
        assert before <= result <= after

    def test_naive_iso_without_tz(self):
        """A naive ISO string without timezone info should still parse."""
        result = parse_iso_timestamp("2026-06-22T10:00:00")
        assert result.year == 2026
        assert result.hour == 10

    def test_z_suffix_returns_utc(self):
        """Z-suffixed timestamp must produce a UTC-aware datetime."""
        result = parse_iso_timestamp("2026-06-22T12:30:45Z")
        assert result.utcoffset() == datetime.timedelta(0)

    def test_negative_tz_offset(self):
        """Negative timezone offsets should parse without error."""
        result = parse_iso_timestamp("2026-06-22T10:00:00-05:00")
        assert result.tzinfo is not None
        assert result.hour == 10


# ===========================================================================
# sync_results tests
# ===========================================================================


def _make_mock_opik():
    """
    Create mocked Opik objects for test assertions.

    Returns:
        tuple: The mock Opik class, client, and trace objects.
    """
    mock_trace = MagicMock()
    mock_client = MagicMock()
    mock_client.trace.return_value = mock_trace
    mock_opik_class = MagicMock(return_value=mock_client)
    return mock_opik_class, mock_client, mock_trace


class TestSyncResultsFileErrors:
    def test_exits_1_when_file_not_found(self, tmp_path):
        """sync_results must call sys.exit(1) for a missing file."""
        missing = tmp_path / "does_not_exist.json"
        with patch("sync_promptfoo_to_opik.opik.Opik"), pytest.raises(SystemExit) as exc_info:
            sync_results(str(missing))
        assert exc_info.value.code == 1

    def test_exits_1_when_json_is_invalid(self, tmp_path):
        """sync_results must call sys.exit(1) for malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ this is not json }")
        with patch("sync_promptfoo_to_opik.opik.Opik"), pytest.raises(SystemExit) as exc_info:
            sync_results(str(bad_file))
        assert exc_info.value.code == 1

    def test_exits_1_for_empty_file(self, tmp_path):
        """sync_results must call sys.exit(1) for a completely empty file (invalid JSON)."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        with patch("sync_promptfoo_to_opik.opik.Opik"), pytest.raises(SystemExit) as exc_info:
            sync_results(str(empty_file))
        assert exc_info.value.code == 1


class TestSyncResultsEmptyResults:
    def test_exits_0_when_results_list_is_empty_v2(self, tmp_path):
        """sync_results must call sys.exit(0) when the v2 results list is empty."""
        data = {"results": {"results": []}}
        json_file = tmp_path / "empty_results.json"
        json_file.write_text(json.dumps(data))
        mock_opik_class, _, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class), pytest.raises(SystemExit) as exc_info:
            sync_results(str(json_file))
        assert exc_info.value.code == 0

    def test_exits_0_when_results_key_missing(self, tmp_path):
        """sync_results must exit(0) when 'results' key is absent from the JSON."""
        data = {}
        json_file = tmp_path / "no_results.json"
        json_file.write_text(json.dumps(data))
        mock_opik_class, _, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class), pytest.raises(SystemExit) as exc_info:
            sync_results(str(json_file))
        assert exc_info.value.code == 0

    def test_exits_0_when_v1_results_list_is_empty(self, tmp_path):
        """sync_results must exit(0) when v1-style results list is empty."""
        data = {"results": []}
        json_file = tmp_path / "empty_v1.json"
        json_file.write_text(json.dumps(data))
        mock_opik_class, _, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class), pytest.raises(SystemExit) as exc_info:
            sync_results(str(json_file))
        assert exc_info.value.code == 0


class TestSyncResultsV2Structure:
    """Tests using v2 Promptfoo JSON structure (results nested inside dict)."""

    def _write_v2_file(self, tmp_path, results_list):
        data = {"results": {"results": results_list}}
        f = tmp_path / "results.json"
        f.write_text(json.dumps(data))
        return str(f)

    def test_creates_one_trace_per_result(self, tmp_path):
        """One Opik trace must be created for each result entry."""
        results = [
            {"prompt": {"raw": "msg1"}, "response": {"output": "out1"}, "success": True, "latencyMs": 100},
            {"prompt": {"raw": "msg2"}, "response": {"output": "out2"}, "success": False, "latencyMs": 200},
        ]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        assert mock_client.trace.call_count == 2

    def test_trace_name_is_promptfoo_eval(self, tmp_path):
        """Every trace must use 'promptfoo_eval' as its name."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "latencyMs": 10}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args
        assert call_kwargs.kwargs.get("name") == "promptfoo_eval" or call_kwargs.args[0] == "promptfoo_eval"

    def test_success_true_logs_score_1(self, tmp_path):
        """A result with success=True must log a feedback score of 1.0."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "latencyMs": 0}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        mock_trace.log_feedback_score.assert_any_call(name="success", value=1.0)

    def test_success_false_logs_score_0(self, tmp_path):
        """A result with success=False must log a feedback score of 0.0."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": False, "latencyMs": 0}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        mock_trace.log_feedback_score.assert_any_call(name="success", value=0.0)

    def test_trace_input_contains_prompt(self, tmp_path):
        """The trace input must include the raw prompt string."""
        results = [{"prompt": {"raw": "my prompt"}, "response": {"output": "o"}, "success": True, "latencyMs": 0}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["input"]["prompt"] == "my prompt"

    def test_trace_output_contains_response(self, tmp_path):
        """The trace output must include the model's raw output."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "the output"}, "success": True, "latencyMs": 0}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["output"]["output"] == "the output"

    def test_latency_sets_start_time_before_end_time(self, tmp_path):
        """start_time must be end_time minus latency milliseconds."""
        ts = "2026-06-22T10:00:01.000Z"
        latency_ms = 500
        results = [
            {
                "prompt": {"raw": "p"},
                "response": {"output": "o"},
                "success": True,
                "timestamp": ts,
                "latencyMs": latency_ms,
            }
        ]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        delta = call_kwargs["end_time"] - call_kwargs["start_time"]
        assert delta == datetime.timedelta(milliseconds=latency_ms)

    def test_zero_latency_makes_start_equal_end(self, tmp_path):
        """A latencyMs of 0 must result in start_time == end_time."""
        ts = "2026-06-22T10:00:00Z"
        results = [
            {"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "timestamp": ts, "latencyMs": 0}
        ]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["start_time"] == call_kwargs["end_time"]

    def test_missing_timestamp_still_creates_trace(self, tmp_path):
        """Results without a timestamp field must still produce a valid trace."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "latencyMs": 100}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        assert mock_client.trace.call_count == 1

    def test_vars_passed_to_trace_input(self, tmp_path):
        """The 'vars' dict from each result must be passed into the trace input."""
        results = [
            {
                "prompt": {"raw": "p"},
                "response": {"output": "o"},
                "success": True,
                "vars": {"diff": "some diff"},
                "latencyMs": 0,
            }
        ]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["input"]["vars"] == {"diff": "some diff"}

    def test_grading_component_results_logged_as_scores(self, tmp_path):
        """Assertion component results in gradingResult must be logged as individual scores."""
        grading = {
            "componentResults": [
                {"type": "javascript", "pass": True, "reason": "length ok"},
                {"type": "javascript", "pass": False, "reason": "regex failed"},
            ]
        }
        results = [
            {
                "prompt": {"raw": "p"},
                "response": {"output": "o"},
                "success": True,
                "latencyMs": 0,
                "gradingResult": grading,
            }
        ]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        mock_trace.log_feedback_score.assert_any_call(name="assertion_javascript", value=1.0, reason="length ok")
        mock_trace.log_feedback_score.assert_any_call(name="assertion_javascript", value=0.0, reason="regex failed")

    def test_grading_component_uses_custom_type_when_missing(self, tmp_path):
        """A grading component without a 'type' field defaults to 'custom'."""
        grading = {"componentResults": [{"pass": True, "reason": "ok"}]}
        results = [
            {
                "prompt": {"raw": "p"},
                "response": {"output": "o"},
                "success": True,
                "latencyMs": 0,
                "gradingResult": grading,
            }
        ]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        mock_trace.log_feedback_score.assert_any_call(name="assertion_custom", value=1.0, reason="ok")

    def test_no_grading_only_success_score_logged(self, tmp_path):
        """Without a gradingResult, only the success feedback score must be logged."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "latencyMs": 0}]
        file_path = self._write_v2_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        # Expect two calls: 'feedback_score' and 'success'
        assert mock_trace.log_feedback_score.call_count == 2

    def test_dummy_json_fixture_parses_successfully(self, tmp_path):
        """The repo dummy.json fixture must process without error."""
        dummy_path = Path(__file__).parent.parent / "dummy.json"
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(str(dummy_path))
        assert mock_client.trace.call_count == 1


class TestSyncResultsV1Structure:
    """Tests using v1 Promptfoo JSON structure (results directly as a list)."""

    def _write_v1_file(self, tmp_path, results_list):
        """
        Write a Promptfoo v1 results fixture to a temporary JSON file.

        Parameters:
            tmp_path: Temporary directory used to create the file.
            results_list: Results data to serialise under the top-level ``results`` key.

        Returns:
            str: Path to the written JSON file.
        """
        data = {"results": results_list}
        f = tmp_path / "results_v1.json"
        f.write_text(json.dumps(data))
        return str(f)

    def test_v1_structure_creates_traces(self, tmp_path):
        """v1-style results list must produce the correct number of traces."""
        results = [
            {"prompt": {"raw": "p1"}, "response": {"output": "o1"}, "success": True, "latencyMs": 100},
        ]
        file_path = self._write_v1_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        assert mock_client.trace.call_count == 1

    def test_v1_success_score(self, tmp_path):
        """v1 success=True must log a 1.0 feedback score."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "latencyMs": 0}]
        file_path = self._write_v1_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        mock_trace.log_feedback_score.assert_any_call(name="success", value=1.0)


class TestSyncResultsMissingFields:
    """Tests that missing optional fields don't crash sync_results."""

    def _write_file(self, tmp_path, results_list):
        """
        Write a Promptfoo v2 results fixture to a temporary JSON file.

        Parameters:
            tmp_path: Temporary directory used to create the file.
            results_list: Result entries to serialise under the nested ``results`` key.

        Returns:
            str: Path to the written JSON file.
        """
        data = {"results": {"results": results_list}}
        f = tmp_path / "results.json"
        f.write_text(json.dumps(data))
        return str(f)

    def test_missing_prompt_key_uses_empty_string(self, tmp_path):
        """A result missing 'prompt' must use an empty string without crashing."""
        results = [{"response": {"output": "o"}, "success": True, "latencyMs": 0}]
        file_path = self._write_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["input"]["prompt"] == ""

    def test_missing_response_key_uses_empty_string(self, tmp_path):
        """A result missing 'response' must use an empty string without crashing."""
        results = [{"prompt": {"raw": "p"}, "success": True, "latencyMs": 0}]
        file_path = self._write_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["output"]["output"] == ""

    def test_missing_success_defaults_to_false(self, tmp_path):
        """A result without a 'success' key must default to False → score 0.0."""
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "latencyMs": 0}]
        file_path = self._write_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        mock_trace.log_feedback_score.assert_any_call(name="success", value=0.0)

    def test_missing_latency_ms_defaults_to_zero(self, tmp_path):
        """A result without 'latencyMs' must default to 0 (start==end for a given timestamp)."""
        ts = "2026-06-22T10:00:00Z"
        results = [{"prompt": {"raw": "p"}, "response": {"output": "o"}, "success": True, "timestamp": ts}]
        file_path = self._write_file(tmp_path, results)
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        call_kwargs = mock_client.trace.call_args.kwargs
        assert call_kwargs["start_time"] == call_kwargs["end_time"]

    def test_empty_grading_component_results_list(self, tmp_path):
        """An empty componentResults list must not raise and only logs success score."""
        grading = {"componentResults": []}
        results = [
            {
                "prompt": {"raw": "p"},
                "response": {"output": "o"},
                "success": True,
                "latencyMs": 0,
                "gradingResult": grading,
            }
        ]
        file_path = self._write_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        # Only success scores, no component scores
        assert mock_trace.log_feedback_score.call_count == 2

    def test_grading_result_without_component_results_key(self, tmp_path):
        """A gradingResult without 'componentResults' key must not raise."""
        grading = {"score": 0.5}
        results = [
            {
                "prompt": {"raw": "p"},
                "response": {"output": "o"},
                "success": True,
                "latencyMs": 0,
                "gradingResult": grading,
            }
        ]
        file_path = self._write_file(tmp_path, results)
        mock_opik_class, _mock_client, mock_trace = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(file_path)
        # Only success scores
        assert mock_trace.log_feedback_score.call_count == 2

    def test_multiple_results_each_get_own_trace(self, tmp_path):
        """Each result in a multi-result file must get its own independent trace."""
        results = [
            {"prompt": {"raw": "p1"}, "response": {"output": "o1"}, "success": True, "latencyMs": 0},
            {"prompt": {"raw": "p2"}, "response": {"output": "o2"}, "success": False, "latencyMs": 0},
            {"prompt": {"raw": "p3"}, "response": {"output": "o3"}, "success": True, "latencyMs": 0},
        ]
        data = {"results": {"results": results}}
        f = tmp_path / "multi.json"
        f.write_text(json.dumps(data))
        mock_opik_class, mock_client, _ = _make_mock_opik()
        with patch("sync_promptfoo_to_opik.opik.Opik", mock_opik_class):
            sync_results(str(f))
        assert mock_client.trace.call_count == 3
