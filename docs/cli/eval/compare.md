# git-cg eval compare

> **Usage:** `git-cg eval compare …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Structural + metric delta; uses replay_compare lineage when linked (§18.3).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval compare [OPTIONS]                                                       
                                                                                
 Structural + metric delta; uses replay_compare lineage when linked (§18.3).    
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --a-experiment-id        TEXT  Left experiment id. [required]             │
│ *  --a-case                 TEXT  Left case id. [required]                   │
│ *  --b-experiment-id        TEXT  Right experiment id. [required]            │
│ *  --b-case                 TEXT  Right case id. [required]                  │
│    --json                         Emit cli_output_envelope_v1 on stdout.     │
│    --help                         Show this message and exit.                │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
