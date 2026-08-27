# git-cg eval resume

> **Usage:** `git-cg eval resume …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Continue an unfinished evaluation from a checkpoint.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval resume [OPTIONS]

 Continue an unfinished evaluation from a checkpoint.

 Does not change how commits are ranked. Requires --checkpoint from a prior run.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --checkpoint             TEXT       Checkpoint id from a prior suite run (required).                                 │
│ --fixture-root           DIRECTORY  Optional alternate fixture directory (for tests/lab layouts).                    │
│ --keep-last              INTEGER    How many recent checkpoints to keep per suite family (default: 10).              │
│                                     [default: 10]                                                                    │
│ --keep-checkpoint                   Keep this run's checkpoint even when the run succeeds.                           │
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
