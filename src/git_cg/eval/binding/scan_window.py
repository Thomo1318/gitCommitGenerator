"""Acceptpath miss-scan window names and defaults.

These names are the stable test and operator surface for the parse window.
Listing still walks every ``*.json`` entry; only parse cost is capped.
``K=512`` is the fail-closed default, not a ratified lock budget.

Refs: #257.
"""

from __future__ import annotations

__all__ = ["DEFAULT_SCAN_WINDOW", "FULL_SCAN_ENV", "SCAN_WINDOW_ENV"]

#: Fail-closed miss-scan parse window. Not a ratified lock budget.
DEFAULT_SCAN_WINDOW = 512

#: Positive ASCII-digit override for :data:`DEFAULT_SCAN_WINDOW`.
SCAN_WINDOW_ENV = "GIT_CG_EVAL_ACCEPTPATH_SCAN_WINDOW"

#: Diagnostic override. Only the exact token ``1`` disables the parse bound.
FULL_SCAN_ENV = "GIT_CG_EVAL_ACCEPTPATH_FULL_SCAN"
