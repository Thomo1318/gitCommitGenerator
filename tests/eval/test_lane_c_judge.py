"""S5c Lane C-prime — pinned GEval judge wiring (never blocking, gold-blind).

Covers the judge outcome contract (input guards, pack resolution, parse
validation), the injectable judge seam (no network), and the runner's eligible
path: real advisory scores on success, honest skip rows on every failure class.
All tests are offline — the judge callable is always injected.
"""

from __future__ import annotations

import json

import pytest

from git_cg.eval.enums import Authority, Source
from git_cg.eval.lane_c.judge import (
    DEFAULT_JUDGE_MAX_RETRIES,
    DEFAULT_JUDGE_TIMEOUT_S,
    REASON_EMPTY_INPUT,
    REASON_INPUT_TOO_LARGE,
    REASON_JUDGE_ERROR,
    REASON_JUDGE_PARSE_ERROR,
    REASON_PACK_UNRESOLVABLE,
    _parse_judge_response,
    openai_compatible_judge_fn,
    resolve_judge_credentials,
    run_pinned_judge,
)
from git_cg.eval.lane_c.runner import REASON_COHORT_INELIGIBLE, run_lane_c

# ---------------------------------------------------------------------------\
# Fake judge seam (no network)
# ---------------------------------------------------------------------------/


def _fake_judge(score: int = 4, rationale: str = "solid"):
    def _fn(system_prompt: str, user_prompt: str, model: str, api_key: str) -> str:
        return json.dumps({"score": score, "rationale": rationale})

    return _fn


def _boom_judge(system_prompt: str, user_prompt: str, model: str, api_key: str) -> str:
    raise RuntimeError("judge unavailable")


# ---------------------------------------------------------------------------\
# Credential resolution
# ---------------------------------------------------------------------------/


class TestResolveJudgeCredentials:
    def test_explicit_args_win(self) -> None:
        model, key = resolve_judge_credentials(judge_model="m1", judge_api_key="k1", environ={})
        assert (model, key) == ("m1", "k1")

    def test_env_fallback(self) -> None:
        env = {"GIT_CG_EVAL_JUDGE_MODEL": "envm", "GIT_CG_EVAL_JUDGE_API_KEY": "envk"}
        assert resolve_judge_credentials(environ=env) == ("envm", "envk")

    def test_strips_whitespace(self) -> None:
        model, key = resolve_judge_credentials(judge_model="  m ", judge_api_key=" k ", environ={})
        assert (model, key) == ("m", "k")


# ---------------------------------------------------------------------------\
# Response parsing (pure)
# ---------------------------------------------------------------------------/


class TestParseJudgeResponse:
    def test_valid(self) -> None:
        assert _parse_judge_response('{"score": 5, "rationale": "great"}') == (5, "great")

    def test_missing_rationale_defaults_empty(self) -> None:
        assert _parse_judge_response('{"score": 3}') == (3, "")

    def test_bool_score_rejected(self) -> None:
        with pytest.raises(ValueError, match="integer"):
            _parse_judge_response('{"score": true}')

    def test_float_score_rejected(self) -> None:
        with pytest.raises(ValueError, match="integer"):
            _parse_judge_response('{"score": 4.5}')

    def test_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            _parse_judge_response('{"score": 0}')
        with pytest.raises(ValueError, match="out of range"):
            _parse_judge_response('{"score": 6}')

    def test_non_object_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a JSON object"):
            _parse_judge_response("[1,2,3]")

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _parse_judge_response("not json")


# ---------------------------------------------------------------------------\
# run_pinned_judge — guards and outcome contract (offline via injected judge)
# ---------------------------------------------------------------------------/


class TestRunPinnedJudge:
    def test_empty_input_skips_before_network(self) -> None:
        called = []

        def _spy(*a: object) -> str:
            called.append(a)
            return '{"score": 5}'

        out = run_pinned_judge(
            "cprime.geval_craft",
            message="   ",
            judge_model="m",
            judge_api_key="k",
            judge_fn=_spy,
        )
        assert out.scored is False
        assert out.reason == REASON_EMPTY_INPUT
        assert out.evidence["h.eval_input_nonempty"] is False
        assert called == []  # judge never invoked

    def test_oversize_input_skips(self) -> None:
        out = run_pinned_judge(
            "cprime.geval_craft",
            message="x" * 100,
            judge_model="m",
            judge_api_key="k",
            max_input_chars=10,
            judge_fn=_fake_judge(),
        )
        assert out.scored is False
        assert out.reason == REASON_INPUT_TOO_LARGE
        assert out.evidence["h.eval_input_size_ok"] is False

    def test_unresolvable_pack_skips(self) -> None:
        out = run_pinned_judge(
            "cprime.usefulness",  # no on-disk pack
            message="feat: x",
            judge_model="m",
            judge_api_key="k",
            judge_fn=_fake_judge(),
        )
        assert out.scored is False
        assert out.reason == REASON_PACK_UNRESOLVABLE

    def test_judge_exception_degrades_not_raises(self) -> None:
        out = run_pinned_judge(
            "cprime.geval_craft",
            message="feat: add thing",
            judge_model="m",
            judge_api_key="k",
            judge_fn=_boom_judge,
        )
        assert out.scored is False
        assert out.reason == REASON_JUDGE_ERROR
        assert out.evidence["error_type"] == "RuntimeError"
        assert out.pack is not None  # pack resolved before the call

    def test_parse_error_degrades(self) -> None:
        out = run_pinned_judge(
            "cprime.geval_craft",
            message="feat: add thing",
            judge_model="m",
            judge_api_key="k",
            judge_fn=lambda *a: "not json",
        )
        assert out.scored is False
        assert out.reason == REASON_JUDGE_PARSE_ERROR

    def test_success_scores_and_pins_pack(self) -> None:
        out = run_pinned_judge(
            "cprime.geval_craft",
            message="feat(eval-lane-c): add thing",
            judge_model="gpt-4o-2024-08-06",
            judge_api_key="k",
            judge_fn=_fake_judge(score=5, rationale="exemplary"),
        )
        assert out.scored is True
        assert out.score == 5
        assert out.rationale == "exemplary"
        assert out.evidence["judge_model"] == "gpt-4o-2024-08-06"
        assert out.evidence["prompt_pack_id"] == "lane_c_geval_craft"
        assert len(out.evidence["prompt_pack_sha256"]) == 64

    def test_gold_blind_prompt_carries_no_expected(self) -> None:
        captured = {}

        def _spy(system_prompt: str, user_prompt: str, model: str, api_key: str) -> str:
            captured["user"] = user_prompt
            return '{"score": 4}'

        run_pinned_judge(
            "cprime.geval_relevance",
            message="fix: correct thing",
            diff_summary="1 file changed",
            judge_model="m",
            judge_api_key="k",
            judge_fn=_spy,
        )
        assert "expected" not in captured["user"].lower()
        assert "fix: correct thing" in captured["user"]
        assert "1 file changed" in captured["user"]


class TestOpenAICompatibleJudgeFn:
    """Default transport is bounded: short timeout, single retry (no storms)."""

    def test_client_is_bounded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        class _FakeCompletions:
            def create(self, **kwargs: object) -> object:
                captured["create_kwargs"] = kwargs

                class _Msg:
                    content = '{"score": 3}'

                class _Choice:
                    message = _Msg()

                class _Resp:
                    def __init__(self) -> None:
                        self.choices = [_Choice()]

                return _Resp()

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeOpenAI:
            def __init__(self, **kwargs: object) -> None:
                captured["client_kwargs"] = kwargs
                self.chat = _FakeChat()

        import sys
        import types

        fake_module = types.ModuleType("openai")
        fake_module.OpenAI = _FakeOpenAI  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        raw = openai_compatible_judge_fn("sys", "user", "m", "k")

        assert raw == '{"score": 3}'
        assert captured["client_kwargs"]["timeout"] == DEFAULT_JUDGE_TIMEOUT_S
        assert captured["client_kwargs"]["max_retries"] == DEFAULT_JUDGE_MAX_RETRIES
        create_kwargs = captured["create_kwargs"]
        assert create_kwargs["model"] == "m"
        assert create_kwargs["temperature"] == 0
        roles = [m["role"] for m in create_kwargs["messages"]]
        assert roles == ["system", "user"]


# ---------------------------------------------------------------------------\
# Runner — eligible path now invokes the pinned judge (S5c)
# ---------------------------------------------------------------------------/

_ENV = {"GIT_CG_EVAL_JUDGE_MODEL": "m", "GIT_CG_EVAL_JUDGE_API_KEY": "k"}


class TestRunLaneCJudgeWiring:
    def test_eligible_real_score_advisory(self) -> None:
        rows, elig = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=_ENV,
            message="feat(eval-lane-c): add thing",
            judge_fn=_fake_judge(score=4, rationale="good craft"),
        )
        assert elig.eligible is True
        r = rows[0]
        assert r.value == 4
        assert r.authority is Authority.ADVISORY  # F3
        assert r.source is Source.LANE_C_JUDGE
        assert r.passed is None  # advisory: no boolean verdict
        assert r.reason == "good craft"
        assert r.evidence and r.evidence["skipped"] is False
        assert r.evidence["prompt_pack_sha256"]

    def test_eligible_judge_failure_emits_skip_not_raise(self) -> None:
        rows, elig = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=_ENV,
            message="feat: x",
            judge_fn=_boom_judge,
        )
        assert elig.eligible is True
        assert rows[0].passed is None
        assert rows[0].reason == REASON_JUDGE_ERROR
        assert rows[0].authority is Authority.ADVISORY

    def test_eligible_empty_message_skips(self) -> None:
        rows, _ = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=_ENV,
            message="",
            judge_fn=_fake_judge(),
        )
        assert rows[0].passed is None
        assert rows[0].reason == REASON_EMPTY_INPUT

    def test_ineligible_still_skips_without_judge(self) -> None:
        called = []

        def _spy(*a: object) -> str:
            called.append(a)
            return '{"score": 5}'

        rows, elig = run_lane_c(
            ["cprime.geval_craft"],
            deterministic_pass=True,
            allows_lane_c=False,  # gate closed
            environ={},
            message="feat: x",
            judge_fn=_spy,
        )
        assert elig.eligible is False
        assert rows[0].reason == REASON_COHORT_INELIGIBLE
        assert rows[0].passed is None
        assert called == []  # judge never runs when gate closed

    def test_per_metric_independent_outcomes(self) -> None:
        # craft scores, relevance has no pack override → both resolve here,
        # but a judge that fails on the second call isolates per-metric.
        calls = {"n": 0}

        def _flaky(system_prompt: str, user_prompt: str, model: str, api_key: str) -> str:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("second metric boom")
            return '{"score": 3, "rationale": "ok"}'

        rows, elig = run_lane_c(
            ["cprime.geval_craft", "cprime.geval_relevance"],
            deterministic_pass=True,
            allows_lane_c=True,
            environ=_ENV,
            message="feat: x",
            judge_fn=_flaky,
        )
        assert elig.eligible is True
        assert rows[0].value == 3
        assert rows[0].passed is None
        assert rows[1].passed is None
        assert rows[1].reason == REASON_JUDGE_ERROR

    def test_unknown_metric_id_still_fails_closed(self) -> None:
        with pytest.raises(KeyError):
            run_lane_c(
                ["cprime.does_not_exist"],
                deterministic_pass=True,
                allows_lane_c=True,
                environ=_ENV,
                message="feat: x",
                judge_fn=_fake_judge(),
            )
