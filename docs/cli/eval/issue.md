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

 List, inspect, and transition local diagnostic issues created from eval failures. Does not change commit ranking or
 gold.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ list      List local diagnostic issues.                                                                              │
│ show      Show one local diagnostic issue.                                                                           │
│ resolve   Mark a local diagnostic issue resolved.                                                                    │
│ reopen    Reopen a local diagnostic issue.                                                                           │
│ suppress  Suppress a local diagnostic issue.                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval issue list`](issue/list.md) — List local diagnostic issues.
* [`git-cg eval issue reopen`](issue/reopen.md) — Reopen a local diagnostic issue.
* [`git-cg eval issue resolve`](issue/resolve.md) — Mark a local diagnostic issue resolved.
* [`git-cg eval issue show`](issue/show.md) — Show one local diagnostic issue.
* [`git-cg eval issue suppress`](issue/suppress.md) — Suppress a local diagnostic issue.

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
