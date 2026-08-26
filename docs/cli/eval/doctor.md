# git-cg eval doctor

> **Usage:** `git-cg eval doctor …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Check local suite health (pins, metrics, fixtures). Offline, network-free. Fail-closed on floating ``latest`` pins and missing catalog/schema hashes. ``h.doctor_green`` aggregates block-severity checks only; warn-severity failures never flip green to red. Emits phantom-metric producers ``h.compat_hash_resume`` / ``h.doctor_green`` / ``h.export_config_resolved`` as ScoreResultV1 rows.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval doctor [OPTIONS]                                                        
                                                                                
 Check local suite health (pins, metrics, fixtures).                            
                                                                                
 Offline, network-free. Fail-closed on floating ``latest`` pins and missing     
 catalog/schema hashes. ``h.doctor_green`` aggregates block-severity checks     
 only; warn-severity failures never flip green to red. Emits phantom-metric     
 producers ``h.compat_hash_resume`` / ``h.doctor_green`` /                      
 ``h.export_config_resolved`` as ScoreResultV1 rows.                            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --suite               TEXT       Suite id to doctor (default:                │
│                                  cm-eval-fixtures-core).                     │
│                                  [default: cm-eval-fixtures-core]            │
│ --fixture-root        DIRECTORY  Optional fixture root override (tests/lab). │
│ --json                           Emit cli_output_envelope_v1 on stdout.      │
│ --help                           Show this message and exit.                 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
