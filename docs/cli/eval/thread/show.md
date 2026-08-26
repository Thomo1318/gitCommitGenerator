# git-cg eval thread show

> **Usage:** `git-cg eval thread show …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Show one local session thread. Read-only: no Opik reach, no chat timeline, no graph browser, no accept authority, no rerun, no ranking mutation.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval thread show [OPTIONS]                                                          
                                                                                
 Show one local session thread.                                                 
                                                                                
 Read-only: no Opik reach, no chat timeline, no graph browser, no accept        
 authority, no rerun, no ranking mutation.                                      
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --id          TEXT       Thread/session id (sess_ or sessmeta_).          │
│                             [required]                                       │
│    --root        DIRECTORY  Repo root (defaults to discovery).               │
│    --json                   Emit cli_output_envelope_v1 on stdout.           │
│    --help                   Show this message and exit.                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
