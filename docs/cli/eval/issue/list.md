# git-cg eval issue list

> **Usage:** `git-cg eval issue list …`  
> **Kind:** `command` · **Status:** canonical S6 surface

List local diagnostic issues (newest last_seen first).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval issue list [OPTIONS]                                                          
                                                                                
 List local diagnostic issues (newest last_seen first).                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --status        TEXT  Filter by status                                       │
│                       (open|acknowledged|resolved|suppressed|reopened).      │
│ --json                Emit cli_output_envelope_v1 on stdout.                 │
│ --help                Show this message and exit.                            │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
