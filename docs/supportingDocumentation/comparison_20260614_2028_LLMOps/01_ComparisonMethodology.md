# 01_ComparisonMethodology.md — LLMOps Tooling Comparison

## 1. Objective

Identify and rigorously compare **free/freemium LLMOps tools** suitable for instrumenting an LLM/agent application that lives in a **public open-source Git repository**. Every candidate is judged against the incumbent **Opik (Comet)** — specifically its **Open Source ($0, self-host)** and **Free Cloud ($0 hosted)** tiers. Candidates are evaluated for their ability to **replace** Opik or **complement/augment** it.

## 2. Hard Requirements Gate (Pass/Fail)

A candidate is **eliminated before scoring** if it fails ANY of these:

| # | Requirement | Rationale |
|---|---|---|
| HR1 | Has a genuine **$0 / free tier** (OSS self-host OR free cloud) | Budget constraint; OSS public repo |
| HR2 | Usable on a **public OSS repo at no cost** | Core use case |
| HR3 | Belongs to the **LLMOps domain** (LLM observability / tracing / evaluation / prompt mgmt / agent monitoring) | Scope. Classical-MLOps-only or training-only or cloud-lock platforms are screened out |
| HR4 | Can **replace OR integrate with Opik** (OTel support, SDK, framework hooks) | Must serve the stated goal |

Candidates that fail HR3/HR4 but are notable get a brief "Eliminated — Reason" entry in `02`.

## 3. Recommendation Classes (per prompt §4)

Final outputs will distinguish:
- **Highest Raw Score** (pure math winner)
- **Best Practical Fit** (incl. switching cost + stack friction)
- **Best Unified Option** vs **Best Specialist Option**
- **Best Value / Budget**
- **Best Overall Recommendation** (the decision)

## 4. Evaluation Categories & Weights

Weights chosen for an **OSS public-repo, individual/small-team, self-host-capable** profile. Sum = 100.

| # | Category | Weight | What it measures |
|---|---|--:|---|
| C1 | **Free-Tier Generosity (OSS/public-repo)** | 18 | $0 ceiling: span/trace limits, retention, seats, self-host availability |
| C2 | **Core Observability & Tracing** | 16 | Trace/span capture, agent graphs, sessions, token/cost tracking, multimedia |
| C3 | **Evaluation & Testing** | 15 | LLM-as-judge, datasets, experiments, regression/unit tests, metrics |
| C4 | **Integrations & OpenTelemetry** | 12 | Framework breadth (LangChain, LlamaIndex, CrewAI…), OTel support, model providers |
| C5 | **Prompt Management** | 8 | Prompt library, versioning, playground, optimization |
| C6 | **Self-Host / Data Ownership** | 10 | Can you run it yourself; license (Apache/MIT vs source-available); data residency |
| C7 | **Migration & Switching Cost** (from/with Opik) | 9 | Friction to adopt alongside or instead of Opik; OTel interop; export/lock-in |
| C8 | **Usability & DX** | 7 | Setup speed, SDK quality, docs, UI |
| C9 | **Community & Maturity** | 5 | GitHub stars, release cadence, ecosystem, support |

> Category weights may be overridden in sensitivity analysis (`08`), where we re-test under Cost-heavy, Usability-heavy, and Security/Data-Ownership-heavy weightings.

## 5. Scoring Scale

Each category scored **0–5** (0 = absent/poor, 5 = best-in-class). Weighted score = Σ(weight × score) / 5, normalized to /100. All arithmetic done in **Python** (deterministic, per prompt §3.4) in `07`.

## 6. TCO Standardization

Per prompt §4. Since the use case targets **$0 tiers**, headline TCO for qualifying candidates = **$0/year**. Where a free tier has hard limits that force a paid upgrade at scale, the **first paid tier** is documented for context using:

`Annual TCO = (Min Seats × Cost/Seat × 12) + Base Fee + Mandatory Add-ons`

GST (10%, AU) applied to AUD-converted paid figures where the vendor bills AU customers.

## 7. Stack / Pairing Logic

"Opik + X" pairings are assessed at **stack level** with explicit friction penalties for: context-switching, dual instrumentation overhead, taxonomy mismatch (spans vs traces), and duplicated admin. Covered in `06`.

## 8. Evidence & Trust Rules

- Prefer official docs & GitHub (Tier 0–2). Exclude SEO "Top 10" listicles.
- Mark facts `VERIFIED` / `UNKNOWN` / `QUOTE_REQUIRED`.
- Sources tracked with timestamps in `99_Sources.md`.

## 9. Tooling Confirmed

`rtk`, `fd`, `rg`, `rga`, `python3` all available. Math will be executed in Python; CSV audit block also emitted.
