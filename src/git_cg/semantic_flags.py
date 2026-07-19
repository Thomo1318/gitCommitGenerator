"""Feature flags for the ADR-0005 semantic core dark-launch path."""

from __future__ import annotations

import os


def is_semantic_enabled(explicit: bool | None = None) -> bool:
    """
    Resolve whether semantic producers are enabled.

    Precedence:
    1. Explicit boolean argument (CLI / caller override)
    2. ``GIT_CG_ENABLE_SEMANTIC`` env var (``1``/``true``/``yes``/``on``)
    3. Default ``False`` (dark launch)
    """
    if explicit is not None:
        return explicit

    raw = os.environ.get("GIT_CG_ENABLE_SEMANTIC", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
