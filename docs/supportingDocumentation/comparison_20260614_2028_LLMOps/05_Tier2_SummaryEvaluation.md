# 05_Tier2_SummaryEvaluation.md — LLMOps Tooling Comparison

> Valid LLMOps tools that are narrower, smaller, or function as metric/complement libraries. Summarized rather than fully scored, but included in the matrix where they compete directly.

| Tool | License / Free | Role | Strength | Weakness vs Opik |
|---|---|---|---|---|
| **Langwatch** | OSS, self-host free; cloud free tier | Observability + eval + **agent simulation** | OTel-native, agent-testing focus, nice UX | Smaller community; younger project |
| **Lunary** | Apache 2.0; cloud free ~1k events/day | Observability + prompt mgmt + analytics | Lightweight, easy self-host, chat replay | Eval shallower; smaller ecosystem |
| **Agenta** | MIT; self-host free; cloud free tier | **Prompt mgmt** + eval + observability | Strong prompt playground/versioning, OSS | Tracing less mature than Opik/Langfuse |
| **PromptLayer** | Closed; free 5 usr/2.5k req/7d | Prompt mgmt + request logging | Good prompt registry, non-eng friendly | Closed; tiny free tier; thin eval |
| **AgentOps** | Closed; free ~1k events/mo (some report higher) | **Agent** session monitoring | Agent-centric replay, multi-agent visualisation | Closed; small free tier; narrow |
| **Latitude** | LGPL-3.0; self-host free | Prompt engineering + agent building | Open, prompt-as-code, eval | More of a build tool; observability secondary |
| **RAGAS** | Apache 2.0; free lib | **RAG eval metrics library** | Gold-standard RAG metrics (faithfulness, recall) | Library only — feeds Opik/others, not a platform |
| **TruLens** | MIT; free lib | **Eval/feedback functions library** | Feedback functions, RAG triad, groundedness | Library only — complements, not replaces |
| **Evidently AI** | Apache 2.0; free lib + cloud free tier | ML + LLM eval/monitoring | 100+ metrics, reports, drift + LLM eval | Broader/heavier; LLM UX less native |
| **W&B Weave** | Closed core; **free for public/personal** | Tracing + eval (LLM module of W&B) | Polished UI, free for public projects, strong experiment lineage | Closed; ties into W&B ecosystem |

---

## Key Tier-2 Takeaways

* **RAGAS** and **TruLens** are **not platforms** — they're metric/feedback libraries. Both integrate *into* Opik (Opik natively lists Ragas as a dataset/eval integration). Use them as **metric providers**, not Opik replacements.
* **Langwatch**, **Lunary**, and **Agenta** are legitimate smaller all-in-one OSS alternatives. Agenta is notable if **prompt management** is the priority; Langwatch if **agent simulation** matters.
* **W&B Weave** is uniquely relevant for a **public OSS repo** because W&B is **free for public/personal projects** — a strong free option if you already use W&B for ML.
* **PromptLayer / AgentOps** are closed with small free tiers — niche complements, not core picks.
* **Datadog LLM Observability** and **New Relic AI Monitoring** have **no genuine free LLM tier** suitable for an OSS repo (APM pricing) → context-only, excluded from scoring.
