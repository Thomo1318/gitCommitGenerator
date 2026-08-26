# git-cg eval review rollup

> **Usage:** `git-cg eval review rollup …`  
> **Kind:** `command` · **Status:** command

Roll up multi-rater advisory scores for review items. Read-only dimension/outcome majority + craft spread. Authority stays advisory; never sole-promotes gold.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review rollup [OPTIONS]                                                        
                                                                                
 Roll up multi-rater advisory scores for review items.                          
                                                                                
 Read-only dimension/outcome majority + craft spread. Authority stays           
 advisory; never sole-promotes gold.                                            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --case             TEXT  Optional case_id filter.                            │
│ --bundle-id        TEXT  Optional bundle_id filter.                          │
│ --json                   Emit cli_output_envelope_v1 on stdout.              │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
