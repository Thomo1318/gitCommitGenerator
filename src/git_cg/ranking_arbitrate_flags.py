"""Feature flags for ranking-confidence arbitration (Issue #195)."""

from __future__ import annotations

import os
from typing import Literal

RankArbitrateMode = Literal["auto", "off"]


def resolve_rank_arbitrate_mode(explicit: bool | str | None = None) -> RankArbitrateMode:
    """
    Resolve whether the Low-confidence arbitration menu may open.

    Precedence:
    1. Explicit CLI / caller override
       - ``True`` / ``"auto"`` → auto
       - ``False`` / ``"off"`` / ``""`` (and falsey tokens) → off
    2. ``GIT_CG_RANK_ARBITRATE`` env var
    3. Default ``auto``
    """
    if explicit is True:
        return "auto"
    if explicit is False:
        return "off"
    if isinstance(explicit, str):
        # Explicit empty string is a falsey token → off (not env fallback).
        raw = explicit.strip().lower()
        if raw == "" or raw in {"0", "false", "no", "off"}:
            return "off"
        if raw in {"1", "true", "yes", "auto", "on"}:
            return "auto"
        return "auto"
    raw = os.environ.get("GIT_CG_RANK_ARBITRATE", "auto").strip().lower()
    if raw in {"0", "false", "no", "off", ""}:
        return "off"
    return "auto"


def is_rank_arbitrate_enabled(explicit: bool | str | None = None) -> bool:
    """Return True when arbitration may open (mode is auto)."""
    return resolve_rank_arbitrate_mode(explicit) == "auto"
