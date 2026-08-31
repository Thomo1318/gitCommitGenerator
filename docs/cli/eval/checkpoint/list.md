# git-cg eval checkpoint list

> **Usage:** `git-cg eval checkpoint list …`  
> **Kind:** `command` · **Status:** canonical S6 surface

List local evaluation checkpoints (read-only).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval checkpoint list [OPTIONS]

 List local evaluation checkpoints (read-only).

 Offline inventory of ``.eval/checkpoints`` for resume/GC planning. Does not
 mutate checkpoint files, contact Opik, or change product ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --suite         TEXT       Optional suite_id filter.                                                                 │
│ --root          DIRECTORY  Repo root (defaults to discovery).                                                        │
│ --json                     Print machine-readable JSON instead of plain text.                                        │
│ --detail                   Show detailed help text and exit.                                                         │
│ --help                     Show this message and exit.                                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
