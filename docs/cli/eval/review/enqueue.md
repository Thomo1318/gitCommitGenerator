# git-cg eval review enqueue

> **Usage:** `git-cg eval review enqueue …`  
> **Kind:** `command` · **Status:** command

Enqueue an advisory human_review_v1 row (pending).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval review enqueue [OPTIONS]                                                       
                                                                                
 Enqueue an advisory human_review_v1 row (pending).                             
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│    --case                     TEXT   Case id under review.                   │
│    --bundle-id                TEXT   Bundle id under review.                 │
│ *  --reviewer                 TEXT   Opaque local reviewer handle (not       │
│                                      email).                                 │
│                                      [required]                              │
│    --redaction-profile        TEXT   R14 redaction profile (default          │
│                                      meta_eval_scrub).                       │
│                                      [default: meta_eval_scrub]              │
│    --craft-rating             FLOAT  human.craft_rating score.               │
│    --gold-dispute             TEXT   human.gold_dispute: true|false.         │
│    --regime-label             TEXT   human.regime_label: A|B|unknown.        │
│    --notes                    TEXT   Free-text notes.                        │
│    --dry-run                         Validate without writing.               │
│    --json                            Emit cli_output_envelope_v1 on stdout.  │
│    --help                            Show this message and exit.             │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../../index.md)
* [Operator API map](../../../eval/operator_api_map.md)
* [Eval operator guide](../../../eval/README.md)
