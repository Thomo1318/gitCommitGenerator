"""Tests for LLM retry logic."""

from typing import Any, cast

import httpx
import openai
import pytest
from tenacity import wait_none

from git_cg.retries import llm_retry


def _with_no_wait(fn: Any) -> Any:
    """Tenacity-wrapped callables expose retry_with at runtime; keep type-checkers calm."""
    return cast(Any, fn).retry_with(wait=wait_none())


class MockClient:
    def __init__(self, exceptions_to_raise, final_result):
        self.exceptions_to_raise = exceptions_to_raise
        self.final_result = final_result
        self.attempts = 0

    def call(self):
        self.attempts += 1
        if self.exceptions_to_raise:
            exc = self.exceptions_to_raise.pop(0)
            if exc:
                raise exc
        return self.final_result


@llm_retry
def flaky_function(client):
    return client.call()


# Unit tests must not sleep on exponential backoff.
flaky_function = _with_no_wait(flaky_function)


def test_llm_retry_success_first_try():
    client = MockClient(exceptions_to_raise=[], final_result="success")
    result = flaky_function(client)
    assert result == "success"
    assert client.attempts == 1


def test_llm_retry_success_after_retries():
    exceptions = [
        openai.APIConnectionError(request=httpx.Request("GET", "url")),
        openai.RateLimitError(
            "rate limited", response=httpx.Response(429, request=httpx.Request("GET", "url")), body={}
        ),
    ]
    client = MockClient(exceptions_to_raise=exceptions, final_result="success")
    result = flaky_function(client)
    assert result == "success"
    assert client.attempts == 3


def test_llm_retry_exhausted():
    exceptions = [
        openai.APIConnectionError(request=httpx.Request("GET", "url")),
        openai.APIConnectionError(request=httpx.Request("GET", "url")),
        openai.APIConnectionError(request=httpx.Request("GET", "url")),
        openai.APIConnectionError(request=httpx.Request("GET", "url")),
    ]
    client = MockClient(exceptions_to_raise=exceptions, final_result="success")

    with pytest.raises(openai.APIConnectionError):
        flaky_function(client)

    assert client.attempts == 3  # Based on stop_after_attempt(3)


def test_llm_retry_unhandled_exception():
    exceptions = [ValueError("not a transient error")]
    client = MockClient(exceptions_to_raise=exceptions, final_result="success")

    with pytest.raises(ValueError):
        flaky_function(client)

    assert client.attempts == 1


def test_graph_retry_retries_only_transient_errors():
    import sqlite3

    from git_cg.retries import graph_retry

    attempts = {"n": 0}

    @graph_retry
    def flaky_graph():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    flaky_graph = _with_no_wait(flaky_graph)
    assert flaky_graph() == "ok"
    assert attempts["n"] == 2


def test_graph_retry_does_not_retry_value_error():
    from git_cg.retries import graph_retry

    attempts = {"n": 0}

    @graph_retry
    def bad_graph():
        attempts["n"] += 1
        raise ValueError("deterministic")

    bad_graph = _with_no_wait(bad_graph)
    with pytest.raises(ValueError):
        bad_graph()
    assert attempts["n"] == 1
