# CLI reference

The `git-cg` CLI is the **primary public operator API** for commit generation and the offline Opik evaluation harness.

This reference mirrors the live Typer tree (same source of truth as `docs/eval/operator_api_map.md`). Each command has a dedicated page with usage, parameters, and authority boundaries — modeled after the mise CLI reference layout (overview + one page per command).

## Design goals

* **Deterministic semantic contract first** — ranking/SOP authority is never overridden by eval UX.
* **Offline Lane A by default** for eval operator flows; network/dogfood surfaces are explicit.
* **Secret-safe projection** on doctor/config/export paths.
* **CLI-first docs** — not a general Python SDK and not full-package autodoc.

## Root commands

| Command | Description |
|:---|:---|
| [`git-cg commit`](commit.md) | Generate an AI commit message based on staged changes. |
| [`git-cg eval`](eval.md) | Evaluation harness operator surface: corpus helpers, offline suite ops, doctor/triage, export queue, and Opik config (no product ranking). |
| [`git-cg evals`](evals.md) | Manage and run the git-cg evals benchmarking suite |
| [`git-cg preflight`](preflight.md) | Print a read-only diff-class / path-class preflight summary (Issue #204). |
| [`git-cg record-telemetry`](record-telemetry.md) | Record final commit telemetry and bind accepted final bytes (S3). |
| [`git-cg release`](release.md) | Run the release workflow. |
| [`git-cg sop`](sop.md) | Display the GitOps SOP matrices and workflows. |

## Global flags

```text
Usage: git-cg [OPTIONS] COMMAND [ARGS]...                                        
                                                                                
 GitOps AI Commit Generator and Release Automation                              
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --interactive      -i                                Enable terminal-native  │
│                                                      interactive review via  │
│                                                      gum.                    │
│ --term             -t                                Use Terminal Editor     │
│                                                      ($EDITOR) when editing  │
│                                                      commit messages         │
│                                                      (Default).              │
│                                                      [default: True]         │
│ --gui              -g                                Use GUI Editor          │
│                                                      ($VISUAL) when editing  │
│                                                      commit messages.        │
│ --enable-semantic      --no-enable-semantic          Enable Phase 1 semantic │
│                                                      producers (default:     │
│                                                      GIT_CG_ENABLE_SEMANTIC  │
│                                                      env or off).            │
│ --rank-arbitrate       --no-rank-arbitrate           Allow Low-confidence    │
│                                                      pre-LLM intent          │
│                                                      arbitration when -i +   │
│                                                      TTY (default:           │
│                                                      GIT_CG_RANK_ARBITRATE   │
│                                                      env or auto).           │
│ --gold-strict                                        Resolve gold lint to    │
│                                                      strict mode without     │
│                                                      enabling general        │
│                                                      --strict.               │
│ --blueprint                                    TEXT  Optional presentation   │
│                                                      CommitBlueprint as      │
│                                                      inline JSON or          │
│                                                      @path.json (max 64KiB;  │
│                                                      never overrides ranked  │
│                                                      intent_id).             │
│ --engine           -e                          TEXT  AI engine to use when   │
│                                                      running git-cg          │
│                                                      directly.               │
│                                                      [default: mtplx]        │
│ --dry-run          -d                                Generate and print the  │
│                                                      commit message without  │
│                                                      applying a commit.      │
│ --verbose          -v                                Enable verbose output.  │
│ --strict                                             Exit non-zero on        │
│                                                      failure for standalone  │
│                                                      CLI use.                │
│                                                      [default: True]         │
│ --recover          -r                                Recover and retry the   │
│                                                      last generated commit   │
│                                                      message without         │
│                                                      querying the AI.        │
│ --help                                               Show this message and   │
│                                                      exit.                   │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ commit            Generate an AI commit message based on staged changes.     │
│ preflight         Print a read-only diff-class / path-class preflight        │
│                   summary (Issue #204).                                      │
│ sop               Display the GitOps SOP matrices and workflows.             │
│ release           Run the release workflow.                                  │
│ record-telemetry  Record final commit telemetry and bind accepted final      │
│                   bytes (S3).                                                │
│ evals             Manage and run the git-cg evals benchmarking suite         │
│ eval              Evaluation harness operator surface: corpus helpers,       │
│                   offline suite ops, doctor/triage, export queue, and Opik   │
│                   config (no product ranking).                               │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Evaluation harness (`git-cg eval`)

See the [eval overview](eval/index.md) for nested groups. Canonical S6 operator commands:

* [`git-cg eval amend-brief`](eval/amend-brief.md)
* [`git-cg eval compare`](eval/compare.md)
* [`git-cg eval diagnose`](eval/diagnose.md)
* [`git-cg eval doctor`](eval/doctor.md)
* [`git-cg eval dogfood`](eval/dogfood.md)
* [`git-cg eval encode-fixture`](eval/encode-fixture.md)
* [`git-cg eval explain`](eval/explain.md)
* [`git-cg eval export drain`](eval/export/drain.md)
* [`git-cg eval export retry`](eval/export/retry.md)
* [`git-cg eval export status`](eval/export/status.md)
* [`git-cg eval failures`](eval/failures.md)
* [`git-cg eval issue list`](eval/issue/list.md)
* [`git-cg eval issue reopen`](eval/issue/reopen.md)
* [`git-cg eval issue resolve`](eval/issue/resolve.md)
* [`git-cg eval issue show`](eval/issue/show.md)
* [`git-cg eval issue suppress`](eval/issue/suppress.md)
* [`git-cg eval materialize-core-goldens`](eval/materialize-core-goldens.md)
* [`git-cg eval opik config show`](eval/opik/config/show.md)
* [`git-cg eval opik doctor`](eval/opik/doctor.md)
* [`git-cg eval promote`](eval/promote.md)
* [`git-cg eval recompute-scores`](eval/recompute-scores.md)
* [`git-cg eval replay`](eval/replay.md)
* [`git-cg eval resume`](eval/resume.md)
* [`git-cg eval run`](eval/run.md)
* [`git-cg eval session show`](eval/session/show.md)
* [`git-cg eval thread show`](eval/thread/show.md)
* [`git-cg eval train-export`](eval/train-export.md)
* [`git-cg eval triage`](eval/triage.md)

### Groups and aliases

* **`git-cg eval amend-brief`**
  * [`git-cg eval amend-brief`](eval/amend-brief.md) — Assemble the v1 amend brief from landed Layer-A data (R11 / §7.2). Advisory authority: summarizes sc
* **`git-cg eval compare`**
  * [`git-cg eval compare`](eval/compare.md) — Structural + metric delta; uses replay_compare lineage when linked (§18.3).
* **`git-cg eval config`**
  * [`git-cg eval config`](eval/config.md) — Deprecated alias for ``eval opik config show`` (temporary bridge). Removal target: first minor relea
* **`git-cg eval diagnose`**
  * [`git-cg eval diagnose`](eval/diagnose.md) — Upsert diag_issue_v1 with stable fingerprint law (§18.4; idempotent).
* **`git-cg eval doctor`**
  * [`git-cg eval doctor`](eval/doctor.md) — Local suite/pin/metric doctor (distinct from ``eval opik doctor``). Offline, network-free. Fail-clos
* **`git-cg eval dogfood`**
  * [`git-cg eval dogfood`](eval/dogfood.md) — Fire the Lane C dogfood shadow sidecar (§7.3). Dark-launched maintainer/operator surface: registered
* **`git-cg eval encode-fixture`**
  * [`git-cg eval encode-fixture`](eval/encode-fixture.md) — Encode a fixture into ``ape_bundle_v1`` and print its identity summary. Requires exactly one of ``--
* **`git-cg eval explain`**
  * [`git-cg eval explain`](eval/explain.md) — Deterministic explain contract (§18.3); no opaque LLM RCA.
* **`git-cg eval export`**
  * [`git-cg eval export`](eval/export.md) — Layer-A export queue ops: status / retry / drain (F4 fail-open).
  * [`git-cg eval export drain`](eval/export/drain.md) — Drain the export queue through the Opik transport (F4 fail-open). Always exits 0 unless the config i
  * [`git-cg eval export retry`](eval/export/retry.md) — Re-queue failed export rows for another drain attempt (P1-4 / P1-11). Default policy: reclaim rows w
  * [`git-cg eval export status`](eval/export/status.md) — Show the Layer-A export queue status (read-only, offline). Never mutates the queue and never contact
* **`git-cg eval export-drain`**
  * [`git-cg eval export-drain`](eval/export-drain.md) — Deprecated alias for ``eval export drain``.
* **`git-cg eval export-retry`**
  * [`git-cg eval export-retry`](eval/export-retry.md) — Deprecated alias for ``eval export retry``.
* **`git-cg eval export-status`**
  * [`git-cg eval export-status`](eval/export-status.md) — Deprecated alias for ``eval export status``.
* **`git-cg eval failures`**
  * [`git-cg eval failures`](eval/failures.md) — List failing bundles/cases with metric_ids + failure_ids (§18.3, read-only). Optional NTH-02 filters
* **`git-cg eval issue`**
  * [`git-cg eval issue`](eval/issue.md) — Local diagnostic issue store ops.
  * [`git-cg eval issue list`](eval/issue/list.md) — List local diagnostic issues (newest last_seen first).
  * [`git-cg eval issue reopen`](eval/issue/reopen.md) — Reopen a previously resolved/suppressed local diagnostic issue.
  * [`git-cg eval issue resolve`](eval/issue/resolve.md) — Mark a local diagnostic issue resolved (requires --resolution-evidence).
  * [`git-cg eval issue show`](eval/issue/show.md) — Show one local diagnostic issue.
  * [`git-cg eval issue suppress`](eval/issue/suppress.md) — Suppress a local diagnostic issue (requires --reason).
* **`git-cg eval materialize-core-goldens`**
  * [`git-cg eval materialize-core-goldens`](eval/materialize-core-goldens.md) — Materialize checked-in core golden bundles + snapshot (corpus write only).
* **`git-cg eval opik`**
  * [`git-cg eval opik`](eval/opik.md) — Opik/export health and secret-safe config (canonical).
  * [`git-cg eval opik config`](eval/opik/config.md) — Secret-safe Opik/mirror config inspection.
  * [`git-cg eval opik config show`](eval/opik/config/show.md) — Inspect resolved Opik/mirror config (secret-safe; canonical).
  * [`git-cg eval opik doctor`](eval/opik/doctor.md) — Secret-safe Opik/export health doctor. Inspects resolved config / export health / queue without tran
* **`git-cg eval promote`**
  * [`git-cg eval promote`](eval/promote.md) — Promotion state machine + split_group_id contamination check.
* **`git-cg eval recompute-scores`**
  * [`git-cg eval recompute-scores`](eval/recompute-scores.md) — Re-run the metric pack over already-landed evidence bundles.
* **`git-cg eval replay`**
  * [`git-cg eval replay`](eval/replay.md) — Replay generation into a new bundle + replay_compare_v1 (never mutates source).
* **`git-cg eval resume`**
  * [`git-cg eval resume`](eval/resume.md) — Resume a suite run from a governed checkpoint + compat hash.
* **`git-cg eval review`**
  * [`git-cg eval review`](eval/review.md) — Local HITL review queue (.eval/review_queue; advisory only).
  * [`git-cg eval review adjudicate`](eval/review/adjudicate.md) — Adjudicate an in_review item (emits typed outcome_ref; never writes gold).
  * [`git-cg eval review claim`](eval/review/claim.md) — Claim a pending review item (pending → in_review).
  * [`git-cg eval review dismiss`](eval/review/dismiss.md) — Dismiss a pending/in_review item (terminal).
  * [`git-cg eval review enqueue`](eval/review/enqueue.md) — Enqueue an advisory human_review_v1 row (pending).
  * [`git-cg eval review list`](eval/review/list.md) — List local review-queue items.
  * [`git-cg eval review rollup`](eval/review/rollup.md) — Multi-rater advisory rollup over local human_review_v1 rows (NTH-05). Read-only dimension/outcome ma
  * [`git-cg eval review show`](eval/review/show.md) — Show one local review-queue item.
* **`git-cg eval run`**
  * [`git-cg eval run`](eval/run.md) — Run an offline evaluation suite (canonical; not ``eval suite run``).
* **`git-cg eval session`**
  * [`git-cg eval session`](eval/session.md) — Local commit-session inspection.
  * [`git-cg eval session show`](eval/session/show.md) — Read a local session twin under .eval/sessions/ (§7.6). Read-only: no Opik reach, no chat timeline, 
* **`git-cg eval thread`**
  * [`git-cg eval thread`](eval/thread.md) — Local session-thread inspection.
  * [`git-cg eval thread show`](eval/thread/show.md) — Read a local message-thread twin under .eval/sessions/ (§7.6). Read-only: no Opik reach, no chat tim
* **`git-cg eval train-export`**
  * [`git-cg eval train-export`](eval/train-export.md) — Export governed train rows from landed bundles (R14 / §7.5). Row scrub-failure policy: drop + report
* **`git-cg eval triage`**
  * [`git-cg eval triage`](eval/triage.md) — Offline advisory router over doctor + failures + explain (Slice 8 / D27). Composes library engines o

## Stability tiers

| Tier | Surface | Promise |
|:---|:---|:---|
| Public | `git-cg` / `git-cg eval …` | Primary operator API; help-tested |
| Supported | Selected `git_cg.eval*` entrypoints in the operator API map | Maintainer/harness-stable |
| Internal | All other modules | No compatibility promise |

Deprecated aliases remove at **first minor release after S6 GA**.

## Related docs

* [Usage (usage-cli generated)](../usage.md)
* [Operator API map](../eval/operator_api_map.md)
* [Eval guide](../eval/README.md)
* [Development guide](../DEVELOPMENT.md)

## Regeneration

```bash
uv run python tools/gen_cli_docs.py
# or: just gen-cli-docs
# or: mise run docs:cli
```
