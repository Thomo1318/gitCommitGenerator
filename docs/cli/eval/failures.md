# git-cg eval failures

> **Usage:** `git-cg eval failures …`  
> **Kind:** `command` · **Status:** canonical S6 surface

List failing cases with metric and failure ids.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval failures [OPTIONS]

 List failing cases with metric and failure ids.

 Local read-only. Does not re-score, promote gold, or change commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --experiment-id        TEXT  Experiment id (defaults to latest local run).                                           │
│ --regime               TEXT  Keep cases matching this regime label (e.g. A|B).                                       │
│ --family               TEXT  Keep cases matching this score family (e.g. I|H|gate).                                  │
│ --failure-id           TEXT  Keep cases that include this failure id.                                                │
│ --severity             TEXT  Keep cases matching this severity (block|warn|info).                                    │
│ --json                       Print machine-readable JSON instead of plain text.                                      │
│ --detail                     Show detailed help text and exit.                                                       │
│ --help                       Show this message and exit.                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
