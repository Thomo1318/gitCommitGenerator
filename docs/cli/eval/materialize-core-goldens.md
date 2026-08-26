# git-cg eval materialize-core-goldens

> **Usage:** `git-cg eval materialize-core-goldens …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Materialize checked-in core golden bundles + snapshot (corpus write only).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval materialize-core-goldens [OPTIONS]                                      
                                                                                
 Materialize checked-in core golden bundles + snapshot (corpus write only).     
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --root        DIRECTORY  Fixture root (defaults to tests/fixtures/eval).     │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
