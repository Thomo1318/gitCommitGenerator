"""E4 — mirror enums must not collapse distinct state machines.

Guards against copy-paste enum drift. ``ExportHealth.pending`` and queue
``pending`` are intentionally distinct surfaces (E7) that share an English
token; they are different types/modules and must not be merged into one enum.
"""

from __future__ import annotations

import pytest

from git_cg.eval.enums import Authority, RedactionProfile, Severity
from git_cg.eval.mirror.config import OpikEnvironment, OpikMode
from git_cg.eval.mirror.health import ExportHealth
from git_cg.eval.mirror.queue import QUEUE_STATUSES
from git_cg.eval.mirror.transport import EXPORT_ERROR_CLASSES


def _values(enum_cls: type) -> set[str]:
    """Return the string values defined by an enum class.
    
    Parameters:
    	enum_cls (type): The enum class to inspect.
    
    Returns:
    	set[str]: The enum members' string values.
    """
    return {m.value for m in enum_cls}


# Pairs that must remain value-disjoint (E4).
_DISJOINT_PAIRS: list[tuple[str, set[str], str, set[str]]] = [
    ("OpikMode", _values(OpikMode), "ExportHealth", _values(ExportHealth)),
    ("OpikMode", _values(OpikMode), "OpikEnvironment", _values(OpikEnvironment)),
    ("OpikMode", _values(OpikMode), "RedactionProfile", _values(RedactionProfile)),
    ("OpikMode", _values(OpikMode), "Authority", _values(Authority)),
    ("OpikMode", _values(OpikMode), "Severity", _values(Severity)),
    ("OpikMode", _values(OpikMode), "ExportErrorClass", set(EXPORT_ERROR_CLASSES)),
    ("OpikMode", _values(OpikMode), "QueueStatus", set(QUEUE_STATUSES)),
    ("ExportHealth", _values(ExportHealth), "RedactionProfile", _values(RedactionProfile)),
    ("ExportHealth", _values(ExportHealth), "Authority", _values(Authority)),
    ("ExportHealth", _values(ExportHealth), "Severity", _values(Severity)),
    ("ExportHealth", _values(ExportHealth), "ExportErrorClass", set(EXPORT_ERROR_CLASSES)),
    ("ExportErrorClass", set(EXPORT_ERROR_CLASSES), "QueueStatus", set(QUEUE_STATUSES)),
    ("ExportErrorClass", set(EXPORT_ERROR_CLASSES), "RedactionProfile", _values(RedactionProfile)),
    ("RedactionProfile", _values(RedactionProfile), "Authority", _values(Authority)),
    ("RedactionProfile", _values(RedactionProfile), "Severity", _values(Severity)),
]


@pytest.mark.parametrize(("left_name", "left", "right_name", "right"), _DISJOINT_PAIRS)
def test_e4_mirror_enums_are_value_disjoint(
    left_name: str,
    left: set[str],
    right_name: str,
    right: set[str],
) -> None:
    overlap = left & right
    assert not overlap, f"{left_name} ∩ {right_name} = {sorted(overlap)}"


def test_e7_export_health_and_queue_status_are_distinct_surfaces() -> None:
    """
    Verifies that export health and queue status values remain distinct surfaces.
    
    Shared status tokens such as ``pending`` may exist in both collections, while
    transport error classes must not be used as queue statuses.
    """
    assert ExportHealth is not QUEUE_STATUSES
    assert ExportHealth.PENDING.value in _values(ExportHealth)
    assert "pending" in QUEUE_STATUSES
    # Error classes must not be queue statuses.
    assert not (set(EXPORT_ERROR_CLASSES) & set(QUEUE_STATUSES))
