#!/usr/bin/env python
"""Legacy Opik test-suite bootstrap — retired as alternate authority (S5 D24 / S5-G05).

Issue #233 / plan §8.9 / D24:

* This script must **never** be accept-path, CI, package, or golden authority.
* Cloud ``evaluate()`` harnesses are **not** the offline ``tests/eval`` SoT.
* Canonical evaluation paths::

      uv run pytest tests/eval/test_lane_c*.py
      src/git_cg/eval/lane_c/run_lane_c
      src/git_cg/eval/scoring/score_bundle

* Do not revive ``scripts/eval_commit_message.py`` / ``scripts/opik_metrics.py``
  as Hybrid/gold/path-class law (S2 demotion + S5 residual board).

This file remains only as a fail-closed pointer so old invocation sites do not
silently regain hard ``import opik`` evaluation authority.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

# No module-level ``import opik`` and no import of sibling legacy scripts
# (I4 / D20 / D24). Offline tests and gated Lane C are the supported surfaces.

__all__ = [
    "CANONICAL_EVAL_COMMANDS",
    "LEGACY_TEST_SUITE_SETUP_RETIRED",
    "main",
    "refuse_legacy_test_suite_setup",
    "run_test_suite",
]

LEGACY_TEST_SUITE_SETUP_RETIRED: Final[bool] = True

CANONICAL_EVAL_COMMANDS: Final[tuple[str, ...]] = (
    "uv run pytest tests/eval/test_lane_c*.py",
    "uv run pytest tests/eval/test_score_runner.py tests/eval/test_family_h.py",
    "# library: git_cg.eval.lane_c.run_lane_c / git_cg.eval.scoring.score_bundle",
)

_REFUSE_MESSAGE: Final[str] = f"""\
ERROR: scripts/setup_opik_test_suites.py is frozen (S5 D24 / S5-G05 / #233).

Reasons:
  * Cloud Opik evaluate() suites are not offline CI / golden / accept-path SoT.
  * Hard top-level Opik import violated product isolation (I4 / D20).
  * Legacy FormatMetric / GEval script metrics are not Hybrid law (S2 demotion).

Canonical path:
  {CANONICAL_EVAL_COMMANDS[0]}
  {CANONICAL_EVAL_COMMANDS[1]}
  {CANONICAL_EVAL_COMMANDS[2]}

Library SoT: src/git_cg/eval/lane_c/** and src/git_cg/eval/scoring/**
Do not import this script from package code, hooks, or CI.
"""


def refuse_legacy_test_suite_setup(*, stream=None) -> int:
    """
    Rejects legacy test-suite setup and emits the retirement notice.
    
    Parameters:
    	stream: Optional output stream for the notice; defaults to standard error.
    
    Returns:
    	int: Exit code 2 indicating that legacy setup is refused.
    """
    out = sys.stderr if stream is None else stream
    print(_REFUSE_MESSAGE, file=out)
    return 2


def run_test_suite(*_args, **_kwargs) -> None:
    """
    Refuse to run the retired legacy test suite.
    
    Raises:
    	SystemExit: Always, with the refusal exit code.
    """
    code = refuse_legacy_test_suite_setup()
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    """
    Parse retained legacy command-line options and refuse execution with guidance to the supported evaluation paths.
    
    Parameters:
        argv (list[str] | None): Command-line arguments to parse, or the process arguments when omitted.
    
    Returns:
        int: Exit code indicating that the retired test-suite setup was refused.
    """
    parser = argparse.ArgumentParser(
        description=("FROZEN: former Opik test-suite runner. Use offline tests/eval and gated Lane C (see #233 D24).")
    )
    parser.add_argument("--dataset", default="git-cg-golden-dataset", help=argparse.SUPPRESS)
    parser.add_argument("--metric", default="git-cg-commit-quality", help=argparse.SUPPRESS)
    parser.parse_args(argv)
    return refuse_legacy_test_suite_setup()


if __name__ == "__main__":
    raise SystemExit(main())
