#!/usr/bin/env python
"""LEGACY ADVISORY ONLY — not S2/S5 scoring law (frozen pointer).

Demoted in S2b (#227). Strengthened freeze under S5 D24 board (#233).

* Do **not** import from ``git_cg.eval.scoring``, CI gates, hooks, or product
  commit paths.
* Format heuristics here are **not** gold / Hybrid / path-class authority.
* Canonical format/structure law lives in offline Family metrics + hooks.

This module no longer imports the Opik SDK. Invocation refuses closed.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

__all__ = [
    "CANONICAL_SCORING_HOME",
    "LEGACY_OPIK_METRICS_RETIRED",
    "FormatMetric",
    "main",
    "refuse_legacy_opik_metrics",
]

LEGACY_OPIK_METRICS_RETIRED: Final[bool] = True
CANONICAL_SCORING_HOME: Final[str] = "src/git_cg/eval/scoring/"

_REFUSE_MESSAGE: Final[str] = f"""\
ERROR: scripts/opik_metrics.py is frozen legacy advisory (S2b demotion / #233).

Reasons:
  * FormatMetric heuristics are not Hybrid/gold/path-class law.
  * Opik SDK metric classes are not the offline score_bundle SoT.
  * Canonical scoring: {CANONICAL_SCORING_HOME}
"""


def refuse_legacy_opik_metrics(*, stream=None) -> int:
    """Print the freeze notice and return a non-zero exit code."""
    out = sys.stderr if stream is None else stream
    print(_REFUSE_MESSAGE, file=out)
    return 2


class FormatMetric:
    """Retired placeholder — instantiation/score always fails closed."""

    def __init__(self, name: str = "CommitFormatQuality") -> None:
        self.name = name

    def score(self, output: str = "", **_kwargs):
        del output
        code = refuse_legacy_opik_metrics()
        raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: refuse with pointer."""
    parser = argparse.ArgumentParser(description="FROZEN: legacy Opik FormatMetric helper. Use git_cg.eval.scoring.")
    parser.parse_args(argv)
    return refuse_legacy_opik_metrics()


if __name__ == "__main__":
    raise SystemExit(main())
