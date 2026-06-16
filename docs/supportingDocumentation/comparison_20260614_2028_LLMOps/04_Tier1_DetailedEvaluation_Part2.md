# 04_Tier1_DetailedEvaluation_Part2.md — LLMOps Tooling Comparison

> Tier-1 profiles, Part 2 of 2.

---

## 8. MLflow (GenAI / Tracing) — ubiquitous OSS platform (REPLACE)

| Attribute | Detail |
|---|---|
| Role | ML lifecycle platform that now ships **GenAI tracing + LLM eval** (`mlflow.genai`) |
| License (OSS) | **Apache 2.0** |
| Free | $0, fully self-host; unlimited; also free on Databricks community-ish, but core is OSS |
| Integrations | **OpenTelemetry-compatible tracing**; autolog for OpenAI, LangChain, LlamaIndex, DSPy, etc. |
| Eval | LLM-as-judge metrics, `mlflow.evaluate`, datasets; prompt registry/versioning |
| Standout | Massive maturity/community (18k+ stars); unifies classic ML + GenAI; no vendor lock |
| Weakness | LLM UX less polished/purpose-built than Opik/Langfuse; tracing UI newer; heavier footprint |

**Verdict:** Credible **OSS replacement** if you already use MLflow or want one tool for ML+GenAI. Less LLM-native polish than Opik/Langfuse, but rock-solid and free forever.

---

## 9. Braintrust — eval-first SaaS, generous free tier (REPLACE)

| Attribute | Detail |
|---|---|
| Role | Eval + experiments + logging + prompt playground (eval-centric) |
| License | **Closed-source** SaaS (self-host = paid/enterprise) |
| Free (Starter) | $0 — **unlimited users**, **1 GB processed data**, **10k scores/mo**, **14-day** retention `VERIFIED` (braintrust.dev) |
| Integrations | Model-agnostic SDK (Py/TS), OTel ingest, CI/CD; framework hooks |
| Eval | Best-in-class eval/experiment UX; `autoevals` library; playground for prompt iteration |
| Standout | Polished eval workflow; unlimited seats on free tier (rare); strong for teams |
| Weakness | Not OSS; free tier metered by GB+scores (can exhaust); no free self-host |

**Verdict:** Strong **eval-focused replacement/complement** with the most generous *seat* allowance. Closed-source is the trade-off vs Opik OSS.

---

## Tier-1 Comparative Snapshot

| Tool | OSS license | Self-host free | Cloud free tier | OTel | Eval depth | Prompt mgmt | Role vs Opik |
|---|---|:--:|---|:--:|:--:|:--:|---|
| **Opik** | Apache 2.0 | ✅ unlimited | 10 usr/25k spans/60d | ✅ native | ★★★★ | ★★★★ | anchor |
| **Langfuse** | MIT | ✅ unlimited | 2 usr/50k units/30d | ✅ native | ★★★★ | ★★★★★ | **replace** |
| **Phoenix/AX** | Elastic 2.0 | ✅ unlimited | 1 dev/25k spans/7d | ✅✅ native | ★★★★ | ★★ | both |
| **Helicone** | Apache 2.0 | ✅ unlimited | 10k req/mo/7d | ✅ | ★★★ | ★★ | both |
| **LangSmith** | Closed | ❌ (ent only) | 1 seat/5k traces/14d | ✅ ingest | ★★★★ | ★★★★ | replace (lock-in) |
| **Traceloop** | Apache 2.0 | ✅ (SDK) | hosted free tier | ✅✅ native | — (pipe) | — | **complement** |
| **Promptfoo** | MIT | ✅ (CLI) | optional cloud | n/a | ★★★★★ (+redteam) | ★★★ | **complement** |
| **DeepEval** | Apache 2.0 | ✅ (lib) | Confident AI free | n/a | ★★★★★ | ★★ | **complement** |
| **MLflow** | Apache 2.0 | ✅ unlimited | n/a (self-host) | ✅ compat | ★★★ | ★★★ | replace |
| **Braintrust** | Closed | ❌ free | ∞ usr/1GB/10k scores/14d | ✅ ingest | ★★★★★ | ★★★★ | replace |

---

## Role Map: Replace vs Complement Opik

```
        REPLACE OPIK  ◀──────────────────────────▶  COMPLEMENT OPIK
   (all-in-one alt)                                  (slots beside it)

 Langfuse ★★★★★        MLflow ★★★          Phoenix/Helicone        Traceloop (OTel pipe)
 (MIT, unlimited)      (ML+GenAI)          (OTel, both ways)        Promptfoo (CI eval/redteam)
                       Braintrust ★★★★                              DeepEval (eval-as-code)
                       (closed, eval-first)                         RAGAS / TruLens (metric libs)
 LangSmith ★★ (lock-in)
```

**Two coherent strategies emerge:**
1. **Replace** Opik with **Langfuse** (if you want a more permissive license + bigger community, all-in-one).
2. **Keep Opik** and **complement** it with **Promptfoo** (CI eval/red-team gate) + **Traceloop/OpenLLMetry** (vendor-neutral instrumentation). This is the strongest practical stack for a public OSS repo.
