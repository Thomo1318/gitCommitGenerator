# git-cg eval config

> **Usage:** `git-cg eval config …`  
> **Kind:** `command` · **Status:** deprecated alias → `eval opik config show`

Deprecated alias for ``eval opik config show`` (temporary bridge). Removal target: first minor release after S6 GA.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval config [OPTIONS] ACTION                                                 
                                                                                
 Deprecated alias for ``eval opik config show`` (temporary bridge).             
                                                                                
 Removal target: first minor release after S6 GA.                               
                                                                                
╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    action      TEXT  Subcommand: show [required]                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --json          Emit cli_output_envelope_v1 on stdout.                       │
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
