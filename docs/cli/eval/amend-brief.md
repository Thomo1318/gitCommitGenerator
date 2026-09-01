# git-cg eval amend-brief

> **Usage:** `git-cg eval amend-brief …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Build an amend brief from landed evaluation data.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval amend-brief [OPTIONS] SCORE_RUN_ID

 Build an amend brief from landed evaluation data.

 Advisory summary of score/failure context. Never reruns, accepts, or re-ranks.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *    score_run_id      TEXT  Score-run id (rs_) to build the brief from. [required]                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --session-thread-id                  TEXT                  Optional session id (sess_) to attach to the brief.       │
│ --case                               TEXT                  Scope the brief to a single case id (default: experiment  │
│                                                            aggregate).                                               │
│ --last                               INTEGER RANGE [x>=0]  How many recent dogfood/Lane C attachments to include     │
│                                                            (default 3).                                              │
│                                                            [default: 3]                                              │
│ --doctor                                                   Include a doctor summary section in the brief.            │
│ --write                --no-write                          Write the brief under .eval/amend_briefs/ (default:       │
│                                                            write).                                                   │
│                                                            [default: write]                                          │
│ --root                               DIRECTORY             Repo root (defaults to discovery).                        │
│ --json                                                     Print machine-readable JSON instead of plain text.        │
│ --detail                                                   Show detailed help text and exit.                         │
│ --help                                                     Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
