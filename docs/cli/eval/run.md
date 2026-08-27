# git-cg eval run

> **Usage:** `git-cg eval run …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Run a local offline evaluation suite.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval run [OPTIONS]

 Run a local offline evaluation suite.

 Does not change how commits are ranked. Default mode starts a fresh suite run.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --suite                          TEXT       Which fixture suite to run (default: cm-eval-fixtures-core).             │
│                                             [default: cm-eval-fixtures-core]                                         │
│ --fixture-root                   DIRECTORY  Optional alternate fixture directory (for tests/lab layouts).            │
│ --mode                           TEXT       How to run: fresh_suite_run (default), resume_missing, recompute_scores, │
│                                             replay_generation, or export_only.                                       │
│                                             [default: fresh_suite_run]                                               │
│ --keep-last                      INTEGER    How many recent checkpoints to keep per suite family (default: 10).      │
│                                             [default: 10]                                                            │
│ --keep-checkpoint                           Keep this run's checkpoint even when the run succeeds.                   │
│ --gold-mode                      TEXT       How tightly to compare against reference answers (default: strict).      │
│                                             [default: strict]                                                        │
│ --case                           TEXT       Limit to specific case ids (comma-separated). Lab/triage only, not CI    │
│                                             golden.                                                                  │
│ --experiment                     TEXT       Existing experiment id (required for export_only; optional parent for    │
│                                             recompute_scores).                                                       │
│ --checkpoint                     TEXT       Checkpoint id to continue (used with --mode resume_missing).             │
│ --allow-replay-generation                   Allow replay_generation mode (blocked unless you set this).              │
│ --json                                      Print machine-readable JSON instead of plain text.                       │
│ --detail                                    Show detailed help text and exit.                                        │
│ --help                                      Show this message and exit.                                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
