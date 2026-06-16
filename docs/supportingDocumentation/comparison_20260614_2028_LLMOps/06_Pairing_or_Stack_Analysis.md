# 06_Pairing_or_Stack_Analysis.md — LLMOps Tooling Comparison

> Per prompt §4: stacks are not perfect fusions. Cross-cutting categories assessed at stack level; explicit friction penalties applied for context-switching, integration brittleness, duplicated admin, and taxonomy inconsistency.

## Candidate Stacks (built around / instead of Opik)

### Stack A — "Opik Augmented" (RECOMMENDED PRACTICAL STACK)
**Opik (observability + eval UI) + Promptfoo (CI eval/red-team) + OpenLLMetry (instrumentation)**

| Dimension | Assessment |
|---|---|
| Coverage | Observability ✅ (Opik), CI eval gate ✅ (Promptfoo), vendor-neutral instrumentation ✅ (OpenLLMetry) |
| Cost | **$0** — all free/OSS |
| Taxonomy friction | **Low** — OpenLLMetry emits OTel spans, Opik ingests OTel natively. Promptfoo runs in CI separately (different surface, low overlap) |
| Context-switching | Low–Medium — Promptfoo lives in CI/CLI; Opik is the runtime dashboard |
| Duplicated admin | Low — Promptfoo is config-in-repo (YAML); no separate account needed |
| Friction penalty | **−0.3** (minor: two eval mental models — Opik experiments vs Promptfoo assertions) |

### Stack B — "Langfuse Native"
**Langfuse (all-in-one) + Promptfoo (CI) + OpenLLMetry (optional)**

| Dimension | Assessment |
|---|---|
| Coverage | Same as A but Langfuse replaces Opik; stronger prompt mgmt, MIT license |
| Cost | **$0** |
| Taxonomy friction | Low — Langfuse OTel-native |
| Migration | Requires moving off Opik (re-instrument; see §07 switching cost) |
| Friction penalty | **−0.3** |

### Stack C — "OTel Standards Stack"
**OpenLLMetry (instrument) → Arize Phoenix (trace/eval) + Promptfoo (CI)**

| Dimension | Assessment |
|---|---|
| Coverage | Best **vendor-neutral** posture; instrument once, swap backends |
| Cost | $0 |
| Taxonomy friction | **Lowest** — pure OpenInference/OTel end-to-end |
| Weakness | Phoenix license source-available; weaker prompt mgmt; AX cloud retention 7d |
| Friction penalty | **−0.2** |

### Stack D — "Eval-Heavy"
**Opik + DeepEval + RAGAS/TruLens**

| Dimension | Assessment |
|---|---|
| Coverage | Deep, research-grade eval; Opik for tracing |
| Taxonomy friction | **Medium** — three eval vocabularies (Opik metrics, DeepEval tests, RAGAS scores) |
| Duplicated admin | Medium — metrics defined in multiple places |
| Friction penalty | **−0.6** (highest — eval-metric sprawl) |

---

## Stack Friction Penalty Summary

| Stack | Components | Raw fit | Friction penalty | Net |
|---|---|--:|--:|--:|
| **A — Opik Augmented** | Opik + Promptfoo + OpenLLMetry | High | −0.3 | **Highest practical** |
| B — Langfuse Native | Langfuse + Promptfoo | High | −0.3 + migration | High |
| C — OTel Standards | OpenLLMetry + Phoenix + Promptfoo | High | −0.2 | High (neutral) |
| D — Eval-Heavy | Opik + DeepEval + RAGAS | Medium-High | −0.6 | Medium |

## Conclusion
- **Best stack given the incumbent is Opik:** **Stack A** — keep Opik, add **Promptfoo** as a CI/PR eval+red-team gate (perfect for a public repo), and **OpenLLMetry** to keep instrumentation vendor-neutral (so you can swap backends later with zero re-code).
- **Best clean-slate / most-permissive stack:** **Stack B** (Langfuse) — only if you prefer MIT licensing and a larger community over Opik's optimizer features.
