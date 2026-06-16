# 09_FinalRecommendation.md — LLMOps Tooling Comparison

## Executive Summary

For instrumenting an **LLM/agent application in a public open-source repo at $0 cost**, the field splits cleanly into **unified platforms** (Opik-replacements) and **specialist complements** (slot beside Opik). The analysis is robust across all weightings: **Opik is an excellent incumbent**, and the only tool that genuinely rivals it as a drop-in replacement is **Langfuse**. The biggest *additive* wins come from pairing Opik with **Promptfoo** (CI eval/red-team) and **OpenLLMetry** (vendor-neutral instrumentation).

---

## Recommendation Classes (per prompt §4)

| Class | Winner | Why |
|---|---|---|
| **Highest Raw Score** | **Langfuse (95.2)** | Top non-anchor; closest unified peer to Opik (99.0) |
| **Best Practical Fit** | **Keep Opik + add Promptfoo + OpenLLMetry** (Stack A) | $0, low friction, OTel-native, adds CI eval gate a public repo needs |
| **Best Unified Option** | **Opik** (incumbent) / **Langfuse** (alternative) | Both all-in-one, OSS, OTel-native |
| **Best Specialist Option** | **Promptfoo** | Best free eval + red-team for CI/PR gating on a public repo |
| **Best Value / Budget** | **MLflow** or **Promptfoo** | Unlimited free forever, no metering |
| **Best Overall Recommendation** | **Stack A: Opik + Promptfoo + OpenLLMetry** | See below |

### Why the highest raw scorer (Langfuse) is NOT the overall recommendation
Langfuse (95.2) beats every other *candidate*, but it does **not** beat the **incumbent Opik (99.0)** on the unified rubric, and switching incurs migration cost (re-instrumentation) for a marginal license/community gain. The mathematically and operationally correct move is therefore **not to replace Opik**, but to **augment** it — capturing the largest capability gains (CI eval, red-teaming, vendor-neutral instrumentation) at **zero migration cost and $0 spend**.

---

## The Decision: Stack A — "Opik Augmented"

```
   ┌────────────────────────────────────────────────────────────┐
   │  OpenLLMetry (Apache-2.0 OTel SDK)  ── instrument once ──▶   │
   │        emits standard OTel/GenAI spans                       │
   └───────────────┬────────────────────────────────────────────┘
                   │ (OTel-native ingest)
                   ▼
            ┌──────────────┐        ┌─────────────────────────────┐
            │  OPIK         │        │  PROMPTFOO (MIT)            │
            │  tracing,     │        │  runs in GitHub Actions     │
            │  eval UI,     │        │  on every PR: eval +        │
            │  prompt mgmt, │        │  red-team / jailbreak gate  │
            │  optimizer    │        └─────────────────────────────┘
            └──────────────┘
   Runtime/dashboard layer            Pre-merge quality/security gate
```

| Component | License | Cost | Role | Replaces/Adds |
|---|---|---|---|---|
| **Opik** (keep) | Apache 2.0 | $0 | Observability + eval + prompt + optimizer | incumbent |
| **Promptfoo** (add) | MIT | $0 | CI/PR eval + red-team/security testing | **adds** what Opik lacks for OSS PR gating |
| **OpenLLMetry** (add, optional) | Apache 2.0 | $0 | Vendor-neutral OTel instrumentation | **insurance** against future lock-in |

**Total annual TCO = $0** (incl. GST — no billable amount). All three are free for public OSS repos with no metering on the self-host/OSS paths.

### Why this beats the alternatives
- **vs replacing with Langfuse:** Same $0 cost, but avoids migration; you only switch if you specifically need MIT licensing or Langfuse's larger community. Keep Langfuse as the documented fallback.
- **vs eval-heavy stack (DeepEval/RAGAS):** Promptfoo gives eval *and* red-teaming with lower metric-vocabulary sprawl (friction −0.3 vs −0.6).
- **vs LangSmith/Braintrust/closed SaaS:** Those meter free tiers and (LangSmith) can't self-host free — wrong fit for an unbounded public repo.

---

## Fallback / Alternatives Ladder

1. **Primary:** Opik + Promptfoo + OpenLLMetry (Stack A).
2. **If you prefer MIT + bigger community:** swap Opik → **Langfuse** (Stack B). Migration is moderate (re-instrument; both OTel-native eases it).
3. **If OTel purity is paramount:** **OpenLLMetry → Arize Phoenix + Promptfoo** (Stack C).
4. **If you already run W&B/MLflow:** add their GenAI modules instead of a new tool.

---

## Migration & Switching Cost (vs incumbent Opik)

| Action | Effort | Reversible? |
|---|---|---|
| Add Promptfoo (CI) | **Low** — add a `promptfooconfig.yaml` + a GitHub Action; no runtime change | ✅ delete files/workflow |
| Add OpenLLMetry | **Low-Med** — wrap SDK init; spans still flow to Opik via OTel | ✅ remove init wrapper |
| Replace Opik→Langfuse | **Medium** — re-point SDK/exporter, recreate dashboards/prompts | ⚠️ keep Opik project until parity confirmed |

---

## Rollback / Reversibility Strategy (per operating rules)

All recommended changes are **fully reversible** and additive:

1. **Version control everything** — `promptfooconfig.yaml`, CI workflow, and instrumentation init live in the repo. Rollback = `git revert`.
2. **Promptfoo:** introduce as a **non-blocking** CI check first (report-only); promote to required status only after green runs. Rollback = remove the workflow file or mark non-required.
3. **OpenLLMetry:** add behind a feature flag / env var (`OTEL_ENABLED`). Spans continue to Opik. Rollback = unset the env var; no code path lost.
4. **Opik stays untouched** during augmentation — zero risk to the existing observability pipeline.
5. **If trialing Langfuse:** run **dual-export** (Opik + Langfuse simultaneously via OTel fan-out) for a parallel period; cut over only after parity verified; keep Opik project archived. **No data destroyed at any step.**
6. **No NON-REVERSIBLE actions** are involved. No data deletion, no destructive migration.

---

## Bottom Line
**Don't replace Opik — augment it.** Add **Promptfoo** for the CI eval + red-team gate that a public repo benefits from most, and **OpenLLMetry** to keep instrumentation vendor-neutral. Total cost: **$0**. Keep **Langfuse** documented as the one credible drop-in replacement should you ever want MIT licensing or to leave the Comet ecosystem.
