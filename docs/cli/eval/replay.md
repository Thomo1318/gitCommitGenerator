# git-cg eval replay

> **Usage:** `git-cg eval replay …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Replay generation into a new bundle + replay_compare_v1 (never mutates source).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval replay [OPTIONS]                                                        
                                                                                
 Replay generation into a new bundle + replay_compare_v1 (never mutates         
 source).                                                                       
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --bundle               TEXT  Source ape_bundle_v1 path or accept-path        │
│                              session_thread_id/stem.                         │
│ --experiment-id        TEXT  Experiment id (with --case) for explain-linked  │
│                              replay.                                         │
│ --case                 TEXT  Case id within the experiment.                  │
│ --notes                TEXT  Optional notes on the compare record.           │
│ --dry-run                    Validate and project without writing.           │
│ --json                       Emit cli_output_envelope_v1 on stdout.          │
│ --help                       Show this message and exit.                     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
