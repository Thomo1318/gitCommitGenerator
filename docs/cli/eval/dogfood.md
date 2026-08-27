# git-cg eval dogfood

> **Usage:** `git-cg eval dogfood …`  
> **Kind:** `command` · **Status:** dark-launch (hidden from regular help), canonical S6 surface

Capture Lane C dogfood evidence for a candidate commit message.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval dogfood [OPTIONS]

 Capture Lane C dogfood evidence for a candidate commit message.

 Dark-launched maintainer surface. Callable, but hidden from regular eval --help.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --commit-message                     TEXT                       Candidate commit message to capture evidence for. │
│                                                                    [required]                                        │
│    --mode                               TEXT                       Capture mode: off | sample | always | async       │
│                                                                    (default async).                                  │
│                                                                    [default: async]                                  │
│    --profile                            TEXT                       Redaction profile (default default_scrub).        │
│                                                                    [default: default_scrub]                          │
│    --population                         TEXT                       Deterministic sample population id(s)             │
│                                                                    (repeatable; for mode=sample).                    │
│    --seed                               TEXT                       Explicit sample seed (for mode=sample).           │
│    --sample-rate                        FLOAT RANGE [0.0<=x<=1.0]  Sample rate 0.0-1.0 (default 0.1; for             │
│                                                                    mode=sample).                                     │
│                                                                    [default: 0.1]                                    │
│    --capture-on                         TEXT                       Which rows are eligible: pass | fail | all        │
│                                                                    (default all).                                    │
│                                                                    [default: all]                                    │
│    --payload                            PATH                       Optional existing JSON payload path for the Lane  │
│                                                                    C judge.                                          │
│    --session-thread-id                  TEXT                       Optional local session-thread id to attach        │
│                                                                    evidence to.                                      │
│    --trigger                            TEXT                       How this capture was started: cli | pre_commit |  │
│                                                                    post_commit | hook.                               │
│                                                                    [default: cli]                                    │
│    --write                --no-write                               Write dogfood attachment files (default: write).  │
│                                                                    [default: write]                                  │
│    --json                                                          Print machine-readable JSON instead of plain      │
│                                                                    text.                                             │
│    --detail                                                        Show detailed help text and exit.                 │
│    --help                                                          Show this message and exit.                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
