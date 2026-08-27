# git-cg eval review dismiss

> **Usage:** `git-cg eval review dismiss …`  
> **Kind:** `command` · **Status:** command

Dismiss a pending/in_review item (terminal).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review dismiss [OPTIONS] REVIEW_ID

 Dismiss a pending/in_review item (terminal).

 Closes without promotion. Never writes gold or changes product commit ranking.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    review_id      TEXT  Review id. [required]                                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --reason             TEXT  Required dismissal reason. [required]                                                  │
│    --adjudicator        TEXT  Opaque adjudicator handle.                                                             │
│    --dry-run                  Validate without writing.                                                              │
│    --json                     Print machine-readable JSON instead of plain text.                                     │
│    --detail                   Show detailed help text and exit.                                                      │
│    --help                     Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
