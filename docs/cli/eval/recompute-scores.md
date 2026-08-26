# git-cg eval recompute-scores

> **Usage:** `git-cg eval recompute-scores …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Re-run the metric pack over already-landed evidence bundles.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval recompute-scores [OPTIONS]                                              
                                                                                
 Re-run the metric pack over already-landed evidence bundles.                   
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --experiment             TEXT       Parent experiment id whose evidence is   │
│                                     re-scored (required).                    │
│ --suite                  TEXT       Suite id / metric pack context (default: │
│                                     cm-eval-fixtures-core).                  │
│                                     [default: cm-eval-fixtures-core]         │
│ --fixture-root           DIRECTORY  Optional fixture root override           │
│                                     (tests/lab).                             │
│ --keep-last              INTEGER    Checkpoint retention bound per suite     │
│                                     family (default 10).                     │
│                                     [default: 10]                            │
│ --keep-checkpoint                   Retain this recompute checkpoint even    │
│                                     after success.                           │
│ --gold-mode              TEXT       Gold comparison mode. [default: strict]  │
│ --json                              Emit cli_output_envelope_v1 on stdout.   │
│ --help                              Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
