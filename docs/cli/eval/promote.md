# git-cg eval promote

> **Usage:** `git-cg eval promote …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Promotion state machine + split_group_id contamination check.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval promote [OPTIONS]                                                       
                                                                                
 Promotion state machine + split_group_id contamination check.                  
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --bundle                   TEXT  Source ape_bundle_v1 path/id (acceptpath │
│                                     or replay).                              │
│                                     [required]                               │
│ *  --destination              TEXT  Terminal destination:                    │
│                                     fixture_lane_a|hard_negative|preference… │
│                                     [required]                               │
│ *  --owner                    TEXT  Promotion owner (opaque local handle).   │
│                                     [required]                               │
│ *  --label                    TEXT  Promotion label (not silent gold).       │
│                                     [required]                               │
│ *  --provenance               TEXT  Provenance token (not popularity/accept  │
│                                     alone).                                  │
│                                     [required]                               │
│ *  --redaction-profile        TEXT  R14 redaction profile for the promoted   │
│                                     artifact.                                │
│                                     [required]                               │
│    --stage                    TEXT  Source stage:                            │
│                                     failure_or_capture|scrubbed_candidate    │
│                                     (default scrubbed_candidate).            │
│                                     [default: scrubbed_candidate]            │
│    --split-group-id           TEXT  Contamination unit (defaults from        │
│                                     bundle/session).                         │
│    --review-id                TEXT  Optional adjudicated review_queue id     │
│                                     (advisory only).                         │
│    --notes                    TEXT  Free-text notes.                         │
│    --popularity-signal              Mark popularity/user_acceptance signal   │
│                                     (cannot promote golden).                 │
│    --dry-run                        Validate decision without writing.       │
│    --json                           Emit cli_output_envelope_v1 on stdout.   │
│    --help                           Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
