# git-cg eval doctor

> **Usage:** `git-cg eval doctor …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Check local suite health (pins, metrics, fixtures).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval doctor [OPTIONS]

 Check local suite health (pins, metrics, fixtures).

 Offline and network-free. Does not run evaluations or change commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --suite               TEXT       Suite id to check (default: cm-eval-fixtures-core).                                 │
│                                  [default: cm-eval-fixtures-core]                                                    │
│ --fixture-root        DIRECTORY  Optional alternate fixture directory (for tests/lab layouts).                       │
│ --json                           Print machine-readable JSON instead of plain text.                                  │
│ --detail                         Show detailed help text and exit.                                                   │
│ --help                           Show this message and exit.                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
