# git-cg eval export

> **Usage:** `git-cg eval export …`  
> **Kind:** `group` · **Status:** group

Export-queue status, retry, and drain.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export [OPTIONS] COMMAND [ARGS]...

 Export-queue status, retry, and drain.

 Operate the local Opik export queue. Status is offline; drain may upload. Never blocks product accept.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ status  Show export-queue status (read-only, offline).                                                               │
│ retry   Re-queue failed export rows for another drain attempt.                                                       │
│ drain   Drain the export queue through the Opik transport.                                                           │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval export drain`](export/drain.md) — Drain the export queue through the Opik transport.
* [`git-cg eval export retry`](export/retry.md) — Re-queue failed export rows for another drain attempt.
* [`git-cg eval export status`](export/status.md) — Show export-queue status (read-only, offline).

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
