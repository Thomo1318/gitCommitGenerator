# git-cg eval review rollup

> **Usage:** `git-cg eval review rollup …`  
> **Kind:** `command` · **Status:** command

Roll up multi-rater advisory scores for review items.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review rollup [OPTIONS]

 Roll up multi-rater advisory scores for review items.

 Read-only. Authority stays advisory and never sole-promotes gold.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --case             TEXT  Optional case_id filter.                                                                    │
│ --bundle-id        TEXT  Optional bundle_id filter.                                                                  │
│ --json                   Print machine-readable JSON instead of plain text.                                          │
│ --detail                 Show detailed help text and exit.                                                           │
│ --help                   Show this message and exit.                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
