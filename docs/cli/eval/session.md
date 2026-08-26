# git-cg eval session

> **Usage:** `git-cg eval session …`  
> **Kind:** `group` · **Status:** group

Local commit-session inspection.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval session [OPTIONS] COMMAND [ARGS]...                                     
                                                                                
 Local commit-session inspection.                                               
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ show  Read a local session twin under .eval/sessions/ (§7.6).                │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval session show`](session/show.md) — Read a local session twin under .eval/sessions/ (§7.6). Read-only: no Opik reach, no chat timeline, no graph browser, no accept authority, n

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
