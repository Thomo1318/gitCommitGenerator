"""S5c Lane C' — injectable pinned judge (C-JUDGE / C-SEC)."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from git_cg.eval.binding.binder import message_sha256_bytes
from git_cg.eval.enums import ArtifactClass
from git_cg.eval.lane_c.judge import (
    DEFAULT_MAX_RETRIES,
    JudgeTransportResult,
    openai_compatible_judge_fn,
    parse_judge_score,
    resolve_judge_credentials,
    run_pinned_judge,
)
from git_cg.eval.lane_c.judge_input import JudgeInput, project_judge_input
from git_cg.eval.lane_c.taxonomy import (
    EXEC_EMPTY_INPUT,
    EXEC_OVERSIZE_INPUT,
    EXEC_PARSE_ERROR,
    EXEC_SCORED,
    EXEC_TIMEOUT,
    EXEC_TRANSPORT_ERROR,
)

PINNED_MODEL = "gpt-4o-2024-08-06"
FINAL_TEXT = (
    "✨ feat(eval): add pinned judge\n\nRefs: #233\nSemVer-Impact: MINOR\nChange-Types: feat\nChangelog-Groups: Added\n"
)


def _judge_input(**overrides: Any) -> JudgeInput:
    """Build a validated ``JudgeInput`` for tests (optional field overrides)."""
    bundle = {
        "artifact_class": ArtifactClass.FINAL_ACCEPT.value,
        "bound": True,
        "final_message": FINAL_TEXT,
        "final_message_sha256": message_sha256_bytes(FINAL_TEXT),
        "encoding": "utf-8",
    }
    bundle.update(overrides)
    return project_judge_input(bundle)


class TestParseJudgeScore:
    def test_score_and_value_keys(self) -> None:
        assert parse_judge_score('{"score": 4, "rationale": "ok"}') == (4, "ok")
        assert parse_judge_score('{"value": 3.5}')[0] == 3.5

    def test_embedded_json(self) -> None:
        text = 'prefix {"score": 2, "rationale": "meh"} suffix'
        assert parse_judge_score(text)[0] == 2

    def test_invalid(self) -> None:
        with pytest.raises(ValueError):
            parse_judge_score("")
        with pytest.raises(ValueError):
            parse_judge_score('{"score": 9}')
        with pytest.raises(ValueError):
            parse_judge_score("not json")


class TestRunPinnedJudge:
    def test_scores_with_fake_transport(self) -> None:
        calls: list[int] = []

        def fake(prompt: str, judge_input: Any, *, model: str, timeout_s: float = 15.0) -> str:
            calls.append(1)
            assert model == PINNED_MODEL
            assert "final_message_text" in judge_input
            assert "api_key" not in str(judge_input)
            return json.dumps({"score": 5, "rationale": "excellent"})

        out = run_pinned_judge("rubric", _judge_input(), judge_fn=fake, model=PINNED_MODEL)
        assert out.ok is True
        assert out.execution_code == EXEC_SCORED
        assert out.score == 5
        assert out.rationale == "excellent"
        assert out.text is None
        assert out.retry_count == 0
        assert len(calls) == 1

    def test_empty_input_never_retries(self) -> None:
        calls = {"n": 0}

        def boom(*_a: Any, **_k: Any) -> str:
            calls["n"] += 1
            raise AssertionError("should not be called")

        empty = JudgeInput(
            artifact_class=ArtifactClass.FINAL_ACCEPT.value,
            final_message_text="   ",
            final_message_sha256=message_sha256_bytes("   "),
            encoding="utf-8",
        )
        out = run_pinned_judge("p", empty, judge_fn=boom, model=PINNED_MODEL)
        assert out.ok is False
        assert out.execution_code == EXEC_EMPTY_INPUT
        assert calls["n"] == 0
        assert out.retry_count == 0

    def test_oversize_input_never_retries(self) -> None:
        calls = {"n": 0}

        def boom(*_a: Any, **_k: Any) -> str:
            calls["n"] += 1
            return "{}"

        huge = "x" * 40000
        over = JudgeInput(
            artifact_class=ArtifactClass.FINAL_ACCEPT.value,
            final_message_text=huge,
            final_message_sha256=message_sha256_bytes(huge),
            encoding="utf-8",
        )
        out = run_pinned_judge("p", over, judge_fn=boom, model=PINNED_MODEL)
        assert out.execution_code == EXEC_OVERSIZE_INPUT
        assert calls["n"] == 0

    def test_transport_retries_once(self) -> None:
        calls = {"n": 0}

        def flaky(*_a: Any, **_k: Any) -> str:
            calls["n"] += 1
            raise TimeoutError("slow")

        out = run_pinned_judge("p", _judge_input(), judge_fn=flaky, model=PINNED_MODEL)
        assert out.ok is False
        assert out.execution_code == EXEC_TIMEOUT
        # initial + one retry
        assert calls["n"] == DEFAULT_MAX_RETRIES + 1
        assert out.retry_count == DEFAULT_MAX_RETRIES

    def test_parse_error_retries_once_then_fails(self) -> None:
        calls = {"n": 0}

        def bad(*_a: Any, **_k: Any) -> str:
            calls["n"] += 1
            return "not-json"

        out = run_pinned_judge("p", _judge_input(), judge_fn=bad, model=PINNED_MODEL)
        assert out.execution_code == EXEC_PARSE_ERROR
        assert calls["n"] == DEFAULT_MAX_RETRIES + 1

    def test_transport_error_normalized(self) -> None:
        def bad(*_a: Any, **_k: Any) -> str:
            raise RuntimeError("socket down")

        out = run_pinned_judge("p", _judge_input(), judge_fn=bad, model=PINNED_MODEL)
        assert out.execution_code == EXEC_TRANSPORT_ERROR
        assert out.error_type == "RuntimeError"

    def test_outcome_evidence_has_no_secrets(self) -> None:
        def ok(*_a: Any, **_k: Any) -> JudgeTransportResult:
            """Transport stub: score=3 success payload without credential material."""
            return JudgeTransportResult(
                text='{"score": 3}',
                usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                latency_ms=12.0,
                finish_reason="stop",
            )

        out = run_pinned_judge("p", _judge_input(), judge_fn=ok, model=PINNED_MODEL)
        ev = out.as_evidence()
        blob = json.dumps(ev)
        assert "sk-" not in blob
        assert "api_key" not in blob
        assert ev["raw_discarded"] is True


class TestFactoryAndCredentials:
    def test_resolve_credentials_presence_only(self) -> None:
        view = resolve_judge_credentials(
            judge_model=PINNED_MODEL,
            environ={"GIT_CG_EVAL_JUDGE_API_KEY": "sk-test", "GIT_CG_EVAL_JUDGE_MODEL": PINNED_MODEL},
        )
        assert view.credentials_present is True
        assert view.model == PINNED_MODEL
        assert "sk-test" not in repr(view)

    def test_factory_closes_over_key_not_in_signature(self) -> None:
        seen: dict[str, Any] = {}

        def transport(**kwargs: Any) -> dict[str, Any]:
            seen.update(kwargs)
            return {"score": 4, "rationale": "fine"}

        fn = openai_compatible_judge_fn(
            model=PINNED_MODEL,
            judge_api_key="sk-closed-secret",
            transport=transport,
        )
        # Runner-facing callable must not accept api_key.
        import inspect

        assert "api_key" not in inspect.signature(fn).parameters
        raw = fn("prompt", _judge_input().as_dict(), model=PINNED_MODEL)
        assert isinstance(raw, JudgeTransportResult)
        assert "sk-closed-secret" not in json.dumps(seen, default=str)
        assert seen["model"] == PINNED_MODEL

    def test_import_lane_c_does_not_load_openai(self) -> None:
        # Clean interpreter: suite-level openai imports must not poison this check.
        import subprocess

        code = (
            "import sys\n"
            "banned = {'openai'}\n"
            "before = {m for m in sys.modules if m == 'openai' or m.startswith('openai.')}\n"
            "import git_cg.eval.lane_c.judge as judge\n"
            "after = {m for m in sys.modules if m == 'openai' or m.startswith('openai.')}\n"
            "leaked = sorted(after - before)\n"
            "assert not leaked, leaked\n"
            "assert hasattr(judge, 'openai_compatible_judge_fn')\n"
            "assert hasattr(judge, 'run_pinned_judge')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


class TestParseJudgeScoreEdgeCases:
    def test_string_numeric_score(self) -> None:
        assert parse_judge_score('{"score": "4", "rationale": "ok"}') == (4, "ok")

    def test_string_non_numeric_score(self) -> None:
        with pytest.raises(ValueError, match="not numeric"):
            parse_judge_score('{"score": "nope"}')

    def test_bool_score_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing or not numeric"):
            parse_judge_score('{"score": true}')

    def test_non_object_payload(self) -> None:
        with pytest.raises(ValueError, match="not a JSON object"):
            parse_judge_score("[1, 2, 3]")

    def test_non_string_rationale_dropped(self) -> None:
        score, rationale = parse_judge_score('{"score": 2, "rationale": 99}')
        assert score == 2
        assert rationale is None


class TestNormalizeAndUsage:
    def test_usage_dict_filters_invalid(self) -> None:
        from git_cg.eval.lane_c.judge import _usage_dict

        assert _usage_dict(None) is None
        assert _usage_dict("x") is None
        assert _usage_dict({"prompt_tokens": True, "completion_tokens": "n"}) is None
        assert _usage_dict({"prompt_tokens": 1.5, "total_tokens": 3}) == {
            "prompt_tokens": 1,
            "total_tokens": 3,
        }

    def test_normalize_raw_variants(self) -> None:
        from git_cg.eval.lane_c.judge import JudgeOutcome, _normalize_raw

        already = JudgeTransportResult(text='{"score":1}', usage={"total_tokens": 1})
        assert _normalize_raw(already) is already

        outcome = JudgeOutcome(ok=True, execution_code=EXEC_SCORED, text='{"score":2}', retry_count=1)
        norm = _normalize_raw(outcome)
        assert norm.text == '{"score":2}'
        assert norm.retry_count == 1

        mapped = _normalize_raw(
            {
                "text": '{"score":3}',
                "usage": {"prompt_tokens": 2, "bogus": 1},
                "latency_ms": 11,
                "finish_reason": "stop",
                "retry_count": 1,
                "error_type": None,
            }
        )
        assert mapped.text.startswith("{")
        assert mapped.usage == {"prompt_tokens": 2}
        assert mapped.latency_ms == 11.0

        convenience = _normalize_raw({"score": 5, "rationale": "great"})
        assert '"score": 5' in convenience.text or '"score":5' in convenience.text.replace(" ", "")

        with pytest.raises(TypeError, match="unsupported judge return type"):
            _normalize_raw(123)


class TestInvokeOnceBranches:
    def test_transport_error_type_without_text(self) -> None:
        def timed_out(*_a: Any, **_k: Any) -> JudgeTransportResult:
            return JudgeTransportResult(text="  ", error_type="TimeoutError")

        out = run_pinned_judge("p", _judge_input(), judge_fn=timed_out, model=PINNED_MODEL)
        assert out.execution_code == EXEC_TIMEOUT
        assert out.error_type == "TimeoutError"

    def test_transport_error_type_generic(self) -> None:
        def broken(*_a: Any, **_k: Any) -> JudgeTransportResult:
            return JudgeTransportResult(text="", error_type="ConnectionReset")

        out = run_pinned_judge("p", _judge_input(), judge_fn=broken, model=PINNED_MODEL)
        assert out.execution_code == EXEC_TRANSPORT_ERROR

    def test_normalize_error_from_bad_return_type(self) -> None:
        def bad_type(*_a: Any, **_k: Any) -> Any:
            return 42

        out = run_pinned_judge("p", _judge_input(), judge_fn=bad_type, model=PINNED_MODEL)
        assert out.execution_code == EXEC_PARSE_ERROR
        assert out.error_type == "normalize_error"

    def test_mapping_payload_accepted(self) -> None:
        payload = _judge_input().as_dict()

        def fake(prompt: str, judge_input: Any, *, model: str, timeout_s: float = 15.0) -> str:
            assert isinstance(judge_input, dict)
            assert judge_input["final_message_text"]
            return json.dumps({"score": 4})

        out = run_pinned_judge("p", payload, judge_fn=fake, model=PINNED_MODEL)
        assert out.ok is True
        assert out.score == 4

    def test_zero_max_retries_single_attempt(self) -> None:
        # max_retries=0 must fail after a single transport attempt.
        calls = {"n": 0}

        def boom(*_a: Any, **_k: Any) -> str:
            calls["n"] += 1
            raise RuntimeError("once")

        out = run_pinned_judge(
            "p",
            _judge_input(),
            judge_fn=boom,
            model=PINNED_MODEL,
            max_retries=0,
        )
        assert out.execution_code == EXEC_TRANSPORT_ERROR
        assert calls["n"] == 1
        assert out.retry_count == 0


class TestCredentialResolverBranches:
    def test_explicit_key_and_base_url(self) -> None:
        view = resolve_judge_credentials(
            judge_model=PINNED_MODEL,
            judge_api_key=" sk-x ",
            base_url=" https://example.test/v1 ",
            environ={},
        )
        assert view.credentials_present is True
        assert view.base_url == "https://example.test/v1"

    def test_secret_resolver_success_and_failure(self) -> None:
        ok = resolve_judge_credentials(
            judge_model=PINNED_MODEL,
            secret_resolver=lambda _name, _default="": "sk-from-resolver",
            environ=None,
        )
        assert ok.credentials_present is True

        def boom(_name: str, _default: str = "") -> str:
            raise RuntimeError("vault down")

        bad = resolve_judge_credentials(
            judge_model=PINNED_MODEL,
            secret_resolver=boom,
            environ=None,
        )
        assert bad.credentials_present is False

    def test_resolve_closed_key_paths(self) -> None:
        from git_cg.eval.lane_c.judge import _resolve_closed_key

        assert _resolve_closed_key(judge_api_key="sk-a", environ=None, secret_resolver=None) == "sk-a"
        assert (
            _resolve_closed_key(
                judge_api_key=None,
                environ={"GIT_CG_EVAL_JUDGE_API_KEY": "sk-env"},
                secret_resolver=None,
            )
            == "sk-env"
        )
        assert (
            _resolve_closed_key(
                judge_api_key=None,
                environ=None,
                secret_resolver=lambda _n, _d="": "sk-res",
            )
            == "sk-res"
        )

        def boom(_n: str, _d: str = "") -> str:
            raise RuntimeError("nope")

        assert _resolve_closed_key(judge_api_key=None, environ=None, secret_resolver=boom) == ""


class TestLiveTransportMocked:
    def test_live_openai_transport_standard_and_reasoning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from git_cg.eval.lane_c import judge as judge_mod

        class _Usage:
            prompt_tokens = 3
            completion_tokens = 4
            total_tokens = 7

        class _Msg:
            content = '{"score": 5, "rationale": "ok"}'

        class _Choice:
            message = _Msg()
            finish_reason = "stop"

        class _Resp:
            def __init__(self) -> None:
                self.choices = [_Choice()]
                self.usage = _Usage()

        client_kwargs: dict[str, Any] = {}
        create_kwargs: dict[str, Any] = {}

        class _Completions:
            def create(self, **kwargs: Any) -> _Resp:
                create_kwargs.clear()
                create_kwargs.update(kwargs)
                return _Resp()

        class _Chat:
            completions = _Completions()

        class _Client:
            def __init__(self, **kwargs: Any) -> None:
                client_kwargs.clear()
                client_kwargs.update(kwargs)
                self.chat = _Chat()

        import sys
        import types

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = _Client  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

        standard = judge_mod._live_openai_transport(
            prompt="rubric",
            judge_input=_judge_input().as_dict(),
            model=PINNED_MODEL,
            timeout_s=5.0,
            api_key="sk-test",
            base_url="https://example.test/v1",
        )
        assert standard.text.startswith("{")
        assert standard.usage == {
            "prompt_tokens": 3,
            "completion_tokens": 4,
            "total_tokens": 7,
        }
        assert create_kwargs["temperature"] == 0
        assert create_kwargs["max_tokens"] == 256
        assert "max_completion_tokens" not in create_kwargs
        assert client_kwargs["base_url"] == "https://example.test/v1"

        reasoning = judge_mod._live_openai_transport(
            prompt="rubric",
            judge_input=_judge_input().as_dict(),
            model="o3-2025-01-01",
            timeout_s=5.0,
            api_key="sk-test",
            base_url=None,
        )
        assert reasoning.finish_reason == "stop"
        assert create_kwargs["max_completion_tokens"] == 256
        assert "temperature" not in create_kwargs
        assert "base_url" not in client_kwargs

    def test_factory_uses_injected_transport_not_live(self) -> None:
        def transport(**kwargs: Any) -> JudgeTransportResult:
            return JudgeTransportResult(text='{"score": 1}', latency_ms=1.0)

        fn = openai_compatible_judge_fn(
            model=PINNED_MODEL,
            judge_api_key="sk-closed",
            transport=transport,
        )
        raw = fn("p", _judge_input().as_dict(), model="")
        assert isinstance(raw, JudgeTransportResult)
        assert raw.text == '{"score": 1}'


def test_credentials_present_via_secret_resolver_only() -> None:
    from git_cg.eval.lane_c.availability import credentials_present

    assert credentials_present(environ=None, secret_resolver=lambda *_a, **_k: "sk-from-resolver") is True
    assert credentials_present(environ=None, secret_resolver=lambda *_a, **_k: "") is False

    def boom(*_a, **_k):
        raise RuntimeError("no secret store")

    assert credentials_present(environ=None, secret_resolver=boom) is False


def test_resolve_closed_key_via_secret_resolver_only() -> None:
    from git_cg.eval.lane_c.judge import _resolve_closed_key

    assert (
        _resolve_closed_key(
            judge_api_key=None,
            environ=None,
            secret_resolver=lambda *_a, **_k: "sk-closed",
        )
        == "sk-closed"
    )

    def boom(*_a, **_k):
        raise RuntimeError("nope")

    assert _resolve_closed_key(judge_api_key=None, environ=None, secret_resolver=boom) == ""


def test_resolve_judge_credentials_via_secret_resolver_only() -> None:
    from git_cg.eval.lane_c.judge import resolve_judge_credentials

    view = resolve_judge_credentials(
        judge_model="gpt-test",
        base_url="https://example.test/v1",
        environ=None,
        secret_resolver=lambda *_a, **_k: "sk-view",
    )
    assert view.model == "gpt-test"
    assert view.base_url == "https://example.test/v1"
    assert view.credentials_present is True

    def boom(*_a, **_k):
        raise RuntimeError("nope")

    view2 = resolve_judge_credentials(
        judge_model="gpt-test",
        environ=None,
        secret_resolver=boom,
    )
    assert view2.credentials_present is False
