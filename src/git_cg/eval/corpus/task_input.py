"""generation_task_input projection + expected/gold isolation (F6 / INT-22)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Property names forbidden by ape_bundle_v1.generation_task_input schema and F6.
_FORBIDDEN_NAME = re.compile(r"^(expected|gold)(_|$)", re.IGNORECASE)

# Explicit non-generation keys that must never ride on task input even if rename-escaped.
_FORBIDDEN_EXACT = frozenset(
    {
        "expected_final_message",
        "expected_gold_codes",
        "expected_output",
        "gold_codes",
        "gold_findings",
        "judge_labels",
        "judge_target",
        "gate_deterministic_pass",
    }
)

_ALLOWED_KEYS = frozenset({"diff_summary", "path_class_gate", "ranked_intent_id"})


class TaskInputError(ValueError):
    """generation_task_input isolation / shape failure."""


def _is_forbidden_key(key: str) -> bool:
    if key in _FORBIDDEN_EXACT:
        return True
    return _FORBIDDEN_NAME.match(key) is not None


def project_generation_task_input(
    raw: Mapping[str, Any] | None,
    *,
    strict: bool = True,
) -> dict[str, str] | None:
    """Project a generation-shaped input object with fail-closed isolation.

    Args:
        raw: candidate mapping from a fixture.
        strict: when True (default), reject forbidden keys and unknown keys.
            when False, strip forbidden keys and drop unknowns (still never
            returns expected/gold).

    Returns:
        None when raw is None/empty after projection; otherwise a dict with only
        allowed string fields.

    Raises:
        TaskInputError: on isolation leaks or invalid shapes under strict mode.
    """
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TaskInputError(f"generation_task_input must be an object, got {type(raw).__name__}")
    if not raw:
        return None

    forbidden = sorted(k for k in raw if isinstance(k, str) and _is_forbidden_key(k))
    if forbidden:
        if strict:
            raise TaskInputError(
                "generation_task_input must not contain expected/gold/judge target fields: " + ", ".join(forbidden)
            )
        # strip path still fails closed for returned content
        working = {k: v for k, v in raw.items() if not (isinstance(k, str) and _is_forbidden_key(k))}
    else:
        working = dict(raw)

    unknown = sorted(k for k in working if k not in _ALLOWED_KEYS)
    if unknown and strict:
        raise TaskInputError(
            f"generation_task_input contains unsupported keys {unknown}; allowed: {sorted(_ALLOWED_KEYS)}"
        )

    out: dict[str, str] = {}
    for key in sorted(_ALLOWED_KEYS):
        if key not in working:
            continue
        value = working[key]
        if value is None:
            continue
        if not isinstance(value, str):
            raise TaskInputError(f"generation_task_input.{key} must be a string")
        out[key] = value
    return out or None
