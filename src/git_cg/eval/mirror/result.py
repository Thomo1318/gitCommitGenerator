"""Machine-readable MirrorResult (P0-7 / P1-5).

Single structured result channel for export ops and eval-job interpretation.

Dual axis (P1-5):
  * ``export_result``     — ops/drain outcome (best-effort under ``mirror``)
  * ``evaluation_job_result`` — eval/CI may fail only under ``strict_mirror``

Both axes are views over one ``MirrorResult``. ``product_accept_blocked`` is
**always** ``false`` — export never blocks git commit accept.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Final

from git_cg.eval.mirror.health import ExportHealth, map_error_class_to_health

__all__ = [
    "MirrorResult",
    "build_mirror_result",
    "evaluation_job_result",
    "export_result",
]

_MAX_NOTES: Final = 32
_MAX_NOTE_LEN: Final = 200


def _scrub_notes(notes: Iterable[str] | None) -> tuple[str, ...]:
    """Bound and sanitize operator notes (max count/length; no multi-line dumps)."""
    if not notes:
        return ()
    out: list[str] = []
    for note in notes:
        text = str(note).replace("\n", " ").strip()
        if not text:
            continue
        out.append(text[:_MAX_NOTE_LEN])
        if len(out) >= _MAX_NOTES:
            break
    return tuple(out)


@dataclass(frozen=True, slots=True)
class MirrorResult:
    """Normative mirror/drain result (P0-7).

    Invariant: ``product_accept_blocked`` is always ``False``.
    """

    mode: str
    health: ExportHealth
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    deferred: int = 0
    error_classes: tuple[str, ...] = field(default_factory=tuple)
    strict_mirror_failed: bool = False
    product_accept_blocked: bool = field(default=False, init=False)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate dataclass invariants after initialization."""
        # Frozen dataclass: use object.__setattr__ for invariant fields.
        object.__setattr__(self, "product_accept_blocked", False)
        object.__setattr__(self, "notes", _scrub_notes(self.notes))
        # Dedupe error classes, preserve order.
        classes = tuple(dict.fromkeys(str(c) for c in self.error_classes if c))
        object.__setattr__(self, "error_classes", classes)
        if not isinstance(self.health, ExportHealth):
            object.__setattr__(self, "health", ExportHealth(str(self.health)))

    def to_dict(self) -> dict[str, Any]:
        """Public MirrorResult view. Always sets ``product_accept_blocked=False``."""
        return {
            "mode": self.mode,
            "health": self.health.value if isinstance(self.health, ExportHealth) else str(self.health),
            "attempted": int(self.attempted),
            "succeeded": int(self.succeeded),
            "failed": int(self.failed),
            "deferred": int(self.deferred),
            "error_classes": list(self.error_classes),
            "strict_mirror_failed": bool(self.strict_mirror_failed),
            "product_accept_blocked": False,
            "notes": list(self.notes),
        }


def build_mirror_result(
    *,
    mode: str,
    health: ExportHealth | str | None = None,
    attempted: int = 0,
    succeeded: int = 0,
    failed: int = 0,
    deferred: int = 0,
    error_classes: Iterable[str] | None = None,
    notes: Iterable[str] | None = None,
) -> MirrorResult:
    """Construct a ``MirrorResult`` with strict_mirror / health defaults.

    Infers section-18.7 health when omitted. ``strict_mirror_failed`` may be
    true only under ``strict_mirror``; product accept is never blocked here.
    """
    classes = tuple(error_classes or ())
    # Materialize once: generators must survive both health inference and result storage.
    note_items = tuple(notes or ())
    if health is None:
        health = _infer_health(
            mode=mode,
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            deferred=deferred,
            error_classes=classes,
            notes=note_items,
        )
    health_enum = health if isinstance(health, ExportHealth) else ExportHealth(str(health))
    strict_failed = mode == "strict_mirror" and (
        failed > 0
        or health_enum
        in {
            ExportHealth.AUTH_ERROR,
            ExportHealth.NETWORK_ERROR,
            ExportHealth.TIMEOUT,
            ExportHealth.CONFIG_ERROR,
            ExportHealth.PARTIAL,
            ExportHealth.REPLAY_NEEDED,
        }
    )
    return MirrorResult(
        mode=mode,
        health=health_enum,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        deferred=deferred,
        error_classes=classes,
        strict_mirror_failed=strict_failed,
        notes=note_items,
    )


def _infer_health(
    *,
    mode: str,
    attempted: int,
    succeeded: int,
    failed: int,
    deferred: int,
    error_classes: tuple[str, ...],
    notes: tuple[str, ...],
) -> ExportHealth:
    """Derive section-18.7 ``ExportHealth`` from mode, counters, notes, and classes.

    Covers skipped_off, auth/config errors, deferred empty drains, partial
    success, and mapped transport failures.
    """
    if mode == "off" or "mode_off" in notes or "skipped_off" in notes:
        return ExportHealth.SKIPPED_OFF
    if any(n.startswith("secret_resolution_failed") or n == "secret_resolution_failed" for n in notes):
        return ExportHealth.AUTH_ERROR
    if "config_error" in notes or "schema_validation_error" in notes:
        return ExportHealth.CONFIG_ERROR
    if deferred > 0 and attempted == 0 and failed == 0:
        return ExportHealth.DEFERRED
    if attempted == 0 and failed == 0 and succeeded == 0:
        # empty queue / nothing to do under active mode
        return ExportHealth.PENDING if mode in {"mirror", "strict_mirror", "local_only"} else ExportHealth.SKIPPED_OFF
    if failed and succeeded:
        return ExportHealth.PARTIAL
    if failed and not succeeded:
        if error_classes:
            return map_error_class_to_health(error_classes[0])
        return ExportHealth.NETWORK_ERROR
    if succeeded and not failed:
        return ExportHealth.SUCCESS
    return ExportHealth.PENDING


def export_result(result: MirrorResult | Mapping[str, Any]) -> dict[str, Any]:
    """Operator export-result axis (P0-7). Never a product-accept blocker."""
    data = result.to_dict() if isinstance(result, MirrorResult) else dict(result)
    return {
        "axis": "export_result",
        "mode": data.get("mode"),
        "health": data.get("health"),
        "attempted": data.get("attempted", 0),
        "succeeded": data.get("succeeded", 0),
        "failed": data.get("failed", 0),
        "deferred": data.get("deferred", 0),
        "error_classes": list(data.get("error_classes") or []),
        "product_accept_blocked": False,
        "notes": list(data.get("notes") or []),
    }


def evaluation_job_result(result: MirrorResult | Mapping[str, Any]) -> dict[str, Any]:
    """Eval/CI job view - may report failure only under ``strict_mirror`` (P1-5).

    Always keeps ``product_accept_blocked=False`` on this axis.
    """
    data = result.to_dict() if isinstance(result, MirrorResult) else dict(result)
    mode = str(data.get("mode") or "off")
    strict_failed = bool(data.get("strict_mirror_failed"))
    job_ok = not (mode == "strict_mirror" and strict_failed)
    return {
        "axis": "evaluation_job_result",
        "mode": mode,
        "health": data.get("health"),
        "ok": job_ok,
        "strict_mirror_failed": strict_failed,
        "product_accept_blocked": False,
        "error_classes": list(data.get("error_classes") or []),
        "notes": list(data.get("notes") or []),
    }


# Silence unused import warning helpers for type checkers that flag asdict.
_ = asdict
