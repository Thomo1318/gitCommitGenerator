# git-cg eval materialize-core-goldens

> **Usage:** `git-cg eval materialize-core-goldens …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Rebuild checked-in evaluation reference files used by tests.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval materialize-core-goldens [OPTIONS]

 Rebuild the checked-in evaluation reference files used by tests.

 Local disk only. Does not run evaluations or change commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --root          DIRECTORY  Directory to write into (default: tests/fixtures/eval).                                   │
│ --detail                   Show detailed help text and exit.                                                         │
│ --help                     Show this message and exit.                                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
