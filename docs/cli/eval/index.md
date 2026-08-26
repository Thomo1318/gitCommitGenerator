# git-cg eval

> **Usage:** `git-cg eval …`  
> **Kind:** `group` · **Status:** group

Run and inspect local evaluation suites, debug failures, manage review/sessions, and operate the export queue. Does not change product commit ranking.

## Authority boundary

* Does **not** re-rank product intents or rewrite SOP authority.
* Does **not** sole-promote gold as CI authority.
* Offline-first by default; transport-bearing surfaces document their fail-open/fail-closed law in help.

## Help

```text
Usage: git-cg eval [OPTIONS] COMMAND [ARGS]...                                        
                                                                                
 Run and inspect local evaluation suites, debug failures, manage                
 review/sessions, and operate the export queue. Does not change product commit  
 ranking.                                                                       
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Corpus ─────────────────────────────────────────────────────────────────────╮
│ materialize-core-goldens  Rebuild the checked-in evaluation reference files  │
│                           used by tests.                                     │
│ encode-fixture            Encode a fixture and print its identity summary.   │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Run ────────────────────────────────────────────────────────────────────────╮
│ run                       Run an offline evaluation suite.                   │
│ resume                    Resume a suite from a checkpoint.                  │
│ recompute-scores          Re-score evidence already written by a prior run.  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Inspect ────────────────────────────────────────────────────────────────────╮
│ doctor                    Check local suite health (pins, metrics,           │
│                           fixtures).                                         │
│ triage                    One-shot advisory view: doctor + failures +        │
│                           explain.                                           │
│ failures                  List failing cases with metric and failure ids.    │
│ explain                   Show a deterministic explanation for a failing     │
│                           case.                                              │
│ compare                   Diff two cases (structure and metrics).            │
│ diagnose                  Create or update a diagnostic issue from a         │
│                           failure.                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Review & sessions ──────────────────────────────────────────────────────────╮
│ review                    Local human review queue (advisory only).          │
│ session                   Inspect local commit sessions.                     │
│ thread                    Inspect local session threads.                     │
│ issue                     Manage local diagnostic issues.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Export & train ─────────────────────────────────────────────────────────────╮
│ amend-brief               Build an amend brief from landed evaluation data.  │
│ train-export              Export redacted training rows from landed bundles. │
│ opik                      Opik health checks and secret-safe config.         │
│ export                    Export-queue status, retry, and drain.             │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Advanced ───────────────────────────────────────────────────────────────────╮
│ replay                    Replay generation into a new bundle (source        │
│                           unchanged).                                        │
│ promote                   Promote a scrubbed candidate with contamination    │
│                           checks.                                            │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Deprecated ─────────────────────────────────────────────────────────────────╮
│ config                    Alias of eval opik config show.      (deprecated)  │
│ export-status             Alias of eval export status.         (deprecated)  │
│ export-retry              Alias of eval export retry.          (deprecated)  │
│ export-drain              Alias of eval export drain.          (deprecated)  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Children

* [`git-cg eval amend-brief`](amend-brief.md) — Build an amend brief from landed evaluation data. Advisory authority: summarizes score/failure/regime/family context and preference pairs; n
* [`git-cg eval compare`](compare.md) — Diff two cases (structure and metrics).
* [`git-cg eval config`](config.md) — Alias of eval opik config show. Removal target: first minor release after S6 GA.
* [`git-cg eval diagnose`](diagnose.md) — Create or update a diagnostic issue from a failure.
* [`git-cg eval doctor`](doctor.md) — Check local suite health (pins, metrics, fixtures). Offline, network-free. Fail-closed on floating ``latest`` pins and missing catalog/schem
* [`git-cg eval dogfood`](dogfood.md) — Capture Lane C dogfood evidence for a candidate commit message. Dark-launched maintainer/operator surface: registered and callable as ``git-
* [`git-cg eval encode-fixture`](encode-fixture.md) — Encode a fixture and print its identity summary. Requires exactly one of ``--path`` or ``--id``; exits non-zero on invalid options, missing 
* [`git-cg eval explain`](explain.md) — Show a deterministic explanation for a failing case.
* [`git-cg eval export`](export.md) — Export-queue status, retry, and drain.
* [`git-cg eval export-drain`](export-drain.md) — Alias of eval export drain.
* [`git-cg eval export-retry`](export-retry.md) — Alias of eval export retry.
* [`git-cg eval export-status`](export-status.md) — Alias of eval export status.
* [`git-cg eval failures`](failures.md) — List failing cases with metric and failure ids. Optional NTH-02 filters (``--regime``, ``--family``, ``--failure-id``, ``--severity``) are A
* [`git-cg eval issue`](issue.md) — Manage local diagnostic issues.
* [`git-cg eval materialize-core-goldens`](materialize-core-goldens.md) — Rebuild the checked-in evaluation reference files used by tests. Writes the main reference bundles and snapshot into the fixture directory (
* [`git-cg eval opik`](opik.md) — Opik health checks and secret-safe config.
* [`git-cg eval promote`](promote.md) — Promote a scrubbed candidate with contamination checks.
* [`git-cg eval recompute-scores`](recompute-scores.md) — Re-score evidence already written by a prior run.
* [`git-cg eval replay`](replay.md) — Replay generation into a new bundle (source unchanged).
* [`git-cg eval resume`](resume.md) — Resume a suite from a checkpoint.
* [`git-cg eval review`](review.md) — Local human review queue (advisory only).
* [`git-cg eval run`](run.md) — Run an offline evaluation suite.
* [`git-cg eval session`](session.md) — Inspect local commit sessions.
* [`git-cg eval thread`](thread.md) — Inspect local session threads.
* [`git-cg eval train-export`](train-export.md) — Export redacted training rows from landed bundles. Row scrub-failure policy: drop + report (scrub_report) + continue; never emit cleartext; 
* [`git-cg eval triage`](triage.md) — One-shot advisory view: doctor + failures + explain. Composes library engines only — never nests Typer presentation commands. Not score law:

## See also

* [CLI overview](../index.md)
* [Operator API map](../../eval/operator_api_map.md)
* [Eval operator guide](../../eval/README.md)
