# git-cg eval diagnose

> **Usage:** `git-cg eval diagnose …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Create or update a diagnostic issue from a failure.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval diagnose [OPTIONS]

 Create or update a diagnostic issue from a failure.

 Builds a local diagnostic issue record. Does not change commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --experiment-id         TEXT  Experiment id (defaults to latest local run).                                          │
│ --case                  TEXT  Case id within the experiment.                                                         │
│ --code                  TEXT  Diagnostic code (defaults to the first failure id).                                    │
│ --title                 TEXT  Optional issue title override.                                                         │
│ --product-impact        TEXT  Impact area: accept_path|golden|train|export|docs|unknown. [default: unknown]          │
│ --owner                 TEXT  Optional issue owner handle.                                                           │
│ --notes                 TEXT  Optional free-text notes for the issue.                                                │
│ --dry-run                     Validate and project the issue without writing files.                                  │
│ --json                        Print machine-readable JSON instead of plain text.                                     │
│ --detail                      Show detailed help text and exit.                                                      │
│ --help                        Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
