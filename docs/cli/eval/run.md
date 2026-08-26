# git-cg eval run

> **Usage:** `git-cg eval run …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Run an offline evaluation suite (canonical; not ``eval suite run``).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval run [OPTIONS]                                                           
                                                                                
 Run an offline evaluation suite (canonical; not ``eval suite run``).           
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --suite                          TEXT       Suite id to run (default:        │
│                                             cm-eval-fixtures-core).          │
│                                             [default: cm-eval-fixtures-core] │
│ --fixture-root                   DIRECTORY  Optional fixture root override   │
│                                             (tests/lab).                     │
│ --mode                           TEXT       Run mode: fresh_suite_run |      │
│                                             resume_missing |                 │
│                                             recompute_scores |               │
│                                             replay_generation | export_only. │
│                                             [default: fresh_suite_run]       │
│ --keep-last                      INTEGER    Checkpoint retention bound per   │
│                                             suite family (default 10).       │
│                                             [default: 10]                    │
│ --keep-checkpoint                           Retain this run's checkpoint     │
│                                             even after success.              │
│ --gold-mode                      TEXT       Gold comparison mode.            │
│                                             [default: strict]                │
│ --case                           TEXT       Optional comma-separated case id │
│                                             filter (triage/lab only; not CI  │
│                                             golden).                         │
│ --experiment                     TEXT       Required for export_only /       │
│                                             optional parent for recompute    │
│                                             via run --mode.                  │
│ --checkpoint                     TEXT       Checkpoint id when --mode        │
│                                             resume_missing.                  │
│ --allow-replay-generation                   Explicit gate for                │
│                                             replay_generation (refused by    │
│                                             default).                        │
│ --json                                      Emit cli_output_envelope_v1 on   │
│                                             stdout.                          │
│ --help                                      Show this message and exit.      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
