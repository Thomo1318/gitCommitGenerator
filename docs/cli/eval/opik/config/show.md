# git-cg eval opik config show

> **Usage:** `git-cg eval opik config show …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Show resolved Opik/mirror config without secrets.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval opik config show [OPTIONS]

 Show resolved Opik/mirror config without secrets.

 Offline and secret-safe. Never prints raw API keys or reaches the network.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --json            Print machine-readable JSON instead of plain text.                                                 │
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../../index.md)
* [Operator API map](../../../../eval/operator_api_map.md)
* [Eval operator guide](../../../../eval/README.md)
