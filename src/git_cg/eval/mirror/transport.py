"""S4b transport layer (F4 fail-open, FIND-022 / P0-4 / P1-3).

Defines the :class:`Transport` protocol and two implementations:

* :class:`OpikSdkTransport` — the real upload path. The ``opik`` package is
  imported **lazily inside the call** so the S4a offline core and the product
  accept path never import Opik. Secrets arrive as an ephemeral
  :class:`OpikRuntimeSecrets` and are never stored.
* :class:`MockTransport` — deterministic test double; records calls, can be
  primed to raise classified errors.

Every failure is classified into the closed ``export_*`` vocabulary
(``export_network`` / ``export_auth`` / ``export_validation`` /
``export_size``) via :class:`ExportTransportError`. Classification prefers
HTTP status codes (P1-3), then exception shape, and never leaks secret
material, URLs, headers, or bodies into the message.

Bounded flush (P0-4 / FIND-022):
  * Config is always ``flush_timeout_ms``.
  * Installed ``opik==2.0.52`` accepts ``flush(timeout: Optional[int])`` in
    **seconds** and returns ``bool``.
  * Adapter converts with ``math.ceil(ms / 1000)`` and wraps an outer
    monotonic deadline so short-lived hook processes cannot hang on exit.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Final, Protocol, runtime_checkable

from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

__all__ = [
    "EXPORT_ERROR_CLASSES",
    "LAZY_OPIK_IMPORT_ALLOWLIST",
    "ExportTransportError",
    "MockTransport",
    "OpikSdkTransport",
    "Transport",
    "classify_export_error",
    "flush_timeout_seconds",
    "scrub_export_note",
]

#: Closed export failure vocabulary (plan §7.2.10 export_batch_v1.error_class).
EXPORT_ERROR_CLASSES = frozenset({"export_network", "export_auth", "export_validation", "export_size"})

#: E5 — only allowed module-scope-or-lazy Opik import site, pinned by path:lineno.
#: Update this constant in the same commit if the lazy ``import opik`` line moves.
LAZY_OPIK_IMPORT_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "src/git_cg/eval/mirror/transport.py:206",
    }
)

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)\b(authorization|api[_-]?key|token|secret|cookie|set-cookie)\b\s*[:=]\s*\S+")
_PATH_QUERY_RE = re.compile(r"(?i)(/v1/\S+|\?[^\s]+)")
_SECRETISH_RE = re.compile(
    r"(?i)\b(?:sk|pk|api[_-]?key|token|secret|password|bearer)[-_A-Za-z0-9]*\b"
    r"|\b[A-Za-z0-9_-]{24,}\b"
    r"|\bsuper-secret\b"
)


def flush_timeout_seconds(timeout_ms: int) -> int:
    """Convert configured flush bound (ms) to Opik SDK seconds (P0-4).

    ``opik.Opik.flush`` takes whole seconds. Sub-second budgets still map to
    at least 1s so the SDK call is not zero/None-open-ended.
    """
    ms = max(1, int(timeout_ms))
    return max(1, math.ceil(ms / 1000))


def scrub_export_note(text: str, *, limit: int = 160) -> str:
    """Scrub URLs/headers/secret-shaped tokens from queue/transport notes (P1-3)."""
    cleaned = str(text or "")
    cleaned = _URL_RE.sub("<redacted-url>", cleaned)
    cleaned = _BEARER_RE.sub(r"\1=<redacted>", cleaned)
    cleaned = _PATH_QUERY_RE.sub("<redacted-path>", cleaned)
    # Catch bare leftover secret-ish tokens (e.g. "super-secret", long keys).
    cleaned = _SECRETISH_RE.sub("<redacted>", cleaned)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > limit:
        return cleaned[: max(0, limit - 1)] + "…"
    return cleaned


class ExportTransportError(RuntimeError):
    """A classified export transport failure (never product-blocking)."""

    def __init__(self, error_class: str, message: str) -> None:
        if error_class not in EXPORT_ERROR_CLASSES:
            error_class = "export_network"
        self.error_class = error_class
        super().__init__(f"{error_class}: {scrub_export_note(message)}")


@runtime_checkable
class Transport(Protocol):
    """Upload a projected batch payload to the mirror backend."""

    def upload(
        self,
        *,
        project: str,
        experiment_name: str,
        payload: dict[str, Any],
        secrets: OpikRuntimeSecrets,
        timeout_ms: int,
    ) -> None:
        """Upload ``payload``; raise :class:`ExportTransportError` on failure."""
        ...


def _status_code_of(exc: BaseException) -> int | None:
    """Best-effort HTTP status extraction without trusting raw bodies."""
    for attr in ("status_code", "status", "http_status", "code"):
        raw = getattr(exc, attr, None)
        if isinstance(raw, int) and 100 <= raw <= 599:
            return raw
        if isinstance(raw, str) and raw.isdigit():
            value = int(raw)
            if 100 <= value <= 599:
                return value
    response = getattr(exc, "response", None)
    if response is not None:
        for attr in ("status_code", "status"):
            raw = getattr(response, attr, None)
            if isinstance(raw, int) and 100 <= raw <= 599:
                return raw
    # Message fall-through: "HTTP 413", "status=429"
    msg = str(exc)
    match = re.search(r"\b(?:HTTP\s*)?(?:status(?:\s*code)?[=:\s]*)?(?P<code>[1-5][0-9]{2})\b", msg, re.I)
    if match:
        return int(match.group("code"))
    return None


def classify_export_error(exc: BaseException) -> ExportTransportError:
    """Map an arbitrary exception to a classified ``ExportTransportError`` (P1-3).

    Order:
      1. explicit ``ExportTransportError`` passthrough
      2. HTTP status codes
      3. exception type-name heuristics
      4. default ``export_network``

    Messages are scrubbed; raw headers/URLs/bodies never become queue notes.
    """
    if isinstance(exc, ExportTransportError):
        return exc

    status = _status_code_of(exc)
    name = type(exc).__name__
    detail = scrub_export_note(f"{name}: {exc}", limit=160)

    if status in {401, 403}:
        return ExportTransportError("export_auth", f"HTTP {status}: {detail}")
    if status == 413:
        return ExportTransportError("export_size", f"HTTP {status}: {detail}")
    if status in {400, 404, 409, 422}:
        return ExportTransportError("export_validation", f"HTTP {status}: {detail}")
    if status in {408, 425, 429} or (status is not None and status >= 500):
        return ExportTransportError("export_network", f"HTTP {status}: {detail}")

    lname = name.lower()
    if any(t in lname for t in ("auth", "permission", "unauthorized", "forbidden", "credential")):
        return ExportTransportError("export_auth", detail)
    if any(t in lname for t in ("timeout", "connection", "network", "socket", "http", "request")):
        return ExportTransportError("export_network", detail)
    if any(t in lname for t in ("size", "toolarge", "payload", "contentlength")):
        return ExportTransportError("export_size", detail)
    if any(t in lname for t in ("value", "validation", "schema", "type", "import")):
        return ExportTransportError("export_validation", detail)
    return ExportTransportError("export_network", detail)


# Back-compat private alias used by existing tests.
_classify = classify_export_error


class OpikSdkTransport:
    """Real transport via the Opik SDK (lazy import, bounded flush).

    The ``opik`` import happens inside :meth:`upload` so importing this module
    never pulls Opik into the offline/product path. The client is constructed
    per-upload with an explicit flush timeout so a short-lived hook process
    cannot hang on exit (FIND-022 / P0-4).
    """

    def upload(
        self,
        *,
        project: str,
        experiment_name: str,
        payload: dict[str, Any],
        secrets: OpikRuntimeSecrets,
        timeout_ms: int,
    ) -> None:
        deadline = time.monotonic() + max(0.001, float(timeout_ms) / 1000.0)
        try:
            import opik
        except ImportError as exc:
            raise ExportTransportError(
                "export_validation",
                "opik package not installed; S4b transport unavailable (offline core unaffected)",
            ) from exc

        try:
            # opik is an optional runtime dep; the attribute exists at runtime
            # but pyright cannot resolve it through the lazy import guard.
            client = opik.Opik(  # type: ignore[attr-defined]
                project_name=project,
                workspace=secrets.workspace,
                host=secrets.base_url,
                api_key=secrets.api_key or None,
            )
            self._send(client, experiment_name=experiment_name, payload=payload)
            self._bounded_flush(client, timeout_ms=timeout_ms, deadline=deadline)
        except ExportTransportError:
            raise
        except Exception as exc:  # classify anything the SDK throws
            raise classify_export_error(exc) from exc

    @staticmethod
    def _send(client: Any, *, experiment_name: str, payload: dict[str, Any]) -> None:
        """Project the payload onto the client.

        Uses the SDK's generic trace/feedback surface. The exact Opik object
        shape is owned by :mod:`git_cg.eval.mirror.projections`; here we only
        forward it. Kept minimal so the SDK surface is easy to adapt.
        """
        trace_fn = getattr(client, "trace", None)
        if callable(trace_fn):
            trace_fn(
                name=experiment_name,
                input=payload.get("input", {}),
                output=payload.get("output", {}),
                metadata=payload.get("metadata", {}),
            )
            return
        raise ExportTransportError("export_validation", "opik client exposes no usable trace surface")

    @staticmethod
    def _bounded_flush(client: Any, *, timeout_ms: int, deadline: float) -> None:
        """Adapter for ``opik.Opik.flush(timeout=seconds) -> bool`` (P0-4).

        * Converts ms → seconds via :func:`flush_timeout_seconds`.
        * Honours an outer monotonic deadline (remaining seconds, ≥1 when work remains).
        * ``flush() is False`` or hang past deadline ⇒ ``export_network`` (timeout class).
        """
        flush = getattr(client, "flush", None)
        if not callable(flush):
            return

        remaining_ms = int(max(1.0, (deadline - time.monotonic()) * 1000.0))
        timeout_s = flush_timeout_seconds(min(timeout_ms, remaining_ms))
        try:
            ok = flush(timeout=timeout_s)
        except TypeError:
            # Extremely defensive: older stubs might still accept timeout_ms.
            try:
                ok = flush(timeout_ms=max(1, timeout_ms))
            except Exception as exc:  # classify below
                raise classify_export_error(exc) from exc
        except Exception as exc:
            raise classify_export_error(exc) from exc

        if time.monotonic() > deadline:
            raise ExportTransportError(
                "export_network",
                f"flush exceeded outer deadline ({timeout_ms}ms)",
            )
        if ok is False:
            raise ExportTransportError(
                "export_network",
                f"flush returned false within {timeout_s}s bound (timeout/incomplete)",
            )


class MockTransport:
    """Deterministic test double. Records uploads; can be primed to fail."""

    def __init__(self, fail_with: ExportTransportError | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail_with = fail_with

    def upload(
        self,
        *,
        project: str,
        experiment_name: str,
        payload: dict[str, Any],
        secrets: OpikRuntimeSecrets,
        timeout_ms: int,
    ) -> None:
        self.calls.append(
            {
                "project": project,
                "experiment_name": experiment_name,
                "payload": payload,
                "timeout_ms": timeout_ms,
            }
        )
        if self._fail_with is not None:
            raise self._fail_with
