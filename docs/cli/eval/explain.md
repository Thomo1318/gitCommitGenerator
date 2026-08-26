# git-cg eval explain

> **Usage:** `git-cg eval explain …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Deterministic explain contract (§18.3); no opaque LLM RCA.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval explain [OPTIONS]                                                       
                                                                                
 Deterministic explain contract (§18.3); no opaque LLM RCA.                     
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --experiment-id        TEXT  Experiment id (defaults to latest local run).   │
│ --case                 TEXT  Case id within the experiment.                  │
│ --json                       Emit cli_output_envelope_v1 on stdout.          │
│ --help                       Show this message and exit.                     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
