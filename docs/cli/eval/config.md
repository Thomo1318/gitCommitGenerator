# git-cg eval config

> **Usage:** `git-cg eval config …`  
> **Kind:** `command` · **Status:** deprecated alias → `eval opik config show`

Alias of eval opik config show.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval config [OPTIONS] ACTION

 (deprecated)
 Alias of eval opik config show.

 Temporary compatibility shim. Prefer the nested canonical path.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    action      TEXT  Only 'show' is supported on this temporary alias. [required]                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --json            Print machine-readable JSON instead of plain text.                                                 │
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
