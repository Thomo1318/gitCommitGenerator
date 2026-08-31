# git-cg eval checkpoint

> **Usage:** `git-cg eval checkpoint …`  
> **Kind:** `group` · **Status:** group

Local evaluation checkpoint inventory (read-only).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval checkpoint [OPTIONS] COMMAND [ARGS]...

 Local evaluation checkpoint inventory (read-only).

 Inspect stored evaluation checkpoints under .eval/checkpoints/.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ list  List local evaluation checkpoints (read-only).                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval checkpoint list`](checkpoint/list.md) — List local evaluation checkpoints (read-only).

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
