# git-cg eval

> **Usage:** `git-cg eval …`

Evaluation harness operator surface: corpus helpers, offline suite ops, doctor/triage, export queue, and Opik config (no product ranking).

## Help

```text
Usage: git-cg eval [OPTIONS] COMMAND [ARGS]...                                        
                                                                                
 Evaluation harness operator surface: corpus helpers, offline suite ops,        
 doctor/triage, export queue, and Opik config (no product ranking).             
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ materialize-core-goldens  Materialize checked-in core golden bundles +       │
│                           snapshot (corpus write only).                      │
│ encode-fixture            Encode a fixture into ``ape_bundle_v1`` and print  │
│                           its identity summary.                              │
│ run                       Run an offline evaluation suite (canonical; not    │
│                           ``eval suite run``).                               │
│ resume                    Resume a suite run from a governed checkpoint +    │
│                           compat hash.                                       │
│ recompute-scores          Re-run the metric pack over already-landed         │
│                           evidence bundles.                                  │
│ doctor                    Local suite/pin/metric doctor (distinct from       │
│                           ``eval opik doctor``).                             │
│ amend-brief               Assemble the v1 amend brief from landed Layer-A    │
│                           data (R11 / §7.2).                                 │
│ train-export              Export governed train rows from landed bundles     │
│                           (R14 / §7.5).                                      │
│ triage                    Offline advisory router over doctor + failures +   │
│                           explain (Slice 8 / D27).                           │
│ failures                  List failing bundles/cases with metric_ids +       │
│                           failure_ids (§18.3, read-only).                    │
│ explain                   Deterministic explain contract (§18.3); no opaque  │
│                           LLM RCA.                                           │
│ compare                   Structural + metric delta; uses replay_compare     │
│                           lineage when linked (§18.3).                       │
│ replay                    Replay generation into a new bundle +              │
│                           replay_compare_v1 (never mutates source).          │
│ promote                   Promotion state machine + split_group_id           │
│                           contamination check.                               │
│ diagnose                  Upsert diag_issue_v1 with stable fingerprint law   │
│                           (§18.4; idempotent).                               │
│ config                    Deprecated alias for ``eval opik config show``     │
│                           (temporary bridge).                                │
│ export-status             Deprecated alias for ``eval export status``.       │
│ export-retry              Deprecated alias for ``eval export retry``.        │
│ export-drain              Deprecated alias for ``eval export drain``.        │
│ review                    Local HITL review queue (.eval/review_queue;       │
│                           advisory only).                                    │
│ session                   Local commit-session inspection.                   │
│ thread                    Local session-thread inspection.                   │
│ issue                     Local diagnostic issue store ops.                  │
│ opik                      Opik/export health and secret-safe config          │
│                           (canonical).                                       │
│ export                    Layer-A export queue ops: status / retry / drain   │
│                           (F4 fail-open).                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Subcommands

* `git-cg eval amend-brief` — Assemble the v1 amend brief from landed Layer-A data (R11 / §7.2).
* `git-cg eval compare` — Structural + metric delta; uses replay_compare lineage when linked (§18.3).
* `git-cg eval config` — Deprecated alias for ``eval opik config show`` (temporary bridge).
* `git-cg eval diagnose` — Upsert diag_issue_v1 with stable fingerprint law (§18.4; idempotent).
* `git-cg eval doctor` — Local suite/pin/metric doctor (distinct from ``eval opik doctor``).
* `git-cg eval dogfood` — Fire the Lane C dogfood shadow sidecar (§7.3).
* `git-cg eval encode-fixture` — Encode a fixture into ``ape_bundle_v1`` and print its identity summary.
* `git-cg eval explain` — Deterministic explain contract (§18.3); no opaque LLM RCA.
* `git-cg eval export` — Layer-A export queue ops: status / retry / drain (F4 fail-open).
* `git-cg eval export-drain` — Deprecated alias for ``eval export drain``.
* `git-cg eval export-retry` — Deprecated alias for ``eval export retry``.
* `git-cg eval export-status` — Deprecated alias for ``eval export status``.
* `git-cg eval failures` — List failing bundles/cases with metric_ids + failure_ids (§18.3, read-only).
* `git-cg eval issue` — Local diagnostic issue store ops.
* `git-cg eval materialize-core-goldens` — Materialize checked-in core golden bundles + snapshot (corpus write only).
* `git-cg eval opik` — Opik/export health and secret-safe config (canonical).
* `git-cg eval promote` — Promotion state machine + split_group_id contamination check.
* `git-cg eval recompute-scores` — Re-run the metric pack over already-landed evidence bundles.
* `git-cg eval replay` — Replay generation into a new bundle + replay_compare_v1 (never mutates source).
* `git-cg eval resume` — Resume a suite run from a governed checkpoint + compat hash.
* `git-cg eval review` — Local HITL review queue (.eval/review_queue; advisory only).
* `git-cg eval run` — Run an offline evaluation suite (canonical; not ``eval suite run``).
* `git-cg eval session` — Local commit-session inspection.
* `git-cg eval thread` — Local session-thread inspection.
* `git-cg eval train-export` — Export governed train rows from landed bundles (R14 / §7.5).
* `git-cg eval triage` — Offline advisory router over doctor + failures + explain (Slice 8 / D27).

## Eval operator surface

The evaluation harness operator API is documented on dedicated pages:

* [Eval overview](eval/index.md)
* [Operator API map](../eval/operator_api_map.md)

Dark-launched commands (currently `eval dogfood`) stay callable but are hidden from regular `git-cg eval --help`.
