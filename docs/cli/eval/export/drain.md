# git-cg eval export drain

> **Usage:** `git-cg eval export drain …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Drain the export queue through the Opik transport (F4 fail-open). Always exits 0 unless the config is invalid (fail-closed). Transport and secret failures are classified and recorded on the queue rows; they never produce a non-zero exit that could block a hook.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval export drain [OPTIONS]                                                         
                                                                                
 Drain the export queue through the Opik transport (F4 fail-open).              
                                                                                
 Always exits 0 unless the config is invalid (fail-closed). Transport and       
 secret failures are classified and recorded on the queue rows; they never      
 produce a non-zero exit that could block a hook.                               
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --root             DIRECTORY  Repo root (defaults to discovery).             │
│ --max-items        INTEGER    Cap on rows processed this drain.              │
│ --dry-run                     Resolve config + list pending rows; no upload. │
│ --json                        Emit cli_output_envelope_v1 on stdout.         │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
