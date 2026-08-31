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

#: E5 — only allowed lazy Opik import site, pinned by path:enclosing_function.
#: Line numbers are intentionally not part of the pin so nearby edits do not churn E5.
LAZY_OPIK_IMPORT_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "src/git_cg/eval/mirror/transport.py:OpikSdkTransport.upload",
        "src/git_cg/eval/mirror/opik_verify.py:_default_client_factory",
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
        """Clamp unknown classes to ``export_network`` and scrub the message."""
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
        """Upload ``payload`` within ``timeout_ms``; raise ``ExportTransportError``.

        Implementations must not log secrets or raw exception bodies.
        """
        ...


def _status_code_of(exc: BaseException) -> int | None:
    """Best-effort HTTP status extraction without trusting raw response bodies."""
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
        """Send one batch via the Opik SDK and bounded-flush to ``timeout_ms``.

        Classifies SDK failures into closed export error classes. Missing
        ``opik`` package becomes ``export_validation`` (offline core unaffected).
        """
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
    def _project_one_item(
        primary: dict[str, Any],
        *,
        experiment_name: str,
        batch_payload: dict[str, Any],
        item_ref: Any,
        item_count: int,
        item_index: int,
    ) -> dict[str, Any]:
        """Project one nested export item onto a single SDK trace surface.

        Preserves authority/gate/score_card metadata; does not rescore.
        """
        trace = primary.get("trace") if isinstance(primary.get("trace"), dict) else {}
        thread = primary.get("thread") if isinstance(primary.get("thread"), dict) else {}
        feedback = primary.get("feedback") if isinstance(primary.get("feedback"), list) else []
        experiment = primary.get("experiment") if isinstance(primary.get("experiment"), dict) else {}

        input_obj = trace.get("input") if isinstance(trace.get("input"), dict) else {}
        output_obj = trace.get("output") if isinstance(trace.get("output"), dict) else {}
        metadata: dict[str, Any] = {}
        if isinstance(trace.get("metadata"), dict):
            metadata.update(trace["metadata"])

        metadata.setdefault("experiment_name", experiment.get("experiment_name") or experiment_name)
        if batch_payload.get("schema_pack"):
            metadata.setdefault("schema_pack", batch_payload.get("schema_pack"))
        if batch_payload.get("metric_catalog"):
            metadata.setdefault("metric_catalog", batch_payload.get("metric_catalog"))
        if batch_payload.get("redaction_profile"):
            metadata.setdefault("redaction_profile", batch_payload.get("redaction_profile"))
        if thread:
            metadata["thread"] = thread
        if feedback:
            metadata["feedback"] = feedback
        if experiment:
            metadata["experiment"] = experiment
        if primary.get("authority") is not None:
            metadata.setdefault("authority", primary.get("authority"))
        if primary.get("gate") is not None:
            metadata.setdefault("gate", primary.get("gate"))
        if primary.get("score_card") is not None:
            metadata.setdefault("score_card", primary.get("score_card"))
        if primary.get("bundle_id") is not None:
            metadata.setdefault("bundle_id", primary.get("bundle_id"))
        if primary.get("artifact_class") is not None:
            metadata.setdefault("artifact_class", primary.get("artifact_class"))

        metadata["item_count"] = item_count
        metadata["item_index"] = item_index
        if item_ref is not None:
            metadata.setdefault("item_ref", item_ref)

        # Thread-only rows still need a usable input surface.
        if not input_obj and thread:
            input_obj = {
                "thread_id": thread.get("thread_id"),
                "experiment_name": thread.get("experiment_name") or experiment_name,
            }
        if not output_obj and thread:
            output_obj = {"messages": thread.get("messages") or []}

        return {
            "name": experiment_name,
            "input": input_obj if isinstance(input_obj, dict) else {},
            "output": output_obj if isinstance(output_obj, dict) else {},
            "metadata": metadata,
        }

    @staticmethod
    def _project_trace_fields(payload: dict[str, Any], *, experiment_name: str) -> list[dict[str, Any]]:
        """Project a durable export_batch transport body onto one SDK trace per item.

        Durable payloads are ``export_batch_v1`` transport bodies::

            {
                "items": [{"item_ref": "...", "payload": {...}}],
                "schema_pack": "...",
                "metric_catalog": "...",
                "redaction_profile": "...",
            }

        Nested item payloads may carry ``trace`` / ``thread`` / ``feedback``
        projections from :mod:`git_cg.eval.mirror.projections`. Top-level
        ``input`` / ``output`` / ``metadata`` keys are accepted only as a
        narrow back-compat shape for unit fixtures.

        Multi-item batches emit one projected trace per valid item so later
        entries are not discarded.
        """
        items = payload.get("items")
        if isinstance(items, list) and items:
            valid_entries: list[tuple[Any, dict[str, Any]]] = []
            for entry in items:
                if isinstance(entry, dict) and isinstance(entry.get("payload"), dict):
                    valid_entries.append((entry.get("item_ref"), entry["payload"]))

            if valid_entries:
                # Align item_count with emitted traces / item_index domain.
                item_count = len(valid_entries)
                projected: list[dict[str, Any]] = []
                for index, (item_ref, primary) in enumerate(valid_entries):
                    projected.append(
                        OpikSdkTransport._project_one_item(
                            primary,
                            experiment_name=experiment_name,
                            batch_payload=payload,
                            item_ref=item_ref,
                            item_count=item_count,
                            item_index=index,
                        )
                    )
                return projected

        # Narrow back-compat: already-projected flat surfaces.
        return [
            {
                "name": experiment_name,
                "input": payload.get("input", {}) if isinstance(payload.get("input"), dict) else {},
                "output": payload.get("output", {}) if isinstance(payload.get("output"), dict) else {},
                "metadata": payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {},
            }
        ]

    @staticmethod
    def _send(client: Any, *, experiment_name: str, payload: dict[str, Any]) -> None:
        """Project the durable payload onto the client trace surface.

        The durable body shape is owned by the queue/batch layer; this adapter
        only maps it onto the SDK. One trace is emitted per export item so
        multi-item batches retain every payload. Kept adaptive so fixture
        double surfaces and real Opik clients can both accept the projected kwargs.
        """
        trace_fn = getattr(client, "trace", None)
        if callable(trace_fn):
            for projected in OpikSdkTransport._project_trace_fields(payload, experiment_name=experiment_name):
                trace_fn(**projected)
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
        """Test double; optional ``fail_with`` raised after recording the call."""
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
        """Record upload kwargs for tests; optionally raise a scripted failure."""
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
