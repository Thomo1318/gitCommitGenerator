# git-cg eval export status

> **Usage:** `git-cg eval export status …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Show the Layer-A export queue status (read-only, offline). Never mutates the queue and never contacts Opik or the network.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export status [OPTIONS]                                                        
                                                                                
 Show the Layer-A export queue status (read-only, offline).                     
                                                                                
 Never mutates the queue and never contacts Opik or the network.                
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --root        DIRECTORY  Repo root (defaults to discovery).                  │
│ --json                   Emit cli_output_envelope_v1 on stdout.              │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
