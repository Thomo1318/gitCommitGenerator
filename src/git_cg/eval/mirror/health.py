"""Closed ExportHealth vocabulary (plan §18.7 / INT-16 / E1).

Operational tokens for two-layer durability. Operator-facing rollups
(healthy/degraded/...) are **derived views**, not a second closed law surface.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "EXPORT_HEALTH",
    "ExportHealth",
    "derive_export_health_rollup",
    "map_error_class_to_health",
]


class ExportHealth(StrEnum):
    """Plan §18.7 operational export-health tokens."""

    SKIPPED_OFF = "skipped_off"
    DEFERRED = "deferred"
    PENDING = "pending"
    SUCCESS = "success"
    CONFIG_ERROR = "config_error"
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    PARTIAL = "partial"
    REPLAY_NEEDED = "replay_needed"


EXPORT_HEALTH: Final[tuple[str, ...]] = tuple(h.value for h in ExportHealth)

# Ensure uniqueness + non-empty at import time (derived_fields pattern).
assert EXPORT_HEALTH, "ExportHealth must be non-empty"
assert len(EXPORT_HEALTH) == len(set(EXPORT_HEALTH)), "ExportHealth values must be unique"


def map_error_class_to_health(error_class: str | None) -> ExportHealth:
    """Map a closed export ``error_class`` onto a section-18.7 ``ExportHealth`` token.

    Unknown/empty classes become ``network_error`` (safe default for operator UX).
    """
    if not error_class:
        return ExportHealth.NETWORK_ERROR
    mapping = {
        "export_auth": ExportHealth.AUTH_ERROR,
        "export_network": ExportHealth.NETWORK_ERROR,
        "export_validation": ExportHealth.CONFIG_ERROR,
        "export_size": ExportHealth.CONFIG_ERROR,
        "export_timeout": ExportHealth.TIMEOUT,
    }
    return mapping.get(error_class, ExportHealth.NETWORK_ERROR)


def derive_export_health_rollup(health: ExportHealth | str) -> str:
    """Human/UI rollup label derived from a section-18.7 token (not a second enum)."""
    token = ExportHealth(health) if not isinstance(health, ExportHealth) else health
    if token is ExportHealth.SUCCESS:
        return "healthy"
    if token in {ExportHealth.SKIPPED_OFF, ExportHealth.DEFERRED, ExportHealth.PENDING}:
        return "idle"
    if token is ExportHealth.PARTIAL:
        return "degraded"
    if token is ExportHealth.REPLAY_NEEDED:
        return "replay"
    return "unhealthy"
