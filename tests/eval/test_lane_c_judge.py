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
        # Ensure openai not pulled by package import path used here.
        assert not any(m == "openai" or m.startswith("openai.") for m in sys.modules)
