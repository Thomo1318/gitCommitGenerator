# 03_Tier1_DetailedEvaluation_Part1.md — LLMOps Tooling Comparison

> Detailed profiles for Tier-1 candidates (Part 1 of 2). All facts `VERIFIED` against official docs/pricing/GitHub as of 2026-06-14 unless marked `UNKNOWN`. Each is judged on its **role vs Opik** (replace / complement / both).

---

## 0. Opik (Comet) — ANCHOR / INCUMBENT

| Attribute        | Detail                                                                        |
| ---------------- | ----------------------------------------------------------------------------- |
| Role             | All-in-one: tracing + eval + prompt mgmt + optimization                       |
| License (OSS)    | Apache 2.0 — self-host the _same_ codebase as cloud                           |
| Free OSS         | $0, unlimited spans/retention/members, self-host                              |
| Free Cloud       | $0 — 10 members, **25k spans/mo**, 60-day retention, US region                |
| Integrations     | 40+ frameworks (LangChain, LangGraph, CrewAI, ADK…), **native OpenTelemetry** |
| Eval             | 30+ built-in metrics, LLM-as-judge, datasets, experiments, test suites        |
| Prompt           | Library, versioning, playground, **Agent Optimizer** (GEPA/MIPRO/etc.)        |
| Standout         | Prompt _optimization_ algorithms; OpikAssist; guardrails (self-host)          |
| Weakness (Cloud) | 25k spans/mo is modest; 60-day retention                                      |

**Verdict:** Strong, well-rounded OSS-friendly baseline. The bar others must clear.

---

## 1. Langfuse — closest all-in-one OSS peer (REPLACE)

| Attribute          | Detail                                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| Role               | Tracing + eval + prompt mgmt + datasets (all-in-one, like Opik)                                               |
| License (OSS)      | **MIT** core (self-host _all_ features incl. evals/prompts in OSS v3)                                         |
| Free OSS           | $0, **unlimited** events/retention/users, self-host (Docker/K8s)                                              |
| Free Cloud (Hobby) | $0 — **50k units/mo**, **30-day** retention, **2 users**, community support `VERIFIED` (langfuse.com/pricing) |
| Integrations       | LangChain, LlamaIndex, OpenAI, LiteLLM, **OpenTelemetry native**, SDKs (Py/JS)                                |
| Eval               | LLM-as-judge, datasets, experiments, annotation queues, custom scores                                         |
| Prompt             | Strong prompt management + versioning + playground (a Langfuse strength)                                      |
| Standout           | Largest OSS LLMOps community (~10k+ GitHub stars), MIT license, mature                                        |
| Weakness           | Cloud free retention 30d < Opik 60d; optimization not as deep as Opik                                         |

**Verdict:** The strongest **drop-in Opik replacement**. MIT > Opik's licensing for permissiveness; bigger community; self-host unlimited. Slightly behind Opik on prompt _optimization_.

---

## 2. Arize Phoenix / Arize AX — OTel-native OSS peer (BOTH)

| Attribute              | Detail                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| Role                   | Tracing + eval + experiments; OTel-native (built on OpenInference)                                |
| License (OSS, Phoenix) | Elastic License 2.0 (source-available; free self-host, some commercial-resale limits)             |
| Free OSS (Phoenix)     | $0, self-host, unlimited local, runs in a notebook/Docker                                         |
| Free SaaS (Arize AX)   | $0 — ~1 developer, **25k spans/mo**, **7-day** retention `VERIFIED`                               |
| Integrations           | **OpenTelemetry / OpenInference native** — instruments LangChain, LlamaIndex, etc.                |
| Eval                   | Phoenix Evals library (LLM-as-judge, hallucination, RAG relevance), experiments                   |
| Standout               | Best OTel/OpenInference standards alignment; great RAG/embedding visualizations                   |
| Weakness               | Phoenix license = source-available (not OSI); AX free retention only 7 days; no prompt-mgmt depth |

**Verdict:** Excellent OTel-native **complement or replacement** for tracing/eval. License is source-available (weaker than MIT). Pairs naturally with Opik via OTel.

---

## 3. Helicone — OSS gateway + observability (BOTH)

| Attribute     | Detail                                                                                |
| ------------- | ------------------------------------------------------------------------------------- |
| Role          | LLM **proxy/gateway** + logging + cost tracking + caching + observability             |
| License (OSS) | **Apache 2.0** — self-host unlimited                                                  |
| Free OSS      | $0, unlimited self-host (Docker/Helm)                                                 |
| Free Cloud    | $0 — **10k requests/mo**, **7-day** retention `VERIFIED` (helicone.ai/pricing)        |
| Integrations  | One-line proxy (change base URL) OR async SDK; OpenLLMetry/OTel support               |
| Eval          | Lighter eval than Opik/Langfuse; focuses on logging, sessions, scores, experiments    |
| Standout      | Easiest integration (proxy = 1 line); built-in caching, rate-limiting, cost guards    |
| Weakness      | Proxy model adds a network hop; eval/prompt features thinner; cloud free retention 7d |

**Verdict:** Best **low-friction complement** — drop in as a gateway for cost/caching while Opik does deep eval. Can replace Opik for basic observability only.

---

## 4. LangSmith (LangChain) — market-leading closed SaaS peer (REPLACE)

| Attribute        | Detail                                                                                               |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| Role             | Tracing + eval + datasets + prompt hub (tight LangChain/LangGraph integration)                       |
| License          | **Closed-source**. Self-host = Enterprise add-on only `VERIFIED`                                     |
| Free (Developer) | $0 — **1 seat**, **5k base traces/mo**, **14-day** retention `VERIFIED` (langchain.com/pricing)      |
| Integrations     | Best-in-class for LangChain/LangGraph; OTel ingest supported; framework-agnostic SDK                 |
| Eval             | Strong: LLM-as-judge, datasets, online eval, pairwise, annotation                                    |
| Standout         | Deep LangGraph debugging; mature, polished UX; large ecosystem                                       |
| Weakness         | **Not OSS / not self-hostable free**; 1 seat + 5k traces is the tightest free tier here; vendor lock |

**Verdict:** Powerful but the **least OSS-friendly** — fails the spirit of "free on public repo at scale." Only a replacement if you live entirely in LangChain and accept the closed SaaS + tiny free tier.

---

## 5. Traceloop / OpenLLMetry — OTel instrumentation SDK (PURE COMPLEMENT)

| Attribute     | Detail                                                                                                                                              |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Role          | **OpenTelemetry-based instrumentation SDK** — emits standardized GenAI spans                                                                        |
| License (OSS) | **Apache 2.0** (OpenLLMetry SDK)                                                                                                                    |
| Free          | $0 SDK (OSS); Traceloop hosted dashboard has a free tier                                                                                            |
| Integrations  | Auto-instruments OpenAI, Anthropic, LangChain, LlamaIndex, vector DBs → exports to **any OTel backend** (incl. **Opik**, Phoenix, Datadog, Grafana) |
| Eval          | None natively — it's the _pipe_, not the destination                                                                                                |
| Standout      | Vendor-neutral; one instrumentation, swap backends freely; future-proofs against lock-in                                                            |
| Weakness      | Not a destination/UI by itself; you still need a backend (Opik/Langfuse/Phoenix)                                                                    |

**Verdict:** Not a competitor — the **glue**. Use OpenLLMetry to instrument once and ship spans into Opik (or anything). Best anti-lock-in insurance.

---

## 6. Promptfoo — OSS eval & red-team specialist (COMPLEMENT)

| Attribute     | Detail                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------ |
| Role          | **Eval + red-teaming/security testing** CLI + config-driven test matrices                        |
| License (OSS) | **MIT**                                                                                          |
| Free          | $0, 100% local CLI, no account needed; optional Promptfoo Cloud/Enterprise                       |
| Integrations  | Model-agnostic; runs in CI/CD (GitHub Actions); compares prompts/models side-by-side             |
| Eval          | Excellent: assertions, LLM-as-judge, red-team attack suites (jailbreak, PII, etc.)               |
| Standout      | Best **CI/CD + security/red-team** eval; declarative YAML; great for OSS repos (gated PR checks) |
| Weakness      | Not an observability/tracing platform; no live trace UI                                          |

**Verdict:** Best **eval/red-team complement**. Pair with Opik (Opik = observability; Promptfoo = pre-merge eval gate in CI). Ideal for a public repo's PR pipeline.

---

## 7. DeepEval / Confident AI — OSS eval framework + hosted (BOTH)

| Attribute     | Detail                                                                                 |
| ------------- | -------------------------------------------------------------------------------------- |
| Role          | **Pytest-style LLM eval framework** (DeepEval) + hosted platform (Confident AI)        |
| License (OSS) | **Apache 2.0** (DeepEval)                                                              |
| Free          | $0 DeepEval lib; Confident AI hosted has a free tier (limited evals/retention)         |
| Integrations  | Pytest, CI/CD, LangChain/LlamaIndex; 14+ metrics (G-Eval, hallucination, RAGAS-style)  |
| Eval          | Very strong, research-backed metrics; component-level + end-to-end agent eval          |
| Standout      | Developer-first eval-as-unit-tests; integrates as a metric source into other platforms |
| Weakness      | Observability/tracing is secondary; Confident AI free tier limits modest               |

**Verdict:** Best **eval-as-code complement**. Use DeepEval for rigorous metric testing in CI; keep Opik for tracing/observability. Confident AI optional hosted layer.
