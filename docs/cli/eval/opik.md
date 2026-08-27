# git-cg eval opik

> **Usage:** `git-cg eval opik …`  
> **Kind:** `group` · **Status:** group

Opik health checks and secret-safe config.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval opik [OPTIONS] COMMAND [ARGS]...

 Opik health checks and secret-safe config.

 Inspect Opik/export health and resolved config offline. Never prints raw secrets or reaches the network.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ doctor  Check Opik/export health without exposing secrets.                                                           │
│ config  Inspect Opik/mirror config without exposing secrets.                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval opik config`](opik/config.md) — Inspect Opik/mirror config without exposing secrets.
* [`git-cg eval opik doctor`](opik/doctor.md) — Check Opik/export health without exposing secrets.

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
