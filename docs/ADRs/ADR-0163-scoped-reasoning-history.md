# ADR-0163: Scoped Reasoning History (Phase 9)

## Status

Accepted (implementation in progress on `refactor/163-scoped-reasoning-history-removal-of-legacy-hacks`)

## Context

Phase 7/7.5 introduced shadow-workspace graph isolation and semantic product fields.
Operators still lacked **high-confidence, fail-open** evidence for:

1. **Split recommendations** when staged files partition into flow-disjoint components
2. **Rename confidence** bands corroborated by AST/`code_fp` + token similarity
3. **Structural markers** (error handling, public API, new CLI command) for enrichment only

Legacy heuristic branches mixed advisory signals with authority fields and were hard to reason about under flag-off.

## Decision

Introduce `git_cg.scoped_history` as an **advisory, default-gated, fail-open** producer:

| Concern | Rule |
|---|---|
| Authority | Ranker/SOP remain sole authority for `intent_id`, gitmoji, SemVer, changelog |
| Plan merge | OR-merge only: may set `split_recommended=True` and append bounded rationale notes |
| Prompt | Channel 4 `SCOPED-HISTORY FEEDBACK` is directive-free guidance text |
| Shadow lifetime | **Policy B**: stats + product queries use `shadow.path` *inside* the live context |
| Flag-off | `--no-enable-semantic` → zero producer side effects; safe enum defaults |
| Telemetry | Free-text rationales redacted; closed enums coerced, not scrubbed |
| Markers | P1/P2 structural markers fold into `fingerprint_markers` (closed vocabulary) |

## Consequences

### Positive

* Deterministic split/rename evidence with explicit fallback reasons
* Clear Policy B lifetime contract for shadow workspaces
* Safer enrichment without authority mutation

### Negative / follow-ups

* Parser stubs in tests must expose `results` (or producers fail-open)
* Legacy heuristic branches must be verified absent after full suite green
* Wide regression across Phase 7 / 7.25 gold paths required before merge

## References

* Issue #163
* Epic A #158
* Phase 7.5 Policy A shadow isolation (#180)
