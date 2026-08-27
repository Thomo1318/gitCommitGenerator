# git-cg eval

> **Usage:** `git-cg eval …`  
> **Kind:** `group` · **Status:** group

Run and inspect local evaluation suites without changing product ranking.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval [OPTIONS] COMMAND [ARGS]...

 Run and inspect local evaluation suites, debug failures, manage review/sessions, and operate the export queue. Does
 not change product commit ranking.

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --detail          Show detailed help text and exit.                                                                  │
│ --help            Show this message and exit.                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Corpus ─────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ materialize-core-goldens  Rebuild checked-in evaluation reference files used by tests.                               │
│ encode-fixture            Print stable identity hashes for one evaluation fixture.                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Run ────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ run                       Run a local offline evaluation suite.                                                      │
│ resume                    Continue an unfinished evaluation from a checkpoint.                                       │
│ recompute-scores          Re-score evidence already written by a prior run.                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Inspect ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ doctor                    Check local suite health (pins, metrics, fixtures).                                        │
│ triage                    One-shot advisory view: doctor + failures + explain.                                       │
│ failures                  List failing cases with metric and failure ids.                                            │
│ explain                   Show a deterministic explanation for a failing case.                                       │
│ compare                   Diff two cases (structure and metrics).                                                    │
│ diagnose                  Create or update a diagnostic issue from a failure.                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Review & sessions ──────────────────────────────────────────────────────────────────────────────────────────────────╮
│ review                    Local human review queue (advisory only).                                                  │
│ session                   Inspect local commit sessions.                                                             │
│ thread                    Inspect local session threads.                                                             │
│ issue                     Manage local diagnostic issues.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Export & train ─────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ amend-brief               Build an amend brief from landed evaluation data.                                          │
│ train-export              Export redacted training rows from landed bundles.                                         │
│ opik                      Opik health checks and secret-safe config.                                                 │
│ export                    Export-queue status, retry, and drain.                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Advanced ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ replay                    Replay generation into a new bundle (source unchanged).                                    │
│ promote                   Promote a scrubbed candidate with contamination checks.                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Deprecated ─────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ config                    Alias of eval opik config show.                                              (deprecated)  │
│ export-status             Alias of eval export status.                                                 (deprecated)  │
│ export-retry              Alias of eval export retry.                                                  (deprecated)  │
│ export-drain              Alias of eval export drain.                                                  (deprecated)  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval amend-brief`](amend-brief.md) — Build an amend brief from landed evaluation data.
* [`git-cg eval compare`](compare.md) — Diff two cases (structure and metrics).
* [`git-cg eval config`](config.md) — Alias of eval opik config show.
* [`git-cg eval diagnose`](diagnose.md) — Create or update a diagnostic issue from a failure.
* [`git-cg eval doctor`](doctor.md) — Check local suite health (pins, metrics, fixtures).
* [`git-cg eval dogfood`](dogfood.md) — Capture Lane C dogfood evidence for a candidate commit message.
* [`git-cg eval encode-fixture`](encode-fixture.md) — Print stable identity hashes for one evaluation fixture.
* [`git-cg eval explain`](explain.md) — Show a deterministic explanation for a failing case.
* [`git-cg eval export`](export.md) — Export-queue status, retry, and drain.
* [`git-cg eval export-drain`](export-drain.md) — Alias of eval export drain.
* [`git-cg eval export-retry`](export-retry.md) — Alias of eval export retry.
* [`git-cg eval export-status`](export-status.md) — Alias of eval export status.
* [`git-cg eval failures`](failures.md) — List failing cases with metric and failure ids.
* [`git-cg eval issue`](issue.md) — Manage local diagnostic issues.
* [`git-cg eval materialize-core-goldens`](materialize-core-goldens.md) — Rebuild checked-in evaluation reference files used by tests.
* [`git-cg eval opik`](opik.md) — Opik health checks and secret-safe config.
* [`git-cg eval promote`](promote.md) — Promote a scrubbed candidate with contamination checks.
* [`git-cg eval recompute-scores`](recompute-scores.md) — Re-score evidence already written by a prior run.
* [`git-cg eval replay`](replay.md) — Replay generation into a new bundle (source unchanged).
* [`git-cg eval resume`](resume.md) — Continue an unfinished evaluation from a checkpoint.
* [`git-cg eval review`](review.md) — Local human review queue (advisory only).
* [`git-cg eval run`](run.md) — Run a local offline evaluation suite.
* [`git-cg eval session`](session.md) — Inspect local commit sessions.
* [`git-cg eval thread`](thread.md) — Inspect local session threads.
* [`git-cg eval train-export`](train-export.md) — Export redacted training rows from landed bundles.
* [`git-cg eval triage`](triage.md) — One-shot advisory view: doctor + failures + explain.

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
