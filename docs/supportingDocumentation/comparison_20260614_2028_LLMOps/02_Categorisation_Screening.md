# 02_Categorisation_Screening.md — LLMOps Tooling Comparison

## Screening Result Summary

Of the ~56 raw candidates, the majority are **classical MLOps / model-training / cloud-vendor / data platforms** — they fail **HR3 (LLMOps domain)** and/or **HR4 (replace/complement Opik)**. They are split off below. The remaining **genuine LLMOps tools** advance to Tier 1 (detailed) or Tier 2 (summary).

---

## ELIMINATED — Out of Scope (failed HR3 / HR4)

These are not LLM observability/eval/prompt tools, or are not meaningfully usable-free on a public OSS repo as an Opik peer.

| Tool | Category | Reason for elimination |
|---|---|---|
| Amazon SageMaker | Cloud ML platform | Classical MLOps + training; cloud-vendor lock; not LLM-eval/trace peer; metered cost |
| Databricks | Data/ML lakehouse | Enterprise data+ML platform; not free for this use; out of LLMOps observability scope |
| Google Cloud Platform | Cloud platform | Vendor platform, not a discrete LLMOps tool |
| Microsoft/Azure (implied) | Cloud platform | Same |
| DataRobot | AutoML platform | Classical AutoML; commercial; not LLM trace/eval |
| H2O.ai | AutoML/ML platform | Classical ML; out of scope |
| Alibaba Cloud PAI | Cloud ML platform | Vendor lock; classical ML |
| Cloudera | Data platform | Big-data platform; out of scope |
| Valohai | MLOps pipelines | Training/pipeline orchestration; not LLM observability |
| Iguazio | MLOps platform | Classical MLOps; commercial |
| Polyaxon | ML experiment/orchestration | Classical ML training; not LLM eval/trace |
| Snorkel AI | Data labeling/programmatic | Data-centric labeling; not LLMOps observability |
| Deep Lake (Activeloop) | Vector/data lake | Data store, not observability/eval |
| Valohai/TitanML | Inference optimization | TitanML = inference serving/compression; not eval/trace |
| Unsloth / HF AutoTrain | Fine-tuning | Training/fine-tuning; not observability/eval |
| Lamini AI | LLM fine-tuning platform | Training-focused; not free-tier observability peer |
| TrueFoundry | ML/LLM deployment platform | Deployment/infra; commercial; not free eval/trace peer |
| Deepset (deepset Cloud) | RAG platform | Commercial RAG build platform (Haystack is the OSS lib — see below) |
| Fine-Tuner AI | Fine-tuning | Training; out of scope |
| ZenML | MLOps pipeline framework | Pipeline orchestration; not LLM observability/eval (has LLMOps recipes but core is orchestration) |
| Weights & Biases (core) | ML experiment tracking | Classical experiment tracking; **W&B Weave** (LLM module) noted in Tier 2 |
| Fiddler | ML monitoring | Enterprise ML monitoring; commercial; not free OSS-repo peer |
| Losswise | ML metrics tracking | Defunct/classical training metrics |
| Superwise.ai | ML monitoring | Enterprise ML observability; commercial |
| Unravel Data | Data-pipeline observability | Data infra monitoring; not LLM |
| WhyLabs | ML/data monitoring | Classical ML+data monitoring; LLM add-on commercial; relegated |
| NVIDIA NeMo | LLM training/framework | Training framework + Guardrails lib; not an Opik-style eval/trace platform |
| Autogen | Agent framework | Microsoft agent-building framework — a *thing you instrument*, not an observability tool |
| LlamaIndex | RAG framework | Framework you build with (instrumented BY Opik), not an LLMOps observability tool |
| Haystack | NLP/RAG framework | Same — a build framework, not observability/eval |
| eval-view | Unknown/niche | No verifiable product/free tier as an LLMOps platform; insufficient evidence |
| AgentTrace | Niche/unverified | No verifiable mature free LLMOps product distinct from tracing libs |
| Cekura / Coval | Voice-agent testing | Niche voice-agent simulation/testing; commercial; narrow; relegated |

> **Note on frameworks:** LlamaIndex, Haystack, Autogen, NeMo are **application/agent frameworks**. Opik (and the Tier-1 tools) *instrument* them. They are complements-by-being-instrumented, not competitors, so they're excluded from scoring.

---

## SHORTLISTED — Genuine LLMOps Tools (advance to scoring)

### Tier 1 — Detailed Evaluation (direct Opik peers or major complements)
1. **Opik** (anchor / incumbent)
2. **Langfuse** (+ OSS) — closest all-in-one OSS peer
3. **Arize Phoenix** (+ OSS) / Arize AX — OTel-native OSS peer
4. **Helicone** — OSS gateway + observability
5. **LangSmith** — market-leading closed SaaS peer
6. **Traceloop / OpenLLMetry** — OTel SDK (pure complement)
7. **Promptfoo** — OSS eval/red-team specialist
8. **DeepEval / Confident AI** — OSS eval framework + hosted
9. **MLflow** (GenAI tracing/eval) — OSS, ubiquitous
10. **Braintrust** — eval-first SaaS (generous free tier)

### Tier 2 — Summary Evaluation (valid but narrower / smaller)
- **Langwatch** — OSS, OTel-native, eval + agent sim
- **Lunary** — OSS observability + prompt mgmt
- **Agenta** — OSS prompt mgmt + eval + observability
- **PromptLayer** — closed SaaS prompt mgmt + logging
- **AgentOps** — closed SaaS agent monitoring
- **Latitude** — OSS prompt engineering + agents
- **RAGAS** — OSS RAG-eval library (metric provider — complements Opik)
- **TruLens** — OSS eval/feedback library (metric provider — complements Opik)
- **Evidently AI** — OSS ML+LLM eval/monitoring library
- **W&B Weave** — LLM module of Weights & Biases (free for public/personal)
- **Datadog LLM Observability / New Relic AI Monitoring** — APM add-ons (no true free LLM tier; context only)

---

## Hard-Requirements Gate Results (shortlist)

| Tool | HR1 $0 tier | HR2 OSS-repo free | HR3 LLMOps | HR4 replace/complement Opik | Verdict |
|---|:--:|:--:|:--:|:--:|---|
| Opik | ✅ | ✅ | ✅ | — (anchor) | Baseline |
| Langfuse | ✅ | ✅ | ✅ | ✅ replace | PASS |
| Arize Phoenix | ✅ | ✅ | ✅ | ✅ both | PASS |
| Helicone | ✅ | ✅ | ✅ | ✅ both | PASS |
| LangSmith | ✅ (limited) | ✅ | ✅ | ✅ replace | PASS |
| Traceloop/OpenLLMetry | ✅ | ✅ | ✅ | ✅ complement | PASS |
| Promptfoo | ✅ | ✅ | ✅ | ✅ complement | PASS |
| DeepEval/Confident AI | ✅ | ✅ | ✅ | ✅ both | PASS |
| MLflow (GenAI) | ✅ | ✅ | ✅ | ✅ replace | PASS |
| Braintrust | ✅ | ✅ | ✅ | ✅ replace | PASS |
| Langwatch | ✅ | ✅ | ✅ | ✅ both | PASS (T2) |
| Lunary | ✅ | ✅ | ✅ | ✅ replace | PASS (T2) |
| Agenta | ✅ | ✅ | ✅ | ✅ both | PASS (T2) |
| PromptLayer | ✅ (limited) | ✅ | ✅ | ✅ complement | PASS (T2) |
| AgentOps | ✅ (limited) | ✅ | ✅ | ✅ complement | PASS (T2) |
| Latitude | ✅ | ✅ | ✅ | ✅ complement | PASS (T2) |
| RAGAS | ✅ | ✅ | ✅ | ✅ complement | PASS (T2) |
| TruLens | ✅ | ✅ | ✅ | ✅ complement | PASS (T2) |
| Evidently AI | ✅ | ✅ | ✅ | ✅ complement | PASS (T2) |
| W&B Weave | ✅ | ✅ | ✅ | ✅ replace | PASS (T2) |
