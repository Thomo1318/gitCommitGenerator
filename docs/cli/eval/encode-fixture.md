# git-cg eval encode-fixture

> **Usage:** `git-cg eval encode-fixture …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Encode a fixture into ``ape_bundle_v1`` and print its identity summary. Requires exactly one of ``--path`` or ``--id``; exits non-zero on invalid options, missing fixtures, or encode failures.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval encode-fixture [OPTIONS]                                                
                                                                                
 Encode a fixture into ``ape_bundle_v1`` and print its identity summary.        
                                                                                
 Requires exactly one of ``--path`` or ``--id``; exits non-zero                 
 on invalid options, missing fixtures, or encode failures.                      
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --path         FILE  Path to a fixture JSON file (canonical encode form).    │
│ --id           TEXT  Optional case_id resolver against known suite/fixture   │
│                      roots.                                                  │
│ --suite        TEXT  Suite id to resolve --id against (default:              │
│                      cm-eval-fixtures-core).                                 │
│ --help               Show this message and exit.                             │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
