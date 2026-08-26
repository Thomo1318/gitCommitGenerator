# git-cg eval diagnose

> **Usage:** `git-cg eval diagnose …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Upsert diag_issue_v1 with stable fingerprint law (§18.4; idempotent).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval diagnose [OPTIONS]                                                      
                                                                                
 Upsert diag_issue_v1 with stable fingerprint law (§18.4; idempotent).          
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --experiment-id         TEXT  Experiment id (defaults to latest local run).  │
│ --case                  TEXT  Case id within the experiment.                 │
│ --code                  TEXT  Diagnostic code (defaults to first             │
│                               failure_id).                                   │
│ --title                 TEXT  Issue title.                                   │
│ --product-impact        TEXT  accept_path|golden|train|export|docs|unknown.  │
│                               [default: unknown]                             │
│ --owner                 TEXT  Issue owner.                                   │
│ --notes                 TEXT  Free-text notes.                               │
│ --dry-run                     Validate + project issue without writing       │
│                               issues/diagnostics.                            │
│ --json                        Emit cli_output_envelope_v1 on stdout.         │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
