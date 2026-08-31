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
| [`git-cg eval`](eval.md) | Run and inspect local evaluation suites, debug failures, manage review/sessions, and operate the export queue. Does not change product commit ranking. |
| [`git-cg evals`](evals.md) | Manage and run the git-cg evals benchmarking suite |
| [`git-cg preflight`](preflight.md) | Print a read-only diff-class / path-class preflight summary (Issue #204). |
| [`git-cg record-telemetry`](record-telemetry.md) | Record final commit telemetry and bind accepted final bytes (S3). |
| [`git-cg release`](release.md) | Run the release workflow. |
| [`git-cg sop`](sop.md) | Display the GitOps SOP matrices and workflows. |

## Global flags

```text
Usage: git-cg [OPTIONS] COMMAND [ARGS]...

 GitOps AI Commit Generator and Release Automation

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --interactive      -i                                Enable terminal-native interactive review via gum.              │
│ --term             -t                                Use Terminal Editor ($EDITOR) when editing commit messages      │
│                                                      (Default).                                                      │
│                                                      [default: True]                                                 │
│ --gui              -g                                Use GUI Editor ($VISUAL) when editing commit messages.          │
│ --enable-semantic      --no-enable-semantic          Enable Phase 1 semantic producers (default:                     │
│                                                      GIT_CG_ENABLE_SEMANTIC env or off).                             │
│ --rank-arbitrate       --no-rank-arbitrate           Allow Low-confidence pre-LLM intent arbitration when -i + TTY   │
│                                                      (default: GIT_CG_RANK_ARBITRATE env or auto).                   │
│ --gold-strict                                        Resolve gold lint to strict mode without enabling general       │
│                                                      --strict.                                                       │
│ --blueprint                                    TEXT  Optional presentation CommitBlueprint as inline JSON or         │
│                                                      @path.json (max 64KiB; never overrides ranked intent_id).       │
│ --engine           -e                          TEXT  AI engine to use when running git-cg directly. [default: mtplx] │
│ --dry-run          -d                                Generate and print the commit message without applying a        │
│                                                      commit.                                                         │
│ --verbose          -v                                Enable verbose output.                                          │
│ --strict                                             Exit non-zero on failure for standalone CLI use.                │
│                                                      [default: True]                                                 │
│ --recover          -r                                Recover and retry the last generated commit message without     │
│                                                      querying the AI.                                                │
│ --help                                               Show this message and exit.                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ commit            Generate an AI commit message based on staged changes.                                             │
│ preflight         Print a read-only diff-class / path-class preflight summary (Issue #204).                          │
│ sop               Display the GitOps SOP matrices and workflows.                                                     │
│ release           Run the release workflow.                                                                          │
│ record-telemetry  Record final commit telemetry and bind accepted final bytes (S3).                                  │
│ evals             Manage and run the git-cg evals benchmarking suite                                                 │
│ eval              Run and inspect local evaluation suites without changing product ranking.                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Evaluation harness (`git-cg eval`)

See the [eval overview](eval/index.md) for nested groups. Canonical S6 operator commands:

* [`git-cg eval amend-brief`](eval/amend-brief.md)
* [`git-cg eval checkpoint list`](eval/checkpoint/list.md)
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
  * [`git-cg eval amend-brief`](eval/amend-brief.md) — Build an amend brief from landed evaluation data.
* **`git-cg eval checkpoint`**
  * [`git-cg eval checkpoint`](eval/checkpoint.md) — Local evaluation checkpoint inventory (read-only).
  * [`git-cg eval checkpoint list`](eval/checkpoint/list.md) — List local evaluation checkpoints (read-only).
* **`git-cg eval compare`**
  * [`git-cg eval compare`](eval/compare.md) — Diff two cases (structure and metrics).
* **`git-cg eval config`**
  * [`git-cg eval config`](eval/config.md) — Alias of eval opik config show.
* **`git-cg eval diagnose`**
  * [`git-cg eval diagnose`](eval/diagnose.md) — Create or update a diagnostic issue from a failure.
* **`git-cg eval doctor`**
  * [`git-cg eval doctor`](eval/doctor.md) — Check local suite health (pins, metrics, fixtures).
* **`git-cg eval dogfood`**
  * [`git-cg eval dogfood`](eval/dogfood.md) — Capture Lane C dogfood evidence for a candidate commit message.
* **`git-cg eval encode-fixture`**
  * [`git-cg eval encode-fixture`](eval/encode-fixture.md) — Print stable identity hashes for one evaluation fixture.
* **`git-cg eval explain`**
  * [`git-cg eval explain`](eval/explain.md) — Show a deterministic explanation for a failing case.
* **`git-cg eval export`**
  * [`git-cg eval export`](eval/export.md) — Export-queue status, retry, and drain.
  * [`git-cg eval export drain`](eval/export/drain.md) — Drain the export queue through the Opik transport.
  * [`git-cg eval export retry`](eval/export/retry.md) — Re-queue failed export rows for another drain attempt.
  * [`git-cg eval export status`](eval/export/status.md) — Show export-queue status (read-only, offline).
* **`git-cg eval export-drain`**
  * [`git-cg eval export-drain`](eval/export-drain.md) — Alias of eval export drain.
* **`git-cg eval export-retry`**
  * [`git-cg eval export-retry`](eval/export-retry.md) — Alias of eval export retry.
* **`git-cg eval export-status`**
  * [`git-cg eval export-status`](eval/export-status.md) — Alias of eval export status.
* **`git-cg eval failures`**
  * [`git-cg eval failures`](eval/failures.md) — List failing cases with metric and failure ids.
* **`git-cg eval issue`**
  * [`git-cg eval issue`](eval/issue.md) — Manage local diagnostic issues.
  * [`git-cg eval issue list`](eval/issue/list.md) — List local diagnostic issues.
  * [`git-cg eval issue reopen`](eval/issue/reopen.md) — Reopen a local diagnostic issue.
  * [`git-cg eval issue resolve`](eval/issue/resolve.md) — Mark a local diagnostic issue resolved.
  * [`git-cg eval issue show`](eval/issue/show.md) — Show one local diagnostic issue.
  * [`git-cg eval issue suppress`](eval/issue/suppress.md) — Suppress a local diagnostic issue.
* **`git-cg eval materialize-core-goldens`**
  * [`git-cg eval materialize-core-goldens`](eval/materialize-core-goldens.md) — Rebuild checked-in evaluation reference files used by tests.
* **`git-cg eval opik`**
  * [`git-cg eval opik`](eval/opik.md) — Opik health checks and secret-safe config.
  * [`git-cg eval opik config`](eval/opik/config.md) — Inspect Opik/mirror config without exposing secrets.
  * [`git-cg eval opik config show`](eval/opik/config/show.md) — Show resolved Opik/mirror config without secrets.
  * [`git-cg eval opik doctor`](eval/opik/doctor.md) — Check Opik/export health without exposing secrets.
* **`git-cg eval promote`**
  * [`git-cg eval promote`](eval/promote.md) — Promote a scrubbed candidate with contamination checks.
* **`git-cg eval recompute-scores`**
  * [`git-cg eval recompute-scores`](eval/recompute-scores.md) — Re-score evidence already written by a prior run.
* **`git-cg eval replay`**
  * [`git-cg eval replay`](eval/replay.md) — Replay generation into a new bundle (source unchanged).
* **`git-cg eval resume`**
  * [`git-cg eval resume`](eval/resume.md) — Continue an unfinished evaluation from a checkpoint.
* **`git-cg eval review`**
  * [`git-cg eval review`](eval/review.md) — Local human review queue (advisory only).
  * [`git-cg eval review adjudicate`](eval/review/adjudicate.md) — Adjudicate an in_review item (emits typed outcome_ref; never writes gold).
  * [`git-cg eval review claim`](eval/review/claim.md) — Claim a pending review item (pending → in_review).
  * [`git-cg eval review dismiss`](eval/review/dismiss.md) — Dismiss a pending/in_review item (terminal).
  * [`git-cg eval review enqueue`](eval/review/enqueue.md) — Enqueue an advisory human-review item.
  * [`git-cg eval review list`](eval/review/list.md) — List local review-queue items.
  * [`git-cg eval review rollup`](eval/review/rollup.md) — Roll up multi-rater advisory scores for review items.
  * [`git-cg eval review show`](eval/review/show.md) — Show one local review-queue item.
* **`git-cg eval run`**
  * [`git-cg eval run`](eval/run.md) — Run a local offline evaluation suite.
* **`git-cg eval session`**
  * [`git-cg eval session`](eval/session.md) — Inspect local commit sessions.
  * [`git-cg eval session show`](eval/session/show.md) — Show one local commit session.
* **`git-cg eval thread`**
  * [`git-cg eval thread`](eval/thread.md) — Inspect local session threads.
  * [`git-cg eval thread show`](eval/thread/show.md) — Show one local session thread.
* **`git-cg eval train-export`**
  * [`git-cg eval train-export`](eval/train-export.md) — Export redacted training rows from landed bundles.
* **`git-cg eval triage`**
  * [`git-cg eval triage`](eval/triage.md) — One-shot advisory view: doctor + failures + explain.

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
