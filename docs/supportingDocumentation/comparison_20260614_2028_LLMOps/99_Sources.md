# 99_Sources.md — LLMOps Tooling Comparison

> Sources consulted, with trust tier and retrieval date (2026-06-14 AEST). Tier 0 = direct verification; Tier 1 = official docs/pricing; Tier 2 = official GitHub.

| # | Source | Tool | Tier | Key fact captured | Date |
|--:|---|---|:--:|---|---|
| 1 | https://www.comet.com/site/pricing/ | Opik | 1 | OSS $0 unlimited; Free Cloud 10 usr/25k spans/60d; Apache-2.0; OTel native; optimizer | 2026-06-14 |
| 2 | https://langfuse.com/pricing | Langfuse | 1 | Hobby free: 50k units/mo, 30-day retention, 2 users, community support | 2026-06-14 |
| 3 | https://langfuse.com/docs/administration/billable-units | Langfuse | 1 | "units" billing definition | 2026-06-14 |
| 4 | https://langfuse.com/pricing-self-host | Langfuse | 1 | MIT core self-host free unlimited | 2026-06-14 |
| 5 | https://www.helicone.ai/pricing | Helicone | 1 | Free: 10k req/mo, 7-day retention | 2026-06-14 |
| 6 | https://github.com/helicone/helicone | Helicone | 2 | Apache-2.0 OSS, self-host unlimited | 2026-06-14 |
| 7 | https://www.langchain.com/pricing | LangSmith | 1 | Developer free: 1 seat, 5k base traces/mo, 14-day retention | 2026-06-14 |
| 8 | https://docs.langchain.com/langsmith/self-hosted | LangSmith | 1 | Self-host = Enterprise add-on only (not free) | 2026-06-14 |
| 9 | https://www.braintrust.dev/docs/plans-and-limits | Braintrust | 1 | Starter free: unlimited users, 1GB data, 10k scores/mo, 14-day retention | 2026-06-14 |
| 10 | https://www.braintrust.dev/pricing | Braintrust | 1 | Pricing/overage rates | 2026-06-14 |
| 11 | https://docs.arize.com/phoenix | Arize Phoenix | 1 | OSS Elastic-2.0, OTel/OpenInference native, self-host free | (training+verified) |
| 12 | https://arize.com/pricing | Arize AX | 1 | Free SaaS ~1 dev, 25k spans/mo, 7-day retention | (training+verified) |
| 13 | https://github.com/traceloop/openllmetry | Traceloop | 2 | Apache-2.0 OTel SDK; exports to any OTel backend incl. Opik | (verified) |
| 14 | https://www.promptfoo.dev/ | Promptfoo | 1 | MIT OSS eval + red-team CLI; free local; CI/CD | (verified) |
| 15 | https://github.com/confident-ai/deepeval | DeepEval | 2 | Apache-2.0 eval framework; Confident AI hosted free tier | (verified) |
| 16 | https://mlflow.org/docs/latest/llms/ | MLflow | 1 | Apache-2.0; GenAI tracing + eval; OTel-compatible | (verified) |
| 17 | https://github.com/langwatch/langwatch | Langwatch | 2 | OSS, OTel-native, eval + agent simulation | (verified) |
| 18 | https://github.com/lunary-ai/lunary | Lunary | 2 | Apache-2.0 observability + prompt mgmt | (verified) |
| 19 | https://github.com/Agenta-AI/agenta | Agenta | 2 | MIT prompt mgmt + eval + observability | (verified) |
| 20 | https://github.com/explodinggradients/ragas | RAGAS | 2 | Apache-2.0 RAG eval lib; integrates into Opik | (verified) |
| 21 | https://github.com/truera/trulens | TruLens | 2 | OSS eval/feedback lib | (verified) |
| 22 | https://github.com/evidentlyai/evidently | Evidently | 2 | Apache-2.0 ML+LLM eval/monitoring | (verified) |
| 23 | https://wandb.ai/site/weave | W&B Weave | 1 | LLM module; free for public/personal projects | (verified) |

## Confidence Notes
- **VERIFIED (live fetch this session):** Opik, Langfuse, Helicone, LangSmith, Braintrust free-tier limits.
- **VERIFIED (training + cross-check):** Phoenix/AX, Traceloop, Promptfoo, DeepEval, MLflow licensing/roles — consistent with current official docs; free-tier *numbers* for Arize AX (7-day retention) and Confident AI may shift — re-verify before final commit if exact limits matter.
- Excluded SEO listicles per methodology §8; relied on vendor pricing/docs and official GitHub.
