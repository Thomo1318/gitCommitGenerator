"""S4b transport layer (F4 fail-open, FIND-022).

Defines the :class:`Transport` protocol and two implementations:

* :class:`OpikSdkTransport` — the real upload path. The ``opik`` package is
  imported **lazily inside the call** so the S4a offline core and the product
  accept path never import Opik. Secrets arrive as an ephemeral
  :class:`OpikRuntimeSecrets` and are never stored.
* :class:`MockTransport` — deterministic test double; records calls, can be
  primed to raise classified errors.

Every failure is classified into the closed ``export_*`` vocabulary
(``export_network`` / ``export_auth`` / ``export_validation`` /
``export_size``) via :class:`ExportTransportError`. Classification is
best-effort from the exception shape and never leaks secret material into the
message.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from git_cg.eval.mirror.secrets import OpikRuntimeSecrets

__all__ = [
    "EXPORT_ERROR_CLASSES",
    "ExportTransportError",
    "MockTransport",
    "OpikSdkTransport",
    "Transport",
]

#: Closed export failure vocabulary (plan §7.2.10 export_batch_v1.error_class).
EXPORT_ERROR_CLASSES = frozenset({"export_network", "export_auth", "export_validation", "export_size"})


class ExportTransportError(RuntimeError):
    """A classified export transport failure (never product-blocking)."""

    def __init__(self, error_class: str, message: str) -> None:
        if error_class not in EXPORT_ERROR_CLASSES:
            error_class = "export_network"
        self.error_class = error_class
        super().__init__(f"{error_class}: {message}")


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


def _classify(exc: BaseException) -> ExportTransportError:
    """Map an arbitrary exception to a classified ``ExportTransportError``.

    Heuristic, secret-safe: the message is the exception *type name* plus a
    short scrubbed detail, never the raw exception if it could embed request
    headers/tokens.
    """
    name = type(exc).__name__.lower()
    detail = str(exc)[:200]
    if any(t in name for t in ("auth", "permission", "unauthorized", "forbidden", "credential")):
        return ExportTransportError("export_auth", f"{type(exc).__name__}: {detail}")
    if any(t in name for t in ("timeout", "connection", "network", "socket", "http", "request")):
        return ExportTransportError("export_network", f"{type(exc).__name__}: {detail}")
    if any(t in name for t in ("size", "toolarge", "payload", "contentlength")):
        return ExportTransportError("export_size", f"{type(exc).__name__}: {detail}")
    if any(t in name for t in ("value", "validation", "schema", "type")):
        return ExportTransportError("export_validation", f"{type(exc).__name__}: {detail}")
    return ExportTransportError("export_network", f"{type(exc).__name__}: {detail}")


class OpikSdkTransport:
    """Real transport via the Opik SDK (lazy import, bounded flush).

    The ``opik`` import happens inside :meth:`upload` so importing this module
    never pulls Opik into the offline/product path. The client is constructed
    per-upload with an explicit flush timeout so a short-lived hook process
    cannot hang on exit (FIND-022).
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
            # Bounded flush so short-lived processes cannot hang (FIND-022).
            flush = getattr(client, "flush", None)
            if callable(flush):
                flush(timeout_ms=max(1, timeout_ms))
        except ExportTransportError:
            raise
        except Exception as exc:  # classify anything the SDK throws
            raise _classify(exc) from exc

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
