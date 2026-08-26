# git-cg eval

> **Usage:** `git-cg eval …`  
> **Kind:** `group` · **Status:** group

Evaluation harness operator surface: corpus helpers, offline suite ops, doctor/triage, export queue, and Opik config (no product ranking).

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

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

## Children

* [`git-cg eval amend-brief`](amend-brief.md) — Assemble the v1 amend brief from landed Layer-A data (R11 / §7.2). Advisory authority: summarizes score/failure/regime/family context and pr
* [`git-cg eval compare`](compare.md) — Structural + metric delta; uses replay_compare lineage when linked (§18.3).
* [`git-cg eval config`](config.md) — Deprecated alias for ``eval opik config show`` (temporary bridge). Removal target: first minor release after S6 GA.
* [`git-cg eval diagnose`](diagnose.md) — Upsert diag_issue_v1 with stable fingerprint law (§18.4; idempotent).
* [`git-cg eval doctor`](doctor.md) — Local suite/pin/metric doctor (distinct from ``eval opik doctor``). Offline, network-free. Fail-closed on floating ``latest`` pins and missi
* [`git-cg eval dogfood`](dogfood.md) — Fire the Lane C dogfood shadow sidecar (§7.3). Dark-launched maintainer/operator surface: registered and callable as ``git-cg eval dogfood``
* [`git-cg eval encode-fixture`](encode-fixture.md) — Encode a fixture into ``ape_bundle_v1`` and print its identity summary. Requires exactly one of ``--path`` or ``--id``; exits non-zero on in
* [`git-cg eval explain`](explain.md) — Deterministic explain contract (§18.3); no opaque LLM RCA.
* [`git-cg eval export`](export.md) — Layer-A export queue ops: status / retry / drain (F4 fail-open).
* [`git-cg eval export-drain`](export-drain.md) — Deprecated alias for ``eval export drain``.
* [`git-cg eval export-retry`](export-retry.md) — Deprecated alias for ``eval export retry``.
* [`git-cg eval export-status`](export-status.md) — Deprecated alias for ``eval export status``.
* [`git-cg eval failures`](failures.md) — List failing bundles/cases with metric_ids + failure_ids (§18.3, read-only). Optional NTH-02 filters (``--regime``, ``--family``, ``--failur
* [`git-cg eval issue`](issue.md) — Local diagnostic issue store ops.
* [`git-cg eval materialize-core-goldens`](materialize-core-goldens.md) — Materialize checked-in core golden bundles + snapshot (corpus write only).
* [`git-cg eval opik`](opik.md) — Opik/export health and secret-safe config (canonical).
* [`git-cg eval promote`](promote.md) — Promotion state machine + split_group_id contamination check.
* [`git-cg eval recompute-scores`](recompute-scores.md) — Re-run the metric pack over already-landed evidence bundles.
* [`git-cg eval replay`](replay.md) — Replay generation into a new bundle + replay_compare_v1 (never mutates source).
* [`git-cg eval resume`](resume.md) — Resume a suite run from a governed checkpoint + compat hash.
* [`git-cg eval review`](review.md) — Local HITL review queue (.eval/review_queue; advisory only).
* [`git-cg eval run`](run.md) — Run an offline evaluation suite (canonical; not ``eval suite run``).
* [`git-cg eval session`](session.md) — Local commit-session inspection.
* [`git-cg eval thread`](thread.md) — Local session-thread inspection.
* [`git-cg eval train-export`](train-export.md) — Export governed train rows from landed bundles (R14 / §7.5). Row scrub-failure policy: drop + report (scrub_report) + continue; never emit c
* [`git-cg eval triage`](triage.md) — Offline advisory router over doctor + failures + explain (Slice 8 / D27). Composes library engines only — never nests Typer presentation com

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
