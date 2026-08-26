# git-cg eval opik

> **Usage:** `git-cg eval opik …`  
> **Kind:** `group` · **Status:** group

Opik/export health and secret-safe config (canonical).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval opik [OPTIONS] COMMAND [ARGS]...                                        
                                                                                
 Opik/export health and secret-safe config (canonical).                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ doctor  Secret-safe Opik/export health doctor.                               │
│ config  Secret-safe Opik/mirror config inspection.                           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval opik config`](opik/config.md) — Secret-safe Opik/mirror config inspection.
* [`git-cg eval opik doctor`](opik/doctor.md) — Secret-safe Opik/export health doctor. Inspects resolved config / export health / queue without transport or network. All secret-bearing out

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
