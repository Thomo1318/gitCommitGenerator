# git-cg eval export

> **Usage:** `git-cg eval export …`  
> **Kind:** `group` · **Status:** group

Layer-A export queue ops: status / retry / drain (F4 fail-open).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export [OPTIONS] COMMAND [ARGS]...                                      
                                                                                
 Layer-A export queue ops: status / retry / drain (F4 fail-open).               
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ status  Show the Layer-A export queue status (read-only, offline).           │
│ retry   Re-queue failed export rows for another drain attempt (P1-4 /        │
│         P1-11).                                                              │
│ drain   Drain the export queue through the Opik transport (F4 fail-open).    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval export drain`](export/drain.md) — Drain the export queue through the Opik transport (F4 fail-open). Always exits 0 unless the config is invalid (fail-closed). Transport and s
* [`git-cg eval export retry`](export/retry.md) — Re-queue failed export rows for another drain attempt (P1-4 / P1-11). Default policy: reclaim rows whose last_error_class is retryable (``ex
* [`git-cg eval export status`](export/status.md) — Show the Layer-A export queue status (read-only, offline). Never mutates the queue and never contacts Opik or the network.

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
