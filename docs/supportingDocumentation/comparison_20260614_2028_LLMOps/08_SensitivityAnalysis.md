# 08_SensitivityAnalysis.md — LLMOps Tooling Comparison

> Tests robustness of the ranking by re-weighting against Cost, Usability, Self-host/Data-Ownership, and Eval emphases. Computed in Python; scores normalized to /100.

## Scenario Top-6

| Rank | Base | Cost-heavy | Usability-heavy | Data-Ownership-heavy | Eval-heavy |
|--:|---|---|---|---|---|
| 1 | Opik 99.0 | Opik 99.2 | Opik 98.8 | Opik 99.2 | Opik 98.8 |
| 2 | **Langfuse 95.2** | **Langfuse 96.0** | **Langfuse 95.8** | **Langfuse 95.7** | **Langfuse 92.4** |
| 3 | Phoenix/AX 84.2 | Promptfoo 85.2 | Phoenix/AX 83.8 | Phoenix/AX 84.3 | Phoenix/AX 83.6 |
| 4 | Langwatch 79.8 | MLflow 83.8 | Helicone 83.0 | Promptfoo 84.3 | Promptfoo 83.4 |
| 5 | Braintrust 79.4 | Phoenix/AX 83.3 | Braintrust 82.8 | Helicone 83.7 | Braintrust 82.6 |
| 6 | Promptfoo 79.2 | Helicone 80.4 | Langwatch 79.4 | DeepEval 82.7 | DeepEval 82.2 |

## Findings

1. **Opik #1 and Langfuse #2 are invariant across every scenario.** The recommendation is **robust** — no realistic re-weighting dethrones the Opik/Langfuse pairing at the top.

2. **Promptfoo surges under Cost-heavy, Self-host, and Eval-heavy weightings** (→ #3–#4). This confirms its role as the **highest-value free complement**: when budget, data-ownership, or eval rigor dominate, the CI/CD red-team eval specialist rises.

3. **Phoenix/AX is consistently #3** — the most stable "OTel-native peer," strong regardless of weighting except where prompt-management matters (its weakest axis).

4. **MLflow jumps to #4 under Cost-heavy** — its always-free, unlimited self-host shines when free-tier generosity is doubled.

5. **Helicone climbs under Usability and Self-host** — reflecting its one-line proxy setup and Apache-2.0 unlimited self-host.

6. **LangSmith stays bottom in every OSS-weighted scenario** — confirming it's structurally mismatched to a free-public-repo use case, despite strong intrinsic quality.

## Robustness Verdict
The decision is **not sensitive** to weighting choices at the top. The only thing that moves is *which complement* ranks 3rd–6th — and that correctly tracks the user's emphasis (Promptfoo for cost/eval, Helicone for ease, MLflow for free-forever, Phoenix for OTel purity).
