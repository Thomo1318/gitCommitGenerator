# git-cg eval train-export

> **Usage:** `git-cg eval train-export …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Export redacted training rows from landed bundles.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval train-export [OPTIONS]

 Export redacted training rows from landed bundles.

 Builds a local redacted training export. Never emits secrets cleartext.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --bundle-id                       TEXT  Bundle id(s) to export (repeatable). Default: all landed bundles.            │
│ --profile                         TEXT  Redaction profile (default train_rich). Unsafe raw profiles are rejected.    │
│                                         [default: train_rich]                                                        │
│ --capture-on                      TEXT  Which rows to include: pass | fail | all (default all). [default: all]       │
│ --split-group-id                  TEXT  Optional split-group label for the export batch.                             │
│ --notes                           TEXT  Optional free-text notes for the export record.                              │
│ --write             --no-write          Write export files under .eval/train_export/ (default: write).               │
│                                         [default: write]                                                             │
│ --dry-run                               Validate and preview paths without writing (same as --no-write).             │
│ --json                                  Print machine-readable JSON instead of plain text.                           │
│ --detail                                Show detailed help text and exit.                                            │
│ --help                                  Show this message and exit.                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
