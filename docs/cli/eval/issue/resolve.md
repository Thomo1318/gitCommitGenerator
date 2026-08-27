# git-cg eval issue resolve

> **Usage:** `git-cg eval issue resolve …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Mark a local diagnostic issue resolved.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval issue resolve [OPTIONS] ISSUE_ID

 Mark a local diagnostic issue resolved.

 Local issue lifecycle only. Requires fix-verification evidence. Does not
 change commit ranking or gold.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    issue_id      TEXT  Issue id. [required]                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --resolution-evidence        TEXT  Required fix-verification evidence. [required]                                 │
│    --json                             Print machine-readable JSON instead of plain text.                             │
│    --detail                           Show detailed help text and exit.                                              │
│    --help                             Show this message and exit.                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
