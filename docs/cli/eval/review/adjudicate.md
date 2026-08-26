# git-cg eval review adjudicate

> **Usage:** `git-cg eval review adjudicate …`  
> **Kind:** `command` · **Status:** command

Adjudicate an in_review item (emits typed outcome_ref; never writes gold).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review adjudicate [OPTIONS] REVIEW_ID                                          
                                                                                
 Adjudicate an in_review item (emits typed outcome_ref; never writes gold).     
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    review_id      TEXT  Review id. [required]                              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --outcome                 TEXT  Typed outcome:                            │
│                                    approve_promote|reject|needs_work|dismis… │
│                                    [required]                                │
│    --adjudicator             TEXT  Opaque adjudicator handle.                │
│    --destination-hint        TEXT  Optional promote destination hint         │
│                                    (advisory).                               │
│    --notes                   TEXT  Free-text notes.                          │
│    --dry-run                       Validate without writing.                 │
│    --json                          Emit cli_output_envelope_v1 on stdout.    │
│    --help                          Show this message and exit.               │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
