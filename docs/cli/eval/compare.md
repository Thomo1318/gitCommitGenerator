# git-cg eval compare

> **Usage:** `git-cg eval compare …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Diff two cases (structure and metrics).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval compare [OPTIONS]

 Diff two cases (structure and metrics).

 Local read-only. Does not replay, re-score, or change commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --a-experiment-id        TEXT  Left experiment id (required). [required]                                          │
│ *  --a-case                 TEXT  Left case id (required). [required]                                                │
│ *  --b-experiment-id        TEXT  Right experiment id (required). [required]                                         │
│ *  --b-case                 TEXT  Right case id (required). [required]                                               │
│    --json                         Print machine-readable JSON instead of plain text.                                 │
│    --detail                       Show detailed help text and exit.                                                  │
│    --help                         Show this message and exit.                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
