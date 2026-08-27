# git-cg eval export-drain

> **Usage:** `git-cg eval export-drain …`  
> **Kind:** `command` · **Status:** deprecated alias → `eval export drain`

Alias of eval export drain.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export-drain [OPTIONS]

 (deprecated)
 Alias of eval export drain.

 Temporary dashed alias. Prefer the nested canonical path.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --root             DIRECTORY  Repo root (defaults to discovery).                                                     │
│ --max-items        INTEGER    Cap on rows processed this drain.                                                      │
│ --dry-run                     Resolve config + list pending rows; no upload.                                         │
│ --json                        Print machine-readable JSON instead of plain text.                                     │
│ --detail                      Show detailed help text and exit.                                                      │
│ --help                        Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
