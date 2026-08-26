# git-cg eval resume

> **Usage:** `git-cg eval resume …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Resume a suite from a checkpoint.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval resume [OPTIONS]                                                        
                                                                                
 Resume a suite from a checkpoint.                                              
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --checkpoint             TEXT       Checkpoint id to resume (required).      │
│ --fixture-root           DIRECTORY  Optional fixture root override           │
│                                     (tests/lab).                             │
│ --keep-last              INTEGER    Checkpoint retention bound per suite     │
│                                     family (default 10).                     │
│                                     [default: 10]                            │
│ --keep-checkpoint                   Retain this run's checkpoint even after  │
│                                     success.                                 │
│ --gold-mode              TEXT       Gold comparison mode. [default: strict]  │
│ --json                              Emit cli_output_envelope_v1 on stdout.   │
│ --help                              Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
