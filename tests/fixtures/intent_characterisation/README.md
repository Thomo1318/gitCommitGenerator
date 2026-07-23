# Intent engine characterisation fixtures (Issue #161 Slice 0)

Freeze of deterministic marker generation, `rank_commit_intents`, and
`derive_intent_selection_constraints` against the production SOP matrix.

| File | Role |
| --- | --- |
| `corpus.json` | Case catalogue + SOP matrix SHA-256 pin + tie-break notes |
| `goldens.json` | Canonical markers, full rank snapshots, constraints per case |

Regenerate goldens only when an intentional engine/SOP change is approved.
Do not edit goldens to “make tests pass” during enrichment work unless the
corpus deliberately records a named compatibility deviation.
