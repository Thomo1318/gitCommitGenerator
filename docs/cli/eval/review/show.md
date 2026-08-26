# git-cg eval review show

> **Usage:** `git-cg eval review show …`  
> **Kind:** `command` · **Status:** command

Show one local review-queue item.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review show [OPTIONS] REVIEW_ID                                                
                                                                                
 Show one local review-queue item.                                              
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    review_id      TEXT  Review id. [required]                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --json          Emit cli_output_envelope_v1 on stdout.                       │
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
