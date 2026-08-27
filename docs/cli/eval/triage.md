# git-cg eval triage

> **Usage:** `git-cg eval triage …`  
> **Kind:** `command` · **Status:** canonical S6 surface

One-shot advisory view: doctor + failures + explain.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval triage [OPTIONS]

 One-shot advisory view: doctor + failures + explain.

 Advisory only. Does not promote gold, rank intents, or change score law.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --suite                TEXT       Suite id for the doctor section (default: cm-eval-fixtures-core).                  │
│                                   [default: cm-eval-fixtures-core]                                                   │
│ --fixture-root         DIRECTORY  Optional alternate fixture directory for the doctor section.                       │
│ --experiment-id        TEXT       Experiment id for failures/explain (defaults to latest local run).                 │
│ --case                 TEXT       Case id for explain (auto-picks when exactly one failing case).                    │
│ --skip-doctor                     Skip the doctor health section.                                                    │
│ --skip-failures                   Skip the failing-cases section.                                                    │
│ --skip-explain                    Skip the explain/blame section.                                                    │
│ --json                            Print machine-readable JSON instead of plain text.                                 │
│ --detail                          Show detailed help text and exit.                                                  │
│ --help                            Show this message and exit.                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
