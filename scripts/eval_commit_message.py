#!/usr/bin/env python
"""Legacy Opik commit-message evaluate harness — retired as scoring law (S2/S5).

Issue #233 / plan §8.9 / D24-adjacent:

* Not Hybrid / gold / path-class / accept-path authority.
* Hard ``import opik`` + live generation path is frozen.
* Canonical surfaces::

      src/git_cg/eval/scoring/score_bundle
      src/git_cg/eval/lane_c/run_lane_c
      uv run pytest tests/eval/

This file remains only as a fail-closed pointer.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

__all__ = [
    "CANONICAL_EVAL_HOMES",
    "LEGACY_EVAL_COMMIT_MESSAGE_RETIRED",
    "evaluation_task",
    "main",
    "refuse_legacy_eval_commit_message",
]

LEGACY_EVAL_COMMIT_MESSAGE_RETIRED: Final[bool] = True

CANONICAL_EVAL_HOMES: Final[tuple[str, ...]] = (
    "src/git_cg/eval/scoring/",
    "src/git_cg/eval/lane_c/",
    "tests/eval/",
)

_REFUSE_MESSAGE: Final[str] = f"""\
ERROR: scripts/eval_commit_message.py is frozen (S2 demotion / S5 D24 board / #233).

Reasons:
  * Live Opik GEval harness is not offline Layer-A / CI / golden SoT.
  * Product generation + cloud judge coupling bypasses gated Lane C law.
  * Format/quality script metrics are advisory-only legacy (see opik_metrics.py).

Canonical homes:
  * Scoring: {CANONICAL_EVAL_HOMES[0]}
  * Lane C:  {CANONICAL_EVAL_HOMES[1]}
  * Tests:   {CANONICAL_EVAL_HOMES[2]}
"""


def refuse_legacy_eval_commit_message(*, stream=None) -> int:
    """Print the legacy evaluator freeze notice and provide its failure exit code.
    
    Parameters:
    	stream: Optional output stream for the notice. Defaults to standard error.
    
    Returns:
    	int: Exit code 2.
    """
    out = sys.stderr if stream is None else stream
    print(_REFUSE_MESSAGE, file=out)
    return 2


def evaluation_task(item=None, **_kwargs):
    """
    Refuse execution of the retired legacy evaluation task.
    
    Raises:
        SystemExit: Always, with exit code 2.
    """
    del item
    code = refuse_legacy_eval_commit_message()
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    """
    Refuse execution of the retired legacy evaluator and direct users to the canonical evaluation locations.
    
    Parameters:
        argv (list[str] | None): Optional command-line arguments to parse.
    
    Returns:
        int: Exit code `2`.
    """
    parser = argparse.ArgumentParser(
        description="FROZEN: former Opik commit-message evaluator. Use tests/eval + lane_c."
    )
    parser.parse_args(argv)
    return refuse_legacy_eval_commit_message()


if __name__ == "__main__":
    raise SystemExit(main())
