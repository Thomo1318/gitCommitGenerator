# git-cg eval dogfood

> **Usage:** `git-cg eval dogfood …`  
> **Kind:** `command` · **Status:** dark-launch (hidden from regular help), canonical S6 surface

Fire the Lane C dogfood shadow sidecar (§7.3). Dark-launched maintainer/operator surface: registered and callable as ``git-cg eval dogfood``, but hidden from regular ``git-cg eval --help`` so basic users do not see it in the default command menu. Lane C is advisory only: it never blocks the product commit path, never mutates intent/ranking, and async mode never awaits the judge outcome.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval dogfood [OPTIONS]                                                       
                                                                                
 Fire the Lane C dogfood shadow sidecar (§7.3).                                 
                                                                                
 Dark-launched maintainer/operator surface: registered and callable as          
 ``git-cg eval dogfood``, but hidden from regular ``git-cg eval --help`` so     
 basic users do not see it in the default command menu.                         
                                                                                
 Lane C is advisory only: it never blocks the product commit path, never        
 mutates intent/ranking, and async mode never awaits the judge outcome.         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --commit-message                   TEXT               Candidate commit    │
│                                                          message.            │
│                                                          [required]          │
│    --mode                             TEXT               off|sample|always|… │
│                                                          [default: async]    │
│    --profile                          TEXT               Redaction profile.  │
│                                                          [default:           │
│                                                          default_scrub]      │
│    --population                       TEXT               Deterministic       │
│                                                          sample population   │
│                                                          (repeatable).       │
│    --seed                             TEXT               Explicit sample     │
│                                                          seed.               │
│    --sample-rate                      FLOAT RANGE        [default: 0.1]      │
│                                       [0.0<=x<=1.0]                          │
│    --capture-on                       TEXT               pass|fail|all.      │
│                                                          [default: all]      │
│    --payload                          PATH               Optional JSON       │
│                                                          payload for the     │
│                                                          Lane C judge        │
│                                                          (exists-check).     │
│    --session-thread…                  TEXT                                   │
│    --trigger                          TEXT               cli|pre_commit|pos… │
│                                                          [default: cli]      │
│    --write              --no-write                       [default: write]    │
│    --json                                                Emit                │
│                                                          cli_output_envelop… │
│                                                          on stdout.          │
│    --help                                                Show this message   │
│                                                          and exit.           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
