"""Tests for LLM retry logic."""

import httpx
import openai
import pytest

from git_cg.retries import llm_retry


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
