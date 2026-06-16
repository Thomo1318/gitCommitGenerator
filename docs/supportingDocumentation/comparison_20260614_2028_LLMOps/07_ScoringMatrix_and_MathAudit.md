# 07_ScoringMatrix_and_MathAudit.md — LLMOps Tooling Comparison

> Arithmetic computed deterministically in Python (per prompt §3.4). Raw CSV provided for external audit. Scores 0–5 per category; weighted total normalized to /100.

## Category Weights (sum = 100)

| Code | Category | Weight |
|---|---|--:|
| C1 | Free-Tier Generosity (OSS/public-repo) | 18 |
| C2 | Core Observability & Tracing | 16 |
| C3 | Evaluation & Testing | 15 |
| C4 | Integrations & OpenTelemetry | 12 |
| C5 | Prompt Management | 8 |
| C6 | Self-Host / Data Ownership | 10 |
| C7 | Migration & Switching Cost (vs Opik; higher = easier) | 9 |
| C8 | Usability & DX | 7 |
| C9 | Community & Maturity | 5 |

## Raw CSV (audit)

```csv
Tool,C1_FreeTier,C2_Observability,C3_Eval,C4_Integrations_OTel,C5_Prompt,C6_SelfHost_DataOwn,C7_Migration,C8_Usability,C9_Community,Score/100
Opik (anchor),5,5,5,5,5,5,5,5,4,99.0
Langfuse,5,5,4,5,5,5,4,5,5,95.2
Arize Phoenix/AX,4,5,4,5,2,4,5,4,4,84.2
Langwatch,4,4,4,5,3,4,4,4,3,79.8
Braintrust,4,4,5,4,4,2,4,5,3,79.4
Promptfoo,5,1,5,4,3,5,5,4,4,79.2
Helicone,4,4,3,4,2,5,5,5,4,79.0
MLflow (GenAI),5,4,3,4,3,5,3,3,5,78.8
DeepEval/Confident,4,2,5,4,2,5,5,4,4,77.2
Agenta,4,3,4,3,5,5,4,4,3,77.0
Traceloop/OpenLLMetry,5,3,1,5,1,5,5,4,4,72.8
Lunary,4,4,2,3,4,5,4,4,3,72.6
W&B Weave,4,4,4,4,3,1,3,5,4,72.0
LangSmith,2,5,4,4,4,1,3,5,5,70.6
```

## Ranked Scoring Matrix (base weights)

| Rank | Tool | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | **Score/100** |
|--:|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|--:|
| — | **Opik (anchor)** | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 4 | **99.0** |
| 1 | **Langfuse** | 5 | 5 | 4 | 5 | 5 | 5 | 4 | 5 | 5 | **95.2** |
| 2 | **Arize Phoenix/AX** | 4 | 5 | 4 | 5 | 2 | 4 | 5 | 4 | 4 | **84.2** |
| 3 | **Langwatch** | 4 | 4 | 4 | 5 | 3 | 4 | 4 | 4 | 3 | **79.8** |
| 4 | **Braintrust** | 4 | 4 | 5 | 4 | 4 | 2 | 4 | 5 | 3 | **79.4** |
| 5 | **Promptfoo** | 5 | 1 | 5 | 4 | 3 | 5 | 5 | 4 | 4 | **79.2** |
| 6 | **Helicone** | 4 | 4 | 3 | 4 | 2 | 5 | 5 | 5 | 4 | **79.0** |
| 7 | **MLflow (GenAI)** | 5 | 4 | 3 | 4 | 3 | 5 | 3 | 3 | 5 | **78.8** |
| 8 | **DeepEval/Confident** | 4 | 2 | 5 | 4 | 2 | 5 | 5 | 4 | 4 | **77.2** |
| 9 | **Agenta** | 4 | 3 | 4 | 3 | 5 | 5 | 4 | 4 | 3 | **77.0** |
| 10 | **Traceloop/OpenLLMetry** | 5 | 3 | 1 | 5 | 1 | 5 | 5 | 4 | 4 | **72.8** |
| 11 | **Lunary** | 4 | 4 | 2 | 3 | 4 | 5 | 4 | 4 | 3 | **72.6** |
| 12 | **W&B Weave** | 4 | 4 | 4 | 4 | 3 | 1 | 3 | 5 | 4 | **72.0** |
| 13 | **LangSmith** | 2 | 5 | 4 | 4 | 4 | 1 | 3 | 5 | 5 | **70.6** |

## Reading the Matrix

- **Opik (99.0)** remains the strongest *unified* tool on this profile — the incumbent is well chosen.
- **Langfuse (95.2)** is the only candidate that comes within striking distance as a **like-for-like replacement**, edging Opik on license permissiveness (MIT) and community, trailing on prompt optimization.
- **Specialists** (Promptfoo 79.2, DeepEval 77.2, Traceloop 72.8) score lower on the *unified* rubric **by design** — they're complements, not all-in-one platforms. Their low C2/C5 scores reflect intentional narrow scope, not weakness.
- **LangSmith (70.6)** ranks last here purely because of the OSS-public-repo weighting (no free self-host, tiny free tier). It would rank far higher on a "LangChain-shop, budget-irrelevant" profile.

> ⚠️ Note: This single leaderboard mixes **unified platforms** and **specialist complements**. Per prompt §4, do not read it as "Promptfoo < Helicone in absolute terms" — read it within role classes. The Final Recommendation (`09`) separates these.
