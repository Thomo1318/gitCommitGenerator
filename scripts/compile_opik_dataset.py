#!/usr/bin/env python
"""Legacy Opik dataset compile scaffold — upload path retired (S4 P2-3 / E6).

Issue #232 / plan §8.9 / D23:

* Direct Opik SDK upload from this script is **retired**.
* Layer-A local labels remain the source of truth for train/gold selection.
* ``user_acceptance`` is **never** a correctness or promotion signal (E6).
* Operators use the S4 library path instead::

      uv run git-cg eval export status
      uv run git-cg eval export drain

  Library home: ``src/git_cg/eval/mirror/**`` (config, R14, queue, transport,
  Q18 train projection via ``git_cg.eval.mirror.train``).

This file remains only as a fail-closed pointer so old invocation sites do not
silently regain hard ``import opik`` or popularity-as-correctness behaviour.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from typing import Any, Final

# No module-level ``import opik`` (I4 / D20). Upload mechanics live in
# ``git_cg.eval.mirror.transport.OpikSdkTransport`` and are reached only via
# the non-blocking export queue drain path.

__all__ = [
    "CANONICAL_EXPORT_COMMANDS",
    "FORBIDDEN_CORRECTNESS_SIGNALS",
    "LEGACY_UPLOAD_RETIRED",
    "compile_dataset",
    "main",
    "refuse_legacy_upload",
    "selection_predicate",
]

LEGACY_UPLOAD_RETIRED: Final[bool] = True

#: Signals that must never gate correctness / golden promotion (E6).
FORBIDDEN_CORRECTNESS_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "user_acceptance",
    }
)

CANONICAL_EXPORT_COMMANDS: Final[tuple[str, ...]] = (
    "uv run git-cg eval export status",
    "uv run git-cg eval export retry",
    "uv run git-cg eval export drain",
)

_REFUSE_MESSAGE: Final[str] = f"""\
ERROR: scripts/compile_opik_dataset.py live upload path is retired (S4 P2-3 / E6).

Reasons:
  * Hard top-level Opik import violated basic offline/product isolation (I4/D20).
  * Filtering on user_acceptance treated popularity as correctness (E6 / FIND-027).
  * Cloud traces must not become Layer-A / CI / golden source of truth (I1).

Canonical path (local Layer-A → R14 → queue → optional drain):
  {CANONICAL_EXPORT_COMMANDS[0]}
  {CANONICAL_EXPORT_COMMANDS[1]}
  {CANONICAL_EXPORT_COMMANDS[2]}

Library SoT: src/git_cg/eval/mirror/**
Train labels: git_cg.eval.mirror.train (Q18 single dataset + label/split metadata).
"""


def selection_predicate(row: Mapping[str, Any]) -> bool:
    """Return whether a **local Layer-A** row may enter a train/gold projection.

    Pure offline helper retained so callers/tests can assert E6 law without
    invoking network or Opik. Selection is label-driven only:

    * closed ``label`` / ``train_label`` of ``positive`` (aliases normalized by
      library consumers), and
    * never ``user_acceptance`` or other popularity feedback scores.

    This predicate does **not** upload, does **not** call Opik, and does **not**
    invent labels from telemetry popularity fields.
    """
    if not isinstance(row, Mapping):
        return False

    # Explicit refuse: any of the forbidden signals used as a row filter key.
    for key in row:
        token = str(key).strip().lower()
        if token in FORBIDDEN_CORRECTNESS_SIGNALS or token.endswith("user_acceptance"):
            return False
        if "user_acceptance" in token:
            return False

    label_raw = row.get("train_label", row.get("label"))
    if label_raw is None:
        return False
    label = str(label_raw).strip().lower().replace("-", "_")
    if not label or label in {"unlabeled", "unknown", "none", "null"}:
        return False
    # Align with git_cg.eval.mirror.train.normalize_train_label positive set.
    return label in {
        "positive",
        "pos",
        "positive_gold",
        "train_positive",
        "preference_chosen",
    }


def refuse_legacy_upload(*, stream=None) -> int:
    """Print the retirement notice and return a non-zero exit code."""
    out = sys.stderr if stream is None else stream
    print(_REFUSE_MESSAGE, file=out)
    return 2


def compile_dataset(
    project_name: str = "gitCommitGenerator",
    dataset_name: str = "git-cg-golden-dataset",
    threshold: float = 0.8,
) -> None:
    """Former upload entrypoint — always refuses (P2-3).

    Parameters are accepted only so historical CLI invocations fail closed with
    a pointer instead of raising ``TypeError``. They are intentionally unused:
    project/dataset/threshold no longer select cloud traces by popularity.
    """
    del project_name, dataset_name, threshold  # retained for CLI back-compat only
    code = refuse_legacy_upload()
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse legacy flags, then refuse with pointer (no network)."""
    parser = argparse.ArgumentParser(
        description=(
            "RETIRED: former Opik dataset uploader. Use `git-cg eval export drain` (see src/git_cg/eval/mirror)."
        )
    )
    parser.add_argument("--project", default="gitCommitGenerator", help=argparse.SUPPRESS)
    parser.add_argument("--dataset", default="git-cg-golden-dataset", help=argparse.SUPPRESS)
    parser.add_argument("--threshold", type=float, default=0.8, help=argparse.SUPPRESS)
    parser.parse_args(argv)
    return refuse_legacy_upload()


if __name__ == "__main__":
    raise SystemExit(main())
