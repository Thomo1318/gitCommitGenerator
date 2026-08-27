# git-cg eval promote

> **Usage:** `git-cg eval promote …`  
> **Kind:** `command` · **Status:** canonical S6 surface

Promote a scrubbed candidate with contamination checks.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval promote [OPTIONS]

 Promote a scrubbed candidate with contamination checks.

 Governed promote path. Writes a decision audit; never silent-mints gold from accept or popularity.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ *  --bundle                   TEXT  Source bundle path or id (accept-path or replay). [required]                     │
│ *  --destination              TEXT  Where to send it: fixture_lane_a | hard_negative | preference_pair |             │
│                                     observability_fixture | quarantine | reject.                                     │
│                                     [required]                                                                       │
│ *  --owner                    TEXT  Who owns this promotion (local handle). [required]                               │
│ *  --label                    TEXT  Promotion label (not silent gold). [required]                                    │
│ *  --provenance               TEXT  Why this is allowed (not popularity/accept alone). [required]                    │
│ *  --redaction-profile        TEXT  Redaction profile applied to the promoted artifact. [required]                   │
│    --stage                    TEXT  Source stage: failure_or_capture | scrubbed_candidate (default                   │
│                                     scrubbed_candidate).                                                             │
│                                     [default: scrubbed_candidate]                                                    │
│    --split-group-id           TEXT  Contamination unit (defaults from bundle/session).                               │
│    --review-id                TEXT  Optional reviewed item id (advisory only; never sole gold authority).            │
│    --notes                    TEXT  Optional free-text notes for the decision record.                                │
│    --popularity-signal              Mark popularity/acceptance signal (cannot promote golden).                       │
│    --dry-run                        Validate the decision without writing files.                                     │
│    --json                           Print machine-readable JSON instead of plain text.                               │
│    --detail                         Show detailed help text and exit.                                                │
│    --help                           Show this message and exit.                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
