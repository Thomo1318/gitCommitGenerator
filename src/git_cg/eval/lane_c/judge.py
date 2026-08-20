"""Pinned injectable Lane C-prime judge (C-JUDGE / C-SEC).

Runner- and test-facing callables never accept ``api_key``. Credentials are
resolved lazily through ``git_cg.secrets.resolve_secret`` and held in a
factory closure. Provider SDKs are imported only inside the live transport
path - ``import git_cg.eval.lane_c`` stays free of ``openai`` / ``anthropic``
/ ``httpx`` / ``opik``.

This module does **not** use ``git_cg.retries.llm_retry``: that helper imports
provider SDKs at module scope and retries three times. Lane C allows at most
one retry and never retries empty/oversize host guards.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol

from git_cg.eval.lane_c.availability import ENV_JUDGE_API_KEY, ENV_JUDGE_BASE_URL, SecretResolver
from git_cg.eval.lane_c.eligibility import ENV_JUDGE_MODEL
from git_cg.eval.lane_c.judge_input import JudgeInput, classify_judge_input_size
from git_cg.eval.lane_c.taxonomy import (
    EXEC_EMPTY_INPUT,
    EXEC_OVERSIZE_INPUT,
    EXEC_PARSE_ERROR,
    EXEC_SCORED,
    EXEC_TIMEOUT,
    EXEC_TRANSPORT_ERROR,
    assert_execution_code,
)

__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_S",
    "JudgeCredentialView",
    "JudgeFn",
    "JudgeOutcome",
    "JudgeTransportResult",
    "openai_compatible_judge_fn",
    "parse_judge_score",
    "resolve_judge_credentials",
    "run_pinned_judge",
]

DEFAULT_TIMEOUT_S: Final = 15.0
DEFAULT_MAX_RETRIES: Final = 1
_GEVAL_MIN: Final = 1.0
_GEVAL_MAX: Final = 5.0

_RETRYABLE: Final[frozenset[str]] = frozenset({EXEC_TIMEOUT, EXEC_TRANSPORT_ERROR, EXEC_PARSE_ERROR})
_NEVER_RETRY: Final[frozenset[str]] = frozenset({EXEC_EMPTY_INPUT, EXEC_OVERSIZE_INPUT})


@dataclass(frozen=True, slots=True)
class JudgeTransportResult:
    """Structured transport payload (D38). Raw provider bodies are discarded."""

    text: str
    usage: dict[str, int] | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None
    retry_count: int = 0
    error_type: str | None = None
    raw_discarded: bool = True


@dataclass(frozen=True, slots=True)
class JudgeOutcome:
    """Normalized judge result. Failures never escape as exceptions."""

    ok: bool
    execution_code: str
    score: int | float | None = None
    rationale: str | None = None
    text: str | None = None
    usage: dict[str, int] | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None
    retry_count: int = 0
    error_type: str | None = None
    raw_discarded: bool = True
    duration_ms: float | None = None

    def as_evidence(self) -> dict[str, Any]:
        """
        Return secret-free execution metadata for evidence records.
        
        Returns:
        	dict[str, Any]: Structured metadata including usage, latency, completion status, retry count, error type, raw-response disposal status, and execution code.
        """
        return {
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "retry_count": self.retry_count,
            "error_type": self.error_type,
            "raw_discarded": self.raw_discarded,
            "execution_code": self.execution_code,
        }


@dataclass(frozen=True, slots=True)
class JudgeCredentialView:
    """Secret-free credential / identity snapshot (C-SEC)."""

    model: str
    base_url: str | None
    credentials_present: bool
    secret_env: str = ENV_JUDGE_API_KEY
    identity_env: str = ENV_JUDGE_MODEL

    def __repr__(self) -> str:
        return (
            f"JudgeCredentialView(model={self.model!r}, base_url={self.base_url!r}, "
            f"credentials_present={self.credentials_present})"
        )


class JudgeFn(Protocol):
    """Runner-facing judge callable. Must not accept ``api_key``."""

    def __call__(
        self,
        prompt: str,
        judge_input: Mapping[str, str],
        *,
        model: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> JudgeTransportResult | Mapping[str, Any] | str | JudgeOutcome: """
        Invoke the judge for the supplied prompt and input.
        
        Parameters:
            prompt: The instruction presented to the judge.
            judge_input: The input content to evaluate.
            model: The model to use for the invocation.
            timeout_s: Maximum duration allowed for the invocation.
        
        Returns:
            The judge response as transport data, a mapping, text, or a normalised outcome.
        """
        ...


def resolve_judge_credentials(
    *,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    base_url: str | None = None,
    environ: Mapping[str, str] | None = None,
    secret_resolver: SecretResolver | None = None,
) -> JudgeCredentialView:
    """
    Resolve the configured judge identity and indicate whether credentials are available without exposing the credential value.
    
    Parameters:
    	judge_model (str | None): Optional model override; otherwise, use the configured environment value.
    	judge_api_key (str | None): Optional credential override used only to determine presence.
    	base_url (str | None): Optional service URL override.
    	environ (Mapping[str, str] | None): Optional environment mapping used for configuration.
    	secret_resolver (SecretResolver | None): Optional resolver used to check credential presence.
    
    Returns:
    	JudgeCredentialView: The resolved model, base URL, and credential-presence status.
    """
    env = environ if environ is not None else os.environ
    model = (judge_model if judge_model is not None else env.get(ENV_JUDGE_MODEL, "")).strip()
    url_raw = base_url if base_url is not None else env.get(ENV_JUDGE_BASE_URL, "")
    url = str(url_raw).strip() or None

    present = False
    if judge_api_key is not None:
        present = bool(str(judge_api_key).strip())
    elif environ is not None:
        present = bool(str(environ.get(ENV_JUDGE_API_KEY, "")).strip())
    else:
        resolver = secret_resolver
        if resolver is None:
            from git_cg.secrets import resolve_secret

            resolver = resolve_secret
        try:
            present = bool(str(resolver(ENV_JUDGE_API_KEY, "") or "").strip())
        except Exception:
            present = False

    return JudgeCredentialView(model=model, base_url=url, credentials_present=present)


def _usage_dict(raw: object) -> dict[str, int] | None:
    """Extract numeric token counts from a usage mapping.
    
    Parameters:
        raw (object): Candidate usage data.
    
    Returns:
        dict[str, int] | None: Normalised token counts, or `None` when the input contains no numeric token counts.
    """
    if not isinstance(raw, Mapping):
        return None
    out: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        val = raw.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = int(val)
    return out or None


def parse_judge_score(text: str) -> tuple[int | float, str | None]:
    """
    Parse a judge response and extract its score and optional rationale.
    
    The response may contain a JSON object within surrounding text. The score
    must be numeric and between 1 and 5 inclusive.
    
    Returns:
        tuple[int | float, str | None]: The score and rationale, or ``None`` if no
        string rationale is provided.
    
    Raises:
        ValueError: If the response is empty, is not a JSON object, or contains a
        missing, non-numeric, or out-of-range score.
    """
    blob = str(text).strip()
    if not blob:
        raise ValueError("empty judge text")
    try:
        payload: Any = json.loads(blob)
    except json.JSONDecodeError:
        start, end = blob.find("{"), blob.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("judge text is not a JSON object") from None
        payload = json.loads(blob[start : end + 1])
    if not isinstance(payload, Mapping):
        raise ValueError("judge payload is not a JSON object")
    raw_score = payload.get("score", payload.get("value"))
    if isinstance(raw_score, str):
        try:
            raw_score = float(raw_score.strip())
        except ValueError as exc:
            raise ValueError("score is not numeric") from exc
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        raise ValueError("score missing or not numeric")
    numeric = float(raw_score)
    if numeric < _GEVAL_MIN or numeric > _GEVAL_MAX:
        raise ValueError("score out of range")
    score: int | float = int(numeric) if numeric.is_integer() else numeric
    rationale = payload.get("rationale")
    rationale_s = rationale if isinstance(rationale, str) else None
    return score, rationale_s


def _normalize_raw(raw: object) -> JudgeTransportResult:
    """Normalise supported judge responses into a transport result.
    
    Parameters:
    	raw (object): A transport result, judge outcome, response string, or mapping containing judge response data.
    
    Returns:
    	JudgeTransportResult: The normalised transport response.
    
    Raises:
    	TypeError: If `raw` has an unsupported type.
    """
    if isinstance(raw, JudgeTransportResult):
        return raw
    if isinstance(raw, JudgeOutcome):
        return JudgeTransportResult(
            text=raw.text or "",
            usage=raw.usage,
            latency_ms=raw.latency_ms,
            finish_reason=raw.finish_reason,
            retry_count=raw.retry_count,
            error_type=raw.error_type,
            raw_discarded=raw.raw_discarded,
        )
    if isinstance(raw, str):
        return JudgeTransportResult(text=raw, raw_discarded=True)
    if isinstance(raw, Mapping):
        if any(k in raw for k in ("text", "usage", "latency_ms", "finish_reason", "error_type")):
            text = raw.get("text")
            return JudgeTransportResult(
                text="" if text is None else str(text),
                usage=_usage_dict(raw.get("usage")),
                latency_ms=float(raw["latency_ms"]) if isinstance(raw.get("latency_ms"), (int, float)) else None,
                finish_reason=str(raw["finish_reason"]) if raw.get("finish_reason") is not None else None,
                retry_count=int(raw["retry_count"]) if isinstance(raw.get("retry_count"), (int, float)) else 0,
                error_type=str(raw["error_type"]) if raw.get("error_type") else None,
                raw_discarded=bool(raw.get("raw_discarded", True)),
            )
        # Convenience: fake already-parsed ``{score, rationale}``.
        return JudgeTransportResult(text=json.dumps(dict(raw), default=str), raw_discarded=True)
    raise TypeError(f"unsupported judge return type: {type(raw).__name__}")


def _classify_exception(exc: BaseException) -> tuple[str, str]:
    """Classify an exception as a timeout or transport failure.
    
    Parameters:
    	exc (BaseException): Exception to classify.
    
    Returns:
    	tuple[str, str]: The execution code and exception type name.
    """
    name = type(exc).__name__
    lowered = name.lower()
    if isinstance(exc, TimeoutError) or "timeout" in lowered:
        return EXEC_TIMEOUT, name
    return EXEC_TRANSPORT_ERROR, name


def _payload_dict(judge_input: JudgeInput | Mapping[str, str]) -> dict[str, str]:
    """Convert judge input into a string-keyed, string-valued dictionary.
    
    Parameters:
    	judge_input (JudgeInput | Mapping[str, str]): Input data to convert.
    
    Returns:
    	dict[str, str]: The normalised input mapping.
    """
    if isinstance(judge_input, JudgeInput):
        return judge_input.as_dict()
    return {str(k): str(v) for k, v in judge_input.items()}


def _host_guard(payload: Mapping[str, str]) -> str | None:
    """
    Classify the combined judge input for empty or oversized content.
    
    Parameters:
    	payload (Mapping[str, str]): Judge input containing the final message and optional diff summary.
    
    Returns:
    	str | None: The applicable input-size execution code, or `None` when the input is within the permitted limits.
    """
    text = str(payload.get("final_message_text") or "")
    extra = payload.get("diff_summary")
    size_text = text if not extra else f"{text}\n{extra}"
    return classify_judge_input_size(size_text)


def _fail(
    code: str,
    *,
    error_type: str | None = None,
    retry_count: int = 0,
    usage: dict[str, int] | None = None,
    latency_ms: float | None = None,
    finish_reason: str | None = None,
    text: str | None = None,
    duration_ms: float | None = None,
) -> JudgeOutcome:
    """
    Construct a failed judge outcome with the supplied execution metadata.
    
    Parameters:
    	code (str): Execution code describing the failure.
    	error_type (str | None): Optional category of the failure.
    	retry_count (int): Number of retries already performed.
    	usage (dict[str, int] | None): Optional token usage metadata.
    	latency_ms (float | None): Optional provider latency in milliseconds.
    	finish_reason (str | None): Optional provider completion reason.
    	text (str | None): Optional response text associated with the failure.
    	duration_ms (float | None): Optional total execution duration in milliseconds.
    
    Returns:
    	JudgeOutcome: A failed outcome with raw response data marked as discarded.
    """
    return JudgeOutcome(
        ok=False,
        execution_code=assert_execution_code(code),
        text=text,
        usage=usage,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        retry_count=retry_count,
        error_type=error_type,
        raw_discarded=True,
        duration_ms=duration_ms,
    )


def _invoke_once(
    judge_fn: JudgeFn,
    prompt: str,
    payload: Mapping[str, str],
    *,
    model: str,
    timeout_s: float,
) -> JudgeOutcome:
    """
    Invoke the judge once and convert its response into a structured outcome.
    
    Returns:
        JudgeOutcome: A scored outcome or a classified failure with secret-free
        metadata.
    """
    started = time.perf_counter()
    try:
        raw = judge_fn(prompt, payload, model=model, timeout_s=timeout_s)
    except Exception as exc:
        code, err = _classify_exception(exc)
        duration_ms = (time.perf_counter() - started) * 1000.0
        return _fail(code, error_type=err, duration_ms=duration_ms)
    duration_ms = (time.perf_counter() - started) * 1000.0
    try:
        transport = _normalize_raw(raw)
    except Exception:
        return _fail(EXEC_PARSE_ERROR, error_type="normalize_error", duration_ms=duration_ms)
    if transport.error_type and not transport.text.strip():
        code = EXEC_TIMEOUT if "timeout" in transport.error_type.lower() else EXEC_TRANSPORT_ERROR
        return _fail(
            code,
            error_type=transport.error_type,
            usage=transport.usage,
            latency_ms=transport.latency_ms if transport.latency_ms is not None else duration_ms,
            finish_reason=transport.finish_reason,
            duration_ms=duration_ms,
        )
    try:
        score, rationale = parse_judge_score(transport.text)
    except Exception:
        return _fail(
            EXEC_PARSE_ERROR,
            error_type="parse_error",
            usage=transport.usage,
            latency_ms=transport.latency_ms if transport.latency_ms is not None else duration_ms,
            finish_reason=transport.finish_reason,
            text=None,  # do not persist raw model text
            duration_ms=duration_ms,
        )
    return JudgeOutcome(
        ok=True,
        execution_code=EXEC_SCORED,
        score=score,
        rationale=rationale,
        text=None,
        usage=transport.usage,
        latency_ms=transport.latency_ms if transport.latency_ms is not None else duration_ms,
        finish_reason=transport.finish_reason,
        retry_count=0,
        error_type=None,
        raw_discarded=True,
        duration_ms=duration_ms,
    )


def run_pinned_judge(
    prompt: str,
    judge_input: JudgeInput | Mapping[str, str],
    *,
    judge_fn: JudgeFn,
    model: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> JudgeOutcome:
    """
    Run the pinned judge and normalise its result into a product-facing outcome.
    
    Empty or oversized inputs are rejected before invocation. Retryable timeout,
    transport, and parsing failures are retried up to ``max_retries``; other
    failures stop immediately.
    
    Parameters:
        prompt (str): The judging prompt.
        judge_input (JudgeInput | Mapping[str, str]): The input payload to evaluate.
        judge_fn (JudgeFn): The judge callable.
        model (str): The model identifier to use.
        timeout_s (float): Maximum duration permitted for each invocation.
        max_retries (int): Maximum number of retries for retryable failures.
    
    Returns:
        JudgeOutcome: A scored outcome or a secret-free structured failure.
    """
    payload = _payload_dict(judge_input)
    guard = _host_guard(payload)
    if guard in _NEVER_RETRY:
        return _fail(guard, error_type=guard, retry_count=0, duration_ms=0.0)

    attempts = 0
    last = _fail(EXEC_TRANSPORT_ERROR, error_type="not_attempted")
    started = time.perf_counter()
    limit = max(0, int(max_retries))
    while attempts <= limit:
        last = _invoke_once(judge_fn, prompt, payload, model=model, timeout_s=timeout_s)
        if last.ok:
            duration_ms = (time.perf_counter() - started) * 1000.0
            return JudgeOutcome(
                ok=True,
                execution_code=EXEC_SCORED,
                score=last.score,
                rationale=last.rationale,
                text=None,
                usage=last.usage,
                latency_ms=last.latency_ms,
                finish_reason=last.finish_reason,
                retry_count=attempts,
                error_type=None,
                raw_discarded=True,
                duration_ms=duration_ms,
            )
        if last.execution_code in _NEVER_RETRY or last.execution_code not in _RETRYABLE:
            break
        if attempts >= limit:
            break
        attempts += 1

    duration_ms = (time.perf_counter() - started) * 1000.0
    return JudgeOutcome(
        ok=False,
        execution_code=last.execution_code,
        score=None,
        rationale=None,
        text=None,
        usage=last.usage,
        latency_ms=last.latency_ms,
        finish_reason=last.finish_reason,
        retry_count=attempts,
        error_type=last.error_type,
        raw_discarded=True,
        duration_ms=duration_ms,
    )


def _resolve_closed_key(
    *,
    judge_api_key: str | None,
    environ: Mapping[str, str] | None,
    secret_resolver: SecretResolver | None,
) -> str:
    """Resolve the API key for a factory closure. Never log or return via evidence."""
    if judge_api_key is not None:
        return str(judge_api_key)
    if environ is not None:
        return str(environ.get(ENV_JUDGE_API_KEY, "") or "")
    resolver = secret_resolver
    if resolver is None:
        from git_cg.secrets import resolve_secret

        resolver = resolve_secret
    try:
        return str(resolver(ENV_JUDGE_API_KEY, "") or "")
    except Exception:
        return ""


def openai_compatible_judge_fn(
    *,
    model: str | None = None,
    base_url: str | None = None,
    environ: Mapping[str, str] | None = None,
    secret_resolver: SecretResolver | None = None,
    judge_api_key: str | None = None,
    transport: Callable[..., JudgeTransportResult | Mapping[str, Any] | str] | None = None,
) -> JudgeFn:
    """
    Build a judge callable with credentials captured privately in its closure.
    
    The optional transport provides an offline or test execution path. Without an
    injected transport, the live OpenAI-compatible client is created when the
    returned callable is invoked.
    
    Parameters:
    	model (str | None): Model identifier used by default.
    	base_url (str | None): OpenAI-compatible API base URL.
    	environ (Mapping[str, str] | None): Environment values used for credential resolution.
    	secret_resolver (SecretResolver | None): Resolver used to obtain credentials lazily.
    	judge_api_key (str | None): Explicit API key used for the closure.
    	transport (Callable | None): Optional transport used instead of the live provider.
    
    Returns:
    	JudgeFn: A callable that executes judge requests without exposing the API key
    	in its signature.
    """
    creds = resolve_judge_credentials(
        judge_model=model,
        judge_api_key=judge_api_key,
        base_url=base_url,
        environ=environ,
        secret_resolver=secret_resolver,
    )
    closed_key = _resolve_closed_key(
        judge_api_key=judge_api_key,
        environ=environ,
        secret_resolver=secret_resolver,
    )
    closed_model = creds.model
    closed_base = creds.base_url
    injected = transport

    def _call(
        prompt: str,
        judge_input: Mapping[str, str],
        *,
        model: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> JudgeTransportResult:
        """
        Send judge input to the configured transport and return its structured response.
        
        Parameters:
            prompt (str): Prompt supplied to the judge.
            judge_input (Mapping[str, str]): Input fields included in the judge request.
            model (str): Model to use, falling back to the configured model when empty.
            timeout_s (float): Request timeout in seconds.
        
        Returns:
            JudgeTransportResult: Structured transport response.
        """
        chosen_model = model or closed_model
        if injected is not None:
            return _normalize_raw(
                injected(
                    prompt=prompt,
                    judge_input=judge_input,
                    model=chosen_model,
                    timeout_s=timeout_s,
                    base_url=closed_base,
                )
            )
        return _live_openai_transport(
            prompt=prompt,
            judge_input=judge_input,
            model=chosen_model,
            timeout_s=timeout_s,
            api_key=closed_key,
            base_url=closed_base,
        )

    return _call


def _live_openai_transport(
    *,
    prompt: str,
    judge_input: Mapping[str, str],
    model: str,
    timeout_s: float,
    api_key: str,
    base_url: str | None,
) -> JudgeTransportResult:
    """
    Send the judge prompt and input to an OpenAI-compatible chat-completion service.
    
    Parameters:
        prompt (str): System prompt supplied to the judge.
        judge_input (Mapping[str, str]): Input payload serialised for the user message.
        model (str): Model identifier used for the completion.
        timeout_s (float): Request timeout in seconds.
        api_key (str): API credential for the provider.
        base_url (str | None): Optional provider-compatible base URL.
    
    Returns:
        JudgeTransportResult: Structured completion text, usage data, latency, and finish reason.
    """
    started = time.perf_counter()
    # Local import - this is the only provider-SDK load site (S5-E08).
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_s}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    # Sampling identity is sampling:temperature=0|max_tokens=256 (eligibility).
    # Reasoning-family model ids (o1/o3/o4/gpt-5*) reject temperature / max_tokens;
    # use max_completion_tokens and omit temperature for those pins only.
    create_kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(dict(judge_input), ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "timeout": timeout_s,
    }
    model_l = model.lower()
    reasoning_family = model_l.startswith(("o1", "o3", "o4", "gpt-5"))
    if reasoning_family:
        create_kwargs["max_completion_tokens"] = 256
    else:
        create_kwargs["temperature"] = 0
        create_kwargs["max_tokens"] = 256
    response = client.chat.completions.create(**create_kwargs)
    latency_ms = (time.perf_counter() - started) * 1000.0
    choice = response.choices[0] if getattr(response, "choices", None) else None
    message = getattr(choice, "message", None) if choice is not None else None
    text = getattr(message, "content", None) or ""
    finish = getattr(choice, "finish_reason", None) if choice is not None else None
    usage_obj = getattr(response, "usage", None)
    usage = None
    if usage_obj is not None:
        usage = _usage_dict(
            {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                "total_tokens": getattr(usage_obj, "total_tokens", None),
            }
        )
    # Drop the raw response immediately; only structured fields escape.
    del response
    return JudgeTransportResult(
        text=str(text),
        usage=usage,
        latency_ms=latency_ms,
        finish_reason=str(finish) if finish is not None else None,
        retry_count=0,
        error_type=None,
        raw_discarded=True,
    )
