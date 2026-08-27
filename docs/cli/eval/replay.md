# git-cg eval replay

> **Usage:** `git-cg eval replay …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Replay generation into a new bundle (source unchanged).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval replay [OPTIONS]

 Replay generation into a new bundle (source unchanged).

 Offline structural replay. Writes a new bundle + compare; never mutates the source.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --bundle               TEXT  Source bundle path or accept-path id/stem.                                              │
│ --experiment-id        TEXT  Experiment id (use with --case for explain-linked replay).                              │
│ --case                 TEXT  Case id within the experiment.                                                          │
│ --notes                TEXT  Optional notes stored on the compare record.                                            │
│ --dry-run                    Validate and project paths without writing files.                                       │
│ --json                       Print machine-readable JSON instead of plain text.                                      │
│ --detail                     Show detailed help text and exit.                                                       │
│ --help                       Show this message and exit.                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
