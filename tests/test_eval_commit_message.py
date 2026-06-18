"""
Tests for scripts/eval_commit_message.py covering the PR changes:
- _generation_cache: caching generated results to avoid duplicate LLM calls
- evaluation_task(): dict vs object input handling, expected_output normalisation,
  isinstance(parsed, dict) guard for JSON list inputs, and engine env-var resolution
- Tier-1/Tier-2 gating logic in main() (all_passed check)
"""

import json
import os
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Stub out all heavy external dependencies before importing the module under
# test so that import succeeds without a real opik installation or git_cg env.
# ---------------------------------------------------------------------------


def _stub_opik():
    """Return a minimal opik stub."""
    mod = types.ModuleType("opik")
    mod.Opik = type("Opik", (), {"get_dataset": lambda self, name: None})
    evaluation_mod = types.ModuleType("opik.evaluation")
    evaluation_mod.evaluate = lambda **kwargs: None
    metrics_mod = types.ModuleType("opik.evaluation.metrics")

    class _GEval:
        def __init__(self, *args, **kwargs):
            pass

    metrics_mod.GEval = _GEval
    score_result_mod = types.ModuleType("opik.evaluation.metrics.score_result")

    class _BaseMetric:
        def __init__(self, name="metric"):
            self.name = name

    class _ScoreResult:
        def __init__(self, name, value, reason=""):
            self.name = name
            self.value = value
            self.reason = reason

    metrics_mod.BaseMetric = _BaseMetric
    score_result_mod.ScoreResult = _ScoreResult

    sys.modules.setdefault("opik", mod)
    sys.modules.setdefault("opik.evaluation", evaluation_mod)
    sys.modules.setdefault("opik.evaluation.metrics", metrics_mod)
    sys.modules.setdefault("opik.evaluation.metrics.score_result", score_result_mod)


# Add scripts to path so opik_metrics is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))

# Now import the module under test
import eval_commit_message as ecm  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeItem:
    """Simulate a non-dict dataset item (attribute-based access)."""

    def __init__(self, diff_output="diff content", expected_output="expected msg"):
        self.diff_output = diff_output
        self.expected_output = expected_output


@pytest.fixture(autouse=True)
def clear_generation_cache():
    """Reset the module-level cache before every test."""
    ecm._generation_cache.clear()
    yield
    ecm._generation_cache.clear()


@pytest.fixture(autouse=True)
def mock_git_cg_dependencies(monkeypatch):
    """Automatically mock AI generation dependencies for all tests in this file."""

    class _FakeCommitPlan:
        def render(self):
            return "✨ feat(test): generated commit message"

    # We must allow kwargs to pass through because generate_commit_message accepts **kwargs
    monkeypatch.setattr(
        ecm,
        "generate_commit_message",
        lambda client, diff_output, model_name, system_prompt, **kwargs: _FakeCommitPlan(),
    )
    monkeypatch.setattr(ecm, "get_ai_client", lambda engine: object())


# ---------------------------------------------------------------------------
# evaluation_task - dict input handling
# ---------------------------------------------------------------------------


class TestEvaluationTaskDictInput:
    def test_dict_input_returns_dict_with_required_keys(self):
        item = {"diff_output": "some diff", "expected_output": "expected"}
        result = ecm.evaluation_task(item)
        assert set(result.keys()) == {"input", "output", "expected_output"}

    def test_dict_input_passes_diff_as_input(self):
        item = {"diff_output": "my diff content", "expected_output": "expected"}
        result = ecm.evaluation_task(item)
        assert result["input"] == "my diff content"

    def test_dict_input_plain_expected_output_preserved(self):
        item = {"diff_output": "diff", "expected_output": "plain expected"}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == "plain expected"

    def test_dict_input_missing_diff_defaults_to_empty_string(self):
        item = {"expected_output": "expected"}
        result = ecm.evaluation_task(item)
        assert result["input"] == ""

    def test_dict_input_missing_expected_defaults_to_empty_string(self):
        item = {"diff_output": "diff"}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == ""


# ---------------------------------------------------------------------------
# evaluation_task - object (attribute) input handling
# ---------------------------------------------------------------------------


class TestEvaluationTaskObjectInput:
    def test_object_input_returns_dict_with_required_keys(self):
        item = _FakeItem(diff_output="diff", expected_output="expected")
        result = ecm.evaluation_task(item)
        assert set(result.keys()) == {"input", "output", "expected_output"}

    def test_object_input_passes_diff_as_input(self):
        item = _FakeItem(diff_output="object diff", expected_output="expected")
        result = ecm.evaluation_task(item)
        assert result["input"] == "object diff"

    def test_object_input_missing_diff_defaults_to_empty_string(self):
        class _NoFields:
            pass

        result = ecm.evaluation_task(_NoFields())
        assert result["input"] == ""

    def test_object_input_plain_expected_output_preserved(self):
        item = _FakeItem(diff_output="diff", expected_output="plain string")
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == "plain string"


# ---------------------------------------------------------------------------
# evaluation_task - expected_output normalisation
# ---------------------------------------------------------------------------


class TestExpectedOutputNormalisation:
    def test_dict_expected_with_output_key_is_unwrapped(self):
        """expected_output as dict with 'output' key should be unwrapped."""
        item = {"diff_output": "diff", "expected_output": {"output": "unwrapped"}}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == "unwrapped"

    def test_dict_expected_without_output_key_is_preserved(self):
        """expected_output as dict WITHOUT 'output' key should stay as-is."""
        item = {"diff_output": "diff", "expected_output": {"other_key": "value"}}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == {"other_key": "value"}

    def test_json_string_with_output_key_is_unwrapped(self):
        """expected_output as JSON string containing 'output' key should be unwrapped."""
        payload = json.dumps({"output": "from json"})
        item = {"diff_output": "diff", "expected_output": payload}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == "from json"

    def test_json_string_without_output_key_is_preserved(self):
        """JSON string dict WITHOUT 'output' key should be left as the parsed string."""
        payload = json.dumps({"other": "value"})
        item = {"diff_output": "diff", "expected_output": payload}
        result = ecm.evaluation_task(item)
        # No "output" key - the original string is preserved (json.loads raises no error,
        # but the branch condition `isinstance(parsed, dict) and "output" in parsed` is False)
        assert result["expected_output"] == payload

    def test_json_list_string_is_not_unwrapped(self):
        """JSON string that parses to a list must NOT attempt dict['output'] access.

        This tests the isinstance(parsed, dict) guard added in this PR that prevents
        a TypeError when the parsed JSON is a list.
        """
        payload = json.dumps(["item1", "item2"])
        item = {"diff_output": "diff", "expected_output": payload}
        # Should NOT raise TypeError, should preserve the original string
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == payload

    def test_invalid_json_string_is_preserved(self):
        """A string that is not valid JSON should be kept as-is (JSONDecodeError caught)."""
        payload = "not valid JSON {{{"
        item = {"diff_output": "diff", "expected_output": payload}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == payload

    def test_plain_string_is_preserved(self):
        """A plain non-JSON string should be kept exactly as-is."""
        item = {"diff_output": "diff", "expected_output": "feat: simple message"}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == "feat: simple message"

    def test_json_number_string_is_preserved(self):
        """A JSON string that parses to a number (not dict) should be preserved as-is."""
        payload = "42"
        item = {"diff_output": "diff", "expected_output": payload}
        result = ecm.evaluation_task(item)
        assert result["expected_output"] == payload


# ---------------------------------------------------------------------------
# _generation_cache - caching behaviour
# ---------------------------------------------------------------------------


class TestGenerationCache:
    def test_result_is_cached_after_first_call(self):
        """After evaluation_task is called, the result should be in _generation_cache."""
        item = {"diff_output": "unique diff abc", "expected_output": "expected"}
        ecm.evaluation_task(item)
        assert "unique diff abc" in ecm._generation_cache

    def test_cached_result_returned_on_second_call(self):
        """Second call with the same diff_output must use the cached value."""
        diff = "same diff content"
        item = {"diff_output": diff, "expected_output": "expected"}

        result1 = ecm.evaluation_task(item)
        # Modify the stub so a second real generation would return a different value
        original_fn = ecm.generate_commit_message
        ecm.generate_commit_message = lambda *args, **kwargs: type(
            "Plan", (), {"render": lambda self: "different message"}
        )()

        result2 = ecm.evaluation_task(item)

        # Restore
        ecm.generate_commit_message = original_fn

        assert result1["output"] == result2["output"]

    def test_different_diffs_have_separate_cache_entries(self):
        """Two different diffs should be cached independently."""
        item1 = {"diff_output": "diff one", "expected_output": "expected"}
        item2 = {"diff_output": "diff two", "expected_output": "expected"}
        ecm.evaluation_task(item1)
        ecm.evaluation_task(item2)
        assert "diff one" in ecm._generation_cache
        assert "diff two" in ecm._generation_cache

    def test_cache_is_empty_at_start(self):
        """Cache starts empty (autouse fixture clears it)."""
        assert ecm._generation_cache == {}

    def test_cached_output_value_matches_generated_output(self):
        """The value stored in the cache must equal the output returned by evaluation_task."""
        diff = "cache consistency diff"
        item = {"diff_output": diff, "expected_output": "expected"}
        result = ecm.evaluation_task(item)
        assert ecm._generation_cache[diff] == result["output"]


# ---------------------------------------------------------------------------
# Engine resolution logic (GIT_CG_ENGINE env var)
# ---------------------------------------------------------------------------


class TestEngineResolution:
    def test_env_var_with_leading_trailing_whitespace_is_stripped(self, monkeypatch):
        """GIT_CG_ENGINE with whitespace should be stripped before use."""
        captured = {}
        original_get_ai_client = ecm.get_ai_client
        ecm.get_ai_client = lambda engine: captured.update({"engine": engine}) or object()

        monkeypatch.setenv("GIT_CG_ENGINE", "  mtplx  ")
        item = {"diff_output": "whitespace engine diff", "expected_output": "expected"}
        ecm.evaluation_task(item)

        ecm.get_ai_client = original_get_ai_client
        assert captured.get("engine") == "mtplx"

    def test_empty_env_var_defaults_to_mtplx(self, monkeypatch):
        """Empty GIT_CG_ENGINE should default to 'mtplx'."""
        captured = {}
        original_get_ai_client = ecm.get_ai_client
        ecm.get_ai_client = lambda engine: captured.update({"engine": engine}) or object()

        monkeypatch.setenv("GIT_CG_ENGINE", "")
        item = {"diff_output": "empty engine diff", "expected_output": "expected"}
        ecm.evaluation_task(item)

        ecm.get_ai_client = original_get_ai_client
        assert captured.get("engine") == "mtplx"

    def test_whitespace_only_env_var_defaults_to_mtplx(self, monkeypatch):
        """Whitespace-only GIT_CG_ENGINE should default to 'mtplx' after strip."""
        captured = {}
        original_get_ai_client = ecm.get_ai_client
        ecm.get_ai_client = lambda engine: captured.update({"engine": engine}) or object()

        monkeypatch.setenv("GIT_CG_ENGINE", "   ")
        item = {"diff_output": "whitespace-only engine diff", "expected_output": "expected"}
        ecm.evaluation_task(item)

        ecm.get_ai_client = original_get_ai_client
        assert captured.get("engine") == "mtplx"

    def test_valid_engine_env_var_is_passed_through(self, monkeypatch):
        """A valid non-default engine name should be passed to get_ai_client."""
        captured = {}
        original_get_ai_client = ecm.get_ai_client
        ecm.get_ai_client = lambda engine: captured.update({"engine": engine}) or object()

        monkeypatch.setenv("GIT_CG_ENGINE", "ollama")
        item = {"diff_output": "custom engine diff", "expected_output": "expected"}
        ecm.evaluation_task(item)

        ecm.get_ai_client = original_get_ai_client
        assert captured.get("engine") == "ollama"


# ---------------------------------------------------------------------------
# Tier-1 / Tier-2 gating logic
# ---------------------------------------------------------------------------


class TestTierGatingLogic:
    """
    Test the all_passed gating logic extracted from main().

    The logic is:
        all_passed = True
        for test_result in getattr(eval_results, "test_results", []):
            for metric_result in getattr(test_result, "score_results", []):
                if (
                    getattr(metric_result, "name", "") == "CommitFormatQuality"
                    and getattr(metric_result, "value", 0.0) < 1.0
                ):
                    all_passed = False
                    break
            if not all_passed:
                break
    """

    @staticmethod
    def _eval_all_passed(eval_results) -> bool:
        """Replicate the all_passed check from main() for isolated testing."""
        all_passed = True
        for test_result in getattr(eval_results, "test_results", []):
            for metric_result in getattr(test_result, "score_results", []):
                if (
                    getattr(metric_result, "name", "") == "CommitFormatQuality"
                    and getattr(metric_result, "value", 0.0) < 1.0
                ):
                    all_passed = False
                    break
            if not all_passed:
                break
        return all_passed

    def _make_eval_results(self, scores: list[tuple[str, float]]):
        """Build a fake eval_results object with the given (name, value) score pairs."""

        class MetricResult:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        class TestResult:
            def __init__(self, score_results):
                self.score_results = score_results

        class EvalResults:
            def __init__(self, test_results):
                self.test_results = test_results

        metric_results = [MetricResult(name, value) for name, value in scores]
        return EvalResults([TestResult(metric_results)])

    def test_all_passed_when_no_test_results(self):
        """Empty test_results should leave all_passed True."""

        class EmptyResults:
            def __init__(self):
                self.test_results = []

        assert self._eval_all_passed(EmptyResults()) is True

    def test_all_passed_when_eval_results_has_no_attribute(self):
        """eval_results without test_results attribute should default to [] via getattr."""
        assert self._eval_all_passed(object()) is True

    def test_all_passed_with_perfect_format_score(self):
        """CommitFormatQuality score of 1.0 should keep all_passed True."""
        results = self._make_eval_results([("CommitFormatQuality", 1.0)])
        assert self._eval_all_passed(results) is True

    def test_all_passed_fails_with_format_score_below_one(self):
        """CommitFormatQuality score < 1.0 must set all_passed to False."""
        results = self._make_eval_results([("CommitFormatQuality", 0.8)])
        assert self._eval_all_passed(results) is False

    def test_all_passed_fails_with_zero_format_score(self):
        """CommitFormatQuality score of 0.0 must set all_passed to False."""
        results = self._make_eval_results([("CommitFormatQuality", 0.0)])
        assert self._eval_all_passed(results) is False

    def test_all_passed_ignores_non_format_metric(self):
        """Other metric names should not affect the all_passed flag."""
        results = self._make_eval_results([("OtherMetric", 0.0)])
        assert self._eval_all_passed(results) is True

    def test_all_passed_fails_when_any_item_fails(self):
        """If any test_result has a failing CommitFormatQuality score, all_passed is False."""

        class MetricResult:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        class TestResult:
            def __init__(self, score_results):
                self.score_results = score_results

        class EvalResults:
            def __init__(self, test_results):
                self.test_results = test_results

        # First test_result passes, second fails
        results = EvalResults(
            [
                TestResult([MetricResult("CommitFormatQuality", 1.0)]),
                TestResult([MetricResult("CommitFormatQuality", 0.5)]),
            ]
        )
        assert self._eval_all_passed(results) is False

    def test_all_passed_with_mixed_metrics_where_format_passes(self):
        """Multiple metrics; CommitFormatQuality passes; all_passed should be True."""
        results = self._make_eval_results(
            [
                ("CommitFormatQuality", 1.0),
                ("CommitMessageQuality", 0.4),  # other metric, should be ignored
            ]
        )
        assert self._eval_all_passed(results) is True

    def test_all_passed_with_missing_name_attribute(self):
        """Metric results without a 'name' attribute should use '' default and be ignored."""

        class NoName:
            value = 0.0

        class TestResult:
            def __init__(self):
                self.score_results = [NoName()]

        class EvalResults:
            def __init__(self):
                self.test_results = [TestResult()]

        assert self._eval_all_passed(EvalResults()) is True

    def test_all_passed_with_missing_value_attribute(self):
        """Metric results without a 'value' attribute should use 0.0 default."""

        class NoValue:
            name = "CommitFormatQuality"

        class TestResult:
            def __init__(self):
                self.score_results = [NoValue()]

        class EvalResults:
            def __init__(self):
                self.test_results = [TestResult()]

        # value defaults to 0.0 which is < 1.0 → all_passed should be False
        assert self._eval_all_passed(EvalResults()) is False


# ---------------------------------------------------------------------------
# Regression: JSON list input does not raise TypeError
# ---------------------------------------------------------------------------


def test_json_list_expected_output_does_not_raise():
    """Regression: JSON list as expected_output must not raise TypeError.

    Prior to the isinstance(parsed, dict) guard, `parsed["output"]` on a list
    would raise TypeError. This test ensures the guard is in place.
    """
    payload = json.dumps(["commit msg", "other"])
    item = {"diff_output": "regression diff", "expected_output": payload}
    # Must not raise
    result = ecm.evaluation_task(item)
    assert result["expected_output"] == payload


def test_evaluation_task_output_is_string():
    """The 'output' field of the evaluation payload must always be a string."""
    item = {"diff_output": "string output diff", "expected_output": "expected"}
    result = ecm.evaluation_task(item)
    assert isinstance(result["output"], str)
