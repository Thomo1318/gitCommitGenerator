# git-cg eval issue

> **Usage:** `git-cg eval issue …`  
> **Kind:** `group` · **Status:** group

Manage local diagnostic issues.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval issue [OPTIONS] COMMAND [ARGS]...                                       
                                                                                
 Manage local diagnostic issues.                                                
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ list      List local diagnostic issues (newest last_seen first).             │
│ show      Show one local diagnostic issue.                                   │
│ resolve   Mark a local diagnostic issue resolved (requires                   │
│           --resolution-evidence).                                            │
│ reopen    Reopen a previously resolved/suppressed local diagnostic issue.    │
│ suppress  Suppress a local diagnostic issue (requires --reason).             │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval issue list`](issue/list.md) — List local diagnostic issues (newest last_seen first).
* [`git-cg eval issue reopen`](issue/reopen.md) — Reopen a previously resolved/suppressed local diagnostic issue.
* [`git-cg eval issue resolve`](issue/resolve.md) — Mark a local diagnostic issue resolved (requires --resolution-evidence).
* [`git-cg eval issue show`](issue/show.md) — Show one local diagnostic issue.
* [`git-cg eval issue suppress`](issue/suppress.md) — Suppress a local diagnostic issue (requires --reason).

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
