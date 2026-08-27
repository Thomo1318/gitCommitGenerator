# git-cg eval session

> **Usage:** `git-cg eval session …`  
> **Kind:** `group` · **Status:** group

Inspect local commit sessions.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval session [OPTIONS] COMMAND [ARGS]...

 Inspect local commit sessions.

 Read-only lookup of a local commit-session record. Does not change commit ranking or gold.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ show  Show one local commit session.                                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval session show`](session/show.md) — Show one local commit session.

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
