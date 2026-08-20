#!/usr/bin/env python
"""Legacy Opik GEval rule bootstrap — retired as alternate authority (S5 D24 / S5-G05).

Issue #233 / plan §8.9 / D24:

* This script must **never** be accept-path, CI, package, or golden authority.
* Cloud automation rules are **not** the Lane C-prime / Hybrid / gate SoT.
* Canonical gated judge path lives in the library::

      src/git_cg/eval/lane_c/**          # eligibility, packs, judge_input, runner
      uv run git-cg eval …              # operator surface (export / lab later)

* Residual R2 meta-eval (if ever enabled) is offline/lab only under
  ``judge_meta_eval_v1`` — not this cloud rule installer.

This file remains only as a fail-closed pointer so old invocation sites do not
silently regain hard network rule creation or alternate scoring authority.
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

# No module-level ``import requests`` / Opik SDK (I4 / D20 / D24).
# Live Lane C transport is lazy and gated inside ``git_cg.eval.lane_c``.

__all__ = [
    "CANONICAL_LANE_C_HOMES",
    "LEGACY_RULE_SETUP_RETIRED",
    "main",
    "refuse_legacy_rule_setup",
]

LEGACY_RULE_SETUP_RETIRED: Final[bool] = True

CANONICAL_LANE_C_HOMES: Final[tuple[str, ...]] = (
    "src/git_cg/eval/lane_c/",
    "src/git_cg/eval/scoring/",
    "schemas/eval/prompt_pack_v1.schema.json",
    "schemas/eval/judge_meta_eval_v1.schema.json",
)

_REFUSE_MESSAGE: Final[str] = f"""\
ERROR: scripts/setup_opik_eval_rule.py is frozen (S5 D24 / S5-G05 / #233).

Reasons:
  * Cloud GEval automation rules are not Layer-A / CI / golden / accept-path SoT.
  * Hard network bootstrap violated offline product isolation (I4 / D20).
  * Alternate rule installers must not compete with gated ``run_lane_c``.

Canonical homes:
  * Library runner: {CANONICAL_LANE_C_HOMES[0]}
  * Scoring / Family H honesty: {CANONICAL_LANE_C_HOMES[1]}
  * Prompt pack schema: {CANONICAL_LANE_C_HOMES[2]}
  * R2 meta-eval schema (lab residual): {CANONICAL_LANE_C_HOMES[3]}

Do not import this script from package code, hooks, or CI.
"""


def refuse_legacy_rule_setup(*, stream=None) -> int:
    """
    Print the legacy rule setup refusal message and provide the failure exit code.
    
    Parameters:
    	stream: Optional output stream for the refusal message. Defaults to standard error.
    
    Returns:
    	int: Exit code 2 indicating that legacy rule setup is refused.
    """
    out = sys.stderr if stream is None else stream
    print(_REFUSE_MESSAGE, file=out)
    return 2


def create_geval_rule(*_args, **_kwargs) -> None:
    """
    Reject attempts to create a legacy cloud GEval rule.
    
    Raises:
        SystemExit: Always, with exit code 2.
    """
    code = refuse_legacy_rule_setup()
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    """
    Accept a historical command-line invocation and refuse legacy rule setup.
    
    Parameters:
        argv (list[str] | None): Command-line arguments to parse, or the process arguments when omitted.
    
    Returns:
        int: Exit code indicating that legacy rule setup was refused.
    """
    parser = argparse.ArgumentParser(
        description=(
            "FROZEN: former Opik GEval rule installer. Use gated Lane C in src/git_cg/eval/lane_c/ (see #233 D24)."
        )
    )
    # Accept and ignore historical flags so old wrappers fail closed cleanly.
    parser.add_argument("--project", default="gitCommitGenerator", help=argparse.SUPPRESS)
    parser.parse_args(argv)
    return refuse_legacy_rule_setup()


if __name__ == "__main__":
    raise SystemExit(main())
