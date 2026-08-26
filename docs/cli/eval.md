# git-cg eval

> **Usage:** `git-cg eval …`

Run and inspect local evaluation suites, debug failures, manage review/sessions, and operate the export queue. Does not change product commit ranking.

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

## Subcommands

* `git-cg eval amend-brief` — Build an amend brief from landed evaluation data.
* `git-cg eval compare` — Diff two cases (structure and metrics).
* `git-cg eval config` — Alias of eval opik config show.
* `git-cg eval diagnose` — Create or update a diagnostic issue from a failure.
* `git-cg eval doctor` — Check local suite health (pins, metrics, fixtures).
* `git-cg eval dogfood` — Capture Lane C dogfood evidence for a candidate commit message.
* `git-cg eval encode-fixture` — Encode a fixture and print its identity summary.
* `git-cg eval explain` — Show a deterministic explanation for a failing case.
* `git-cg eval export` — Export-queue status, retry, and drain.
* `git-cg eval export-drain` — Alias of eval export drain.
* `git-cg eval export-retry` — Alias of eval export retry.
* `git-cg eval export-status` — Alias of eval export status.
* `git-cg eval failures` — List failing cases with metric and failure ids.
* `git-cg eval issue` — Manage local diagnostic issues.
* `git-cg eval materialize-core-goldens` — Rebuild the checked-in evaluation reference files used by tests.
* `git-cg eval opik` — Opik health checks and secret-safe config.
* `git-cg eval promote` — Promote a scrubbed candidate with contamination checks.
* `git-cg eval recompute-scores` — Re-score evidence already written by a prior run.
* `git-cg eval replay` — Replay generation into a new bundle (source unchanged).
* `git-cg eval resume` — Resume a suite from a checkpoint.
* `git-cg eval review` — Local human review queue (advisory only).
* `git-cg eval run` — Run an offline evaluation suite.
* `git-cg eval session` — Inspect local commit sessions.
* `git-cg eval thread` — Inspect local session threads.
* `git-cg eval train-export` — Export redacted training rows from landed bundles.
* `git-cg eval triage` — One-shot advisory view: doctor + failures + explain.

## Eval operator surface

The evaluation harness operator API is documented on dedicated pages:

* [Eval overview](eval/index.md)
* [Operator API map](../eval/operator_api_map.md)

Dark-launched commands (currently `eval dogfood`) stay callable but are hidden from regular `git-cg eval --help`.
