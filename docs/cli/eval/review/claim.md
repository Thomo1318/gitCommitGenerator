# git-cg eval review claim

> **Usage:** `git-cg eval review claim …`  
> **Kind:** `command` · **Status:** command

Claim a pending review item (pending → in_review).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review claim [OPTIONS] REVIEW_ID

 Claim a pending review item (pending → in_review).

 Local queue state only. Never writes gold or changes product commit ranking.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    review_id      TEXT  Review id. [required]                                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --reviewer        TEXT  Opaque local reviewer handle. [required]                                                  │
│    --dry-run               Validate without writing.                                                                 │
│    --json                  Print machine-readable JSON instead of plain text.                                        │
│    --detail                Show detailed help text and exit.                                                         │
│    --help                  Show this message and exit.                                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
