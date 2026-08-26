# git-cg eval review list

> **Usage:** `git-cg eval review list …`  
> **Kind:** `command` · **Status:** command

List local review-queue items.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review list [OPTIONS]                                                          
                                                                                
 List local review-queue items.                                                 
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --status        TEXT  Filter: pending|in_review|adjudicated|dismissed.       │
│ --json                Emit cli_output_envelope_v1 on stdout.                 │
│ --help                Show this message and exit.                            │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
