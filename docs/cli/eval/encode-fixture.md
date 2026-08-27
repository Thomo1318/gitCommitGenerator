# git-cg eval encode-fixture

> **Usage:** `git-cg eval encode-fixture …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Print stable identity hashes for one evaluation fixture.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval encode-fixture [OPTIONS]

 Print stable identity hashes for one evaluation fixture.

 Local disk only. Does not run evaluations or change commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --path          FILE  Path to one fixture JSON file.                                                                 │
│ --id            TEXT  Fixture case id to load from a suite (use instead of --path).                                  │
│ --suite         TEXT  Suite to search when using --id (default: cm-eval-fixtures-core).                              │
│ --detail              Show detailed help text and exit.                                                              │
│ --help                Show this message and exit.                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
