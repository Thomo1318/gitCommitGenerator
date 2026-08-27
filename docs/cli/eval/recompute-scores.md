# git-cg eval recompute-scores

> **Usage:** `git-cg eval recompute-scores …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Re-score evidence already written by a prior run.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval recompute-scores [OPTIONS]

 Re-score evidence already written by a prior run.

 Does not re-generate cases and does not change how commits are ranked.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --experiment             TEXT       Parent experiment id whose evidence is re-scored (required).                     │
│ --suite                  TEXT       Suite id / metric pack to use (default: cm-eval-fixtures-core).                  │
│                                     [default: cm-eval-fixtures-core]                                                 │
│ --fixture-root           DIRECTORY  Optional alternate fixture directory (for tests/lab layouts).                    │
│ --keep-last              INTEGER    How many recent checkpoints to keep per suite family (default: 10).              │
│                                     [default: 10]                                                                    │
│ --keep-checkpoint                   Keep this recompute checkpoint even when the run succeeds.                       │
│ --gold-mode              TEXT       How tightly to compare against reference answers (default: strict).              │
│                                     [default: strict]                                                                │
│ --json                              Print machine-readable JSON instead of plain text.                               │
│ --detail                            Show detailed help text and exit.                                                │
│ --help                              Show this message and exit.                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
