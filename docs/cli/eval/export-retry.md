# git-cg eval export-retry

> **Usage:** `git-cg eval export-retry …`  
> **Kind:** `command` · **Status:** deprecated alias → `eval export retry`

Alias of eval export retry.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export-retry [OPTIONS]

 (deprecated)
 Alias of eval export retry.

 Temporary dashed alias. Prefer the nested canonical path.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --root             DIRECTORY  Repo root (defaults to discovery).                                                     │
│ --id               TEXT       Retry a single failed queue id (default: all failed rows).                             │
│ --force                       Also retry validation/auth/size failures.                                              │
│ --max-items        INTEGER    Cap on failed rows re-queued this invocation.                                          │
│ --json                        Print machine-readable JSON instead of plain text.                                     │
│ --detail                      Show detailed help text and exit.                                                      │
│ --help                        Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
