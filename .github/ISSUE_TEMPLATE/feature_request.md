---
name: Feature request
about: Suggest an idea or new feature
title: "✨ feat(scope): "
labels: enhancement
assignees: ""
---

## 🎯 Summary

<!-- Provide a high-level overview of the feature you are requesting. -->

## 💡 Why this matters

<!-- Explain the problem being solved and the value it brings to the project. -->

## 🛠️ Proposed Solution

<!-- Describe how you envision this feature working. -->

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

## ✅ Expected Behaviour

<!-- Outline what the user experience should look like. -->
