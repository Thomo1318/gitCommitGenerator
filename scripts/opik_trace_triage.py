#!/usr/bin/env python
"""Legacy Opik trace triage — retired as dual score law (S6 Slice 8 / D27 / #246).

Former behaviour used live Opik ``search_traces`` with
``feedback_scores.user_acceptance`` thresholds (``> 0.8`` / ``< 0.2``) to label
"Golden" and "Regression" traces. That is **not** Hybrid / gold / path-class /
accept-path authority and must not be revived.

Canonical offline surfaces::

    git-cg eval triage
    git-cg eval doctor
    git-cg eval failures
    git-cg eval explain

This file remains only as a fail-closed pointer. ``user_acceptance`` thresholds
are not gold or accept-path law.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

__all__ = [
    "CANONICAL_TRIAGE_HOMES",
    "LEGACY_OPIK_TRACE_TRIAGE_RETIRED",
    "main",
    "refuse_legacy_opik_trace_triage",
    "triage_traces",
]

LEGACY_OPIK_TRACE_TRIAGE_RETIRED: Final[bool] = True

CANONICAL_TRIAGE_HOMES: Final[tuple[str, ...]] = (
    "git-cg eval triage",
    "git-cg eval doctor",
    "git-cg eval failures",
    "git-cg eval explain",
)

_REFUSE_MESSAGE: Final[str] = f"""\
ERROR: scripts/opik_trace_triage.py is frozen (S6 Slice 8 / D27 / #246).

Reasons:
  * Live Opik search_traces + user_acceptance thresholds are not offline Layer-A.
  * Popularity / acceptance-threshold triage is not gold, ranking, or accept-path law.
  * Dual score law is prohibited; use the offline eval triage router instead.

Canonical homes:
  * Router:   {CANONICAL_TRIAGE_HOMES[0]}
  * Doctor:   {CANONICAL_TRIAGE_HOMES[1]}
  * Failures: {CANONICAL_TRIAGE_HOMES[2]}
  * Explain:  {CANONICAL_TRIAGE_HOMES[3]}

Note: user_acceptance thresholds are not gold or accept-path law.
"""


def refuse_legacy_opik_trace_triage(*, stream=None) -> int:
    """Print the freeze notice and return a non-zero exit code."""
    out = sys.stderr if stream is None else stream
    print(_REFUSE_MESSAGE, file=out)
    return 2


def triage_traces(project_name: str = "gitCommitGenerator", **_kwargs):
    """Former live Opik triage entry — always refuses (no network, no SDK)."""
    del project_name
    code = refuse_legacy_opik_trace_triage()
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: refuse with pointer (no network)."""
    parser = argparse.ArgumentParser(
        description=(
            "FROZEN: former Opik acceptance-threshold triage. Use git-cg eval triage / doctor / failures / explain."
        )
    )
    parser.add_argument(
        "--project",
        default="gitCommitGenerator",
        help="Ignored (legacy flag retained for pointer compatibility).",
    )
    parser.parse_args(argv)
    return refuse_legacy_opik_trace_triage()


if __name__ == "__main__":
    raise SystemExit(main())
