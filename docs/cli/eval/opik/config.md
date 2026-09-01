# git-cg eval opik config

> **Usage:** `git-cg eval opik config …`  
> **Kind:** `group` · **Status:** group

Inspect Opik/mirror config without exposing secrets.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval opik config [OPTIONS] COMMAND [ARGS]...

 Inspect Opik/mirror config without exposing secrets.

 Show the resolved public Opik/mirror view. Never prints raw API keys.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ show  Show resolved Opik/mirror config without secrets.                                                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval opik config show`](config/show.md) — Show resolved Opik/mirror config without secrets.

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
