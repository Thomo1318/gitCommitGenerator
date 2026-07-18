"""
Centralised retry configuration for git-cg.

Replaces ad-hoc bare ``except Exception: pass`` retry patterns with robust
``tenacity`` circuit-breaker behaviours.  Each decorator targets a specific
failure domain so deterministic errors (``ValueError``, ``JSONDecodeError``)
are never wastefully retried.

Phase 14.5 — ADR-0005
"""

import logging
import subprocess

import httpx
import openai
from rich.console import Console
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)
_console = Console()


def _before_sleep_llm(retry_state: RetryCallState) -> None:
    """Log retries to Python logging AND Rich console for user visibility."""
    before_sleep_log(log, logging.WARNING)(retry_state)
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    exc_type = type(exc).__name__ if exc else "unknown"
    _console.print(f"[yellow]⏳ Retrying LLM call (attempt {attempt}) after {exc_type}…[/yellow]")


llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (
            ConnectionError,
            TimeoutError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.RateLimitError,
            openai.InternalServerError,
        )
    ),
    before_sleep=_before_sleep_llm,
    reraise=True,
)
"""Retry decorator for LLM API calls.  Catches only transient networking
and timeout errors — deterministic failures (``ValueError``,
``JSONDecodeError``) propagate immediately."""

graph_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
"""Retry decorator for code-review-graph operations.
Exported for future ``graph_context.py``."""

git_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type(subprocess.CalledProcessError),
    reraise=True,
)
"""Retry decorator for ``subprocess`` git commands.
Exported for future ``semantic_diff.py``."""
