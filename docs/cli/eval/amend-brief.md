# git-cg eval amend-brief

> **Usage:** `git-cg eval amend-brief …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Assemble the v1 amend brief from landed Layer-A data (R11 / §7.2). Advisory authority: summarizes score/failure/regime/family context and preference pairs; never auto-applies reruns, never accepts, never re-ranks.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval amend-brief [OPTIONS] SCORE_RUN_ID                                      
                                                                                
 Assemble the v1 amend brief from landed Layer-A data (R11 / §7.2).             
                                                                                
 Advisory authority: summarizes score/failure/regime/family context and         
 preference pairs; never auto-applies reruns, never accepts, never re-ranks.    
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    score_run_id      TEXT  Case score run id (rs_) to brief against.       │
│                              [required]                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --session-thread-id                  TEXT                Optional session    │
│                                                          twin (sess_) this   │
│                                                          brief belongs to.   │
│ --last                               INTEGER RANGE       Last-N dogfood/Lane │
│                                      [x>=0]              C attachments.      │
│                                                          [default: 3]        │
│ --doctor                                                 Include the doctor  │
│                                                          projection.         │
│ --write                --no-write                        Persist under       │
│                                                          .eval/amend_briefs… │
│                                                          [default: write]    │
│ --root                               DIRECTORY           Repo root (defaults │
│                                                          to discovery).      │
│ --json                                                   Emit                │
│                                                          cli_output_envelop… │
│                                                          on stdout.          │
│ --help                                                   Show this message   │
│                                                          and exit.           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
