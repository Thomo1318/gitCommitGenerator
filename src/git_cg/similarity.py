"""
Body-similarity helpers for semantic producers (ADR-0005 Phase 2).

Minimal rapidfuzz axis used by the fingerprint algebra gate and telemetry.
Does not own ranking policy or adaptive thresholds.
"""

from __future__ import annotations

from rapidfuzz import fuzz

# Dark-launch gate: shape-equal + code-unequal bodies above this are formatting_only.
FORMATTING_BODY_SIMILARITY_THRESHOLD = 0.9


def body_similarity(baseline_text: bytes | str, staged_text: bytes | str) -> float:
    """
    Return token-set similarity in ``[0.0, 1.0]`` between two source bodies.

    Uses ``rapidfuzz.fuzz.token_set_ratio`` so minor token reorder / whitespace
    heavy edits score high while substantive rewrites score lower.
    """
    left = baseline_text.decode("utf-8", errors="replace") if isinstance(baseline_text, bytes) else baseline_text
    right = staged_text.decode("utf-8", errors="replace") if isinstance(staged_text, bytes) else staged_text
    return float(fuzz.token_set_ratio(left, right)) / 100.0
