# git-cg eval gc

> **Usage:** `git-cg eval gc …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Purge stale acceptpath debris; authoritative bundles need --force.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.
* Offline acceptpath retention only (`--acceptpath` and `--older-than`).
* Bind never auto-evicts; this command is the operator retention path.
* Normal mode deletes stale non-authoritative debris only.
* Authoritative `sess_<32-hex>.json` names need `--force`.
* `.bind.lock` and legacy `sess_*.json` names are unmanaged even with `--force`.
* Stale-lock reclamation belongs to the binder. A leftover `.bind.lock` remains until a later bind reclaims it; GC will not delete it.
* `--dry-run` selects without deleting. Age is file mtime.
* Repository-resolution failures (`EVAL_REPO_UNRESOLVABLE`, exit 1) are distinct from store-integrity failures (`EVAL_STORE_INTEGRITY`, exit 4).
* Unexpected GC failures stay `EVAL_INTERNAL` (exit 4) with a JSON/human envelope and no traceback.

## Help

```text
Usage: git-cg eval gc [OPTIONS]

 Purge stale acceptpath debris.

 Offline retention for ``.eval/bundles/acceptpath/``. Bind never
 auto-evicts; this command is the operator retention path. Does not
 change product ranking, contact Opik, or import the binder at CLI
 module load.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --acceptpath                   Operate on .eval/bundles/acceptpath/ (required; only supported scope).                │
│ --older-than        TEXT       Required positive duration with s/m/h/d suffix (for example 7d, 2h, 15m, 30s).        │
│ --force                        Allow deletion of authoritative acceptpath bundles required for reuse identity.       │
│ --dry-run                      Select matching files without deleting them.                                          │
│ --root              DIRECTORY  Repo root (defaults to discovery).                                                    │
│ --json                         Print machine-readable JSON instead of plain text.                                    │
│ --detail                       Show detailed help text and exit.                                                     │
│ --help                         Show this message and exit.                                                           │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
