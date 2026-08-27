# git-cg eval thread show

> **Usage:** `git-cg eval thread show …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Show one local session thread.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval thread show [OPTIONS]

 Show one local session thread.

 Read-only lookup of one local session-thread record. Does not change commit
 ranking or gold.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --id            TEXT       Thread/session id (sess_ or sessmeta_). [required]                                     │
│    --root          DIRECTORY  Repo root (defaults to discovery).                                                     │
│    --json                     Print machine-readable JSON instead of plain text.                                     │
│    --detail                   Show detailed help text and exit.                                                      │
│    --help                     Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
