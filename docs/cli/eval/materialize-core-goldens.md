# git-cg eval materialize-core-goldens

> **Usage:** `git-cg eval materialize-core-goldens …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Rebuild the checked-in evaluation reference files used by tests. Writes the main reference bundles and snapshot into the fixture directory (default: tests/fixtures/eval). If optional archive fixtures exist there, those are rebuilt too. Local disk only — does not run evaluations and does not change how commits are ranked. Use after you change eval fixtures and need the checked-in reference outputs refreshed. Prints the paths written and how many bundles were produced.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval materialize-core-goldens [OPTIONS]                                      
                                                                                
 Rebuild the checked-in evaluation reference files used by tests.               
                                                                                
 Writes the main reference bundles and snapshot into the fixture directory      
 (default: tests/fixtures/eval). If optional archive fixtures exist there,      
 those are rebuilt too. Local disk only — does not run evaluations and does     
 not change how commits are ranked.                                             
                                                                                
 Use after you change eval fixtures and need the checked-in reference outputs   
 refreshed. Prints the paths written and how many bundles were produced.        
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --root        DIRECTORY  Directory to write into (default:                   │
│                          tests/fixtures/eval).                               │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
