# git-cg eval opik verify

> **Usage:** `git-cg eval opik verify …`  
> **Kind:** `command` · **Status:** optional / advisory

Optional online Opik project/FD verification (advisory).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.
* Advisory only (`authority=advisory_non_sot`).
* Does not change `eval opik doctor` exit codes or green rollup.
* Does not feed promote, gates, CI merge, or product accept.
* Network and auth failure are warning-only (exit 0).
* Project creation requires `--remote --create-missing`.
* Local project pins and `config/feedback_definitions.json` remain vocabulary/source of truth.

## Help

```text
Usage: git-cg eval opik verify [OPTIONS]

 Optional online Opik project/FD verification (advisory).

 Disabled by default. Never a CI/product-accept gate. Network failure is
 warning-only. Doctor remains the offline authority surface.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --remote                  Enable online verification (default: offline skip).                                        │
│ --create-missing          Also attempt to create missing remote projects (requires --remote).                        │
│ --json                    Print machine-readable JSON instead of plain text.                                         │
│ --detail                  Show detailed help text and exit.                                                          │
│ --help                    Show this message and exit.                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
