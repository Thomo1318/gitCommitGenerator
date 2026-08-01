---
name: Implementation Task (Internal)
about: Define a structured task for active project development
title: "🛠️ task(scope): "
labels: enhancement, internal
assignees: ""
---

## 🎯 Summary

<!-- Provide a high-level overview of the distinct goals for this task. -->

## 💡 Why this matters

<!-- Explain the problem being solved and the value it brings. -->

## 🔄 Expected workflow

1. <!-- Step 1 -->
2. <!-- Step 2 -->

## 📦 In scope

- [ ] <!-- Task 1 -->

## 📡 Telemetry (Opik / Sentry)

<!-- Required for phases/features that change generation, hooks, gold, ranking, recover, semantic
     producers, or observability. Delete this entire section if N/A.
     Specify field tables + non-goals here so close-out cannot drop metrics.
     Infrastructure SSOT: Phase 14/14.5 (#150, closed). Field catalogues: this issue + 
     docs/stagingADRs/.../implementation_plan_Phase_14-14_5.md § Post-close field backlog.
     Promptfoo batch eval ≠ GenerationTelemetry (ADR-0011 § Phase 8.5). -->

### Field tables

| Field | Sink | Type / notes |
| --- | --- | --- |
| <!-- name --> | Opik `GenerationTelemetry` / Sentry tag | <!-- enum/count/bool; codes only --> |

### Non-goals

* No diffs, commit bodies, guidance free text, sidecar JSON, or secrets in any sink
* Opik = product funnel (closed enums/counts/scores); Sentry = failure tags/breadcrumbs only
* Do not reopen #150 for product fields; do not invent a parallel metrics bus

### Acceptance hooks

- [ ] Fields on allowlist + redaction tests when implemented
- [ ] DoD / PR checklist references this section

## 🚫 Out of scope

- <!-- What specifically should NOT be done? -->

## ✅ Acceptance criteria

- <!-- Criteria 1 -->

## 🧪 Suggested test scenarios

<!-- Outline how this feature should be tested (unit, integration, manual). -->

## ⚠️ Risks / things to watch

<!-- Identify potential regressions, performance impacts, or security considerations. -->

## 📂 File plan

<!-- Outline the files expected to be created or modified -->

### `path/to/file`

-
