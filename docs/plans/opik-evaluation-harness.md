# Opik Evaluation Harness — Design & Implementation Plan

> **Status:** v0.9.5 S5/S6/S7 API-surface policy (CLI-first) · v0.9.4 S5 eligibility/availability split (#233 Slice 0) · v0.9.3 S2b clarifications (#227 T1–T12) · v0.9.2 body-residual ingest · v0.9.1 briefing locks · v0.9.0 comment-depth · §14 filing gate complete (Q1=A + #220 S0 filed)  
> **Document class:** formal design + implementation SSOT (promoted from scratch)  
> **Parent epic:** #216 — E2E Observability Stack  
> **Governing issue:** #217 — formalise Opik commit-message evaluation harness  
> **This document:** authoritative living plan for the Opik evaluation harness (S0–S7)  
> **Path:** `docs/plans/opik-evaluation-harness.md`  
> **Related ADRs:** ADR-0010 (Opik telemetry), ADR-0011 (E2E observability stack)  
> **Authority order:** product ranker/SOP/Hybrid/`commit_gold`/`commit_quality`/path-class ▸ ADR-0010/0011 ▸ **gold-miss package** [`docs/quality/`](../quality/README.md) (METHOD · F*/P* · cases) ▸ this plan ▸ #217 governance pointer/comments ▸ vendor Opik docs/skills  
> **#204 / #217 split:** #204 = corpus epic + intake; living gold-miss SSOT = `docs/quality/`. #217 = harness governance index; living harness design SSOT = **this plan**. Do not re-host Session 12 case novels or F*/P* prose in #217.
>
> **Gold-miss package SSOT:** [`docs/quality/README.md`](../quality/README.md) · Session 12 synthesis [`session-12-synthesis.md`](../quality/cases/204/session-12-synthesis.md) · G1 [`session-12.md`](../quality/cases/204/session-12.md)  

---

## 0. Document control

| Field | Value |
|:---|:---|
| Version | `0.9.5-s5-s6-s7-api-surface` |
| Stage | Formal design SSOT · S5/S6/S7 API-surface policy locked (CLI-first; selected `git_cg.eval*` supported; internals internal) · S5 eligibility/availability split + §8.5 spine/residual locks (#233) remain · S2b T1–T12 + body residual + briefing locks remain |
| Location | `docs/plans/opik-evaluation-harness.md` (versioned; was `scratch/0.OpikIntegration/opik.md`) |
| Filled from | #217 body residual (2026-08-13) + #217 (all 26 comments) + full plan compile + owner training-corpus / thread / redaction-ladder approval + comment-depth + live Daily Briefing locks + owner API-surface split (S5 narrow export / S6 operator map / S7 Zensical+ADR) |
| Filled through §14 gate | SSOT pointer in #217 body + Q1=A + S0 filed as #220; implement S0 next |
| Companion artefacts (planned) | optional YAML machine map under `docs/plans/`; optional per-slice briefs |
| Out of scope for this file | Runtime product behaviour changes; Promptfoo deep design (#219); Sentry deep design (#218) |



### 0.5 Live pin honesty (D44 / #233 Slice 0)

Planning text may use `schema_pack_v0@…` / `metric_catalog_v0@…` as **shape** examples. **Live frozen identities** are whatever `just eval-schema-hash` / `tests/eval/test_catalog_pins.py` assert on the current tree (also printed in [`docs/eval/README.md`](../eval/README.md)). After any S5 docs touch that mentions pins, reconcile README ↔ generator output; never leave contradictory concrete hashes unexplained.

### 0.1 How to use this file

1. Keep **§1–§4** stable (mission, locks, decomposition).  
2. Fill **§5+** from existing #217 comments without re-arguing locks.  
3. When a section is ratified, tick its checkbox and note the source comment/date.  
4. File GitHub grandchildren only from **§8 Issue filing plan**, not ad-hoc from chat.

### 0.2 Fill legend

| Mark | Meaning |
|:---:|:---|
| `[ ]` | Not started |
| `[~]` | Drafted in chat / comment; not compiled here yet |
| `[x]` | Compiled into this doc |
| `[R]` | Ratified (design accepted; impl may still be open) |

### 0.3 Working notes (operator / reviewer protocol)

1. **Audience of Opik** — Opik is a **developer / maintainer lab and observability tool**. Basic `git-cg` end users must not need to know Opik exists, install it, configure it, or have it on the accept-path critical path. Product commit UX stays clean; Opik remains opt-in for developers dogfooding, eval, and ops.
2. **Gold-standard challenge protocol** — If during planning or implementation a vendor capability, metric, or workflow would materially improve `git-cg` quality, operability, or correctness but is blocked by an existing lock/law/reject, **do not silently drop it**. Surface a **Finding** with:
   * what the capability is
   * what it would bring to `git-cg`
   * which F#/reject/R-gap blocks it today
   * risks if relaxed or adopted
   * proposed path (new R-item, constitution amendment, sibling pillar, or deferred lab)
   Owner reviews and may authorize a controlled relaxation or amendment before integration.
3. **Default remains hard law** until an explicit authorization is recorded in this plan and/or #217.
4. **AI amend-before-push is the live LLM review gate (operator workflow)** — Every commit message is reviewed by the AI assistant (Raycast AI / agent sessions) and **amended by that assistant before the owner pushes**. In practice the assistant is the interactive LLM-judge / craft blocker for shipped history — **under owner authority**, not as an unattended Opik online rule.
   * This is **not** Opik Lane C, not `commit_gold` product law, and not a hook-time cloud judge.
   * Product deterministic gates (`commit_gold` / `commit_quality` / path-class / Hybrid hooks) still fire in-tool as machine law.
   * Opik builtin judges remain **non-authoritative automation**; they may **inform** the AI amend session (advisory evidence) but must not silently replace either product validators or the owner’s push decision.
   * Eval harness should optimize for: (a) offline regression the assistant/owner can trust, (b) optional advisory packs the amend session can read, (c) never requiring Opik for a basic commit.
5. **High-frequency dogfood GEval ≠ product GEval-on-commit** — During git-cg development, maintainer profiles may run pinned GEval/C′ on every (or sampled) commit as **lab dogfood** (see **R12** / FIND-008). That is allowed and often desirable. What remains banned is the *shape*: default-user / universal / unattended / **sole or product-authoritative** GEval gate on every commit.
6. **Training-corpus mission (CRITICAL — owner 2026-08-13)** — Maintainer dogfood + L2 amend-every-message is not only regression theatre. It deliberately builds a **golden collection of metrics, trajectories, preference pairs, and labeled anti-patterns** for future **training / fine-tuning** of commit models. Opik (owner-pinned project) is a primary **enrichment + longitudinal corpus lake** in addition to local CI SoT. Agents must **not** thin, skip, or refuse enrichment solely because a field is non-gating.
7. **Non-degradation / additive law** — Existing product functionality and existing metrics/telemetry must **not** be degraded. Eval/Opik work is **additive** unless the owner explicitly authorises a replacement sink. New threads, scores, and train fields sit beside current logs.
8. **Commit-session thread (additive UX + corpus)** — Prefer one Opik/local **thread per commit unit of work** spanning start → signals/ranker → drafts → L1 → L2 amend loop → dogfood → owner accept, so humans and agents can open a single thread for the full story. This **adds** to traces/spans/metrics; it does not collapse or remove them.
9. **Owner-chosen redaction ladder** — The owner selects retained payload depth for maintainer sinks (`public_ci` → `train_rich` / `antipattern_vault`). Thin defaults remain for basic users, CI public logs, and unscoped exports. Training intent **may** justify richer bodies/diffs under scrub + pin + scope tags; it never justifies secret leak or making judges product law.
10. **#217 comment-depth contracts (v0.9.0)** — Tracing topology, no-Ollie debug/diagnostics, score placement, config/flush, two-layer export durability, replay lineage, promotion/split laws, and official Opik URL matrix are **first-class plan law** (FIND-019…025). Comments written before R11–R14 are reanalysed under current relaxations (see §18.1); agents must implement from **this document**, not from raw issue comments.
11. **Live Opik Daily Briefing locks (v0.9.1)** — Current cloud “quality collapse” symptoms (empty-output ×N evaluator errors; near-zero `header_length_ok`/`has_body`; stale cloud experiments vs prompt churn; acceptance≫format gap) are treated as **live Opik-plane misconfiguration / wrong scored artifact**, not evidence that Hybrid/SOP product law is wrong. Fixes land naturally as S2–S6 evaluation-suite work (FIND-026…028, §18.13). **Do not** relax 72-char/body/SOP thresholds from unbinding online scores.
12. **#217 issue-body residual (v0.9.2)** — The original GitHub #217 **body** (pre-R11–R14) remains a primary source for **scaffold indictment, Regime A/B teaching, Session-12 seed requirements, #204 provenance/ID namespaces, and operator “what good looks like.”** Living design law is **this plan**; the issue body is governance + executive index. On conflict: **this plan ▸ #217 body ▸ comments**. Body-era absolute “thin export / regen-only thread / mirror-only forever” readings are superseded by R13/R14/dual-axis (§18.1, §18.14).
13. **API-surface policy (v0.9.5)** — **CLI-first:** the CLI is the primary public API; selected `git_cg.eval*` entrypoints are **supported** maintainer/harness APIs; product implementation modules remain **internal**. No general-purpose Python SDK; no REST/OpenAPI; no external API-doc services. **S5** ships only the narrow harness-facing surface; **S6** defines the operator API map + help alignment; **S7** preserves the decision in durable Zensical/ADR docs (optional allowlist autodoc only). See §8.5–§8.7 and **RS17**.


### 0.4 #217 comment-depth integration checklist (v0.9.0)

> **Rule:** every row below is design-integrated into this plan. Implementation remains S0–S7.  
> **Sources:** #217 comments 04–26 (pre-R11–R14 wording reanalysed under current floor) + live Opik Daily Briefing (dated §18.13).  
> **Marks:** `[x]` = compiled here · `PARK` = deferred non-MVP · `REJ` = explicit non-import.

#### 0.4.1 Master checklist

| ID | Item | Pri | Plan loci | Status |
|:---|:---|:---:|:---|:---:|
| INT-01 | Trace/span/thread topology contract + closed span taxonomy | P0 | §2.9, §6.9b Family I, §7.2.12 | [x] |
| INT-02 | Family I topology/lifecycle metrics | P0 | §6.9b, §6.11, S2 | [x] |
| INT-03 | R13 glossary supersession (full session thread ≠ regen-only) | P0 | §2.9, §3 R13, §7.2.10 | [x] |
| INT-04 | Thread continuity / settlement / contamination metrics | P0 | §2.9, §6.9b | [x] |
| INT-05 | No-Ollie debug loop FIND→EXPLAIN→COMPARE→REPLAY→PROMOTE→VERIFY | P0 | §8.6, §18.3 | [x] |
| INT-06 | `eval explain/compare/replay/promote/failures` command contracts | P0 | §8.6, §18.3 | [x] |
| INT-07 | `diag_issue_v1` + deterministic fingerprints | P0 | §7.2.13, §18.4 | [x] |
| INT-08 | `eval diagnose` + issue list/show/resolve/reopen/suppress | P0 | §8.6, §18.4 | [x] |
| INT-09 | `git_cg_opik_config_v1` modes/projects/env/flush | P0 | §7.2.14, §10.6, §18.5 | [x] |
| INT-10 | Bounded hook flush + fail-open export (never block accept) | P0 | §10.6, §18.5 | [x] |
| INT-11 | No silent Default Project; lane projects live/eval/ci/import | P0 | §10.6, S4 | [x] |
| INT-12 | `eval opik doctor` + `opik config show` (secret-safe) | P0 | §8.6, FIND-003 extended | [x] |
| INT-13 | Score/annotation placement matrix (trace/span/thread/artifact) | P0 | §6.1b, §18.6 | [x] |
| INT-14 | SCORE-POLARITY foot-gun + STRUCT-LOCAL (reject Opik LLM SOC as law) | P0 | §5.3, §6.0 M1, §6.13 | [x] |
| INT-15 | Correlation envelope + cross-hook finalization (no live child-span assume) | P0 | §7.2.15, S3 | [x] |
| INT-16 | Two-layer durability (Layer A bundle SoT vs SDK SQLite secondary) | P0 | §10.7, §18.7 | [x] |
| INT-17 | Export health field set (deferred/replay/pending/config errors) | P0 | §6.9 H ext, §10.7 | [x] |
| INT-18 | Replay lineage + `replay_compare_v1` | P1 | §7.2.16, §18.3 | [x] |
| INT-19 | First-party `.eval/export_queue` + export status/retry/drain | P1 | §7.1 layout, §8.6, §10.7 | [x] |
| INT-20 | Failure→fixture/corpus promotion state machine | P1 | §7.3, §18.8 | [x] |
| INT-21 | `split_group_id` contamination law (prefs/replays/antipatterns) | P1 | §7.3.1, FIND-024 | [x] |
| INT-22 | JUDGE-INPUT / expected isolation harness tests (F6 strengthen) | P1 | §2.1 F6, §7.0, S1/S5 | [x] |
| INT-23 | AGG-GATE (aggregates cannot hide per-item hard fails) | P1 | §6.11, §18.9 | [x] |
| INT-24 | Experiment/dataset pin matrix (DS-VER; no `latest`) | P1 | §7.2.x, §18.9 | [x] |
| INT-25 | Declared pipeline graph `git_cg_pipeline_graph_v1` | P1 | §7.2.17, Family I | [x] |
| INT-26 | Prompt pack identity `prompt_pack_v1` (repo SoT; no cloud latest) | P1 | §7.2.18, H pins | [x] |
| INT-27 | Operator E-LOOP SOP + Suite vs Dataset vs Experiment authority | P1 | §18.2 | [x] |
| INT-28 | LLM usage/cost/latency metadata on `llm_generation` (advisory) | P1 | §10.1.5, S4/S5 | [x] |
| INT-29 | Report headers + local `.eval/index|diagnostics|issues|replays` | P1 | §7.1 layout, §18.3 | [x] |
| INT-30 | Official Opik reference matrix (dated) FIND-025 | P1 | §5.7 / Appendix C | [x] |
| INT-31 | Worked APC Session-12 topology-fail example | P1 | §18.10 | [x] |
| INT-32 | FIND-019…025 logged + owner disposition table | P0 | §17 | [x] |
| INT-33 | Slice S0–S7 AC/deliverable deltas for all above | P0 | §8 | [x] |
| INT-34 | Historical supersession table (pre-R11–R14 comment ideas) | P0 | §18.1 | [x] |
| INT-35 | Explicit non-import list from comments | P0 | §18.11 | [x] |
| INT-36 | Blame-span → code surface static map | P2 | §18.4 | [x] |
| INT-37 | Without-Ollie boundary box (agent-facing) | P2 | §18.11, §11 | [x] |
| INT-38 | Thread secondary scores (chain_complete etc.) advisory | P2 | §6.9b | [x] |
| INT-39 | Local experiment CLI semantics (variant×suite) | PARK | §18.12 | PARK |
| INT-40 | Optional headless `opik endpoint` | PARK | §18.12 | PARK |
| INT-41 | Optimizer algorithms / Studio control plane | REJ | F8, §18.11 | REJ |
| INT-42 | Ollie / Playground as control plane | REJ | F8, §18.11 | REJ |
| INT-43 | Webhook/alert routing on fingerprints | PARK | §18.12 | PARK |
| INT-44 | Synthetic Expand-with-AI quarantine law | P2 | §18.8 | [x] |
| INT-45 | METRIC-SPLIT builtin inventory pointer | P2 | §5.3 / §18.6 | [x] |
| INT-46 | EMPTY-OUT / ERR-FANOUT precondition (no N× evaluator exception storms) | P0 | §18.13, FIND-026, S2/S4/S6 | [x] |
| INT-47 | ARTIFACT-BIND-LIVE — online metrics score final message / product `score_card` only | P0 | §18.13, FIND-027, S2/S3/S4 | [x] |
| INT-48 | ACCEPT-GAP-NO-SOP-RELAX — acceptance≫format triggers binding investigation | P0 | §18.13, F3/F1, S6/S7 | [x] |
| INT-49 | OVERSIZE-EVAL-GUARD — max payload; no LLM-judge 504 retry storms | P1 | §18.13, FIND-026, S4/S5 | [x] |
| INT-50 | PROMPT-DRIFT-WITHOUT-SUITE — cloud prompt churn without local suite pin is doctor-red | P1 | §18.13, FIND-028, S6/S7 | [x] |
| INT-51 | ONLINE ≠ PRODUCT CARD — forbid dual format authorities on different strings | P0 | §18.13, FIND-027, S2/S4 | [x] |
| INT-52 | Live Daily Briefing evidence box (dated, non-authoritative) | P1 | §18.13 | [x] |

#### 0.4.2 Comment → integration map

| #217 comment | Integrated as |
|:---|:---|
| 01–03 meta/CodeRabbit/predecessor | No design delta (context only) |
| 04 Tracing Concepts | INT-01,02,15,28, Family I |
| 05 Debug Agents w/o Ollie | INT-05,06,18,20,36 |
| 06 Diagnostics w/o Ollie | INT-07,08,36 |
| 07 Log Traces | INT-01,09–12,15,17,28 |
| 08 Log Conversations | INT-03,04,38 (reanalysed under R13) |
| 09 Log Agent Graphs | INT-25 |
| 10 Annotate Traces | INT-13,45 |
| 11 SDK Configuration | INT-09–12 |
| 12 Offline Fallback & Replay | INT-16,17,19 |
| 13 Agent Playground | INT-05,37,42 REJ control plane |
| 14 Prompt Playground | INT-39 PARK / experiment semantics notes |
| 15 Prompt Library | INT-26 |
| 16 Optimizer | INT-41 REJ; objective-vector ship notes only |
| 17 Evaluation Docs Set | INT-18,22,24,27 |
| 18 Metrics Overview | INT-14,45 (polish) |
| 19 Agents/Threads/Halu/Mod | INT-22,04,25 |
| 20 Eval Overview | INT-20,27 |
| 21 Eval Docs Batch | INT-20–24,44 |
| 22–23 Metrics Docs Review | INT-14,23,45 |
| 24–25 Full inclusion maps | Already §5; INT-30 matrix |
| 26 R-register appendix | Historical; live R1–R14 in §3 supersede |


---

## 1. Mission & non-goals

### 1.1 Mission

[x] Compiled from #217 summary.

Formalise a **first-class Opik-backed evaluation harness** for generated commit messages as the Opik pillar of epic **#216**.

The harness scores the **real accepted final message** against product authorities with stable failure taxonomy, provenance, offline reproducibility, and an optional non-blocking Opik mirror/**owner corpus lake**. It converts the #204 failure-analysis archive, current Opik/eval scaffold, and ratified inclusion maps into durable evaluation architecture, schema, metric catalog, dataset strategy, and slice plan.

**Critical co-mission (owner):** high-frequency maintainer dogfood + L2 amend-before-push builds a **training-grade golden corpus** (metrics, commit-session threads, message version/preference pairs, trajectory evidence, labeled anti-patterns) for later model training/fine-tuning. **Gate authority** and **corpus retention** are separate axes — recording enrichment is encouraged; sole-LLM product gating remains banned.

**#217 itself is design-first.** This plan compiles that design into filable implementation grandchildren. Neither document implements product behaviour alone, weakens gold-strict, degrades existing product behaviour, or makes LLM judges authoritative.

### 1.2 One-line diagnosis

[x] We have an Opik scaffold and deep #204 forensic evidence, but not yet a formal evaluation system that scores the real accepted final message against product authorities with stable failure taxonomy, provenance, and offline reproducibility.

### 1.3 In scope

[x]

* Opik-lane architecture lanes **A–C** (and explicit non-ownership of D/E)
* `ape_bundle_v1` as canonical evaluation object
* Local-first dataset/corpus SoT + optional Opik mirror
* Metric catalog v0 with dual plane (authoritative A–H vs secondary C′/human.*/lab)
* #204 regime A/B + provenance + failure/prevention IDs as corpus law
* Golden promotion stricter than `user_acceptance`
* Full vendor evaluation-suite inclusion map (core + metrics + agents/threads + H/M cookbooks)
* Controlled relaxations register **R1–R14** under hard floor **F0–F9** (incl. session thread + train ladder)
* Implementation slice plan S0–S7 as #217 grandchildren
* Skills policy for `.agents/skills/opik` and `.agents/skills/instrument`
* Telemetry field/score catalog posture and **owner redaction ladder** for eval/train sinks
* **Training-corpus plane**: commit-session threads, preference pairs, train labels, anti-pattern vault, local `train_export_v1`
* ADR/docs alignment expectations (S7), especially ADR-0011 eval layer rewrite

### 1.4 Out of scope / non-goals

[x]

* Runtime product behaviour change from design-only closure of #217
* Weakening gold-strict or skeleton provenance law
* Making GEval / online / builtin LLM judges authoritative
* Prompt optimizer loops / Ollie auto-edits as ship authority
* Replacing pytest unit/corpus tests
* Merging Promptfoo into commit-acceptance scores (**#219**)
* Using Sentry as quality score bus (**#218**)
* Broad cloud payload expansion / raw diff logging **without owner profile + scrub** (owner `train_rich` is explicit, not ambient default)
* Degrading existing product functionality or stripping existing metrics to “simplify” Opik
* Refusing non-gating enrichment that would improve the training/dogfood corpus
* Full historical re-litigation of closed #118/#119 beyond supersession notes
* One GitHub issue per Opik doc page
* Treating vendor skills as architecture SSOT

### 1.5 Success definition (design vs implementation)

| Layer | Done means |
|:---|:---|
| Design (#217) | Locks + catalogs + maps ratified in **this plan**; #217 body points at path+version; no code required to close design |
| This plan doc | Findings compiled (incl. body residual pedagogy); issue graph filable without re-debate; §14 checklist green |
| Implementation | Grandchildren S0–S7 ship; Opik pillar of #216 advances without authority inversion |

### 1.6 Operator “what good looks like” (from #217 body; normative intent)

These are **design/pilot success pictures**, not alternate product law:

1. Offline suite reproduces Session-12 **Regime A and B** without LLM/network.
2. Final rendered accept-path message bytes are the primary scored product artifact.
3. Historical **`Opik-unbound`** evidence is importable and explicitly labeled (never fake-bound).
4. Gold counter / findings / blocked / regen integrity failures are machine-detectable.
5. Empty `path_class_gate` + green shallow score-card **cannot** become golden.
6. Semantic judges **cannot** greenlight a deterministic-illegal envelope.
7. Experiments compare raw vs gold vs post-fix with pinned engine/prompt/harness/catalog versions.
8. Optional Opik REST/bulk export is projection-only, batched, idempotent, size-bounded (default **≤4MB**/batch), non-blocking.
9. Maintainer train/dogfood enrichment may be rich under R14 without becoming gates (dual axis).
10. Basic users never need Opik installed, configured, or healthy to commit.

---
## 2. Authority model & hard floor

> Nothing below §5 may contradict this section.

### 2.1 Non-negotiable floor (F0–F9)

| ID | Floor | Statement |
|:---|:---|:---|
| F0 | Local SoT | Local `ape_bundle_v1` / fixtures / JSONL are **CI, offline regression, and golden-promotion** authority. Opik datasets/experiments/scores are optional non-blocking **mirror + owner longitudinal/training corpus lake** — never CI sole green and never a reason to strip local fields. |
| F1 | Primary artifact | Primary **product-law** scored artifact = **final rendered accept-path message** (exact accept-path / `COMMIT_EDITMSG` final bytes). Never silently mix raw/mid/final/live-regen classes in one unlabeled score stream. **Secondary declared inputs** (plan, trajectory, staged paths, message_versions) may be scored/stored under explicit `input_artifact` / train fields without becoming Hybrid accept law. |
| F2 | Product authorities | Ranker + SOP + Hybrid + `commit_gold` + `commit_quality` + path-class/contract remain accept/semantic law. Eval metrics **wrap** them; they do not fork parallel regex/prompt law. |
| F3 | Judges non-authoritative | All LLM-as-judge / vendor builtin semantic metrics / NL test-suite assertions are Lane C′ / lab / advisory unless a separate constitution amendment re-ratifies gating. They cannot solely pass CI, accept-path, or golden promotion. |
| F4 | Non-blocking Opik | Export, flush, UI, cloud, or judge-provider failure must **never** block `git commit` / accept-path success. |
| F5 | No live/CI `latest` | Accept-path, hooks, and CI suites always pin harness, metric catalog, prompt-pack/hash, engine/model, suite/dataset snapshot; judge pins if Lane C/lab ran. Unpinned cloud float forbidden on those paths. |
| F6 | Gold / expected isolation | Expected outputs, assertions, and gold must **never** enter generation task input. Lane C judge input stays gold-blind except in explicitly labeled `judge_meta_eval_v1` envelopes. **Harness tests (JUDGE-INPUT / INT-22)** must prove isolation for generation *and* default Lane C paths. |
| F7 | Plane separation | Promptfoo = **#219** (Lane D assert/red-team). Sentry = **#218** (Lane E crash/ops). Opik eval = **#217** (Lanes A–C + mirror). Do not collapse gates or score buses across pillars. |
| F8 | No Ollie / optimizer ship authority | No Ollie as required authoring/diagnosis path. Optimizers deferred; ship only via git-pinned prompt packs + suite green — never UI save / library latest / auto-apply. |
| F9 | Slice order | Authoritative offline A/B (S0–S2/S3) before Lane C / judge lab (S5) and before trusting mirrors as operator UX (S4). Design-first on #217; implementation via grandchildren only. |

**Amendment rule:** weakening any F0–F9 is a constitution change, not a Slice PR and not an R-item.

**Product non-weaken (from #217 body):** Gold remains a **validator**. Do **not** weaken `GOLD_SKELETON_FALLBACK_FINAL` / skeleton provenance law to chase online scorecards. Evaluation must detect when gold counters/findings/blocked/regen state disagree with the final rendered message (Family D + Family I counters).

### 2.2 Lane model

```text
Product authorities (ranker/SOP/Hybrid/gold/path-class)
        │ consume, never fork
        ├─ Lane A: Deterministic offline fixture eval (authoritative regression)
        ├─ Lane B: Accept-path / trace-bound eval (binding + counter integrity)
        ├─ Lane C: Secondary semantic LLM cohort (gated, non-authoritative)
        │
        │  (siblings under #216 — not owned by #217)
        ├─ Lane D: Promptfoo assert/red-team          → #219
        └─ Lane E: Sentry crash/ops                  → #218
                 │
                 ▼
     Local bundles/JSONL ──mirror──▶ Opik datasets/experiments/scores
```

Locked architecture decisions (from #217 D-set / body):

1. Design-first on #217; implementation via grandchildren/slices after ratification  
2. Milestone home via parent #216  
3. Primary scored artifact = accept-path bundle / final rendered message  
4. Local fixture/bundle first; Opik mirror second  
5. LLM judge = secondary gated cohort only  
6. Deterministic product validators are metric engines  
7. #204 taxonomy is first-class corpus law  
8. Promptfoo remains separate from commit-acceptance metric semantics  
9. Sentry remains ops/crash, not high-cardinality quality score bus  
10. Optimizer loops deferred until golden corpus + binding integrity trusted  
11. Privacy/redaction bounds: no unbounded raw diffs/prompts/secrets as default cloud payloads  
12. Opik availability/export/flush must never block commit acceptance  
13. No Ollie as required/authoritative authoring or diagnosis path  
14. No unpinned Opik `latest` for CI/accept-path  
15. Expected outputs/assertions/gold must never be merged into actual task input  
16. Valid final message + incomplete evidence = product pass + accept-path observability/eval failure  

### 2.3 Aggregate gates

| Gate | May LLM/heuristic builtins participate? |
|:---|:---|
| `gate.deterministic_pass` | **No** — Families A–H **and Family I (topology/lifecycle harness law)** / product wrappers only. No C′/GEval/human/R10. |
| `gate.semantic_cohort_eligible` | **Entry only** after deterministic classification; enables Lane C, does not pass product |
| `gate.golden_promotion_eligible` | **No LLM-only path** — binding + schema + deterministic + path-class/gold consistency (+ weak live acceptance signal) |
| Commit accept-path success | **Never** depends on Opik judges, export, or cloud health |
| CI offline suite (Lane A/B) | Judges **not required**; deterministic only |
| Lane C / judge lab jobs | Optional, non-blocking, pinned, advisory |

### 2.4 Golden promotion minimum

```text
binding complete
AND bundle schema valid
AND deterministic gates pass
AND path-class/gold consistency pass
AND user_acceptance high (if live-origin; weak signal only)
→ golden eligible
```

`user_acceptance` alone never promotes. Popularity ≠ correctness (Regime B can look perfect).

### 2.5 Score authority matrix

| Source | May fail product accept? | May sole-promote golden? | Role |
|:---|:---:|:---:|:---|
| Deterministic product wrappers (Families A–H) | Yes (eval/CI law) | Required | **Law** |
| Harness/binding health (Family H / binding) | Yes as eval fail | Required | **Law** |
| Trace topology / lifecycle (Family I) | Yes as **eval/CI / golden-eligibility** fail; does **not** alone mean Hybrid prose fail | Required for bound accept-path golden | **Harness law** |
| Export / config health (`export.*`) | No (export class only) | No | Projection health |
| Lane C LLM judges / R1 / R8 | No | No | Advisory |
| NLP heuristics R10 | No | No | Diagnostic |
| Judge meta-eval R2 | No | No | Lab calibration |
| Human `human.*` / R4 | No | No | Adjudication aid |
| Moderation/compliance ops R6 | No | No | Review/ops flag |
| Opik mirror/export R3 | No (export class only) | No | Projection / owner corpus lake |
| Trajectory/span evidence R7 | Supports A/H; not semantic override | No sole semantic yes | Evidence + train feature |
| Commit-session thread R13 | No | No | Additive readability / join key |
| Train corpus plane R14 | No | No | Retention profile + labels only |

Every secondary score should carry equivalent of `source=…` and `authority=advisory` (or stronger local enum).

**Record ≠ gate (M11):** advisory/lab/train features may be **emitted and retained** whenever the owner profile allows — including on L1 fail rows for hard-negatives — without entering `gate.deterministic_pass` or sole golden promotion.

### 2.6 Live review stack (who blocks what)

| Layer | Who / what | When | Authority | Notes |
|:---|:---|:---|:---|:---|
| L1 Product validators | `commit_gold` / `commit_quality` / path-class / Hybrid hooks / ranker+SOP | generate + hook / accept-path | **Machine product law** | Must remain automatable offline; no Opik required |
| L2 AI amend-before-push | AI assistant reviews & amends message with owner before `git push` | pre-push operator workflow | **Interactive review under owner authority** | De-facto LLM craft/semantic blocker for *shipped* history; not an Opik rule; not unattended |
| L3 Owner push decision | Owner | push / PR | **Final human authority** | Can override assistant amend; assistant does not force-push |
| L4 Opik Lane C / builtins | Optional dev judges, dashboards, meta-eval | offline / dogfood lab | **Advisory only (F3)** | May feed L2 as evidence packs; never sole CI/accept/golden gate |
| L5 HITL queue `human.*` | Structured local review items | dispute / regression intake | Advisory adjudication aid | Must not sole-promote golden |
| L6 Opik mirror/export | REST/UI | after local precompute | Projection only | Dev-only; non-blocking |

**Implications for the harness:**

* Do **not** model “LLM judge” as absent — it exists at **L2** (assistant amend workflow).
* Do **not** collapse L2 into Opik online G-Eval/Hallucination rules (different trust boundary, credentials, blocking semantics, reproducibility).
* Design eval artifacts so L2 can consume them: compact failure IDs, family scores, regime tags, counter mismatches, optional C′ rationales, optional last-N GEval attachments — without requiring Opik UI uptime (**R11**).
* Unattended CI/offline Lane A/B must still catch Regime A/B without the assistant present (assistants are not a substitute for fixture regression).
* **Maintainer dogfood** may run high-frequency Lane C GEval/C′ (**R12**) as advisory/async/sample/always — this is continuous lab signal, not a second product blocker.
* **Anti-pattern (narrow):** product-plane, universal, unattended, sole-authoritative “GEval on every commit.”  
  **Not an anti-pattern:** dev-plane, opt-in, pinned, budgeted, non-sole GEval-on-commit while building git-cg.
* **Training co-mission:** L2 amend sessions should leave durable **message_versions / preference pairs** and a **commit_session_thread** join key even when Opik UI is down (local first).

### 2.7 Three-tier commit review (refined)

| Tier | Scope | Frequency | Authority |
|:---|:---|:---|:---|
| **T1 / L1** | All users, all commits | Always | Hard product law (`commit_gold` / quality / hooks / SOP) |
| **T2 / L2** | Owner + AI amend-before-push | Always (this project’s shipping workflow) | Interactive review under owner authority |
| **T3 / L4-dev** | Maintainer / dogfood profile only | `off` \| `sample` \| `always` \| `async` (R12) | Advisory lab; may soft-warn after budgets proven; never sole greenlight; never default-user |

**Preferred dogfood shape while building eval stack:** `always` + `async` + advisory → attach into next **amend-brief** (R11).  
**Sync warn** only if measured overhead fits budget (see R12).  
**Sync hard-block** is dev-only and explicit — not a silent default, not CI sole-fail without flake policy.

### 2.8 Dual axis: gate authority vs corpus retention

| Axis | Question | Hard rule |
|:---|:---|:---|
| **Gate** | May this fail product accept / sole-promote golden / sole CI green? | Deterministic product wrappers + hooks only; judges/export never sole |
| **Corpus** | May this be stored for dogfood, Opik lake, train export, anti-pattern sets? | **Owner profile + pins + scrub**; prefer completeness for maintainer train mission; additive fields |
| **UX** | May basic-user commit path change? | No degradation; Opik/train off by default for basic users |
| **Readability** | How do humans/agents review one commit end-to-end? | Additive **commit_session_thread** + existing traces/metrics |

```text
gate.deterministic_pass     ⊂  product law          (narrow)
corpus.train_row_eligible   ⊃  pass ∪ fail ∪ pairs  (owner-configured; labeled)
opik_owner_lake             ⊇  scrubbed train rows  (non-blocking projection)
```

---

### 2.9 Normative glossary & identity contract (FIND-019 / R13)

| Term | Meaning | Must not mean |
|:---|:---|:---|
| `session_thread_id` | Full **commit unit of work** (R13): start → signals/ranker → drafts → L1 → L2 amend → dogfood → accept | Chat-bot conversation; sole quality gate |
| `thread_subchain_id` | Optional regen / L2-amend sub-chain under a session thread | The only thread key (supersedes pre-R13 “regen-only thread”) |
| `trace_id` | One generation / accept / replay / finalize **attempt** | An entire multi-day dogfood project |
| `span_id` | One lifecycle step inside a trace (closed taxonomy §6.9b) | One internal Python helper unless it is a named stage |
| `bundle_id` / `bundle_hash` | Local `ape_bundle_v1` identity (Layer A SoT) | Opik cloud id alone |
| `replay_of_trace_id` / `replay_of_bundle_hash` | Lineage to the source attempt/bundle | In-place mutation of history |
| `message_version_id` | One draft/amend/owner/final message version | Soft ephemeral UI buffer only |
| `preference_pair_id` | Chosen/rejected pair under a session | Unlabeled A/B noise |
| `split_group_id` | Contagion unit for train/test splits (case/session family) | Per-row random split that separates pairs |
| `diag_fingerprint` | Stable hash inputs for issue clustering (no raw text/ids) | Opaque LLM cluster id |
| `project_lane` | `live` \| `eval` \| `ci` \| `import` Opik/local project partition | Ambient “Default Project” |
| `environment` | `development` \| `dogfood` \| `ci` \| `eval` \| `staging` \| `production` | Free-text only tags |
| Layer A | Local durable bundle/scores/topology/correlation | SDK temp SQLite |
| Layer B | Optional Opik SDK offline SQLite park/replay | Accept-path evidence SoT |
| `provenance_label` | Closed #204/body enum for message/evidence origin (§7.4.2) | Free-text blog provenance only |
| `Opik-unbound` | Explicit label: no trustworthy Opik bind for this case | Silent missing trace treated as bound |

**Topology (normative):**

```text
commit_session_thread_v1
└── commit_attempt_trace          # one attempt
    ├── diff_extraction
    ├── path_classification
    ├── intent_ranking
    ├── contract_resolution
    ├── llm_generation            # type=llm; usage optional
    ├── plan_normalisation
    ├── gold_evaluation
    ├── presentation_guard
    ├── regeneration              # 0..N
    ├── fallback
    ├── final_render
    ├── accept_path_finalization  # may be correlation-linked across hooks
    └── opik_export               # best-effort; never blocks accept
```

**Invariants:**
1. One root trace per attempt; unrelated commits never share `session_thread_id`.
2. A session thread may contain many attempt traces (incl. replay).
3. Replay keeps `session_thread_id`, creates new `trace_id` + bundle, sets replay lineage fields.
4. Cross-hook processes use **correlation envelope** (§7.2.15); do not assume live parent/child spans across process death.
5. Root terminal states: `ok | product_error | export_error | cancelled`. Missing terminal ⇒ `i.lifecycle_complete=0`.
6. Product failure and export failure remain distinct failure classes (§10.3).
7. Thread-level scores are secondary; they never override Families A–H message law.

## 3. Controlled relaxations (R-register only)

> Constitution stays hard. Only listed R-items may add secondary/lab/operator flexibility.

### 3.1 Activation rules

A controlled relaxation may ship only if **all** hold:

1. **ID referenced** in the grandchild issue / PR (`Relaxation: R#`)  
2. **Floor F0–F9** explicitly preserved in the PR description  
3. **Default/off posture** honored unless the issue flips a documented flag  
4. **Pins present** in experiment/suite config when any model/prompt/judge/dataset is involved  
5. **Authority mark** set on scores: `source=llm_judge|human|heuristic_diag|…` and `authority=advisory` (or equivalent)  
6. **Failure class separation** preserved: product fail ≠ eval harness fail ≠ export fail ≠ lab fail  
7. **No silent gate promotion** — moving any R-item toward gating requires a new ratified constitution amendment, not a drive-by PR  

**Rollback:** each R-item must be flag- or entrypoint-killable without breaking Lane A/B offline suites. Turning an R-item off must not rewrite historical local bundles (scores may be absent/null). If an R-item causes false-green pressure, disable first, amend second.

### 3.2 Register R1–R14

| ID | Relaxation | Why allowed | Still locked | Slice | Default | Status |
|:---|:---|:---|:---|:---:|:---:|:---:|
| **R1** | Richer Lane C rubric pack (G-Eval, usefulness, answer relevance, meaning-match, optional hallucination-like narrative) on deterministic-pass / explicitly eligible cohorts | Residual prose/diagnostic signal after product gates | Non-gating · pinned judge/prompt/model · no golden sole authority · no override of deterministic fail | 5 | **off** | [x] drafted |
| **R2** | Offline `judge_meta_eval_v1` lab (HaluEval-style / moderation-corpus: run judge → Equals vs label → FP/FN) | Measures secondary-judge fallibility before dashboard trust | Offline only · labeled meta-eval envelope · expected labels not product gates · Lane A/B still zero judge credentials | 5–6 | **off** | [x] drafted |
| **R3** | Richer Opik mirror / owner corpus-lake export (datasets, experiments, side-by-side, **commit_session threads**, REST) under **owner redaction ladder** | Operator visibility + training-grade longitudinal store without moving CI SoT | Local precompute first · batched/idempotent · export failure = export class only · project/lane pinned · scrub always · owner chooses profile | 4 | maintainer on when train/dogfood on; users off | [x] **amended** 2026-08-13 |
| **R4** | Deeper local HITL annotation (multi-rater `human.*`, craft/gold dispute dimensions, review queue UX) | Better adjudication of borderline craft/gold cases | Human scores non-overriding · cannot sole-promote golden · local queue SoT; Opik queue mirror optional later | 6 | local-first | [x] drafted |
| **R5** | Lab-only dirty overlays (`config_dirty` prompt/model/param overlays not shipped) | Fast prompt/judge research without touching live pins | Never on accept-path/hooks/CI green path · every trial stamps dirty provenance · promote only via git pack bump | 5–6 | lab only | [x] drafted |
| **R6** | Optional moderation / compliance-risk ops signal (review flag / dashboard), scrubbed | Safety review adjacency without Hybrid pollution | Not default Lane C cohort member · never accept/Hybrid gate · scrubbed payloads · prefer #219 for red-team depth | 5–6 / #219 | **off** | [x] drafted |
| **R7** | Accept-path trajectory/span/graph metrics (declared vs observed stages, recovery-poison visibility) | Regime A/B observability + train features | Not generic agent-tool mythology · not conversation-coherence gates · supports Families A/H + binding · **additive** spans under session thread | 2–3 | **on** for maintainer train/dogfood profile; off basic users | [x] **amended** 2026-08-13 |
| **R8** | Lane C flakiness studies (`runs_per_item`, stability thresholds) | Quantify judge variance | Results cannot alone pass product gate or promote golden · pinned cohort/snapshot | 5 | lab only | [x] drafted |
| **R9** | Cohort filters / `nb_samples` for triage & lab subsets | Faster debug loops | CI SoT remains full pinned suite snapshot · filters never silently redefine golden corpus | 1–6 | triage/lab | [x] drafted |
| **R10** | Advisory NLP heuristics (BLEU/ROUGE/BERTScore/Levenshtein) as diagnostics beside catalogs | Cheap similarity smoke signals | Never sole Hybrid/gold/path-class law · never replace product wrappers | 5 / lab | **off** | [x] drafted |
| **R11** | Amend-session evidence pack (`eval amend-brief`) for L2 AI review/amend; optional last-N Lane C attachments; writes **message_versions / preference pairs** into session thread | Makes advisory metrics consumable where real LLM review happens; captures train preference gold | Local-first · non-blocking · not accept/golden gate · schema-versioned · redaction profile · Opik optional | 6 | on for maintainer amend workflow; off for basic users | [x] **approved** 2026-08-12; train pairs **2026-08-13** |
| **R12** | Maintainer `eval.dogfood` profile: GEval/C′ at `off\|sample\|always\|async` on dev commits; **R12-MVP** may start after S2a (single pinned craft judge) before full S5 | High-frequency lab signal; assistant-drift catch; failure→fixture + **train feature** fuel | Never basic-user default · never sole accept/golden · L1 wins · pin required · budgets · async+advisory preferred · capture_on pass\|fail\|all owner-set | 6 | dogfood default `always+async+advisory`; users `off` | [x] **approved** 2026-08-12; MVP **2026-08-13** |
| **R13** | **Commit-session thread** (`commit_session_thread_v1`) — one thread per commit unit of work (start→accept), additive over traces/spans; regen = optional **subchain** (§2.9) | Human/agent readability; join key for train rows & Opik thread UX | Not chat-agent law · not sole gate · does not remove existing metrics · local twin required · continuity/contamination metrics in Family I | 3/4/6 | on for maintainer train/dogfood; off basic | [x] **approved** 2026-08-13; glossary v0.9.0 |
| **R14** | **Owner redaction ladder** + **train corpus plane** (`train_rich`, `antipattern_vault`, `train_export_v1`, train_label, capture_on) | Owner controls retention depth for training/anti-patterns without ambient leak defaults | Secrets scrub fail-closed/quarantine · scope tags · not CI SoT · not basic-user default · record≠gate | 0/4/6 | owner chooses maintainer default; CI/`public_ci` thin | [x] **approved** 2026-08-13 |

### 3.3 Explicitly non-relaxable rejects

Do **not** treat these as R-series items:

* Builtin Hallucination / Moderation / G-Eval / juries / answer-relevance / etc. as `gate.deterministic_pass` or golden sole gate  
* Cloud dataset / experiment / `latest` as CI or golden SoT  
* Blocking accept-path on Opik, judge provider, or export health  
* Expected/gold leakage into ordinary Lane C judge prompts  
* Agent tool-correctness / multi-turn dialogue helpfulness as commit legality  
* Summarization coherence/consistency force-fit as core commit metrics  
* Ollie-authored suites or optimizer auto-ship to live pins  
* Merging Promptfoo red-team or Sentry ops scores into Opik accept gates  
* Replacing Families A–H with vendor heuristic packs  
* Unpinned Prompt Library runtime fetch on accept-path/CI  
* Local Runner / `opik connect` as required commit-path UX  
* Weakening `GOLD_SKELETON_FALLBACK_FINAL` / gold-strict skeleton provenance to greenwash online dashboards  
* Scoring live regen (or raw model dumps) as if they were final accept-path bytes without explicit `artifact_class`  

### 3.4 One-line relaxation policy

> **Constitution stays hard; only registered R-relaxations (**R1–R14 active**) may add secondary/lab/operator/train-corpus flexibility, each off-by-default unless noted, always pinned, always non-authoritative for accept/golden sole decisions, and always subordinate to F0–F9. Corpus retention richness is owner-profiled and does not by itself promote gate authority.**

### 3.5 Approved R-extensions

| ID | Proposal | Status |
|:---|:---|:---|
| **R11** | **Amend-session evidence pack** (`eval amend-brief`) — versioned local brief for AI assistant pre-push review/amend (FIND-006). Not an Opik online gate; not product accept blocker. Brief **MAY** include optional **last-N GEval/C′ attachments** from R12. **MUST** be able to reference **message_versions / preference pairs** and `session_thread_id` (FIND-012). | **approved** — S6; train pairs 2026-08-13 |
| **R12** | **Maintainer `eval.dogfood` profile** — high-frequency Lane C GEval/C′ on *our* commits (FIND-008). Modes: `off` \| `sample` \| `always` \| `async`. Default while building: **`always` + `async` + advisory**. **R12-MVP** after S2a with one pinned craft judge before full S5 (FIND-010). `corpus.capture_on=pass\|fail\|all` for train negatives. | **approved** — S6; MVP 2026-08-13 |
| **R13** | **Commit-session thread** — additive per-commit thread for human/agent navigation + corpus join (FIND-011). | **approved** 2026-08-13 |
| **R14** | **Owner redaction ladder + train corpus plane** — profiles, train_label, preference pairs, anti-pattern vault, local train export (FIND-009/013–016). | **approved** 2026-08-13 |

#### R11 schema sketch (non-binding until §7)

```text
amend_brief_v1:
  schema_version
  commit_subject / trailers (redacted as needed)
  l1: { family_scores[], failure_ids[], regime, path_class, gold_counters }
  l2_hints: { questions[], sop_tension_notes[] }   # optional
  lane_c_attachments: [                            # optional; R12 feed
    { run_id, judge_id, pin_ref, mode, score, polarity,
      rationale_short, latency_ms, created_at, authority: advisory }
  ]  # last-N, N default 1..5
  opik_refs?: { project, trace_ids[] }             # optional; offline-ok without
```

#### R12 overhead budgets (initial targets — measure on M4 Max, then lock)

| Mode | Latency target | Blocking | Default audience |
|:---|:---|:---|:---|
| `off` | 0 | — | **All basic users** |
| `async` | commit path +0ms user-visible; judge finishes in background | non-blocking; result → brief/Opik | **Recommended dogfood default** |
| `sample` | same as always/async on selected commits only (e.g. 20% or risky path-class) | per selected mode | Cost control |
| `always` + async | same as async | non-blocking | High-signal dogfood |
| `always` + sync advisory | **≤ ~5s** soft; **≤ ~15s** only if owner accepts | warn/attach only | Optional local pinned judge |
| `always` + sync soft-warn | budgets must be met first | exit warn, commit still allowed unless owner escalates | Dev profile |
| `always` + sync hard-block | explicit owner opt-in only | blocks commit/push checklist | Painful lab gate — never default, never sole CI law |

**Pinning required for any on mode:** model id, prompt/template version, temperature, timeout, score polarity registry entry, redaction profile. Floating “latest” judge = reject.

**Payload default (basic / public_ci):** message hash/subject + redacted metadata.  
**Payload default (maintainer train/dogfood):** owner **redaction ladder** (R14) — commonly `train_rich` for private owner project; secrets still scrubbed; raw diffs only under explicit profile + quarantine on scrub fail.

**Arbitration:** L1 fail ⇒ product/eval fail regardless of GEval. GEval red + L1 green ⇒ advisory/soft only (unless owner hard-block profile). L2 may weigh GEval rationale but must not auto-rewrite solely to maximize judge score against Hybrid/SOP. **L1 fail rows may still be corpus-captured** as hard-negatives when `capture_on` includes fail.

#### R13 commit_session_thread sketch

```text
commit_session_thread_v1:
  schema_version
  session_thread_id                 # stable join key (local + Opik thread id map)
  opened_at / closed_at?
  repo_fingerprints                 # no secrets
  stages[]: { name, t, status, refs }   # signals, rank, gen, l1, l2_amend, dogfood, accept
  message_versions[]: {
    version_id, role: model_draft|l2_amend|owner_edit|final_accept|rejected,
    message_sha256, message_text?,  # text per redaction_profile
    source_actor, created_at, l1_snapshot_ref?, judge_attachment_refs?[]
  }
  preference_pairs[]: { chosen_version_id, rejected_version_id[], owner_approved, notes? }
  train_label?: positive_gold|hard_negative|preference_chosen|preference_rejected|unlabeled|holdout
  redaction_profile
  opik_thread_ref?
  existing_trace_span_ids[]         # additive links — do not delete other logs
```

#### R14 redaction ladder (owner-selectable)

| Profile | Bodies | Diffs | Prompts | Typical sink |
|:---|:---:|:---:|:---:|:---|
| `public_ci` | hash/subject | no | no | CI logs |
| `default_scrub` | limited | paths | no | general dev |
| `private_message` | yes | paths/meta | no | private Opik compare |
| `train_rich` | yes | structured/allowlisted or full opt-in | optional pin-hash only | owner train lake |
| `antipattern_vault` | yes | as needed | controlled | labeled negatives |
| `raw_dev_unsafe` | all | all | all | break-glass local only |

Every non-`public_ci` export runs secret scrub; hit ⇒ field quarantine / omit, session kept if possible.

---
## 4. Issue decomposition decision

### 4.1 Decision (recommended)

| Option | Use? | Rationale |
|:---|:---:|:---|
| **A. Single mega-implementation issue for all slices** | ❌ | Unreviewable; blocks parallel work; confuses design-vs-impl closure of #217 |
| **B. One issue per Opik doc page** | ❌ | ~40 issues of process overhead; pages are evidence, not ship units |
| **C. Keep #217 as design SSOT; file grandchild issues per implementation slice (0–7)** | ✅ **accepted default** | Matches #217 body; clear AC; maps to PR size |
| **D. Hybrid: slice issues + thin vertical spikes where needed** | ✅ **accepted escape hatch** | e.g. binding spike unblocking Slice 3 without opening all of Slice 2 |
| **E. Separate issues per metric family (A–H)** | ⚠️ only if Slice 2 explodes | Prefer packages under Slice 2 first |

**Decomposition for this plan (accepted as working default):**

```text
#216 (epic board)
 └── #217 (design SSOT — Opik pillar)          [design-only closure]
      ├── #217.S0 Law & schema package
      ├── #217.S1 Offline corpus / bundles
      ├── #217.S2 Authoritative deterministic metrics
      ├── #217.S3 Accept-path binding hardening
      ├── #217.S4 Opik mirror (datasets/experiments/REST)
      ├── #217.S5 Secondary Lane C cohort (+ optional R1/R2/R6)
      ├── #217.S6 Operator UX / CI / triage / review queue
      └── #217.S7 Docs/ADR alignment
```

Sibling pillars (not children of #217):

```text
#216
 ├── #217 Opik eval harness (this plan)
 ├── #218 Sentry crash/ops
 └── #219 Promptfoo assert/red-team
```

### 4.2 Issue sizing rules

| Rule | Statement |
|:---|:---|
| Design vs impl | #217 stays design-closeable without code |
| One slice ≈ one grandchild | Unless slice must split by dependency or PR blast radius |
| No page-issues | Inclusion-map pages attach as checklists inside slices |
| R-items | Never solo epic issues; attach to Slice 5/6 (or #219 for red-team depth) |
| Skills | No issues “implement opik skill”; skills are references only |
| Spike allowed when | Unknown binding/telemetry gap blocks S3; time-box and fold back |

### 4.3 Dependency graph (slices)

```text
S0 ──► S1 ──► S2 ──► S3 ──► S4
              │       │
              │       └──► S5 (after eligibility gate exists)
              │
              └──► S6 (entrypoints may start after S1; full after S2–S4)
S0–S6 ──► S7 (ADR/docs continuous, formal close at end)
```

Hard constraints:

* S1 must not require Opik network  
* S2 must not include builtin H/M/G-Eval as authority  
* S5 must not start as merge-gate work  
* S4 failures must not gate accept-path  

### 4.4 What gets filed when

| Phase | File | Do not file yet |
|:---|:---|:---|
| Now | This skeleton → fill plan | Random page issues |
| After plan §5–§8 compiled | Optional: mark #217 checkboxes / comment pointer to this doc | Impl PRs that skip S0 |
| After design ratification | S0 (+ S1 if schema stable) | S5 judge gates |
| After S2 green offline | S3/S4 | Optimizer / Ollie work |
| After eligibility gate real | S5 optional | Promoting R-items to gates |

---

## 5. Vendor surface — inclusion maps

> **Source:** Opik Evaluation docs (core suite + metrics pack + agents/threads + H/M cookbooks), compiled from #217 analyses.  
> **Rule of construction:** import *structure*; reject *authority creep*.  
> **Audience reminder (§0.3):** all of this is developer/maintainer surface. Basic `git-cg` users never see or depend on it.

### 5.1 Global locks applying to every page

[x]

| # | Lock | Effect on every vendor page |
|:---:|:---|:---|
| G1 | Local-first SoT (F0) | Local fixtures/bundles/JSONL/`ape_bundle_v1` = CI/regression law. Opik datasets/experiments/scores = mirror/compare only. |
| G2 | Primary scored artifact (F1) | Final rendered accept-path message (exact bytes). Not live regen by default; not plan-only. |
| G3 | Deterministic authorities first (F2) | Ranker/SOP/Hybrid/gold/path-class/`commit_quality` are metric engines. No eval-only regex/prompt forks. |
| G4 | LLM judges secondary (F3) | All LLM-as-judge surfaces = Lane C′ / lab / advisory unless constitution amendment. |
| G5 | Non-blocking Opik (F4) | Export/flush/UI/cloud/judge outage never blocks commit accept. |
| G6 | No unpinned `latest` (F5) | Pin harness, metric catalog, prompt-pack/hash, model, suite/dataset snapshot, judge pins if used. |
| G7 | Gold/expected isolation (F6) | Expected outputs, assertions, gold never merge into generation task input (judge input only in labeled meta-eval). |
| G8 | No Ollie authority (F8) | Ollie/UI-only suite authoring/diagnosis is not required path or law. |
| G9 | Optimizer deferred (F8) | Prompt/agent optimizers not MVP; later offline candidate search only; ship via git pins. |
| G10 | Sibling planes (F7) | Promptfoo = Lane D / #219. Sentry = Lane E / #218. Do not collapse into Opik product gates. |
| G11 | Privacy / redaction ladder | No **ambient** cloud dump of raw diffs, full prompts, secrets, unrestricted bodies, or harmful samples. **Owner** may select richer maintainer profiles (`train_rich` / `antipattern_vault`) with scrub + scope tags. Basic-user and `public_ci` stay thin. |
| G12 | Design-first / slice order (F9) | #217 design SSOT; impl via grandchildren. Lanes A/B first; Lane C and judge lab later. |
| G13 | Dev-only audience (§0.3) | Opik never becomes end-user product surface or required install for basic `git-cg` use. |

**Page mark legend:** ✅ import under pins & local SoT · ⚠️ reshape / secondary / later · ❌ reject as accept-path / golden sole gate / CI sole law / product authority.

---

### 5.2 Core evaluation suite (10 pages)

[x]

| Page | Mark | Slice home | #216/#217 action | Hard restrictions |
|:---|:---:|:---:|:---|:---|
| [Getting started](https://www.comet.com/docs/opik/evaluation/getting-started) | ⚠️ | — / S6 lab | Steal onboarding shape only (cases → task → scores → experiment). Default runner is **local offline**, not cloud-first SDK tour. | ❌ cloud project bootstrap as control plane · ❌ dashboard trust as CI law · ❌ required for basic users |
| [Concepts](https://www.comet.com/docs/opik/evaluation/concepts) | ✅/⚠️ | S3 / S4 / S6 | Keep trace/span/thread/dataset/experiment vocabulary. Remap **thread = commit_session_thread (full commit unit)** plus optional regen sub-groups; traces/spans remain. Opik = mirror **and** owner corpus lake. | ❌ thread/chat metrics as product law · ❌ experiment UI as CI SoT · ❌ deleting other metrics because thread exists |
| [Building test suites](https://www.comet.com/docs/opik/evaluation/advanced/building-test-suites) | ⚠️ | S1 / S5 | Keep suite loop. Local suite assertions = deterministic product-authority checks. Opik Test Suite = optional mirror **or** Lane C probes. | ❌ NL + LLM-judge assertions as `gate.deterministic_pass` / golden sole gate · ❌ Ollie-authored suites as law |
| [Evaluate your LLM](https://www.comet.com/docs/opik/evaluation/advanced/evaluate_your_llm) | ⚠️ | S1–S4 | Keep pinned `experiment_config`, scoring_key_mapping, explicit task fn, cohort filters. Default modes: `fixture_offline`, `acceptpath_bound`; `live_regen` opt-in only. | ❌ live regen default · ❌ unpinned `nb_samples`/filters as SoT · ❌ cloud experiment as CI authority |
| [Resume evaluations](https://www.comet.com/docs/opik/evaluation/advanced/resume_evaluations) | ✅ | S6 | Local checkpoints first: `resume_missing` / `recompute_scores` / `replay_generation` / `fresh_suite_run`. | ❌ silent merge across compatibility-hash mismatch · ❌ resume state living only in cloud |
| [Manage datasets](https://www.comet.com/docs/opik/evaluation/advanced/manage_datasets) | ⚠️ | S1 / S4 | Versioned local snapshots + hashes are authority. Opik datasets = optional mirror. `expected_output` allowed in fixture envelope only. | ❌ Opik dataset as golden SoT · ❌ `latest` float on CI/accept-path · ❌ expected_output in model/judge task input · ❌ `user_acceptance` alone promotes golden |
| [Evaluate agent trajectory](https://www.comet.com/docs/opik/evaluation/advanced/evaluate_agent_trajectory) | ⚠️ | S2 / S3 | Keep **E2E + step/graph dual depth**. Map to declared vs observed accept-path stage taxonomy / graph metrics (R7). | ❌ generic tool-agent trajectory score as golden/CI gate · ❌ agent-framework cargo-cult as required architecture |
| [Evaluate multi-turn agents](https://www.comet.com/docs/opik/evaluation/advanced/evaluate_multi_turn_agents) | ⚠️/❌ | S3 / S5 | Multi-attempt regen/review chain evidence only. Conversation-agent framing is mostly out of product shape. | ❌ multi-turn chat quality as Hybrid/gold law · ❌ simulated-user authority |
| [Annotation queues](https://www.comet.com/docs/opik/evaluation/advanced/annotation_queues) | ✅/⚠️ | S6 | Local-first HITL queue (`.eval/review_queue/`). Multi-rater human scores as `human.*` (R4). Optional later Opik queue mirror. | ❌ human scores override deterministic fail · ❌ human scores sole golden promotion · ❌ cloud queue as SoT · ❌ required for basic users |
| [Log experiments with REST API](https://www.comet.com/docs/opik/evaluation/advanced/log_experiments_with_rest_api) | ✅ | S4 | Projection-only bulk upload of **precomputed local** results: batched, idempotent, size-bounded, project/lane pinned (R3). | ❌ REST as scoring execution engine · ❌ export failure ⇒ product/accept fail · ❌ unscoped Default Project dumping |

#### Core-suite hard rejects (aggregate)

* Cloud/UI suite state as golden SoT  
* LLM/NL assertions as `gate.deterministic_pass` or golden sole gate  
* Unpinned dataset/prompt/model/`latest`  
* Simulated-user / multi-turn agent authority  
* Blocking accept-path on Opik  
* Mixing artifact classes (raw/mid/final/live-regen) in one silent score stream  
* Ollie-authored suites as law  
* Requiring Opik for basic end-user commits  

---

### 5.3 Metrics suite

#### 5.3.1 Catalog / plumbing

[x]

| Page | Mark | Slice | #216/#217 action | Hard restrictions |
|:---|:---:|:---:|:---|:---|
| [Metrics overview](https://www.comet.com/docs/opik/evaluation/metrics/overview) | ⚠️ | S0 / S2 | Import dual-plane **shape** + ScoreResult envelope (`name`/`value`/`reason`/evidence). Our split: authoritative product wrappers vs secondary judges. | ❌ Opik’s “heuristics ∧ judges are peer gates” · ❌ unversioned builtin pack as catalog law |
| [Heuristic metrics](https://www.comet.com/docs/opik/evaluation/metrics/heuristic_metrics) | ⚠️/❌ | S5 / lab (R10) | BLEU/ROUGE/BERTScore/Levenshtein/etc. diagnostic only. Prefer wrappers of real product validators. | ❌ NLP similarity as sole Hybrid/gold/path-class law |
| [Custom metric](https://www.comet.com/docs/opik/evaluation/metrics/custom_metric) | ✅ | S2 | **Preferred authoritative path.** Wrap `commit_gold` / `commit_quality` / path-class/contract / inventory / harness health into Families A–H. | ❌ parallel product policy invented only inside eval prompts |
| [Custom model](https://www.comet.com/docs/opik/evaluation/metrics/custom_model) | ⚠️ | S5 / lab | Lane C/lab judge providers only; pin model/version/params. | ❌ required for Lane A/B offline · ❌ `OPIK_DEFAULT_LLM` for product generation or authoritative scoring · ❌ required for basic users |
| [Advanced configuration](https://www.comet.com/docs/opik/evaluation/metrics/advanced_configuration) | ⚠️ | S5 / S6 | Local timeouts/retries/key-mapping OK. `runs_per_item` / thresholds = Lane C flakiness studies only (R8). | ❌ flakiness knobs as product/golden pass criteria · ❌ unpinned judge defaults |
| [Custom conversation metric](https://www.comet.com/docs/opik/evaluation/metrics/custom_conversation_metric) | ⚠️ | S5 / S3 | Regen-chain grouping/diagnostics only. | ❌ conversation metric as accept/golden gate |
| [Structured output compliance](https://www.comet.com/docs/opik/evaluation/metrics/structure_output_compliance) | ⚠️/✅ | S2 / H | OK if remapped to bundle/ScoreResult/schema/harness compliance, or if it literally wraps product validators (Hybrid envelope helpers). | ❌ substitute for Hybrid trailer / gold law without product wrappers |
| [Task span metrics](https://www.comet.com/docs/opik/evaluation/metrics/task_span_metrics) | ⚠️/✅ | S2–S3 (R7) | Step/span/graph health → Family H / trajectory evidence. | ❌ span scores as semantic commit authority |

#### 5.3.2 Builtin LLM / semantic / agent metrics

[x]

| Page | Mark | Allowed role | Hard restrictions |
|:---|:---:|:---|:---|
| [Hallucination](https://www.comet.com/docs/opik/evaluation/metrics/hallucination) | ⚠️/❌ | Optional Lane C grounding narrative (R1) **or** offline judge meta-eval (R2). Product “hallucination” → Families C/D/F (inventory/path-class/gold). | ❌ product gate · ❌ golden sole gate · ❌ replace inventory/gold checks |
| [Moderation](https://www.comet.com/docs/opik/evaluation/metrics/moderation) | ⚠️/❌ | Optional ops/review flag only (R6); **not default** semantic cohort member. Prefer #219 adjacency for red-team depth. | ❌ Hybrid legality · ❌ accept-path block · ❌ unrestricted sensitive corpus export |
| [LLM juries](https://www.comet.com/docs/opik/evaluation/metrics/llm_juries) | ⚠️/❌ | Multi-judge ensemble remains advisory/lab (under R1 posture). | ❌ ensemble vote as CI/golden authority |
| [G-Eval](https://www.comet.com/docs/opik/evaluation/metrics/g_eval) | ⚠️/❌ | Lane C only (R1); criteria must not silently become SOP. Existing shallow GEval scripts ≠ law. | ❌ accept/golden/CI sole gate |
| [G-Eval conversation metrics](https://www.comet.com/docs/opik/evaluation/metrics/g_eval_conversation_metrics) | ⚠️/❌ | Thread/regen advisory only. | ❌ conversation G-Eval as product gate |
| [Compliance risk](https://www.comet.com/docs/opik/evaluation/metrics/compliance_risk) | ⚠️/❌ | Ops/review/policy adjacency only (near R6 / #219). | ❌ commit accept gate · ❌ Hybrid/SOP replacement · payload scrubbing required |
| [Prompt diagnostics](https://www.comet.com/docs/opik/evaluation/metrics/prompt_diagnostics) | ⚠️ | Harness/lab diagnostics on prompt packs (dev-only). | ❌ alone authorize pin-move / ship |
| [Meaning match](https://www.comet.com/docs/opik/evaluation/metrics/meaning_match) | ⚠️/❌ | Semantic similarity diagnostic only (R1/R10 adjacency). | ❌ sole gold/Hybrid authority |
| [Usefulness](https://www.comet.com/docs/opik/evaluation/metrics/usefulness) | ⚠️/❌ | Advisory narrative quality only (R1). | ❌ accept/golden gate |
| [Summarization consistency](https://www.comet.com/docs/opik/evaluation/metrics/summarization_consistency) | ❌/⚠️ | Poor fit for commit-message product law; do not force-fit. | ❌ product metric family by default |
| [Summarization coherence](https://www.comet.com/docs/opik/evaluation/metrics/summarization_coherence) | ❌/⚠️ | Same as above. | ❌ product metric family by default |
| [Dialogue helpfulness](https://www.comet.com/docs/opik/evaluation/metrics/dialogue_helpfulness) | ❌/⚠️ | Multi-turn dialogue framing ≠ product accept law. | ❌ Hybrid/gold gate |
| [Answer relevance](https://www.comet.com/docs/opik/evaluation/metrics/answer_relevance) | ⚠️/❌ | Lane C narrative only (R1). | ❌ accept/golden/CI sole gate |
| [Context precision](https://www.comet.com/docs/opik/evaluation/metrics/context_precision) | ⚠️/❌ | Only if carefully remapped to evidence-surface diagnostics. Default RAG framing is not git-cg accept law. | ❌ ranker/SOP substitute |
| [Context recall](https://www.comet.com/docs/opik/evaluation/metrics/context_recall) | ⚠️/❌ | Same as precision. | ❌ ranker/SOP substitute |
| [Trajectory accuracy](https://www.comet.com/docs/opik/evaluation/metrics/trajectory_accuracy) | ⚠️ | Remap to declared vs observed stage/graph metrics on accept-path pipeline (R7). | ❌ generic agent trajectory score as golden/CI gate |
| [Agent task completion](https://www.comet.com/docs/opik/evaluation/metrics/agent_task_completion) | ⚠️/❌ | Only if mapped to bounded pipeline stage completion evidence. | ❌ tool-agent success as commit legality |
| [Agent tool correctness](https://www.comet.com/docs/opik/evaluation/metrics/agent_tool_correctness) | ❌ | Commit path is not a free-form tool agent. | ❌ import as product metric family |
| [Conversation threads metrics](https://www.comet.com/docs/opik/evaluation/metrics/conversation_threads_metrics) | ⚠️/❌ | Continuity/grouping for regen chains only. | ❌ product/golden/CI gate |

#### 5.3.3 Local family placement (metric catalog v0)

[x]

| Family | Authority | May absorb Opik builtins? | Notes |
|:---|:---|:---|:---|
| **A** Artifact/binding integrity | Authoritative | Custom/local only | final present, bound/unbound, schema, artifact class |
| **B** Hybrid format | Authoritative | Wrap product validators only | header/emoji/type/scope/subject/trailers — no G-Eval |
| **C** Path-class/contract | Authoritative | Custom/local only | expected class vs `path_class_gate`, SemVer ceilings, envelope |
| **D** Gold strict truth | Authoritative | Wrap `commit_gold` only | findings, counters, blocked, regen consistency |
| **E** Craft/presentation | Authoritative | Wrap `commit_quality` only | banned openers, docs/tests craft, skeleton avoidance |
| **F** Inventory/attribution | Authoritative | Custom/local | **replaces much product “hallucination”** (claims vs staged set) |
| **G** Authority/safety (deterministic) | Authoritative | Deterministic product sense — **not** Opik Moderation | ranked identity preservation, no SOP mutation claims |
| **H** Harness health | Authoritative | Span/export/schema/repro metrics; structured-output-as-harness OK | evaluator errors, offline completeness, pin integrity |
| **C′** Semantic cohort | Secondary | Hallucination, G-Eval, relevance, usefulness, juries, meaning-match, etc. (R1) | only after `gate.semantic_cohort_eligible` |
| **`human.*`** | Secondary | Annotation queues (R4) | non-overriding |
| **`judge_meta_eval_v1`** | Later lab only | H/M cookbook pattern (R2) | never product gate |

**Dual-plane law (mandatory):**

```text
Plane A (authoritative): product-authority wrappers + harness integrity
  → Families A–H, gate.deterministic_pass, golden_promotion_eligible

Plane B (secondary): LLM judges, NLP similarity, conversation/agent builtins
  → C′ / human.* / lab only after gate.semantic_cohort_eligible (where applicable)
```

---

### 5.4 Agents / threads / judge-lab cookbooks

[x]

| Page | Mark | Slice | #216/#217 action | Hard restrictions |
|:---|:---:|:---:|:---|:---|
| [Evaluate agents](https://www.comet.com/docs/opik/evaluation/evaluate_agents) | ⚠️ | S2 / S3 / S7 | Keep depth model: observe → score final → score steps/session → human review → iterate **in git**. | ❌ E2E quality = Hallucination/Relevance/Moderation · ❌ tool-agent cargo-cult · ❌ auto-optimize ship loops · ❌ end-user facing |
| [Evaluate threads](https://www.comet.com/docs/opik/evaluation/evaluate_threads) | ⚠️ | S3 / S5 / S6 | Thread = **commit_session_thread** (R13) for full commit UX; regen sub-chain optional. Conversation metrics advisory only. Filters = cohort tools (R9). | ❌ thread metrics as CI/product gate · ❌ filter-selected subsets as silent golden/train-positive corpus without labels |
| [Evaluate hallucination metric](https://www.comet.com/docs/opik/evaluation/evaluate_hallucination_metric) | ⚠️ | S5–S6 (R2) | **Later offline judge lab only:** labeled cohort → pinned judge → deterministic Equals vs label → FP/FN report. Optional non-blocking mirror. | ❌ product/CI/golden sole gate · ❌ Lane A/B requires judge credentials · ❌ ~80% demo as sufficiency · ❌ expected labels in judge-visible prompt unless explicit meta-eval envelope |
| [Evaluate moderation metric](https://www.comet.com/docs/opik/evaluation/evaluate_moderation_metric) | ⚠️ | S5–S6 (R2/R6) / #219 | **Later offline judge lab / optional ops pack** with same meta-eval pattern. Controlled sensitive corpus handling. | ❌ Hybrid/accept blocker · ❌ default Lane C semantic-cohort member · ❌ ~85% demo as sufficiency · ❌ unrestricted cloud export of harmful samples |

**Safe meta-eval shape (H/M cookbooks → R2):**

```text
versioned local labeled cohort
  → scrubbed judge input (no leaked expected labels unless meta-eval envelope)
  → pinned Hallucination/Moderation judge (model + prompt/rubric hash)
  → task returns judge label/score
  → deterministic Equals (or similar) vs expected label
  → item-level FP/FN report
  → optional non-blocking Opik mirror (dev-only)
```

**Product remaps (do not cargo-cult cookbook names):**

* git-cg “hallucination” concerns → deterministic Families **C/D/F**, not Opik `Hallucination()` as law  
* git-cg “moderation” → optional ops/review (R6) or #219; never Hybrid legality  

---

### 5.5 Relax vs remove restrictions — trade-off summary

[x]

**Question answered:** would relaxing or fully removing suite restrictions yield significant *product* functionality?

**Answer:** **No for product acceptance.** Full removal buys vendor convenience and dashboard beauty; costs authority, reproducibility, and safety. Significant residual value is already captured by **R1–R14** without constitution breach (train/session extensions included).

| Restriction family | If fully removed | Real gain | Real cost | Plan posture |
|:---|:---|:---|:---|:---|
| Local-first SoT | Cloud becomes golden/CI law | Hosted compare UX | Non-reproducible CI; SoT fights | **Keep F0**; use R3 mirror |
| Judges secondary | Judges co-gate / gate | Residual prose catch | Regime B false-green; authority inversion | **Keep F3**; use R1/R2 |
| Pinning / no `latest` | Float models/prompts/datasets | Less pin churn | Bisect death; silent drift | **Keep F5**; R5 dirty lab overlays only |
| Non-blocking Opik | Accept path waits on Opik/judges | Stronger export discipline | CLI fragility; user-visible outage coupling | **Keep F4** (esp. given basic users) |
| Gold isolation | Judges see labels routinely | Easier cookbook demos | Inflated calibration; fake confidence | **Keep F6**; R2 labeled envelopes only |
| Custom wrappers vs builtins | Builtins become law | Less metric code | Forked law; #118/#119 regression | **Keep F2**; custom = S2 path |
| Plane separation | One observability blob | Single pane | Un-ownable epic; wrong failure classes | **Keep F7** |
| Optimizer / Ollie deferred | Auto prompt ship | Looks fast | Optimizes advisory scores; ignores gold_blocked | **Keep F8** |

**Controlled relaxations with positive payoff (already in §3):** R1–R14 (R11–R14 owner-approved; R3/R7 amended for corpus).

**Functionality math (blunt):**

```text
Product correctness functionality from full removal  ≈ small
Developer convenience from full removal              ≈ medium–high
Lab velocity from R-register (kept locks)            ≈ medium–high  ← preferred
Determinism / auditability lost on full removal      ≈ very high
False-green accept / bad golden risk on full removal ≈ very high
Basic-user blast radius if Opik coupled to accept    ≈ unacceptable
```

**One-line ratification (vendor surface):**

> **Adopt Opik Evaluation as a local, deterministic, evidence-complete accept-path operating model for developers** (`ape_bundle_v1` + product-authority metric catalog + non-blocking Opik **mirror/owner corpus lake** + commit-session threads). **Treat builtin LLM/heuristic/agent/conversation metrics as secondary/lab/train features** — never sole semantic authority, never CI golden SoT, never on the basic-user commit critical path — while **recording** them under owner profiles for dogfood and training.

---

### 5.6 Aggregate gates recall (vendor metrics → gates)

| Gate / path | Builtin Opik LLM/heuristic metrics allowed? |
|:---|:---|
| `gate.deterministic_pass` | ❌ No |
| `gate.semantic_cohort_eligible` | Entry only (deterministic classification first) |
| `gate.golden_promotion_eligible` | ❌ No LLM-only path |
| Commit accept-path success | ❌ Never depends on Opik judges/export |
| CI offline suite (Lane A/B) | ❌ Judges not required; deterministic only |
| Lane C / judge lab jobs (dev) | ⚠️ Optional, non-blocking, pinned |

---


### 5.7 Official Opik reference matrix (FIND-025 / INT-30)

> Dated check baseline: **2026-08-13**. Re-check URLs when S4/S7 land. This matrix records **what we adopt vs deliberately reject**.

| Title | Canonical URL | Adopt claim | Local adaptation | Deliberate reject |
|:---|:---|:---|:---|:---|
| Tracing concepts | https://www.comet.com/docs/opik/tracing/concepts | traces/spans/threads/feedback model | Map to §2.9 taxonomy + Family I | thread ≠ product law |
| Log traces | https://www.comet.com/docs/opik/tracing/log_traces | SDK span kinds + usage metadata | closed span names; correlation envelope | unbounded hook flush |
| Log conversations | https://www.comet.com/docs/opik/tracing/log_conversations | thread grouping UX | R13 full session thread | chat-bot metrics as Hybrid law |
| Log agent graphs | https://www.comet.com/docs/opik/tracing/log_agent_graphs | graph visualisation | declared `git_cg_pipeline_graph_v1` | auto-framework tracers only |
| Annotate traces | https://www.comet.com/docs/opik/tracing/annotate_traces | feedback on trace/span | §6.1b placement matrix | annotation rewrites history silently |
| SDK configuration | https://www.comet.com/docs/opik/tracing/sdk_configuration | env/project config | `git_cg_opik_config_v1` modes | silent Default Project |
| Offline / export data | https://www.comet.com/docs/opik/tracing/export_data | offline/export concept | Layer A SoT + Layer B optional + `.eval/export_queue` | SDK SQLite as sole evidence |
| Evaluation overview | https://www.comet.com/docs/opik/evaluation/overview | experiments/datasets | local suite authority | cloud experiment as golden |
| Metrics overview | https://www.comet.com/docs/opik/evaluation/metrics/overview | metric inventory | SCORE-POLARITY remap; STRUCT-LOCAL | builtin SOC/Hallucination as law |
| Task span metrics | https://www.comet.com/docs/opik/evaluation/metrics/task_span_metrics | span-level scoring | Family I / stage metrics | untyped free metrics |
| Evaluate agent trajectory | https://www.comet.com/docs/opik/evaluation/advanced/evaluate_agent_trajectory | trajectory evidence | H/R7 only | trajectory as Hybrid law |
| Prompt library | https://www.comet.com/docs/opik/prompt_engineering/prompt_management | versioned prompts | repo `prompt_pack_v1` SoT | UI “latest” runtime pin |
| Optimizer | https://www.comet.com/docs/opik/agent_optimization/overview | optimise-under-metrics idea | objective vector + git pin ship | Studio/control-plane authority |
| Ollie / AI assist | product docs (Ollie assist) | RCA **pattern** only | FIND-020 deterministic loop | Ollie required in product path |

## 6. Metric catalog v0 (design compile)

[x] **Catalog pin id:** `metric_catalog_v0` · **Status:** design-approved with FIND-001…025 / R11–R14 / M10–M12 / Family I  
**Rule:** metric *IDs* and *polarity* are law for the harness; implementations wrap product modules — they do not fork SOP/Hybrid/gold rules into eval-only prompts.  
**Count footnote (T7):** the frozen catalog has **137** metrics counted by the `family` field (A7 B11 C9 Cprime9 D18 E9 F7 G6 H26 I16 gate3 lab5 human4 nlp4 dogfood3). Naive first-letter counting is invalid.

### 6.0 Catalog laws

| # | Law |
|:---:|:---|
| M0 | Every score is a `ScoreResult` (or compatible local subclass) with stable `metric_id`. |
| M1 | **Polarity is explicit** — `higher_is_better` **or** `lower_is_better` **or** `pass_fail` — never implied. **Never inherit Opik builtin polarity blindly** (Hallucination/Moderation often high=bad; G-Eval high=good). Local catalog remap is SoT (INT-14 / SCORE-POLARITY). |
| M2 | Authoritative metrics (A–H) wrap **product code paths** (`commit_gold`, `commit_quality` / path-class, Hybrid/render validators, binding emitters). No eval-only regex forks of those rules. |
| M3 | Secondary metrics (C′, human.*, lab, R10, R12 GEval) always stamp `authority=advisory` (or weaker). |
| M4 | Aggregate `gate.deterministic_pass` ∈ **only** A–H **+ Family I** (+ binding). No C′/GEval/human/R10/export-success-as-quality. |
| M5 | Catalog is **pinned** on CI/accept-path suites (`metric_catalog_version` + content hash). |
| M6 | Failure IDs prefer product codes when they exist (e.g. `GOLD_*`); harness adds `EVAL_*` only for harness/binding gaps. |
| M7 | Metrics declare **input artifact class**: `final_message` · `plan` · `bundle` · `trajectory` · `fixture_envelope` · `judge_input` (lab). |
| M8 | R11 amend-brief consumes a **stable projection** of this catalog (not raw Opik UI). |
| M9 | R12 dogfood GEval is catalogued under C′/lab attachment ids — never A–H. |
| M10 | **Severity parity** — for the same product rule, eval severity must not exceed product severity (wrap, don’t escalate). |
| M11 | **Record ≠ gate** — advisory/lab/train metrics may always be recorded when owner profile allows; recording never implies `gate.deterministic_pass` or sole golden authority. Prefer enrichment over omission for maintainer train mission. |
| M12 | **AGG-GATE** — experiment/suite **aggregates** (mean/min/max pass rates) are dashboards only. Any per-item hard fail remains visible and binding; averages must not hide Hybrid/gold/topology failures (INT-23). |

### 6.1 ScoreResult envelope

```text
ScoreResult_v1:
  metric_id: string              # stable, dotted: family.metric[.facet]
  name: string                   # human label (may change); id must not
  family: A|B|C|D|E|F|G|H|I|Cprime|human|lab|binding|export
  authority: law|advisory|lab|ops|projection
  value: number | bool           # bool only for pass_fail polarity
  polarity: higher_is_better | lower_is_better | pass_fail
  threshold?: number             # optional; gate policy may override per suite
  passed?: bool                  # required when used by any gate
  severity: block|warn|info      # product gate uses block/warn; advisory uses warn/info
  reason: string                 # short, stable-ish; safe for amend-brief; **required on fail**
  evidence: object               # structured, redaction-aware
  evidence_paths?: string[]      # JSON-ish paths into bundle/span tree for RCA
  failure_ids: string[]          # GOLD_* / EVAL_* / HYBRID_* / TOPO_* / ...
  product_authority?: string     # e.g. commit_gold.check_commit_gold
  input_artifact: final_message|plan|bundle|trajectory|fixture_envelope|judge_input
  feedback_target: trace|span|thread|artifact   # INT-13 placement
  feedback_target_id?: string    # e.g. span:gold_evaluation
  blame_span?: string            # RCA hint when this score is primary fail
  pin_refs?: string[]            # catalog/suite/judge pins contributing to this score
  source: local_wrapper|lane_c_judge|human|lab_meta|export_health
  duration_ms?: number
```

### 6.1b Feedback score placement matrix (INT-13)

| Score class | Default `feedback_target` | Authority | Notes |
|:---|:---|:---|:---|
| `gate.deterministic_pass` / `gate.golden_promotion_eligible` | `trace` (+ evaluation record) | law | Never LLM-only |
| `artifact.final_matches_scored` / binding | `trace` + `accept_path_finalization` span | law | |
| Families B–G product wrappers | span of origin **and** local bundle | law | Prefer blame span for RCA |
| Family I topology | `trace` (+ missing-node lists in evidence) | harness law | |
| C′ / R12 / Lane C judges | `llm_generation` or eval span | advisory | `source=lane_c_judge` |
| `human.*` | targeted span/trace/thread | advisory | reason required if promo-relevant |
| `export.*` / config health | `opik_export` span / trace health | projection | never quality gate |
| train labels | local train row (+ optional dataset) | corpus only | R14 |

**Rules:** trace rules only on traces; thread rules only on threads; reasons required for failing deterministic scores, all human promo-relevant scores, and all LLM judges; local bundle write is synchronous SoT; Opik score upload is async best-effort. Annotations cannot silently rewrite historical scores — append-only with provenance.

**Opik mapping:** export may flatten to Opik feedback `{name, value, reason}` — **local envelope remains SoT**. Never let Opik rename collapse distinct `metric_id`s.

**Normalization for dashboards (optional, non-gating):**

| polarity | display_score ∈ [0,1] |
|:---|:---|
| `pass_fail` | `1.0` if passed else `0.0` |
| `higher_is_better` | clamp01(value) or suite-defined map |
| `lower_is_better` | clamp01(1 - value) or suite-defined inverse |

Gates **must not** rely on display normalization alone — use `passed` / raw policy.

---

### 6.2 Family A — Artifact / binding

**Authority:** law · **Plane:** A · **Slice:** S2–S3  
**Product authority:** accept-path emitters, bundle binders, final-bytes capture  
**Gate role:** any fail ⇒ `gate.deterministic_pass=false`; required for golden promotion

| metric_id | Polarity | Severity | Input | Pass when | Failure IDs (indicative) | Evidence |
|:---|:---|:---|:---|:---|:---|:---|
| `a.final_message_present` | pass_fail | block | bundle/final | Final rendered message bytes present & non-empty | `EVAL_FINAL_ABSENT` | byte_len, content_sha256 |
| `a.final_bytes_stable` | pass_fail | block | bundle | Scored bytes == accepted bytes (no silent restrip) | `EVAL_FINAL_BYTES_MISMATCH` | scored_sha, accepted_sha |
| `a.artifact_class_known` | pass_fail | block | bundle | Artifact class ∈ closed set (`final_accept`, `fixture_expected`, …) | `EVAL_ARTIFACT_CLASS_UNKNOWN` | artifact_class |
| `a.binding_complete` | pass_fail | block | bundle/trajectory | Bound path has required stage stamps / ids | `EVAL_BINDING_INCOMPLETE` | missing_fields[] |
| `a.binding_unbound_explicit` | pass_fail | warn/block* | bundle | Unbound runs label unbound (no fake bind) | `EVAL_FAKE_BOUND` | bound=false reasons |
| `a.bundle_schema_valid` | pass_fail | block | bundle | `ape_bundle_v1` validates | `EVAL_BUNDLE_SCHEMA` | schema_version, errors[] |
| `a.scored_target_order_ok` | pass_fail | block | bundle | Scoring order respects final-primary law (F1) | `EVAL_SCORE_TARGET_ORDER` | targets[] |

\*block in CI/offline SoT suites; warn allowed only on explicit exploratory profiles.

---

### 6.3 Family B — Hybrid format

**Authority:** law · **Plane:** A · **Slice:** S2  
**Product authority:** Hybrid Commit Standard validators / render + hook parity (`validate_commit` / models trailers) — **wrap, don’t reimplement in NL**  
**Gate role:** block on shape illegal for accept

| metric_id | Polarity | Severity | Pass when | Failure IDs | Notes |
|:---|:---|:---|:---|:---|:---|
| `b.header_shape` | pass_fail | block | `<emoji> <type>(<scope>): <subject>` parse OK | `HYBRID_HEADER_SHAPE` | |
| `b.gitmoji_present` | pass_fail | block | gitmoji present & known mapping path | `HYBRID_GITMOJI` | |
| `b.cc_type_known` | pass_fail | block | type ∈ SOP/CC closed set | `HYBRID_CC_TYPE` | |
| `b.scope_shape` | pass_fail | block | scope present/legal per product rules | `HYBRID_SCOPE` | overlaps gold scope-filename at D |
| `b.subject_length` | pass_fail | block | subject ≤ 72 (unless explicit product exception) | `HYBRID_SUBJECT_LEN` | |
| `b.trailers_parse` | pass_fail | block | required trailer block parses | `HYBRID_TRAILER_PARSE` | |
| `b.trailers_issue_ref` | pass_fail | block/warn† | `Resolves\|Refs\|Closes\|Fixes\|Null` form; `Null` ⇒ `#0` only | `HYBRID_ISSUE_REF` | |
| `b.trailers_semver` | pass_fail | block | `SemVer-Impact` present & closed vocab | `HYBRID_SEMVER_TRAILER` | value legality vs path-class → Family C |
| `b.trailers_change_types` | pass_fail | block | `Change-Types` present & parse | `HYBRID_CHANGE_TYPES` | |
| `b.trailers_changelog_groups` | pass_fail | block | `Changelog-Groups` present & parse | `HYBRID_CHANGELOG_GROUPS` | allowlist fit → C/E |
| `b.structured_envelope` | pass_fail | block | machine envelope/schema for plan/message struct OK (FIND-002) | `HYBRID_STRUCT_ENVELOPE` | wraps product models, not G-Eval |

†Owner/`Null` policy stays product law; harness mirrors it.

---

### 6.4 Family C — Path-class / contract

**Authority:** law · **Plane:** A · **Slice:** S2  
**Product authority:** `commit_quality.classify_diff_class` / `presentation_constraints` / `evaluate_presentation_gates`; contract smoke adjacency. **Do not** call `evaluate_presentation_guards` or invent a third presentation table.  
**Gate role:** block when presentation violates path-class ceilings. Catalog warn rows (`c.changelog_antisignal`, FIND-004 evidence-surface) stay out of default S2b `require_block` unless a suite promotes them.

| metric_id | Polarity | Severity | Product wrap | Failure IDs | Notes |
|:---|:---|:---|:---|:---|:---|
| `c.diff_class_resolved` | pass_fail | block | `classify_diff_class` | `PATH_CLASS_UNRESOLVED` | emits `path_class_gate` label |
| `c.semver_ceiling` | pass_fail | block | constraints + gold path-class | `GOLD_PATH_CLASS_SEMVER_CEILING` | |
| `c.type_allowed` | pass_fail | block | forbid/force type matrices | `GOLD_PATH_CLASS_TYPE_MISMATCH` | |
| `c.scope_forced_ok` | pass_fail | block | force_scope / hints | `PATH_CLASS_SCOPE` | |
| `c.security_claim_evidence` | pass_fail | block | security path evidence helpers | `PATH_CLASS_SECURITY_EVIDENCE` | claim vs path |
| `c.changelog_antisignal` | pass_fail | **warn** | changelog path antisignal | `PATH_CLASS_CHANGELOG_ANTISIGNAL` | catalog warn; not in default S2b block |
| `c.contract_smoke` | pass_fail | block | `GOLD_CONTRACT_SMOKE` path | `GOLD_CONTRACT_SMOKE` | primary fields ↔ contract |
| `c.evidence_surface_precision` | higher_is_better | warn‡ | deterministic allowlist (FIND-004) | `EVAL_EVIDENCE_SURFACE_NOISE` | claims outside staged/path-class/contract surfaces |
| `c.evidence_surface_recall` | higher_is_better | warn‡ | deterministic required surfaces | `EVAL_EVIDENCE_SURFACE_GAP` | required surfaces unmentioned when policy says required |

‡Default **warn** in v0 (diagnostic→may promote to block per suite after calibration). **Never** implemented as Opik ContextPrecision/Recall LLM builtins.

---

### 6.5 Family D — Gold strict

**Authority:** law · **Plane:** A · **Slice:** S2  
**Product authority:** `commit_gold.check_commit_gold` / `GoldReport` / `STRICT_FAIL_CODES`  
**Gate role:** `gold_mode=strict` codes ⇒ block; warn mode ⇒ severity warn but still recorded

| metric_id | Polarity | Maps from product codes | Notes |
|:---|:---|:---|:---|
| `d.gold_report_ok` | pass_fail | aggregate `GoldReport.ok_for_mode` | single rollup; evidence lists codes |
| `d.body_inventory` | pass_fail | `GOLD_BODY_INVENTORY` | banned body openers |
| `d.subject_inventory` | pass_fail | `GOLD_SUBJECT_INVENTORY` | multi-action subject |
| `d.included_changes_coverage` | pass_fail | `GOLD_INCLUDED_CHANGES_MISSING` | multi-surface coverage |
| `d.group_primary_match` | pass_fail | `GOLD_GROUP_PRIMARY_MISMATCH` | |
| `d.type_group_coherent` | pass_fail | `GOLD_TYPE_GROUP_INCOHERENT` | |
| `d.semver_matrix` | pass_fail | `GOLD_SEMVER_MATRIX_MISMATCH` | SOP matrix |
| `d.scope_filename` | pass_fail | `GOLD_SCOPE_FILENAME` | |
| `d.subject_title_case` | pass_fail | `GOLD_SUBJECT_TITLE_CASE` | |
| `d.skeleton_fallback_final` | pass_fail | `GOLD_SKELETON_FALLBACK_FINAL` | final must not be skeleton · **non-weaken** product code |
| `d.process_meta_body` | pass_fail | `GOLD_PROCESS_META_BODY` | |
| `d.path_class_semver` | pass_fail | `GOLD_PATH_CLASS_SEMVER_CEILING` | may alias C for dual emit once |
| `d.path_class_type` | pass_fail | `GOLD_PATH_CLASS_TYPE_MISMATCH` | |
| `d.fixture_product_framing` | pass_fail | `GOLD_FIXTURE_PRODUCT_FRAMING` | |
| `d.docs_implementation_claim` | pass_fail | `GOLD_DOCS_IMPLEMENTATION_CLAIM` | |
| `d.breaking_compat` | pass_fail | `GOLD_BREAKING_COMPAT_CONTRADICTION` | |
| `d.high_risk_theme_coverage` | pass_fail | `GOLD_HIGH_RISK_THEME_MISSING` | |
| `d.strict_fail_set` | lower_is_better | count(`STRICT_FAIL_CODES` ∩ findings) | value=count; pass iff 0 in strict suites |

**Shared API (S2b / #227 T11):** `score_family_d(...) -> tuple[list[ScoreResultV1], GoldReport | None]` **or** an equivalent runner-owned slot. Exactly **one** `check_commit_gold` call per evaluable case. The runner retains the report; Family F consumes it and never invokes gold independently. Add a call-count test.

**Emit rule (evaluable messages):** emit every mapped catalog D row from that one report. Present gold code ⇒ failed; absent code ⇒ passed; gold build/parse error ⇒ fail closed, especially `d.strict_fail_set`. Do **not** N-scan the message.

**Empty / oversize exception (T3):** missing, empty, or oversize selected targets emit H precondition / A/H health rows and **skip message-dependent families, including mapped D**. Never mint an empty-input `d.strict_fail_set` gold pass. Compatibility rows, if retained, are `unevaluable`/`skipped`, not pass. Preserve FIND-026 anti-fan-out. `h.eval_input_size_ok` is catalog **warn** and only blocks through explicit suite promotion.

**C/D dual emission (T2):** one product/gold finding may be represented in Family C and the mapped Family D row from **shared** evidence/`GoldReport`. Requiring both IDs must not trigger a second gold scan or double-count. Evidence must identify the shared source. Add a C∩D consistency test.

**Body lock:** gold is a validator, not optional cosmetic — counters/findings/`gold_blocked`/`gold_regen_attempts` must be consistency-checked against the final message (Session-12 / Regime A recovery-poison class).

---

### 6.6 Family E — Craft / presentation

**Authority:** law · **Plane:** A · **Slice:** S2  
**Product authority:** `evaluate_presentation_guards` and craft helpers only (`changelog_groups_allowlisted`, `min_included_change_bullets`, secondary-fill, low-confidence posture, banned openers). **Do not** call `evaluate_presentation_gates` or invent a third presentation table.  
**Gate role:** block when product craft gate would; else warn. Catalog warn rows stay out of the default S2b block tuple.

| metric_id | Polarity | Severity | Intent |
|:---|:---|:---|:---|
| `e.presentation_constraints_applied` | pass_fail | block | constraints derivation succeeded for class |
| `e.stub_inventory_coherent` | pass_fail | warn/block | included-change stubs ↔ body bullets policy |
| `e.banned_craft_openers` | pass_fail | block | craft openers (if not wholly under D body inventory) |
| `e.docs_tests_craft` | pass_fail | warn/block | docs/tests-only craft rules |
| `e.low_confidence_posture` | pass_fail | warn | low-confidence presentation posture respected when ranked low |
| `e.skeleton_avoidance` | pass_fail | block | overlaps D skeleton; craft-side detection retained if distinct |
| `e.secondary_intent_fill_legal` | pass_fail | block | secondary fill cannot invent forbidden feat/fix under purity |
| `e.changelog_groups_allowlisted` | pass_fail | block | `changelog_groups_allowlisted` product helper |
| `e.min_included_bullets` | pass_fail | warn/block | `min_included_change_bullets` policy |

---

### 6.7 Family F — Inventory / attribution

**Authority:** law · **Plane:** A · **Slice:** S2  
**Product authority:** gold inventory checks + deterministic claim-vs-staged attribution (product “hallucination” remap)  
**Gate role:** block on core inventory fails; evidence-surface diagnostics per C/F policy

| metric_id | Polarity | Severity | Intent |
|:---|:---|:---|:---|
| `f.subject_attribution` | pass_fail | block | subject claims attributable to staged signals |
| `f.body_attribution` | pass_fail | block | body claims attributable / not banned inventory openers |
| `f.included_changes_vs_diff` | pass_fail | block | included changes cover required surfaces |
| `f.staged_path_allowlist` | pass_fail | block | no primary claim naming unstaged/foreign paths (policy) |
| `f.counter_integrity` | pass_fail | block | gold counters / expected fixture counters match where encoded |
| `f.claim_evidence_alignment` | higher_is_better | warn | FIND-004 family rollup (precision×recall style deterministic) |
| `f.security_claims_need_paths` | pass_fail | block | `security_claims_without_path_evidence` |

**Shared gold:** Family F consumes Family D’s retained `GoldReport` and **never** calls `check_commit_gold` independently.

**Explicit non-goal:** Opik `Hallucination()` as implementation of Family F.

---

### 6.8 Family G — Authority / safety (deterministic)

**Authority:** law · **Plane:** A · **Slice:** S2  
**Product authority:** ranker/SOP identity, no SOP-mutation claims, deterministic safety of accept path — **not** Opik Moderation  
**Gate role:** block

| metric_id | Polarity | Severity | Intent |
|:---|:---|:---|:---|
| `g.ranked_identity_preserved` | pass_fail | block | final message respects ranked semantic contract identity |
| `g.sop_not_mutated` | pass_fail | block | no claim/path that mutates SOP via eval overlay |
| `g.semantic_contract_bound` | pass_fail | block | selected contract still bound at score time |
| `g.no_eval_policy_fork` | pass_fail | block | **non-vacuous** source/import-surface self-check: fail on a second gold/Hybrid/path-class/header authority, eval-only `GOLD_*`, or duplicate header regex law; require product-symbol wrapping/imports |
| `g.issue_null_policy` | pass_fail | block | `Null` issue id is `#0` only (owner law) |
| `g.secrets_not_in_message` | pass_fail | block | named **local** deterministic secret-shape helper on the **final message only**; no `git_cg.secrets`, `resolve_secret`, `.env`, 1Password, vault, live store, or environment discovery |

**Not in G:** LLM moderation, compliance-risk builtins (→ R6 ops / #219).

---

### 6.9 Family H — Harness health

**Authority:** law (eval/CI) · **Plane:** A · **Slice:** S2–S3, S6  
**Product authority:** harness itself, pins, schema, offline completeness, trajectory health (R7), structured compliance (FIND-002)  
**Gate role:** fails **eval/CI** and golden eligibility; does **not** alone mean “Hybrid prose ugly,” but **does** mean “measurement invalid”

| metric_id | Polarity | Severity | Intent |
|:---|:---|:---|:---|
| `h.catalog_pinned` | pass_fail | block | `metric_catalog_version` matches suite pin |
| `h.suite_snapshot_pinned` | pass_fail | block | dataset/suite hash pinned (no `latest`) |
| `h.prompt_pack_pinned` | pass_fail | block | when generation recorded, pack hash present |
| `h.offline_complete` | pass_fail | block | offline suite needed no network |
| `h.score_envelope_valid` | pass_fail | block | all emitted scores validate ScoreResult_v1 |
| `h.structured_bundle_compliance` | pass_fail | block | FIND-002 bundle/plan structured compliance |
| `h.evaluator_error_free` | pass_fail | block | no metric exception / empty skip without reason |
| `h.pin_integrity` | pass_fail | block | judge/model pins resolvable when Lane C ran |
| `h.trajectory_stages_declared` | pass_fail | warn/block | R7 declared stage taxonomy present when bound |
| `h.trajectory_stages_observed` | pass_fail | warn/block | observed stages ⊆/≈ declared (policy) |
| `h.export_nonblocking` | pass_fail | info | export fail classified export-only (F4) — **must pass** as “nonblocking held” |
| `h.compat_hash_resume` | pass_fail | block | resume refused across incompatible hashes |
| `h.doctor_green` | pass_fail | warn | FIND-003 `eval doctor` aggregate (dev profile) |


**Export / config health extensions (Family H adjacency — not message prose):**

| metric_id | Polarity | Severity | Intent |
|:---|:---|:---|:---|
| `h.export_config_resolved` | pass_fail | warn | project/env/mode resolved; no Default Project fallthrough |
| `h.export_status_classified` | pass_fail | info | export status ∈ known enum |
| `h.local_bundle_durable` | pass_fail | block (eval) | Layer A present before/without cloud |
| `h.layer_a_before_export` | pass_fail | block (eval) | bundle written before SDK export attempt |
| `h.flush_bounded` | pass_fail | warn | flush used explicit timeout on short-lived procs |
| `h.prompt_pack_hash_known` | pass_fail | block when gen | prompt identity recorded (INT-26) |
| `h.graph_version_known` | pass_fail | warn | pipeline graph pin present when topology asserted |
| `h.judge_input_isolated` | pass_fail | block (suite) | F6/JUDGE-INPUT hold for the run |
| `h.eval_input_nonempty` | pass_fail | block (eval row) | scored artifact present after bind; empty ⇒ single classified fail (FIND-026) |
| `h.eval_input_size_ok` | pass_fail | **warn** | artifact under max eval bytes; oversized ⇒ classify/unevaluable and short-circuit; **not** a default S2b veto (blocks only if a suite explicitly promotes it); never N× 504 storm |
| `h.eval_error_fanout_bounded` | pass_fail | block (harness) | one bad row must not multiply into K identical evaluator exceptions |
| `h.online_scores_match_product_card` | pass_fail | block (bound export) | live feedback for product checks matches local `score_card` / final bytes (FIND-027) |
| `h.prompt_pack_suite_fresh` | pass_fail | warn (doctor) | prompt pack change has local suite pin/result (FIND-028) |

---

### 6.9b Family I — Trace topology & lifecycle (FIND-019)

**Authority:** harness/eval law (golden-eligibility + CI topology suites) · **Plane:** A/B evidence · **Slice:** S2–S3, S6  
**Product authority:** instrumentation + accept-path completeness — **not** Hybrid prose semantics  
**Gate role:** missing/contradictory topology ⇒ **eval fail** and **blocks golden promotion** on bound accept-path; valid message may still be product-pass (F1/D16 incomplete evidence pattern)

#### Closed span taxonomy → Opik kinds

| Span name | Opik kind | Required on bound accept-path? |
|:---|:---|:---:|
| `diff_extraction` | `data_processing` | ✅ |
| `path_classification` | `data_processing` | ✅ |
| `intent_ranking` | `function` | ✅ |
| `contract_resolution` | `function` | ✅ |
| `llm_generation` | `llm` | ✅ when model called |
| `plan_normalisation` | `data_processing` | ✅ when plan path used |
| `gold_evaluation` | `function` | ✅ |
| `presentation_guard` | `guardrail` or `function` | ✅ |
| `regeneration` | `function` | when regen attempts > 0 |
| `fallback` | `function` | when fallback path taken |
| `final_render` | `data_processing` | ✅ |
| `accept_path_finalization` | `function` | ✅ accept-path |
| `opik_export` | `external_api` or `general` | when export attempted |

#### Metrics

| metric_id | Polarity | Severity | Intent |
|:---|:---|:---|:---|
| `i.trace_root_present` | pass_fail | block | root attempt trace exists for bound run |
| `i.lifecycle_complete` | pass_fail | block | terminal state recorded |
| `i.span_tree_valid` | pass_fail | block | tree parses; no cycles/orphans beyond policy |
| `i.span_parentage_valid` | pass_fail | block | parent ids resolve inside trace |
| `i.required_spans_present` | pass_fail | block | required taxonomy present for artifact_class |
| `i.span_order_valid` | pass_fail | block/warn | stages respect declared pipeline graph |
| `i.thread_id_present` | pass_fail | block | `session_thread_id` set on multi-attempt and accept-path |
| `i.thread_continuity` | pass_fail | block | attempts join same session thread correctly |
| `i.counter_span_consistent` | pass_fail | block | e.g. gold_regen_attempts ↔ regeneration spans (Session-12 class) |
| `i.finalization_observed` | pass_fail | block | accept-path finalization member present when claimed bound |
| `i.export_status_classified` | pass_fail | info | export enum known (mirrors H) |
| `i.graph_observed_matches_declared` | pass_fail | warn/block | declared `git_cg_pipeline_graph_v1` vs observed edges |
| `i.replay_lineage_valid` | pass_fail | block | replay rows carry lineage; do not clobber source |
| `i.no_cross_case_contamination` | pass_fail | block | two case_ids never share session thread |
| `i.attempt_order_valid` | pass_fail | warn | attempt_index monotonic in thread |
| `i.correlation_envelope_valid` | pass_fail | block | cross-hook join fields present when multi-process |

**Thread secondary scores (advisory only — INT-38; never in `gate.deterministic_pass`):**  
`thread.chain_complete`, `thread.evidence_complete`, `thread.regeneration_count_consistent`, `thread.final_matches_last_generation`, `thread.human_accepted`, `thread.settled`.

**RCA fields derived from Family I (for explain/diagnose):** `blame_span`, `first_divergent_span`, `missing_required_spans[]`, `unexpected_spans[]`, `diag_fingerprint` inputs.

**Official refs:**  
[Tracing concepts](https://www.comet.com/docs/opik/tracing/concepts) · [Log traces](https://www.comet.com/docs/opik/tracing/log_traces) · [Task span metrics](https://www.comet.com/docs/opik/evaluation/metrics/task_span_metrics) · [Evaluate agent trajectory](https://www.comet.com/docs/opik/evaluation/advanced/evaluate_agent_trajectory) · [Log agent graphs](https://www.comet.com/docs/opik/tracing/log_agent_graphs) · [Log conversations](https://www.comet.com/docs/opik/tracing/log_conversations)

---

### 6.10 Secondary sets — C′ / human.* / lab / R12

**Authority:** advisory or lab · **Plane:** B · **Never** in `gate.deterministic_pass` / sole golden

#### 6.10.1 Eligibility gate (product-side)

| metric_id | Polarity | Pass when |
|:---|:---|:---|
| `gate.deterministic_pass` | pass_fail | all required A–H block-severity metrics passed |
| `gate.semantic_cohort_eligible` | pass_fail | **authorization only** — `suite.allows_lane_c` ∧ (`gate.deterministic_pass` ∨ `suite.lab_override`) ∧ **judge identity pins resolvable** (model/pack/params — **NOT secrets**). Credentials/network affect availability/skip only (D4/D4′). |
| `gate.golden_promotion_eligible` | pass_fail | §2.4 minimum — no LLM-only path |

#### 6.10.2 C′ semantic cohort (R1) — after eligibility

| metric_id | Polarity | Default | Notes |
|:---|:---|:---|:---|
| `cprime.geval_craft` | higher_is_better | off | pinned G-Eval craft rubric; **not** SOP |
| `cprime.geval_relevance` | higher_is_better | off | residual relevance narrative |
| `cprime.answer_relevance` | higher_is_better | off | advisory |
| `cprime.usefulness` | higher_is_better | off | advisory |
| `cprime.meaning_match` | higher_is_better | off | vs expected only in fixture/meta envelopes |
| `cprime.hallucination_narrative` | lower_is_better | off | narrative only; product hallucination = F |
| `cprime.jury_aggregate` | higher_is_better | off | R1 ensemble still advisory |
| `cprime.conversation_thread` | higher_is_better | off | regen-chain only |
| `cprime.flakiness_std` | lower_is_better | lab (R8) | multi-run stddev |

All C′ rows: `authority=advisory`, `source=lane_c_judge`, require judge pins.

#### 6.10.3 R12 dogfood attachments (feeds R11)

| metric_id | Polarity | Mode linkage | Notes |
|:---|:---|:---|:---|
| `dogfood.geval_last` | higher_is_better | always/sample/async | last run score for amend-brief |
| `dogfood.geval_latency_ms` | lower_is_better | any on | budget accounting |
| `dogfood.geval_pin_ok` | pass_fail | any on | pin integrity for dogfood judge |
| `dogfood.mode` | n/a (label) | — | `off\|sample\|always\|async` recorded as evidence, not scored |

Arbitration: see §3 R12 — L1 wins; never sole accept.

#### 6.10.4 `human.*` (R4)

| metric_id | Polarity | Notes |
|:---|:---|:---|
| `human.craft_rating` | higher_is_better | multi-rater capable |
| `human.gold_dispute` | pass_fail / categorical | dispute flag |
| `human.regime_label` | categorical | A/B adjudication aid |
| `human.notes_present` | pass_fail | ops completeness |

Non-overriding; cannot sole-promote golden.

#### 6.10.5 Lab meta-eval (R2) + ops (R6) + NLP (R10)

| metric_id | Authority | Polarity | Notes |
|:---|:---|:---|:---|
| `lab.judge_equals_label` | lab | pass_fail | H/M cookbook shape |
| `lab.judge_fp_rate` | lab | lower_is_better | cohort aggregate |
| `lab.judge_fn_rate` | lab | lower_is_better | cohort aggregate |
| `ops.moderation_flag` | ops | pass_fail / higher risk | R6 off-by-default; scrubbed |
| `ops.compliance_risk` | ops | higher_is_better risk↓ map carefully | never Hybrid legality |
| `nlp.bleu` / `nlp.rouge` / `nlp.bertscore` / `nlp.levenshtein` | diagnostic | per metric | R10; never sole law |

---

### 6.11 Aggregate gate composition (v0)

```text
gate.deterministic_pass =
    ALL block-severity metrics in Families A–H with suite.require=true
    AND Family I block metrics with suite.require_topology=true (default on bound accept-path)
    AND h.evaluator_error_free
    AND a.binding_complete (for bound suites)
    AND d.gold_report_ok under suite gold_mode
    # AGG-GATE: never substitute suite/mean pass-rate for the above (M12)

gate.semantic_cohort_eligible =   # authorization ONLY (D4) — entry enablement, not product pass
    suite.allows_lane_c
    AND (gate.deterministic_pass OR suite.lab_override)
    AND judge_identity_pins_resolvable   # model/pack/params — NOT secrets (D4′)
    # NOTE: corpus.capture_on / train eligibility is SEPARATE and may include fails

judge_execution_available =        # availability / skip / lab class ONLY (D4′)
    gate.semantic_cohort_eligible
    AND credentials_present
    AND provider_client_constructible
    # Missing key/network MUST NOT render cohort "unauthorized"
    # Default offline scoring path NEVER invokes network judges

# lab_override (F-B / C-TAX / C-ELIG):
#   marks the run eligible-diagnostic and emits skip rows only —
#   zero judge side effects on det-fail cohorts (spine never runs judges there)

# Advisory emission (D30/D31) — when C′ rows are produced later:
#   use make_advisory_score (or equivalent); never make_score(passed=None) for 1–5
#   success reason MUST be the stable machine class "scored" (not None)
#   free-form judge prose lives only in evidence["rationale"] (≤800, scrubbed)

corpus.train_row_eligible =   # not a product gate
    owner.profile.allows_train_capture
    AND pins_and_schema_ok
    AND secret_scrub_status in {clean, quarantined_fields}
    AND train_label is set OR unlabeled_allowed
    AND capture_on matches row outcome (pass|fail|all)
    AND split_group_id assigned
    AND antipattern rows excluded from positive_train destinations

gate.golden_promotion_eligible =
    a.binding_complete AND a.bundle_schema_valid
    AND gate.deterministic_pass
    AND path-class/gold consistency (C∩D)
    AND i.lifecycle_complete AND i.required_spans_present  # incomplete evidence ≠ promote
    AND optional weak user_acceptance
    AND NOT any sole-LLM shortcut
    AND export health does NOT substitute for the above

commit accept-path success (product) =
    product validators / hooks only
    ⊭ Opik export, C′, R12, human.*, lab, Family I alone as Hybrid prose fail
```

**S2b / #227 interpretation (does not repeal later S2c/S3 topology law):**

* Offline S2b implements Families **A–H** only and adds H FIND-002. Family I validators/emitters, live topology metrics, and `suite.require_topology=true` remain **S2c/S3** and are not #227 close-bar items.
* `c.` / `e.` / `f.` / `g.` are Plane A. Requested C/E/F/G already participate in `gate.deterministic_pass` and fail closed. Removing those prefixes from `_IGNORE_FAMILY_PREFIXES` corrects **stale advisory labeling** of *unrequested* failures; it is not a veto-path invention.
* Still advisory / record≠gate: C′ / `cprime`, lab, human, NLP, export, dogfood.
* Keep `gate.semantic_cohort_eligible=False` in offline S2b. C is not C′. Replace stale “S2a/C-prime deferred (S2b)” wording with offline-S2b / later Lane C or S2c wording.

---

### 6.12 R11 amend-brief projection (catalog → L2)

Minimum fields the brief **must** be able to carry from this catalog:

| Brief field | Source metrics |
|:---|:---|
| `l1.regime` | derived from failure_ids / suite tags |
| `l1.family_rollups[]` | pass counts per A–H |
| `l1.failure_ids[]` | union of block/warn failures |
| `l1.path_class` | `c.diff_class_resolved` evidence |
| `l1.gold_counters` | `f.counter_integrity` / D evidence |
| `l1.blocking` | `gate.deterministic_pass` |
| `lane_c_attachments[]` | `dogfood.*` + optional `cprime.*` last-N |
| `doctor` | `h.doctor_green` summary (optional) |

---

### 6.13 Explicitly NOT in authoritative catalog (v0)

| Excluded as law | Why | Where it may live |
|:---|:---|:---|
| Opik Hallucination / Moderation / G-Eval / Juries builtins | F3 | C′ / lab / R12 only |
| **Opik `StructuredOutputCompliance` as accept/CI law** | Vendor SOC is LLM-backed, not schema-absolute (INT-14 / STRUCT-LOCAL) | Lab diagnostic only; local Pydantic/schema wrappers remain law |
| Context precision/recall builtins | RAG framing | FIND-004 deterministic C/F only |
| Trajectory accuracy as semantic commit score | tool-agent myth | H/R7 evidence only |
| Agent tool correctness | not product shape | ❌ |
| Summarization coherence/consistency | poor fit | ❌ default |
| Dialogue helpfulness | not accept law | ❌ |
| BLEU/ROUGE/etc. sole Hybrid/gold | R10 | diagnostic only |
| Ollie-authored ephemeral metrics | F8 | ❌ |
| Unpinned floating judge metrics | F5 | ❌ |
| Export success as product pass | F4 | `h.export_nonblocking` inverse law |
| Experiment mean pass-rate alone | M12 AGG-GATE (INT-23) | Dashboard only |
| Thread secondary scores as Hybrid substitute | R13 additive | advisory only |
| Unmapped Opik builtin polarity | SCORE-POLARITY foot-gun (INT-14) | remap via catalog or keep lab |
| Online format metrics on raw unparsed trace blob | FIND-027 / ARTIFACT-BIND-LIVE | disable until rebound to final message / product card |
| SOP threshold changes driven only by `user_acceptance`≫online format gap | INT-48 / F3 | investigate binding first |
| Cloud prompt version count as validation | FIND-028 | local suite pin + optional experiment mirror |

---

### 6.13b SCORE-POLARITY registry notes (INT-14)

| Opik / external name | Typical vendor polarity | Local handling |
|:---|:---|:---|
| Hallucination | high often **worse** | C′ only; remap or invert label; never sole gate |
| Moderation | high often **worse** | lab/ops; never accept law |
| G-Eval / Usefulness / Answer relevance | high better | advisory C′ / R12 under pin |
| StructuredOutputCompliance (Opik) | pass-ish via LLM | **reject as law** — STRUCT-LOCAL |
| Local `ScoreResult.polarity` | explicit enum | **SoT for dashboards & gates** |

Silent polarity flips require **major** catalog bump (§6.14).

### 6.14 Catalog versioning & change control

| Event | Required |
|:---|:---|
| Add authoritative metric | bump `metric_catalog_v0` → v0.x or v1; update suite pins; tests |
| Change polarity | **major** catalog bump; migrate dashboards; forbid silent flip |
| Add C′/dogfood metric | minor OK if advisory; still pin judge pack |
| Remove metric_id | deprecate window; keep alias read for old snapshots |
| Fork product rule into eval-only prompt | **forbidden** (M2) — change product module + tests instead |

**Pin string (suite header example):**

```text
metric_catalog: metric_catalog_v0@<content_sha256>
```

---

### 6.15 Implementation mapping (slice ownership)

| Families / sets | Primary slice | Notes |
|:---|:---:|:---|
| Envelope + catalog pin | S0 | schemas + this doc |
| A binding-related | S2–S3 | binding hardened in S3 |
| B–G wrappers | S2 | single gold fan-out |
| H core | S2 + S6 doctor | R7 trajectory in S3 |
| **Family I topology** | S2 validators + S3 emitters + S6 explain | FIND-019 harness law |
| export/config health | S3–S4 + S6 doctor | never quality gate |
| C′ / R1 / R8 / R10 | S5 | gated |
| R2 lab / R6 ops | S5–S6 | off-by-default |
| R11 brief / R12 dogfood | S6 | approved active |
| Docs of catalog | S7 | ADR + contributor map |

---

### 6.16 v0 completeness checklist

- [x] ScoreResult envelope + polarity law  
- [x] Families A–H metric_id sketches bound to product authorities  
- [x] Gold codes mapped (D)  
- [x] FIND-002 structured compliance → H/B  
- [x] FIND-004 evidence-surface → C/F  
- [x] FIND-003 doctor → H  
- [x] C′ / human / lab / R10 secondary sets  
- [x] R12 dogfood ids + R11 projection  
- [x] M10 severity parity + M11 record≠gate  
- [x] Gate composition / dual corpus eligibility  
- [x] Explicit exclusions  
- [x] Versioning / slice ownership  
- [x] Runtime JSON Schema design → **§7** (files on disk → S0)  
- [x] Per-metric pytest AC ownership → **§8.2** (detail in impl)  


---

## 7. Local schemas & corpus

[x] **Schema pack pin id:** `schema_pack_v0` · pairs with `metric_catalog_v0`  
**Rule:** local files under repo (or dev-only `.eval/`) are SoT. Opik datasets/experiments are **projections**. JSON Schema freeze happens in S0; this section is the design SSOT until then.

### 7.0 Schema pack laws

| # | Law |
|:---:|:---|
| S0 | Every scored run materializes or references an `ape_bundle_v1` (bound or explicit unbound). |
| S1 | `expected_*` fields live only in **fixture / meta-eval envelopes** — never injected into generation task input (F6). |
| S2 | Compatibility hash covers: schema_pack + metric_catalog + suite snapshot + prompt-pack (if gen) + judge pins (if Lane C). |
| S3 | Resume/export refuse silent merge across compatibility-hash mismatch. |
| S4 | Redaction profile is a first-class field (**R14 ladder**). `public_ci`/`default_scrub` stay thin; owner may select `train_rich` / `antipattern_vault`. Secrets always scrubbed; scrub fail ⇒ quarantine fields, not silent ambient leak. |
| S5 | Artifact classes are a **closed enum**; mixed classes in one score stream without labels = harness fail (Family H). |
| S6 | Regime A/B + failure/prevention IDs are first-class corpus fields (#204 law), not free-text only. |
| S7 | R11 `amend_brief_v1`, R12 dogfood, **R13 session threads**, and **R14 train_export** are schema-versioned consumers/producers — not side-channel JSON. |
| S8 | **Additive corpus:** `commit_session_thread_v1`, `message_versions`, preference pairs, and train_labels do not replace traces/spans/product telemetry. |
| S9 | **Non-degradation:** schema evolution must not require removing existing product metric fields to “make room” for Opik. |

**Default on-disk roots (dev/maintainer):**

```text
.eval/                              # gitignored local operator state (default)
  review_queue/
  checkpoints/
  dogfood/
  amend_briefs/
  sessions/                         # commit_session_thread_v1 local twins
  train_export/                     # train_export_v1 packs
  antipattern_vault/                # labeled hard-negatives (gitignored default)
  export_queue/
tests/fixtures/eval/                # committed SoT fixtures (Lane A)
  suites/
  cases/
  snapshots/
  bundles/                          # optional checked-in golden bundles
schemas/eval/                       # committed JSON Schema (S0 deliverable)
  ape_bundle_v1.schema.json
  ...
```

Basic users never need `.eval/` or `schemas/eval/`.

---

### 7.1 `ape_bundle_v1` (canonical evaluation object)

**Purpose:** one self-contained object the harness can score offline without Opik or network.  
**Produced by:** fixture encoder (S1), accept-path binder (S3), optional live capture (opt-in).  
**Consumed by:** Families A–H, gates, R11 brief, S4 mirror.

```text
ape_bundle_v1:
  schema_version: "ape_bundle_v1"
  bundle_id: string                         # stable uuid or content-addressed id
  created_at: iso8601
  producer: fixture_encoder|acceptpath_binder|live_capture|lab_tool
  redaction_profile: default_scrub|message_only|meta_eval_scrub|raw_dev_unsafe

  # --- identity / pins ---
  pins:
    schema_pack: string                     # schema_pack_v0@sha
    metric_catalog: string                  # metric_catalog_v0@sha
    suite_id?: string
    suite_snapshot_hash?: string
    prompt_pack_hash?: string               # if generation recorded
    harness_version?: string
    judge_pins?: { judge_id: pin_ref }      # only if Lane C attachments present

  # --- artifact class (closed) ---
  artifact_class:
    final_accept
    | fixture_expected
    | fixture_input_only
    | live_regen
    | unbound_offline
    | dogfood_capture
    | meta_eval_labeled

  binding:
    state: bound|unbound|partial
    bind_errors?: string[]
    thread_id?: string                      # accept-path / regen chain id
    trace_id?: string
    commit_sha?: string
    repo_fingerprint?: string               # dirty tree hash / worktree id (redacted)

  # --- primary scored target (F1) ---
  scored_targets_order: [final_message, ...]   # final_message MUST be first when present
  final_message:
    text: string                            # exact bytes as accepted/scored
    content_sha256: string
    byte_len: int
    rendered_from?: plan|raw_edit|fixture

  # --- product context (minimal, redaction-aware) ---
  plan?: object                             # CommitPlan-shaped subset if available
  hybrid_fields?: { emoji, cc_type, scope, subject, trailers: object }
  path_class:
    diff_class?: string                     # DiffClass.name or none
    path_class_gate?: string
    staged_paths?: string[]                 # may be path-only allowlist; no file bodies by default
    high_risk_surfaces?: string[]
  gold:
    mode?: off|warn|strict
    findings?: [{ code, message, severity? }]
    counters?: object                       # gold counter snapshot when relevant
  ranking?:
    primary_intent?: string
    confidence?: string
    contract_id?: string
  signals_summary?: object                  # compact DiffSignals rollup — not full diff

  # --- trajectory / R7 (optional but required when bound accept-path) ---
  trajectory?: trajectory_evidence_v1

  # --- fixture / expected envelope (ONLY on fixture & meta-eval classes) ---
  expected?:
    final_message?: string
    gold_codes_absent?: string[]
    gold_codes_present?: string[]
    counters?: object
    gate_deterministic_pass?: bool
    labels?: object                         # meta-eval only
  # WARNING: expected MUST NOT be copied into generation/judge task input except
  #          explicit judge_meta_eval_v1 envelope (F6).

  # --- corpus law / #204 ---
  corpus:
    dataset_id?: string
    case_id?: string
    source: synthetic|204_archive|acceptpath_live|dogfood|manual
    regime?: A|B|unknown                    # #204 Regime A/B
    instance_kind?: A|B|other               # Instance A/B encoding when applicable
    session_tags?: string[]                 # e.g. session-12-seed
    failure_ids?: string[]
    prevention_ids?: string[]
    provenance:
      origin: string
      captured_by?: string
      notes?: string
      links?: string[]                      # issue/PR refs, not secrets

  # --- scores (filled by harness; may start empty) ---
  scores?: ScoreResult_v1[]
  gates?:
    deterministic_pass?: bool
    semantic_cohort_eligible?: bool
    golden_promotion_eligible?: bool

  # --- secondary attachments (never authoritative alone) ---
  lane_c_attachments?: dogfood_attachment_v1[]
  human_reviews?: human_review_v1[]
  opik_projection?:
    project?: string
    dataset_name?: string
    experiment_name?: string
    trace_ids?: string[]
    export_status?: pending|ok|failed|skipped
```

#### 7.1.1 Required dimensions by artifact class

| artifact_class | final_message | binding | path_class | expected | trajectory | corpus.regime |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `final_accept` | ✅ | bound | ✅ | ❌ | ✅ preferred | optional |
| `fixture_expected` | ✅ | unbound OK | ✅ | ✅ | optional | ✅ when #204 |
| `fixture_input_only` | optional | unbound | ✅ | optional | optional | optional |
| `live_regen` | ✅ after run | partial/bound | ✅ | ❌ default | ✅ | optional |
| `unbound_offline` | ✅ | unbound explicit | optional | optional | ❌ | optional |
| `dogfood_capture` | ✅ | optional | optional | ❌ | optional | optional |
| `meta_eval_labeled` | judge I/O | unbound | optional | ✅ labels | ❌ | lab |

#### 7.1.2 Scored target order (normative)

```text
1. final_message          # F1 primary — always prefer
2. plan                   # only if suite explicitly scores plan facets
3. trajectory facets      # H/R7 — supporting
4. never: raw model scratch, mid-regen drafts, cloud-only blobs as silent primary
```

Mixing raw/mid/final in one stream without `artifact_class` + target labels ⇒ `h.score_envelope_valid` / `a.scored_target_order_ok` fail.

---

### 7.2 Supporting schemas

| Schema | Purpose | Slice | Status |
|:---|:---|:---:|:---:|
| `ape_bundle_v1` | Canonical scored object | S0–S3 | [x] design |
| `ScoreResult_v1` | Per-metric envelope (§6.1) | S0/S2 | [x] design |
| `eval_suite_v1` | Suite definition + pins + metric set | S0/S1 | [x] design |
| `eval_case_v1` | One case row → builds/points at bundle | S1 | [x] design |
| `dataset_snapshot_v1` | Immutable local snapshot + hash | S1/S4 | [x] design |
| `experiment_v1` | Local experiment run record | S2–S6 | [x] design |
| `evaluation_checkpoint_v1` | Resume checkpoints | S6 | [x] design |
| `trajectory_evidence_v1` | Declared vs observed stages (R7) | S3 | [x] design |
| `human_review_v1` / review-queue item | HITL `human.*` (R4) | S6 | [x] design |
| `judge_meta_eval_v1` | Offline judge lab (R2) | S5–S6 | [x] design |
| `thread_eval_v1` | Optional regen sub-chain grouping | S3/S5 | [x] design |
| `commit_session_thread_v1` | Full commit-unit thread (R13) | S0 stub / S3–S6 | [x] design |
| `amend_brief_v1` | R11 L2 pack (+ version refs) | S6 | [x] design (§3/§6) |
| `dogfood_attachment_v1` | R12 GEval/C′ attachment | S6 | [x] design |
| `train_row_v1` / `train_export_v1` | Training plane export (R14) | S6 | [x] design |
| `export_batch_v1` | S4 REST / Opik lake projection | S4 | [x] design |
| `trace_topology_v1` | Closed span/lifecycle tree (FIND-019) | S0 stub / S2–S3 | [x] design |
| `correlation_envelope_v1` | Cross-hook join fields (INT-15) | S0 stub / S3 | [x] design |
| `diag_issue_v1` | Deterministic diagnostic issue + fingerprint | S0 stub / S6 | [x] design |
| `git_cg_opik_config_v1` | Mode/project/env/flush config | S0 stub / S4–S6 | [x] design |
| `replay_compare_v1` | Replay lineage compare record | S0 stub / S6 | [x] design |
| `git_cg_pipeline_graph_v1` | Declared pipeline graph | S0 stub / S3 | [x] design |
| `prompt_pack_v1` | Repo-first prompt identity | S0 stub / S3–S5 | [x] design |
| `export_queue_item_v1` | Local Layer-A export queue row | S0 stub / S4–S6 | [x] design |

#### 7.2.1 `eval_suite_v1`

```text
eval_suite_v1:
  schema_version: "eval_suite_v1"
  suite_id: string                          # e.g. cm-eval-fixtures-core
  title: string
  lane: A|B|C|lab|dogfood
  pins:
    schema_pack: string
    metric_catalog: string
    snapshot: string                        # dataset_snapshot hash/id
    prompt_pack?: string
    judge_pack?: string
  mode_default: fixture_offline|acceptpath_bound|live_regen
  gold_mode: off|warn|strict
  metrics:
    require_block: metric_id[]              # must pass for gate.deterministic_pass
    require_warn_record: metric_id[]        # recorded; warn severity
    optional: metric_id[]
  gates:
    deterministic_pass: true
    semantic_cohort: false|true
    golden_promotion: false|true
  filters?: object                          # R9 triage only; never silent SoT redefine
  nb_samples?: int                          # lab/triage only
  network_policy: offline_required|network_optional|mirror_optional
  redaction_profile: string
  compatibility_hash_inputs: string[]       # explicit list folded into hash
```

#### 7.2.2 `eval_case_v1`

```text
eval_case_v1:
  schema_version: "eval_case_v1"
  case_id: string
  suite_id: string
  bundle_ref: path|bundle_id                # local SoT pointer
  artifact_class: <enum>
  corpus: <ape_bundle.corpus subset>
  tags: string[]                            # path-class, regime, session-12, ...
  expectations?:                            # fixture only
    gate_deterministic_pass?: bool
    gold_codes_absent?: string[]
    gold_codes_present?: string[]
    metric_overrides?: { metric_id: { passed?: bool, value?: number } }
  skip?: { reason: string, until?: date }
```

#### 7.2.3 `dataset_snapshot_v1`

```text
dataset_snapshot_v1:
  schema_version: "dataset_snapshot_v1"
  snapshot_id: string
  dataset_id: string                        # logical name (§7.3)
  created_at: iso8601
  content_hash: sha256                      # hash of canonical case list + bundle hashes
  case_ids: string[]
  case_count: int
  source_commit?: string                    # repo commit that built snapshot
  notes?: string
  opik_mirror?: { dataset_name, last_sync_at?, status? }
```

**Law:** CI SoT = snapshot hash, not “whatever is in Opik.”

#### 7.2.4 `experiment_v1` (local)

```text
experiment_v1:
  schema_version: "experiment_v1"
  experiment_id: string
  suite_id: string
  snapshot_id: string
  started_at / finished_at?: iso8601
  mode: fixture_offline|acceptpath_bound|live_regen|dogfood|lab_meta
  pins: <copy of effective pins>
  compatibility_hash: string
  result_summary:
    n_total / n_pass / n_fail / n_warn / n_error / n_skip
    gate_deterministic_pass_rate?: number
  item_results_ref: path                    # JSONL of per-case score bundles
  lane_c_enabled: bool
  export?: { status, batch_ids[] }
```

#### 7.2.5 `evaluation_checkpoint_v1`

```text
evaluation_checkpoint_v1:
  schema_version: "evaluation_checkpoint_v1"
  checkpoint_id: string
  experiment_id: string
  compatibility_hash: string                # MUST match to resume
  completed_case_ids: string[]
  pending_case_ids: string[]
  last_progress_at: iso8601
  mode: resume_missing|recompute_scores|replay_generation|fresh_suite_run
```

#### 7.2.6 `trajectory_evidence_v1` (R7)

```text
trajectory_evidence_v1:
  schema_version: "trajectory_evidence_v1"
  thread_id?: string
  declared_stages: string[]                 # closed accept-path taxonomy
  observed_stages: [{ name, status, ts?, detail? }]
  recovery_events?: [{ kind, detail? }]     # e.g. guard regen, skeleton risk
  graph_refs?: string[]
  complete: bool
```

Closed stage vocabulary is owned by product accept-path (S3); eval does not invent a parallel agent mythology.

#### 7.2.7 Review queue / `human_review_v1` (R4)

```text
human_review_v1:
  schema_version: "human_review_v1"
  review_id: string
  case_id / bundle_id: string
  reviewer_id: string                       # local handle; not end-user PII store
  created_at: iso8601
  scores:
    human.craft_rating?: number
    human.gold_dispute?: bool
    human.regime_label?: A|B|unknown
  notes?: string
  authority: advisory
```

Queue item path: `.eval/review_queue/<id>.json` (local SoT). Optional Opik annotation-queue mirror later — never sole SoT.

#### 7.2.8 `judge_meta_eval_v1` (R2 lab)

```text
judge_meta_eval_v1:
  schema_version: "judge_meta_eval_v1"
  cohort_id: string
  judge_id: string
  judge_pin: string
  items: [{
    item_id,
    judge_input_ref,                        # scrubbed
    expected_label,                         # visible to Equals metric only
    judge_output_label / score?,
    equals: bool,
    error_type?: FP|FN|OK|judge_error
  }]
  aggregates: { fp_rate, fn_rate, n }
  authority: lab
  network_policy: offline_preferred
```

Expected labels **must not** appear inside the judge-visible prompt unless this envelope explicitly opts into a labeled protocol and stamps it.

#### 7.2.9 `thread_eval_v1` (optional)

```text
thread_eval_v1:
  schema_version: "thread_eval_v1"
  thread_id: string
  bundle_ids: string[]                      # ordered regen/accept attempts
  advisory_scores?: ScoreResult_v1[]        # C′ conversation only
  authority: advisory
```

#### 7.2.10 `dogfood_attachment_v1` / `export_batch_v1`

```text
dogfood_attachment_v1:
  schema_version: "dogfood_attachment_v1"
  run_id: string
  judge_id: string
  pin_ref: string
  mode: off|sample|always|async
  metric_id: dogfood.geval_last|cprime.*|...
  score?: number
  polarity?: higher_is_better|...
  rationale_short?: string
  latency_ms?: number
  created_at: iso8601
  authority: advisory
  message_sha256: string                    # link without storing full text twice

export_batch_v1:
  schema_version: "export_batch_v1"
  batch_id: string
  project: string                           # pinned project/lane — no Default Project dump
  experiment_id: string
  item_refs: string[]
  idempotency_key: string
  size_bytes: int
  status: pending|ok|failed|skipped
  error_class?: export_network|export_auth|export_validation|export_size
  # failure NEVER flips gate.deterministic_pass
```

#### 7.2.11 `amend_brief_v1` (R11) — normative pointer

See §3.5 / §6.12. Brief **reads** bundles + scores + last-N `dogfood_attachment_v1`; it does not become golden SoT.

---


#### 7.2.12 `trace_topology_v1` (FIND-019 / INT-01)

```text
trace_topology_v1:
  schema_version: "trace_topology_v1"
  session_thread_id: string
  thread_subchain_id?: string
  trace_id: string
  attempt_index: int
  parent_trace_id?: string
  replay_of_trace_id?: string
  replay_of_bundle_hash?: string
  root:
    name: "commit_attempt_trace"
    terminal_state: ok|product_error|export_error|cancelled|unknown
    started_at?: iso8601
    ended_at?: iso8601
  spans: SpanNode[]
  required_span_set: string[]          # resolved from artifact_class + path
  declared_graph_pin?: string          # git_cg_pipeline_graph_v1@sha
  correlation?: correlation_envelope_v1
  counters?: object                    # gold_regen_attempts, fallback_used, ...
```

#### 7.2.13 `diag_issue_v1` (FIND-021 / INT-07)

```text
diag_issue_v1:
  schema_version: "diag_issue_v1"
  issue_id: string
  fingerprint: string                  # stable; excludes trace ids, timestamps, raw text, Opik URLs
  status: open|acknowledged|resolved|suppressed|reopened
  severity: block|warn|info
  title: string
  first_seen_at: iso8601
  last_seen_at: iso8601
  occurrence_count: int
  failure_ids: string[]
  prevention_ids: string[]
  metric_ids: string[]
  regime?: string
  blame_span?: string
  sample_bundle_ids: string[]          # capped
  sample_trace_ids: string[]           # capped; never in fingerprint
  product_impact: accept_path|golden|train|export|docs|unknown
  suggested_surfaces: string[]         # static code/doc paths
  resolution_evidence?: string
  owner?: string
```

**Fingerprint inputs (normative):** sorted `failure_ids` + `metric_ids` + `blame_span` + `regime` + `artifact_class` + topology missing-span set + path-class key.  
**Excluded from fingerprint:** `trace_id`, timestamps, raw message/diff text, Opik URLs, usernames, absolute paths.

#### 7.2.14 `git_cg_opik_config_v1` (FIND-022 / INT-09)

```text
git_cg_opik_config_v1:
  schema_version: "git_cg_opik_config_v1"
  mode: off|local_only|mirror|strict_mirror
  environment: development|dogfood|ci|eval|staging|production
  projects:
    live: string
    eval: string
    ci: string
    import: string
  endpoint?: string                    # OPIK_URL_OVERRIDE
  workspace?: string
  flush_timeout_ms: int                # hard bound for short-lived procs
  track_disable: bool
  check_tls_certificate: bool
  config_path?: string
  # secrets NEVER stored here — only resolved at runtime via env/1Password
```

**Env vars (document; never commit values):**  
`OPIK_API_KEY`, `OPIK_URL_OVERRIDE`, `OPIK_WORKSPACE`, `OPIK_PROJECT_NAME`, `OPIK_ENVIRONMENT`, `OPIK_CONFIG_PATH`, `OPIK_TRACK_DISABLE`, `OPIK_DEFAULT_FLUSH_TIMEOUT`, `OPIK_CHECK_TLS_CERTIFICATE`,  
`GIT_CG_OPIK_MODE`, `GIT_CG_OPIK_FLUSH_TIMEOUT_MS`, `GIT_CG_OPIK_PROJECT_LIVE`, `GIT_CG_OPIK_PROJECT_EVAL`, `GIT_CG_OPIK_PROJECT_CI`, `GIT_CG_OPIK_PROJECT_IMPORT`.

#### 7.2.15 `correlation_envelope_v1` (INT-15)

```text
correlation_envelope_v1:
  schema_version: "correlation_envelope_v1"
  session_thread_id: string
  root_trace_id: string
  attempt_index: int
  hook_phase: pre_commit|commit_msg|post_commit|cli_eval|dogfood|other
  process_id_token: string             # not OS PID alone; rotation-safe token
  finalization_token?: string
  bundle_hash?: string
  git_head?: string
  created_at: iso8601
```

Cross-process members attach via this envelope; **do not** assume a live OpenTelemetry parent context survives hook boundaries.

#### 7.2.16 `replay_compare_v1` (FIND-023 / INT-18)

```text
replay_compare_v1:
  schema_version: "replay_compare_v1"
  source_bundle_hash: string
  source_trace_id: string
  replay_bundle_hash: string
  replay_trace_id: string
  session_thread_id: string            # same as source
  pinned:
    harness_version: string
    metric_catalog: string
    schema_pack: string
    prompt_pack?: string
    model?: string
    dataset_snapshot?: string
  deltas:
    input_equal: bool
    first_divergent_span?: string
    metric_deltas: object[]
    artifact_delta?: object
    product_result_delta?: object
    eval_result_delta?: object
  regression_status: improved|regressed|unchanged|incomparable
  notes?: string
```

**Law:** never mutate source bundle; replay always creates new trace/bundle.

#### 7.2.17 `git_cg_pipeline_graph_v1` (INT-25)

```text
git_cg_pipeline_graph_v1:
  schema_version: "git_cg_pipeline_graph_v1"
  graph_id: string
  version: string
  content_sha256: string
  nodes: { id: string, span_name: string, optional?: bool }[]
  edges: { from: string, to: string, kind: sequence|optional|xor }[]
```

Observed Family I spans compare against this declared graph (`i.graph_observed_matches_declared`).

#### 7.2.18 `prompt_pack_v1` (INT-26)

```text
prompt_pack_v1:
  schema_version: "prompt_pack_v1"
  pack_id: string
  version: string
  content_sha256: string
  lane: generation|judge|dogfood|lab
  variable_schema: object
  files: string[]                      # repo-relative
  cloud_mirror?: { provider: opik, prompt_name: string, commit?: string }
```

**Law:** runtime uses **git-pinned local packs**. Cloud Prompt Library is optional immutable mirror only. Variant changes require local PR — not UI save/latest.

**S5 / #233 amendment (`0.9.4-s5-eligibility-split`):**
* Frozen `prompt_pack_v1` identity fields above remain the schema floor.
* Runtime pack decode is **strict UTF-8 fail-closed**; content hash is over stored bytes (D41).
* Suite/meta may carry pack pin refs and amendment notes; they do **not** authorize floating cloud “latest”.
* Ordinary C′ judges consume **S3 final-accept evidence projection** (D29): `artifact_class=final_accept` (or explicit lab class under `lab_override`), `final_message_sha256` over original bytes, encoding metadata (`utf-8` | `utf-8-replace`), session/bundle identity when available. Invalid UTF-8: judge the S3 text projection; stamp encoding + original byte hash; **do not invent a second decode path**.
* Default offline scoring never loads network judges; unit tests stay green via injectable offline seams.


### 7.3 Dataset strategy (local names)

#### 7.3.1 Split / contamination law (FIND-024 / INT-21)

| Rule | Law |
|:---|:---|
| `split_group_id` | Derived from case/session family; **all** preference variants, message versions, and replay descendants share one group |
| Pair integrity | Chosen/rejected rows of a `preference_pair_id` never cross train/test |
| Anti-pattern vault | Rows labeled antipattern **cannot** enter `positive_train` destinations |
| Holdouts | Immutable once published; exports carry manifest + content hash |
| Popularity ≠ gold | Never mint gold from production acceptance alone; promotion state machine §18.8 |
| Synthetic Expand-with-AI | Quarantine until human/schema validated (INT-44) |


| dataset_id | Lane | Purpose | Snapshot SoT | Opik mirror |
|:---|:---:|:---|:---|:---|
| `cm-eval-fixtures-core` | A | Core offline regression; Hybrid/gold/path-class smoke | committed fixtures + snapshot hash | optional |
| `204-archive` | A/B | #204 forensic encodings; Regime A/B taxonomy | committed / controlled import | optional scrubbed |
| `gold-counter-integrity` | A | Counter / inventory integrity edge cases | committed | optional |
| `acceptpath-live` | B | Bound accept-path captures (dev) | local `.eval` + optional committed subsets | optional |
| `semantic-cohort` | C | Eligibility-gated residual prose cohort | pinned snapshot; not CI sole gate | optional |
| `regression-queue` | A/ops | Failure→fixture promotions + disputed cases | local queue + promote-to-fixtures workflow | optional |
| `dogfood-rolling` | dogfood | R12 rolling maintainer captures | local `.eval/dogfood` + optional train_export | optional lake |
| `train-positive` | train | Owner-labeled positive_gold / preference_chosen rows | local train_export + pins | optional lake |
| `train-negative` | train | hard_negative / preference_rejected / antipattern_vault | local vault + labels mandatory | optional restricted |
| `judge-meta-hm` | lab | R2 hallucination/moderation labeled meta-eval | lab-only; scrubbed | optional |

#### 7.3.2 Dataset ID aliases (historical #217 body names)

| Stable `dataset_id` (this plan) | #217 body / design alias | Notes |
|:---|:---|:---|
| `cm-eval-fixtures-core` | `cm-eval-fixtures-core` | unchanged |
| `204-archive` | `cm-eval-204-archive` | encoder/docs MAY accept alias |
| `acceptpath-live` | `cm-eval-acceptpath-live` | |
| `gold-counter-integrity` | `cm-eval-gold-counter-integrity` | |
| `semantic-cohort` | `cm-eval-semantic-cohort` | |
| `regression-queue` | `cm-eval-regression-queue` | |
| `dogfood-rolling` | — (post-body) | R12 |
| `train-positive` / `train-negative` | — (post-body) | R14 train axis |

**Experiment naming (S4 / operator convention):**

```text
eval_<lane>_<catalog_version>_<gitsha>_<utc>
```

Pins required on every experiment: harness, metric catalog, prompt-pack/hash, engine/model, artifact class, lane, dataset/suite snapshot hash (never unpinned `latest`).

**Promotion paths:**

```text
# Fixture / CI law path
dogfood / live fail or L2 dispute
  → regression-queue item (human.* optional)
  → encode ape_bundle_v1 + eval_case_v1
  → PR adds to cm-eval-fixtures-core or 204-archive
  → snapshot hash bump
  → CI Lane A owns it forever (offline)

# Training corpus path (parallel, not CI sole green)
commit_session_thread + message_versions + scores
  → train_label + redaction_profile + scope_tag
  → local train_export_v1 (and/or Opik owner lake under R3/R14)
  → splits: train-positive | train-negative | holdout
  → never silent merge of unlabeled antipatterns into positive_gold
```

**Naming rules:**
* dataset_id = kebab-case stable id  
* snapshot_id = `{dataset_id}@{yyyy-mm-dd}-{short_hash}`  
* Opik dataset display names may differ but must store `dataset_id` + `snapshot_id` in metadata  

---

### 7.4 #204 corpus encoding requirements

Issue `#204` archive material is **corpus law**, not narrative scrap.  
**Living homes (repo SSOT):** [`docs/quality/`](../quality/README.md) — especially [`METHOD.md`](../quality/METHOD.md), [`FAILURE_TAXONOMY.md`](../quality/FAILURE_TAXONOMY.md), [`PREVENTION_BACKLOG.md`](../quality/PREVENTION_BACKLOG.md), [`cases/204/session-12.md`](../quality/cases/204/session-12.md) (G1 Regime A), [`cases/204/session-12-synthesis.md`](../quality/cases/204/session-12-synthesis.md) (A+B systems map), [`cases/204/quality-package-regime-b.md`](../quality/cases/204/quality-package-regime-b.md) (later Regime B dogfood).  
GitHub #204 comments are intake/archive after promotion; #217 must **cite** these paths, not duplicate them.

| Field | Required | Values / notes |
|:---|:---:|:---|
| `corpus.source` | ✅ | `204_archive` |
| `corpus.regime` | ✅ | `A` = detectable deterministic/process failure class; `B` = looks-good false-green / attribution-semantic risk |
| `corpus.instance_kind` | ✅ when applicable | `A` / `B` instance encoding from archive |
| `corpus.session_tags` | ✅ when known | must include `session-12-seed` for Session 12 seeds (proof: `docs/quality/cases/204/session-12.md` + `session-12-synthesis.md`) |
| `corpus.failure_ids` | ✅ | stable IDs from archive taxonomy (not only prose) |
| `corpus.prevention_ids` | ✅ when known | prevention checklist IDs |
| `corpus.provenance` | ✅ | origin path/issue link; capturer; no secrets |
| `final_message` | ✅ | real accepted or fixture final bytes |
| `path_class` / signals_summary | ✅ preferred | enough to re-score offline |
| `expected` | ✅ for fixture class | gate + gold code expectations |
| `gold.findings` observed | optional | if re-score differs, harness records delta — fixture expected still law |

**Regime semantics (normative for tagging):**

| Regime | Means | Primary families |
|:---|:---|:---|
| **A** | Failure should be caught by deterministic product/harness gates | A–E, G–H, much of D/F |
| **B** | Plausible message that still violates attribution/contract/truth | C, D, F (+ E craft lie detectors) |

#### 7.4.1 Regime A/B teaching table (#217 body; corpus pedagogy)

| Regime | Pattern | Symptom | Harness must catch |
|:---|:---|:---|:---|
| **A** | Controls fire, recovery poisons final | skeleton / process-meta catastrophe after regen | gold findings, hostile regen, fallback provenance, counter truth (Family D + I) |
| **B** | Controls never fire; wrong envelope looks perfect | empty `path_class_gate`, green shallow score-card, wrong type/SemVer/inventory | path-class authority, inventory/attribution, silent wrong acceptance (Families C/F + gates) |

Instance **A ≠ B** encoding from the #204 archive is mandatory when the archive distinguishes them (`corpus.instance_kind`).

#### 7.4.2 Provenance label enum (#217 body / #204)

Closed labels (store on bundle / corpus; extend only via catalog/schema bump):

| Label | Meaning |
|:---|:---|
| `Git-raw` | Raw tip / pre-repair git message bytes |
| `Git-mid` | Mid-pipeline rewrite (pre-final) |
| `Gold-final` | Post-gold / gold-accepted final |
| `Rewrite-map-confirmed` | Rewrite map confirmed path |
| `Opik-unbound` | No trustworthy Opik bind (explicit; importable) |
| `final_accept` | Bound accept-path / `COMMIT_EDITMSG` final bytes (primary product score class) |
| `live_regen` | Explicit secondary live regeneration artifact |
| `fixture` | Synthetic / committed fixture final |

Unbound historical evidence **must** remain importable under `Opik-unbound` — never silently coerced to bound.

#### 7.4.3 #204 / Session failure & prevention ID namespaces

Preserve archive strings as first-class `failure_ids` / `prevention_ids` (not prose-only):

| Namespace | Examples (indicative) | Role |
|:---|:---|:---|
| Instance B failures | `F-IB*` | Regime/instance taxonomy |
| Session numeric failures | `F72`–`F80`, … | Archive failure IDs |
| Instance B preventions | `P-IB-*` | Prevention checklist |
| Session 12 preventions | `P-S12-1`…`P-S12-9` | Session-12 proof map |

S1 encoder **MUST** round-trip these strings when `corpus.source=204_archive`.

#### 7.4.4 Session-12 seed suite requirements (S1 AC fuel)

Session 12 is the **seed proof pack**, not a full archive import bar. Seed fixtures / tags (`session-12-seed`) must collectively exercise:

| # | Residual gap (from #217 body) | Harness ownership | Notes |
|:---:|:---|:---|:---|
| 1 | Authoritative staged-path harvesting | S1/S3 bundle fields + Family F | |
| 2 | Concrete `path_class_gate` | S2 Family C + telemetry bind | |
| 3 | Final rendered-message gold blocking | S2 Family D + S3 final bytes | |
| 4 | Regeneration attempt accounting | Family I counters + D consistency | |
| 5 | Stable-ID / inventory enforcement | Family F | |
| 6 | Hook isolation (`GIT_CG_SKIP_PREPARE`) | **Historical / shipped outside this harness** | Cite only; do not re-open as #217 S1 scope |
| 7 | Both Regime A and Regime B coverage | §7.4.1 fixtures | hard S1 intent; exact counts = Q8 |

#### 7.4.5 Encoding bans

* ❌ Dropping failure_ids and keeping only blog prose  
* ❌ Re-running live regen as silent replacement of archive final bytes  
* ❌ Merging expected labels into task input  
* ❌ Using Regime tags as LLM judge sole authority  
* ❌ Mixing Instance A and Instance B evidence without `instance_kind`  
* ❌ Encoding only happy-path fixtures and dropping Regime A recovery-poison cases  

---

### 7.5 Resume modes

Local checkpoints first (Opik resume is non-authoritative convenience only).

| Mode | Behaviour | Allowed when | Refuses when |
|:---|:---|:---|:---|
| `fresh_suite_run` | New experiment_id; ignore prior checkpoint | always | — |
| `resume_missing` | Score only cases not in `completed_case_ids` | compatibility_hash match | hash mismatch; missing checkpoint |
| `recompute_scores` | Keep bundles/inputs; re-run metric pack only | hash match on schema+catalog+snapshot | generation pin required but missing for modes that need it |
| `replay_generation` | Opt-in live regen then score | explicit flag; network policy allows | default CI; offline_required suites |
| `export_only` | Project existing local results to Opik | local experiment complete/partial | never scores; failure = export class only |

**Compatibility hash (minimum preimage):**

```text
sha256(
  schema_pack_pin || metric_catalog_pin || suite_id || snapshot_hash
  || gold_mode || network_policy || judge_pack_pin_or_none
)
```

Mismatch ⇒ hard stop with `EVAL_COMPAT_HASH_MISMATCH` (Family H); no silent partial merge.

---

### 7.6 Redaction profiles (R14 ladder)

Owner-selectable ladder (normative names). Thin profiles remain defaults for basic users / public CI; richer profiles require owner pin + scope + scrub.

| Profile | Keeps | Strips / hashes by default | Typical sink |
|:---|:---|:---|:---|
| `public_ci` | hashes, codes, gates, metric ids | bodies, diffs, paths optional truncate | CI logs |
| `message_only` | final_message + hybrid_fields + scores | paths optional; no diffs; no prompts | thin local/brief |
| `default_scrub` | message, path list, path_class, gold codes, trajectory names | file bodies, raw diffs, secrets, full prompts, env | default local/dev |
| `private_message` | full final_message + versions metadata | diffs/prompts unless allowlisted | private Opik |
| `train_rich` | message versions, preference pairs, structured/allowlisted trajectory + optional full bodies under pin | secrets always; scrub-fail ⇒ quarantine | owner train lake / local train_export |
| `meta_eval_scrub` | scrubbed judge_input refs + labels in envelope | harmful raw samples unless vault | R2 lab |
| `antipattern_vault` | labeled hard_negatives / rejects with mandatory train_label | unlabeled mixing into positives | vault + restricted export |
| `raw_dev_unsafe` | owner-local debug only | **never** CI, never default export, never basic user | local gitignored only |

**Export path (S4):** default max remains `default_scrub` for non-owner sinks. Owner-pinned maintainer project **may** use `private_message` / `train_rich` / `antipattern_vault` under R14. Secrets always scrubbed; scrub failure quarantines/omits fields rather than ambient leak.

Also see §3 R14 sketch and §10.2.

---

### 7.7 Compatibility with gates & R11–R14

| Consumer | Reads | Must not need |
|:---|:---|:---|
| `gate.deterministic_pass` | bundle.scores A–H + gates | Opik, C′, human, train_label |
| `corpus.train_row_eligible` | capture_on + labels + redaction profile | product accept flip |
| Lane C eligibility | gates + pins | cloud UI |
| R11 amend-brief | bundle rollup + dogfood attachments + session_thread_id + version refs | Opik uptime |
| R12 dogfood | message_sha + attachment write into `.eval/dogfood` | product accept block |
| R13 session thread | local twin + linked trace/span ids | sole gate authority |
| R14 train_export | labeled rows under owner ladder | CI sole green |
| S4 export | experiment + scrubbed bundles + optional threads/train datasets | re-score authority |

---

### 7.8 S0 deliverable freeze list (implementation)

When S0 ships, commit under `schemas/eval/` (paths adjustable):

1. `ape_bundle_v1.schema.json`  
2. `score_result_v1.schema.json`  
3. `eval_suite_v1.schema.json`  
4. `eval_case_v1.schema.json`  
5. `dataset_snapshot_v1.schema.json`  
6. `experiment_v1.schema.json`  
7. `evaluation_checkpoint_v1.schema.json`  
8. `trajectory_evidence_v1.schema.json`  
9. `human_review_v1.schema.json`  
10. `judge_meta_eval_v1.schema.json`  
11. `thread_eval_v1.schema.json`  
12. `amend_brief_v1.schema.json`  
13. `dogfood_attachment_v1.schema.json`  
14. `export_batch_v1.schema.json`  
15. `trace_topology_v1.schema.json`  
16. `correlation_envelope_v1.schema.json`  
17. `diag_issue_v1.schema.json`  
18. `git_cg_opik_config_v1.schema.json`  
19. `replay_compare_v1.schema.json`  
20. `git_cg_pipeline_graph_v1.schema.json`  
21. `prompt_pack_v1.schema.json`  
22. `export_queue_item_v1.schema.json`  
23. `commit_session_thread_v1.schema.json`  
24. `train_row_v1.schema.json` / `train_export_v1.schema.json`  

Plus: content-hash script for `schema_pack_v0@sha`, polarity registry fixture, official reference matrix stub, and pytest schema fixtures.

---

### 7.9 v0 completeness checklist

- [x] `ape_bundle_v1` dimensions + artifact classes + scored target order  
- [x] Supporting schema sketches (suite/case/snapshot/experiment/checkpoint/trajectory/human/lab/thread/dogfood/export/brief)  
- [x] Dataset strategy names + promotion path  
- [x] #204 regime/instance/session/failure/prevention encoding law  
- [x] Resume modes + compatibility hash  
- [x] Redaction profiles  
- [x] Gate/R11/R12 consumption map  
- [x] S0 freeze list  
- [x] Topology/diag/config/replay/graph/prompt-pack schema sketches (v0.9.0)  
- [x] Split/contamination law §7.3.1  
- [ ] JSON Schema files on disk → **S0**  
- [ ] Encoder CLI / tests → **S1**  


---

## 8. Implementation slices (grandchildren)

[x] **Filing posture:** each slice below is one default GitHub grandchild under #217 unless split per §4.2.  
**Design doc remains SSOT** until S0 lands schemas on disk. **Do not file S5 as merge-gate work.**

### 8.00 Cross-slice invariants (every PR)

| # | Invariant |
|:---:|:---|
| I1 | Local fixtures/bundles remain CI SoT; Opik is never sole green. |
| I2 | Authoritative metrics wrap product modules (`commit_gold`, `commit_quality`, Hybrid validators, binders). |
| I3 | No GEval/H/M/NLP builtin as `gate.deterministic_pass` or sole golden. |
| I4 | Basic `git-cg commit` path works with Opik uninstalled / network down. |
| I5 | Pins everywhere on CI/accept-path suites (catalog, schema pack, snapshot, judge if used). |
| I6 | Export/judge/doctor failures use correct failure class (§10); export never blocks accept. |
| I7 | Secrets never ambient-exported; richer payloads only via owner redaction ladder + scrub. |
| I8 | Tests preferred via `just test` / `uv run pytest`; targeted tests for touched families. |
| I9 | Owner handles git commits; assistants may prepare patches and L2 amend-briefs only when asked. |
| I10 | **Non-degradation** — existing product functionality and existing metrics/telemetry must not regress; eval/Opik changes are additive unless owner explicitly replaces a sink. |
| I11 | **Training enrichment** — do not omit storable session/train fields solely because they are non-gating (M11). |
| I12 | **Session thread additive** — commit_session_thread links existing logs; does not delete traces/spans/metrics. |

**Suggested package root (adjustable in S0):** `src/git_cg/eval/` (or `evals/`) — not `scripts/` forever.

```text
src/git_cg/eval/
  __init__.py
  schemas/          # or repo schemas/eval/ loaded by pack pin
  bundle.py
  suite.py
  scoring/
    envelope.py
    families/       # a.py ... h.py
    gates.py
  corpus/
  binding/
  mirror/
  lane_c/
  dogfood/
  brief.py
  doctor.py
  cli.py            # git-cg eval ...
tests/fixtures/eval/
schemas/eval/
```

---

### 8.0 Slice 0 — Law & schema package

> **v0.9.0 addendum (INT-33):** S0 must also stub/freeze schemas for `trace_topology_v1`, `correlation_envelope_v1`, `diag_issue_v1`, `git_cg_opik_config_v1`, `replay_compare_v1`, `git_cg_pipeline_graph_v1`, `prompt_pack_v1`, `export_queue_item_v1`, Family I metric ids in catalog pin, SCORE-POLARITY notes, and FIND-025 reference matrix stub. **S0 remains implementation-free regarding network/replay/diagnostics runtime** — schemas + laws only.

| Field | Content |
|:---|:---|
| **Issue title** | `eval(S0): freeze schema pack + metric catalog pins` |
| **Goal** | Land immutable design → machine-checkable schema pack + catalog pin machinery so later slices cannot drift. |
| **Depends on** | Design ratification of this plan (§1–§8); no code blockers. |
| **Network** | none |
| **Delivers** | (1) `schemas/eval/*.schema.json` for §7 list (**≥14 schemas**, including stubs for `commit_session_thread_v1`, `train_export_v1`). (2) `schema_pack_v0` content-hash helper. (3) `metric_catalog_v0` machine-readable index (YAML/JSON of metric_ids from §6 incl. M10/M11) + hash. (4) Pydantic (or equivalent) models validating bundles/scores. (5) Redaction profile enum (R14 ladder). (6) pytest: schema fixtures valid; polarity/authority enums closed; unknown artifact_class fails. (7) Short `docs/eval/README.md` pointer to plan + pins + train axis (full ADR in S7). (8) Package skeleton `src/git_cg/eval/`. |
| **Non-goals** | Scoring logic; Opik client; corpus encoding; CLI UX beyond maybe `eval schema-version`; Lane C. |
| **Primary paths** | `schemas/eval/**`, `src/git_cg/eval/**`, `tests/eval/test_schemas*.py`, optional `just eval-schema-hash` |
| **R-items** | none (defines floor); records R11–R14 / session+train schema stubs |
| **Findings** | FIND-002 envelope types; FIND-006/008/009–016 schema stubs |
| **Skills** | none required; do not let `opik` skill rewrite authority |
| **AC** | ☐ Schema pack validates known-good examples and rejects known-bad (incl. session/train stubs). ☐ `schema_pack_v0@sha` reproducible in CI. ☐ `metric_catalog_v0@sha` lists Families A–H + secondary sets with polarity/authority + M10/M11. ☐ ScoreResult_v1 requires `metric_id`, `polarity`, `authority`, `source`. ☐ Redaction ladder enum present. ☐ expected_* documented as fixture/meta-eval only. ☐ Offline unit tests green without network. ☐ No dependency on Opik package for S0 import path. ☐ Docs state train corpus axis ≠ gate axis. |
| **Exit risk** | Overbuilding CLI — keep freeze minimal. |

---

### 8.1 Slice 1 — Encode offline corpus / bundles

> **v0.9.0 addendum:** fixtures for valid/invalid topology, incomplete traces, missing spans, counter/span mismatch (Session-12 class), replay lineage rows, split contamination negatives, and JUDGE-INPUT leak attempts.

| Field | Content |
|:---|:---|
| **Issue title** | `eval(S1): encode offline fixtures as ape_bundle_v1` |
| **Goal** | Make Lane A real: committed fixtures → `ape_bundle_v1` / `eval_case_v1` / snapshots without network. |
| **Depends on** | S0 |
| **Network** | **none required** (hard AC) |
| **Delivers** | (1) Fixture layout under `tests/fixtures/eval/`. (2) Encoder: case/fixture → `ape_bundle_v1`. (3) Seed suites: at least `cm-eval-fixtures-core` + stub snapshot; path for `204-archive` import. (4) `#204` corpus fields enforced when `source=204_archive`. (5) `dataset_snapshot_v1` builder + hash. (6) pytest offline load+validate. (7) Migration notes from any ad-hoc JSONL/scripts. |
| **Non-goals** | Full Families A–H scoring (emit empty scores OK); Opik upload; live accept-path bind; Lane C. |
| **Primary paths** | `src/git_cg/eval/corpus/**`, `tests/fixtures/eval/**`, `tests/eval/test_corpus*.py`, thin wrapper retiring bits of `scripts/compile_opik_dataset.py` / `eval_commit_message.py` inputs |
| **R-items** | R9 filters may exist as data tags only |
| **Findings** | FIND-004 cases may be fixture-tagged for later |
| **AC** | ☐ `cm-eval-fixtures-core` snapshot builds offline and validates all cases. ☐ Each case has stable `case_id`, `artifact_class`, `bundle_ref`. ☐ #204 sample(s) carry regime, failure_ids, prevention_ids when known, provenance_label enum, instance_kind when applicable (or explicit skip with reason). ☐ At least one `session-12-seed` path covering Regime A **and** B intent (§7.4.4; counts per Q8). ☐ Alias acceptance for `cm-eval-204-archive` → `204-archive` (and siblings in §7.3.2) documented or implemented. ☐ expected_* never appears in a “task_input” projection helper. ☐ Re-encode is deterministic (stable hashes). ☐ `just test` (or targeted pytest) green offline. |
| **Exit risk** | Boiling the ocean on full #204 import — seed + import path OK; full archive can ramp. |

---

### 8.2 Slice 2 — Authoritative deterministic metrics

> **v0.9.0 addendum:** implement Family I validators (lifecycle/parentage/required spans/counter consistency), RCA field emitters (`blame_span`, missing spans), fingerprint inputs, STRUCT-LOCAL schema compliance scores, and score placement metadata on `ScoreResult_v1`.  
> **v0.9.1 addendum (FIND-026/027):** evaluators receive **bound final-message / product `score_card` fields only**; empty/missing input short-circuits with **one** classified row error (`h.eval_input_nonempty`) — no N× fan-out; prefer wrapping `run_deterministic_checks` / Hybrid authorities over re-parsing raw Opik blobs; `header_length_ok`/`has_body` must use header/body parse of the final Hybrid message (same law as `telemetry.run_deterministic_checks`).  
> **v0.9.3 S2b addendum (#227 T1–T12):** split S2 as **S2a** (landed A/B/D-core/H-core) → **S2b** (this lock: complete C/E/F/G + remaining D/H FIND-002) → **S2c** (Family I / topology). S2b locks: (1) empty/oversize skips message-dependent families including mapped D and never mints an empty `d.strict_fail_set` pass; (2) shared `GoldReport` API/slot, one gold call, F consumes D; (3) C/D dual emission from shared evidence, no double-count; (4) remove `c.`/`e.`/`f.`/`g.` from advisory prefixes (labeling fix; requested IDs already veto); (5) C = `evaluate_presentation_gates`, E = `evaluate_presentation_guards`; (6) local secret-shape helper only; (7) non-vacuous `g.no_eval_policy_fork`; (8) opt-in S2b block tuple = `S2A_REQUIRE_BLOCK` ∪ catalog block C/E/F/G ∪ remaining catalog block D ∪ `h.structured_bundle_compliance` (68 ids); warn/info stay out. Family I / `require_topology` stay S2c.

| Field | Content |
|:---|:---|
| **Issue title** | Split: **S2a** landed (`eval(S2a): Families A/B/D-core/H-core`); **S2b** = #227 (`eval(S2b): complete product-authority metrics C–G and harden offline scoring`); **S2c** = Family I / `suite.require_topology=true` |
| **Goal** | Score bundles with dual-plane **Plane A** metrics wrapping real product authorities; compute `gate.deterministic_pass`. **S2a** unblocks capture/R12-MVP. **S2b** completes C/E/F/G + remaining D + H FIND-002 and hardens empty/oversize, GoldReport, dual emission, and gate labels. **S2c** is Family I only. |
| **Depends on** | S0–S1; S2b depends on landed S2a |
| **Network** | none required |
| **Forbids** | builtin H/M/G-Eval/NLP as authority; eval-only regex forks of gold/Hybrid/path-class; Family I / live topology as S2b close-bar |
| **Delivers** | **S2a (landed):** A/B/D-core/H-core + `S2A_REQUIRE_BLOCK` (30). **S2b (#227):** (1) C via `classify_diff_class` / `presentation_constraints` / `evaluate_presentation_gates` only. (2) E via `evaluate_presentation_guards` + craft helpers only. (3) Remaining catalog-block D rows + shared `GoldReport` API, exactly one gold call, F consumes D. (4) C/D dual emission from shared evidence, no double-count. (5) G local secret-shape helper + non-vacuous `g.no_eval_policy_fork`. (6) H FIND-002 (`h.structured_bundle_compliance`); `h.eval_input_size_ok` stays warn. (7) Empty/oversize skip of message-dependent families including mapped D; never mint empty `d.strict_fail_set` pass. (8) Remove `c.`/`e.`/`f.`/`g.` from `_IGNORE_FAMILY_PREFIXES` (labeling only). (9) Opt-in 68-id S2b block tuple. (10) Absorb/demote/delete `scripts/opik_metrics.py` **and** `tests/test_opik_metrics.py` together. **S2c:** Family I + `require_topology`. |
| **Non-goals** | Opik mirror; Lane C judges; dogfood profile; amend-brief UX (can emit scores only). |
| **Primary paths** | `src/git_cg/eval/scoring/**`, `tests/eval/test_family_*.py`, bridges into `commit_gold.py`, `commit_quality.py`, Hybrid validators |
| **R-items** | none required; R10 not in this slice as law |
| **Findings** | FIND-002, FIND-004 |
| **AC** | ☐ Suite `cm-eval-fixtures-core` produces per-case ScoreResult list + gates. ☐ `gate.deterministic_pass` ignores any C′ ids if present. ☐ Gold STRICT_FAIL_CODES map to D metric failures. ☐ Product rule change covered by product tests still authoritative — eval wraps same functions. ☐ Mutating SOP via eval overlay impossible (`g.no_eval_policy_fork` or equivalent review). ☐ Offline CI job/example runs Lane A without Opik install. ☐ No judge credentials required. |
| **Exit risk** | Duplicating gold rules in eval — reject in review. |

---

### 8.3 Slice 3 — Accept-path binding hardening

> **v0.9.0 addendum:** emit root/spans under closed taxonomy; correlation envelope + finalization; session thread lifecycle; **Layer A before export**; disabled/export-failure semantics; replay lineage fields; observe declared pipeline graph; optional LLM usage metadata on `llm_generation`.  
> **v0.9.1 addendum (FIND-027):** bind and export the **final rendered accept-path message bytes** (and product `score_card`) as the scored artifact; never leave generation JSON / multi-line raw model dump as the default online `output` for format evaluators; distinguish generation-draft vs final-accept artifacts when both exist.

| Field | Content |
|:---|:---|
| **Issue title** | `eval(S3): accept-path final-bytes binding + trajectory evidence` |
| **Goal** | Score the **real accepted final message** with bound/unbound honesty and R7 trajectory evidence. |
| **Depends on** | S2 (partial parallel OK for emit audit hooks after S0) |
| **Network** | none required for unit/fixtures; live capture optional |
| **Delivers** | (1) Accept-path binder → `artifact_class=final_accept` bundles. (2) `a.final_bytes_stable` / binding metrics green on happy path. (3) Explicit unbound labeling (no fake bind). (4) `trajectory_evidence_v1` declared vs observed stages — **default on** for maintainer train/dogfood profile (R7). (5) **commit_session_thread_v1** open/close + links to existing trace/span ids (R13) — additive. (6) `message_versions` hooks for draft/amend/final when available. (7) Tests for incomplete evidence = product pass + eval fail class where required. (8) Capture off for basic users; no product UX regression (I10). |
| **Non-goals** | Blocking users on Opik; changing ranker semantics; Lane C. |
| **Primary paths** | `src/git_cg/eval/binding/**`, accept-path emit sites in `main`/telemetry (minimal hooks), `tests/eval/test_binding*.py` |
| **R-items** | **R7, R13** (session thread hooks) |
| **AC** | ☐ Bound bundle round-trip: accept → bundle → score offline. ☐ Tampered final bytes fail `a.final_bytes_stable`. ☐ Missing trajectory on bound suite fails H/R7 policy as designed. ☐ Unbound offline fixtures still score. ☐ Basic commit path unchanged when eval capture disabled (default). ☐ No network calls on bind. |
| **Exit risk** | Heavy main.py invasive rewrite — prefer narrow emit hooks. |

---

### 8.4 Slice 4 — Opik mirror

> **v0.9.0 addendum:** project/environment binding (no Default Project); hierarchy-preserving export; score placement on export; **bounded flush**; `.eval/export_queue` + retry/drain; R14 redaction on export; dataset/experiment pin consistency; `git_cg_opik_config_v1` resolution.  
> **v0.9.1 addendum (FIND-026/027):** online/automation evaluators must be **disabled or gated** until empty-output + artifact-bind guards exist; export product feedback scores from local card rather than attaching divergent cloud rules on raw traces; oversize payload guard before any LLM judge; classify 504/timeout as export/eval health not Hybrid fail.

| Field | Content |
|:---|:---|
| **Issue title** | `eval(S4): non-blocking Opik mirror + owner corpus lake` |
| **Goal** | Project **precomputed local** results to Opik for operator compare **and owner training/longitudinal corpus lake**; never scoring engine of record / CI sole green. |
| **Depends on** | S1–S3 (need something real to export) |
| **Network** | optional; all flows degrade safe |
| **Delivers** | (1) `export_batch_v1` builder. (2) REST/SDK upload path, batched, idempotent, size-bounded with **default max batch payload 4MB** (configurable downward; raise only with explicit owner note). (3) Experiment naming `eval_<lane>_<catalog_version>_<gitsha>_<utc>` + full pin set. (4) Pinned project/lane — no Default Project dump. (5) **R14 redaction ladder** on export (not only thin default). (6) Export failure classification; cannot flip `gate.deterministic_pass`. (7) Dataset mapping + **commit_session_thread** projection. (8) Optional train-positive/negative dataset projections. (9) Prefer publishing product deterministic score_card / final-bytes-bound scores (FIND-027). (10) Tests with mocked transport + scrub/quarantine. (11) Absorb/retire `scripts/compile_opik_dataset.py` upload parts as library calls. |
| **Non-goals** | Cloud SoT; online score execution; Ollie; requiring export on commit. |
| **Primary paths** | `src/git_cg/eval/mirror/**`, `tests/eval/test_mirror*.py` |
| **R-items** | **R3, R14** (corpus lake + redaction ladder) |
| **AC** | ☐ Offline suite remains green if export throws. ☐ Idempotent re-export does not duplicate corruptly (keys). ☐ Default batch builder refuses >4MB uncompressed payload (or splits). ☐ Experiment names follow convention + pins present. ☐ Secrets always scrubbed; richer bodies only under owner ladder profile. ☐ Scrub fail quarantines fields (no silent ambient leak). ☐ Pin missing → fail export validation, not product gate. ☐ Optional train-positive/negative dataset projection. ☐ Session thread projection when present. ☐ Documented `git-cg eval export` or `just eval-export` dev-only. |
| **Exit risk** | Pulling scoring into Opik task fns — forbid. |

---

### 8.5 Slice 5 — Secondary semantic cohort

> **v0.9.0 addendum:** JUDGE-INPUT isolation tests; polarity remapping tests for any enabled builtin; advisory LLM usage/cost fields; keep all C′/human work non-authoritative.  
> **v0.9.1 addendum:** any Lane C / Format Compliance-style LLM judge must enforce `h.eval_input_size_ok` and must not run on empty output; 504 retry storms are harness bugs.  
> **v0.9.5 addendum (API surface):** S5 exports only the **narrow** harness-facing `git_cg.eval*` surface needed for Lane C′/scoring. CLI remains the primary public API. Full operator API map = S6; durable Zensical/ADR API documentation = S7. No general-purpose SDK claim in S5.

| Field | Content |
|:---|:---|
| **Issue title** | `eval(S5): gated Lane C′ cohort + optional judge lab` |
| **Goal** | Enable residual advisory judges **after** eligibility; optional R2 meta-eval; never merge-gate. |
| **Depends on** | eligibility gate from S2–S3; pins from S0 |
| **Network** | judge optional; Lane A/B still offline without it |
| **Forbids** | merge-gate authority; moderation-as-default; unpinned latest judges |
| **Delivers (spine)** | (1) `gate.semantic_cohort_eligible` authorization-only enforcement (D4/D4′ — identity pins, not secrets). (2) Availability/skip path separate from eligibility. (3) Pinned C′ GEval craft/relevance subset on eligible path. (4) Final-accept–linked judge input (D29) + gold-blind projection. (5) Advisory emission without `make_score(passed=None)` footgun (D30) and `reason="scored"` (D31). (6) Scripts `setup_opik_eval_rule.py` / `setup_opik_test_suites.py` freeze headers or thin lab adapters (never accept-path authority). (7) **Narrow supported Python surface:** selected harness-facing `git_cg.eval*` entrypoints used by S5 (at minimum `score_bundle` and Lane C′ wiring such as `run_lane_c` where implemented, plus shared result/pin contracts) are **supported** maintainer/harness APIs; product internals stay **internal**. S5 does **not** publish a general-purpose Python SDK — operator API map is S6; durable API docs are S7. |
| **Residuals (D28 — ship, split, or explicit defer; never silent-drop)** | R1 richer rubrics · R2 `judge_meta_eval_v1` (FIND-001; DEFER OK with checkbox) · R5 dirty overlays · R6 moderation ops · R8 flakiness hooks · R10 NLP diagnostics · Family H C′ honesty metrics (D39) · full script absorption polish. Plan “delivers” must not overclaim residuals as spine-required. |
| **Non-goals** | Making C′ required for CI green; accept-path block on judge timeout; S6 doctor/amend-brief UX; S7 ADR rewrite; publishing a general-purpose Python SDK; broad source-tree API extraction / full-package autodoc in S5. |
| **Primary paths** | `src/git_cg/eval/lane_c/**`, `prompts/eval/lane_c/**`, `tests/eval/test_lane_c*.py` |
| **R-items** | R1, R2, R6, R8, R10 (optional / residual per D28) |
| **Findings** | FIND-001, FIND-005, FIND-007, FIND-026/027/028 (as consumed) |
| **AC** | ☐ Lane C does **not** run judges when eligibility is false. ☐ `lab_override` marks the run **eligible-diagnostic** and emits **skip rows only — zero judge side effects** (spine never runs judges on det-fail cohorts). ☐ Judge results stamp `authority=advisory` / `source=lane_c_judge`. ☐ Missing credentials → availability skip/lab class only; Lane A still pass; cohort is **not** “unauthorized.” ☐ Meta-eval Equals does not leak labels into judge_input by default. ☐ No job named like “required GEval gate” in default CI. ☐ Default offline scoring never invokes network judges. ☐ Supported S5 Python surface is explicit and narrow (`score_bundle` / Lane C′ wiring + shared contracts); internals are not implied public. ☐ S5 docs/exports do not present the repo as a general-purpose Python SDK (operator map → S6; Zensical/ADR API pages → S7). |
| **Exit risk** | Dashboard beauty → authority creep; keep gates tests; D28 residual honesty; API-surface creep into undocumented internals. |

---

### 8.6 Slice 6 — Operator UX / CI / triage / review queue

> **v0.9.5 addendum (API surface):** S6 **defines and exposes** the supported API surface for operators. CLI is primary public API; selected `git_cg.eval*` entrypoints are supported; internals stay internal. Ship the operator API map + help/usage alignment here. Durable Zensical contract pages and optional allowlist autodoc wait for S7.

| Field | Content |
|:---|:---|
| **Issue title** | `eval(S6): eval CLI, doctor, amend-brief, dogfood, train-export, sessions` |
| **Goal** | Maintainer-facing UX: run/resume/triage offline suites; R11 brief for L2 amend; R12 dogfood; doctor; local HITL queue. |
| **Depends on** | S1+; full value after S2–S4; dogfood may use S5 pins |
| **Network** | optional |
| **Delivers** | (1) `git-cg eval` subcommands (or `just eval-*`): `run`, `resume`, `recompute-scores`, `export`, `doctor`, `amend-brief`, `dogfood`, `train-export`, `session-show`, **`failures`**, **`explain`**, **`compare`**, **`replay`**, **`promote`**, **`diagnose`**, **`issue list|show|resolve|reopen|suppress`**, **`opik doctor`**, **`opik config show`**, **`export status|retry|drain`**, **`thread show`**. (2) Resume modes §7.5 + checkpoints. (3) **FIND-003** `eval doctor` + FIND-020/021 debug+diag loop. (4) **R11** `amend_brief_v1` + preference-pair write. (5) **R12** dogfood + **R12-MVP** path. (6) **R13** session thread local store + Opik map. (7) **R14** train_export_v1 + antipattern vault helpers. (8) Local `.eval/review_queue` + `human_review_v1` (R4). (9) R9 triage filters. (10) CI recipe: offline Lane A on PR. (11) Absorb triage scripts. (12) Hidden from basic commit UX; **I10** no product help/path regression. (13) Local indexes: `.eval/index/`, `.eval/diagnostics/`, `.eval/issues/`, `.eval/replays/`, `.eval/export_queue/`. (14) Operator E-LOOP SOP §18.2. (15) **API-surface policy + operator API map (CLI-first):** CLI = **primary public API**; selected `git_cg.eval*` entrypoints = **supported** maintainer/harness APIs; product internals = **internal**. Map covers supported `git-cg eval` commands and canonical Python entrypoints (**not** a general-purpose SDK). Canonical library names include `score_bundle`, `score_case`, `score_suite`, `compose_gates`, `ScoreResultV1`, pin constructors, and `run_lane_c` where implemented. (16) **Generated CLI usage/help alignment:** `git-cg --help` / eval help / usage snippets stay synchronized with the S6 command surface; basic commit path remains free of Opik configuration requirements and eval-only noise. |
| **Non-goals** | End-user onboarding through Opik; hard-block dogfood default; cloud queue SoT; full Python SDK autodocumentation; broad source-tree API extraction; REST/OpenAPI documentation; external API-documentation services (Scalar/Redoc/SwaggerHub/etc.); mandatory `mkdocstrings` / `mkdocs-click` integration in S6 (optional allowlist autodoc is S7). |
| **Primary paths** | `src/git_cg/eval/cli.py`, `brief.py`, `doctor.py`, `dogfood/**`, `justfile`/`mise` entries, `tests/eval/test_cli*.py` |
| **R-items** | **R4, R9, R11, R12, R13, R14** (+ uses R3 export) |
| **Findings** | FIND-003, FIND-006, FIND-007 docs touch, FIND-008, FIND-009–016, FIND-019–024 |
| **AC** | ☐ `eval doctor` fails on unpinned latest / missing catalog hash. ☐ `amend-brief` prints family rollups + failure_ids without network and can reference session_thread_id. ☐ Preference pair emitted on amend when versions ≥2. ☐ dogfood `off` default for non-maintainer profiles. ☐ async dogfood +0ms user-visible when wired. ☐ `train-export` respects redaction ladder + scrub quarantine. ☐ capture_on=fail stores hard_negative candidate without failing product accept. ☐ resume hard-fails on compat hash mismatch. ☐ review_queue cannot sole-promote golden. ☐ Basic `git-cg --help` does not force Opik setup. ☐ Existing commit path behaviour unchanged when eval off (I10). ☐ `eval explain` returns IDs, artifact/result classes, first divergent/blame span, failure/prevention IDs, counters, replay command, bundle path, export state, static surfaces — **no** opaque LLM RCA. ☐ `eval diagnose` upserts `diag_issue_v1` with stable fingerprint. ☐ `eval replay` writes new bundle + `replay_compare_v1` without mutating source. ☐ `eval promote` enforces promotion state machine + split_group_id. ☐ `opik doctor` / `opik config show` are secret-safe. ☐ export queue retry/drain never blocks accept-path. ☐ doctor red on empty-output fan-out config / unbound online format metrics (FIND-026/027). ☐ doctor warn/red when prompt pack changed without local suite pin/result (FIND-028). ☐ explain surfaces artifact_class + scored-field source for format metrics. ☐ API stability tiers documented for operators: **CLI = public**; **selected `git_cg.eval*` = supported**; **product internals = internal**. ☐ Operator API map names supported `git-cg eval` commands and canonical Python entrypoints (`score_bundle`, `score_case`, `score_suite`, `compose_gates`, `ScoreResultV1`, pins, `run_lane_c` where implemented) without implying a general-purpose SDK. ☐ Generated CLI usage/help covers supported S6 commands; basic `git-cg --help` and normal commit path stay free of Opik setup requirements and eval-specific noise. ☐ S6 API map does **not** promise compatibility for undocumented internal modules. |
| **Exit risk** | CLI sprawl — keep subcommands thin; API-map drift vs actual Typer surface. |

---

### 8.7 Slice 7 — Docs / ADR alignment

> **v0.9.0 addendum:** ADRs/docs for topology, lifecycle/error states, no-Ollie debugging, diagnostics, replay, corpus split/contamination, redaction/export, prompt-pack SoT, FIND-025 reference matrix, worked R11/R12 + Session-12 payloads, Without-Ollie boundary box.  
> **v0.9.1 addendum:** document live Daily Briefing misconfiguration class (§18.13); “do not relax SOP from online scores”; operator runbook to gate/disable unbound cloud evaluators during migration.  
> **v0.9.5 addendum (API surface):** S7 **preserves** the CLI-first API-surface decision in durable Zensical + ADR prose. Curated contract pages beat full-package autodoc. Optional `mkdocstrings` is allowlist-only after S6 exports stabilize.

| Field | Content |
|:---|:---|
| **Issue title** | `docs(S7): ADR-0011 eval layer + catalog/authority map` |
| **Goal** | Durable docs so future agents do not reinvent GEval-as-gate or cloud SoT; lock CLI-first API-surface policy so internals are not mistaken for a public SDK. |
| **Depends on** | continuous; formal close after S2+ (ideally after S6 entrypoints named) |
| **Delivers** | (1) ADR-0011 (or next ADR id) eval layer rewrite: F0–F9, dual-plane, L1/L2/L4, R11–R14, dual gate/corpus axes. (2) Metric catalog doc generated/synced from `metric_catalog_v0` (incl. M10/M11). (3) Contributor map: how to add a fixture/metric/train field. (4) FIND-007 narrow anti-pattern language in skills policy + AGENTS/GEMINI pointers. (5) #217 design closure comment pointing at this plan + slice issues. (6) Supersession notes for shallow GEval scripts. (7) Training-corpus / redaction-ladder operator notes. (8) **Durable Zensical API documentation:** API overview + stability policy; CLI reference/navigation; curated Python contract pages for **supported** evaluation surfaces only (not the entire package tree). (9) **Supported-library contract pages** document canonical entrypoints, invariants, minimal examples, failure taxonomy, pin identity, offline-by-default behaviour, Lane C′ advisory status, gold-blind input projection, and secret/network boundaries. (10) **Optional signature generation** via `mkdocstrings[python]` only for an **explicit allowlist** of supported modules after exports/contracts are stable — subordinate to hand-written contract docs. (11) **Documentation-source policy:** CLI definitions + explicit Python exports are the source of truth; undocumented internals must not be treated as SDK APIs; ADR language matches the CLI-first / supported-eval / internal split. |
| **Non-goals** | Re-litigating #118/#119; implementing product code; documenting every importable `git_cg` module as public SDK surface; publishing internal helpers as supported API; introducing REST/OpenAPI, Scalar, Redoc, or external API-documentation services; treating generated signatures as a substitute for contract documentation. |
| **Primary paths** | `docs/adr/**`, `docs/eval/**`, Zensical pages under `docs/` (API overview / CLI reference / curated Python contracts), `.agents/skills/opik` policy notes if needed, plan link from #217 |
| **R-items** | documents all R1–R14 |
| **Findings** | FIND-007 primary; all findings cross-linked |
| **AC** | ☐ ADR states judges non-authoritative + dogfood allowed. ☐ Catalog doc lists A–H vs C′ + M10/M11. ☐ “GEval on every commit” narrow ban wording present. ☐ Basic-user “Opik not required” explicit. ☐ Dual gate vs corpus axes documented. ☐ R13/R14 / train_export documented. ☐ #216/#217/#218/#219 plane separation documented. ☐ Zensical API overview distinguishes **public CLI**, **supported evaluation-library surfaces**, and **internal** implementation modules. ☐ CLI reference is generated or synchronized from the actual Typer command surface and separates basic-user commands from maintainer eval/Opik commands. ☐ Curated Python API pages document only explicitly supported surfaces (initially `git_cg.eval`, `git_cg.eval.scoring`, `git_cg.eval.lane_c` as implemented/exported). ☐ Docs state `score_bundle` is the Lane C′ opt-in surface while default scoring remains deterministic/offline; `score_case` / `score_suite` do not gain a silent identical Lane C′ passthrough without an explicit design decision. ☐ Lane C′ docs state rows are advisory, gold-blind, promotion-immune; unavailable/non-invoked paths are represented honestly. ☐ API examples/signatures do not expose secrets, provider credentials, raw gold carriers, or internal implementation details. ☐ Any `mkdocstrings` integration is allowlist-based and does **not** autodocument the entire `src/git_cg` tree. ☐ Zensical strict builds pass with API documentation enabled. ☐ ADR/prose language matches the CLI-first API-surface policy (no accidental “public Python SDK” framing). |
| **Exit risk** | Docs-only PR lagging code — allow incremental ADR drafts; autodoc allowlist drift into internals. |

---

### 8.8 Proposed GitHub titles (filing list)

| Slice | Title | Type labels (suggested) |
|:---:|:---|:---|
| S0 | `eval(S0): freeze schema pack + metric catalog pins` | eval, schemas, #217 |
| S1 | `eval(S1): encode offline fixtures as ape_bundle_v1` | eval, corpus, #217 |
| S2 | `eval(S2): Families A–H product-authority metrics` | eval, metrics, #217 |
| S3 | `eval(S3): accept-path final-bytes binding + trajectory evidence` | eval, binding, #217 |
| S4 | `eval(S4): non-blocking Opik dataset/experiment mirror` | eval, opik, #217 |
| S5 | `eval(S5): gated Lane C′ cohort + optional judge lab` | eval, lane-c, #217 |
| S6 | `eval(S6): eval CLI, doctor, amend-brief, dogfood, review queue` | eval, ux, #217 |
| S7 | `docs(S7): ADR-0011 eval layer + catalog/authority map` | docs, adr, #217 |

**Body template (each issue):** Goal · Depends · Delivers · Non-goals · AC (checkboxes) · R-items · Findings · Primary paths · Link to `docs/plans/opik-evaluation-harness.md` §8.x · Explicit “Out of scope: basic-user Opik requirement”.

---

### 8.9 Script absorption map (toward package)

| Current surface | Target | Slice | Notes |
|:---|:---|:---:|:---|
| `scripts/opik_metrics.py` **and** `tests/test_opik_metrics.py` | absorb/delete/demote **together** into `eval/scoring/` or delete-as-law | S2b | Format heuristics ≠ gold law. Surviving script is advisory-only and **not** imported by scoring, CI, or gates; rewrite/retire the existing test. |
| `scripts/eval_commit_message.py` | `eval` runner CLI | S1–S6 | split encode/score/export |
| `scripts/compile_opik_dataset.py` | corpus + mirror | S1/S4 | local snapshot first |
| `scripts/opik_trace_triage.py` | `eval` triage / doctor | S6 | |
| `scripts/setup_opik_eval_rule.py` | lane_c lab helper or docs | S5 | non-gate |
| `scripts/setup_opik_test_suites.py` | mirror/lab helper or docs | S5/S4 | |
| new `src/git_cg/eval/**` | package home | S0–S6 | preferred |

---

### 8.10 Filing order & parallelism

```text
Design close prep: this plan §1–§8
    │
    ▼
File S0 → implement S0
    │
    ▼
File S1 → implement S1
    │
    ├─► File S2 → implement S2 ──► File S3
    │                              │
    │                              └─► File S4 (after bind+score exist)
    │
    ├─► S6 skeleton (doctor/run offline) after S1 (parallel thin)
    │       full R11/R12 after S2 (+ S5 pins if dogfood judges)
    │
    ├─► S5 only after eligibility real (S2/S3) — never as first CI gate
    │
    └─► S7 continuous; formal after S2+ naming stable
```

**Do not file yet:** per-Opik-page issues; optimizer work; Ollie authority; #219 merge.

---

### 8.11 v0 completeness checklist

- [x] S0–S7 filing-grade sheets (goal/depends/delivers/non-goals/AC/paths)  
- [x] Cross-slice invariants  
- [x] GitHub titles  
- [x] Script absorption map  
- [x] Filing order  
- [ ] Actual GitHub grandchildren opened → **after §14 + owner file command**  
- [ ] CI workflow merged → S6 (+ S2 offline job)  


---

## 9. Opik mapping (keep / redesign / do-not-collapse)

[x] **Purpose:** freeze what we keep from today’s scaffold, what we redesign into `src/git_cg/eval/`, and what must never collapse into the Opik pillar.

### 9.0 Current scaffold gap matrix (#217 body indictment)

> **Source:** original #217 issue body “Current eval scaffold is insufficient.”  
> **Use:** justifies S0–S4 without re-arguing; update rows when scripts are absorbed.

| Surface | Current state (body-era) | Gap | Primary slice |
|:---|:---|:---|:---:|
| `scripts/opik_metrics.py` + `tests/test_opik_metrics.py` | shallow `FormatMetric` + parallel test | does not consume `commit_gold` / `commit_quality` / path-class contracts; absorb/retire together in S2b | S2b |
| `scripts/eval_commit_message.py` | live LLM regen + format/GEval | wrong default artifact; live-model dependent | S1–S6 |
| `scripts/compile_opik_dataset.py` | promote by `user_acceptance` | popularity ≠ correctness; Regime B can look “good” | S1/S4 |
| `scripts/setup_opik_eval_rule.py` | generic GPT-4o judges | not Hybrid/SOP/gold/path-class vocabulary | S5 |
| `scripts/opik_trace_triage.py` | acceptance thresholds only | no regime / gold-integrity / unbound triage | S6 |
| acceptpath + commit_quality fixtures | strong local evidence packs | not yet encoded as versioned eval bundles | S1 |
| runtime `GenerationTelemetry` | rich fields exist | not systematically evaluated for binding/counter integrity | S2–S3 |
| Opik workspace | project + traces + prompt versions + old experiments | comparison plane exists; evaluation semantics do not | S4–S6 |

**Redesign target modes for the eval runner (body → package law):**

| Mode | Default? | Role |
|:---|:---:|:---|
| `fixture_offline` | **yes** (offline CI) | Lane A |
| `acceptpath_bound` | **yes** (bound scoring) | Lane B |
| `live_regen` | **opt-in only** | secondary artifact class; never silent primary |

### 9.1 Keep (import posture)

| Keep | Why | Where it lives after redesign |
|:---|:---|:---|
| Trace / span / thread / dataset / experiment **vocabulary** | Shared operator language with Opik UI | binding + mirror metadata; thread = **commit_session_thread** (full unit; regen sub-chain optional) |
| Local-first dataset snapshot idea | CI SoT | `dataset_snapshot_v1` |
| Experiment config pinning instinct | F5 | `eval_suite_v1.pins` + compatibility hash |
| ScoreResult-shaped feedback (`name`/`value`/`reason`) | Interop with Opik export | `ScoreResult_v1` superset locally |
| Custom metric path | Only safe authoritative path | Families A–H wrappers |
| Resume concept | Operator speed | local `evaluation_checkpoint_v1` first |
| Annotation queue concept | HITL | local `.eval/review_queue` + `human.*` |
| REST bulk upload pattern | Non-blocking mirror | `export_batch_v1` + S4 |
| Optional project hygiene (`doctor`) | Maintainer confidence | `git-cg eval doctor` (FIND-003) |
| Dual depth (final + stages) | Accept-path observability | R7 trajectory + Family H |
| Existing product authorities | Law | `commit_gold`, `commit_quality`, Hybrid hooks, ranker/SOP — **unchanged ownership** |

**Keep as dev-only optional integration**, never product requirement:
* Opik Python SDK / REST credentials  
* Opik UI dashboards  
* Prompt Library browse (compare only)  
* Online experiment compare views  

---

### 9.2 Redesign (scripts → package)

| Current surface | Target | Slice | Redesign notes |
|:---|:---|:---:|:---|
| `scripts/opik_metrics.py` + `tests/test_opik_metrics.py` | `src/git_cg/eval/scoring/` or delete-as-law | S2b | Today’s header/format ScoreResult helpers are **not** gold/Hybrid law. Absorb/retire script **and** test together; leftover NLP/format heuristic → R10 diagnostic or delete from CI. Surviving script is advisory-only and outside scoring/CI/gates. |
| `scripts/eval_commit_message.py` | `eval` runner (`cli` + suite runner) | S1–S6 | Split: encode → score → (optional) export. Default mode `fixture_offline`. |
| `scripts/compile_opik_dataset.py` | `eval/corpus` + `eval/mirror` | S1/S4 | Local snapshot builder is primary; Opik dataset push is projection. |
| `scripts/opik_trace_triage.py` | `eval doctor` / triage commands | S6 | Surface pin/export/offline health; don’t invent second score law. |
| `scripts/setup_opik_eval_rule.py` | `eval/lane_c` lab helpers **or** docs | S5 | Rules = advisory cohort config only; never accept-path install. |
| `scripts/setup_opik_test_suites.py` | mirror/lab **or** docs | S4/S5 | Opik Test Suite ≠ `gate.deterministic_pass`. |
| `scripts/sync_promptfoo_to_opik.py` | **stay on #219 plane** | — | May project to Opik under Promptfoo pillar; **not** commit-accept scores. |
| `scripts/sync_prompts_to_opik.py` | optional prompt-pack mirror | S4/S7 | Prompt Library is not runtime SoT; pin via git pack hash. |
| `src/git_cg/evals/` (if present/empty) | merge/rename into `src/git_cg/eval/` | S0 | One package home; avoid dual trees. |
| ad-hoc JSONL / notebook scores | `ape_bundle_v1` + experiments | S1–S2 | No shadow score formats in CI. |
| Shallow “GEval script = quality” habit | C′/R12 advisory only | S5–S6 | FIND-007/008 |

**Redesign principles:**
1. Library code in package; scripts become thin CLIs or `just` wrappers.  
2. Scoring engine of record is local.  
3. Opik clients isolated behind `eval/mirror` + optional `eval/lane_c` imports.  
4. `import opik` must not be required to import `git_cg` product path.  
5. Deprecation: scripts print “use `git-cg eval …`” once parity exists; remove in a later cleanup PR.

---

### 9.3 Do not collapse

| Surface | Owner plane | Why not collapse into #217/Opik accept law |
|:---|:---|:---|
| **Promptfoo** assert/red-team | **#219 / Lane D** | Different authority, corpora, and failure classes; may share scrubbed export bus only |
| **Sentry** crash/ops | **#218 / Lane E** | Reliability ≠ commit semantic quality |
| **Ollie / UI suite authoring** | Opik product assistant | Not design SSOT; not CI law (F8) |
| **Prompt optimizers** | Deferred lab | Optimize advisory scores → ship via git pins only; never auto-merge |
| **Cloud dataset/experiment as golden SoT** | — | Violates F0 |
| **Opik builtin LLM metrics as Hybrid/gold** | — | Violates F2/F3 |
| **Support-demo / marketing eval noise** | — | Not product contract |
| **hipdash / local history DB** | local-only | No product-plane authority; redaction already required |
| **End-user Raycast/CLI commit UX** | product | Must not require Opik install, login, or network |
| **L2 AI amend-before-push** | owner workflow | Not an Opik online rule; don’t replace with unattended GEval gate |
| **#118/#119 historical issues** | supersession notes | Don’t re-open as live law; cite in S7 only |

**One-line collapse ban:**

> One observability blob that mixes Sentry crashes, Promptfoo red-team, Opik judges, and Hybrid validity into a single “quality score” is an epic-level architecture failure — keep planes split.

---

### 9.4 Lane ownership matrix (recall)

| Lane | Name | Authority | Home |
|:---:|:---|:---|:---|
| A | Deterministic offline fixtures | **Law** (CI regression) | #217 S0–S2 |
| B | Accept-path bound eval | **Law** (eval/CI + golden bind) | #217 S3 |
| C | Secondary semantic / judges | Advisory | #217 S5 + R12 dogfood |
| D | Promptfoo | Separate | **#219** |
| E | Sentry | Separate | **#218** |

---

### 9.5 v0 checklist

- [x] Keep list  
- [x] Redesign/absorption map  
- [x] Do-not-collapse planes  
- [x] Lane ownership recall  

---

## 10. Telemetry & privacy

[x] **Purpose:** define what evaluation may emit, what it must never emit by default, and how failures classify — without turning telemetry into a second score bus.

### 10.0 Telemetry planes (do not mix)

| Plane | Examples | May affect commit accept? | May affect golden? |
|:---|:---|:---:|:---:|
| Product generation telemetry | existing `GenerationTelemetry`, path_class_gate, gold codes | only via **product** validators already wired | via product gold/path-class |
| Eval harness telemetry | suite run ids, metric durations, gate booleans, pin refs | **no** (eval job / doctor only) | yes as **eval eligibility** signals |
| Opik mirror telemetry | export status, batch ids | **no** | **no** |
| Dogfood / L2 brief | amend-brief files, last-N GEval | **no** (unless owner hard-block profile) | **no** sole path |
| **Train corpus** | session threads, message_versions, train_export, antipattern vault | **no** | **no** product golden sole; has own train splits |
| Sentry | exceptions, perfs | crash only | **no** quality golden |

---

### 10.1 Evaluation-oriented fields / scores

Fields below are **eval-layer** (bundle/experiment/brief). Prefer reusing product enums when present.

#### 10.1.1 Identity & pins

| Field | Type | Required on CI suite | Notes |
|:---|:---|:---:|:---|
| `bundle_id` | string | ✅ | |
| `case_id` / `suite_id` | string | ✅ | |
| `snapshot_id` / `content_hash` | string | ✅ | |
| `metric_catalog_pin` | string | ✅ | `metric_catalog_v0@sha` |
| `schema_pack_pin` | string | ✅ | |
| `compatibility_hash` | string | ✅ | resume/export |
| `prompt_pack_hash` | string | when gen recorded | |
| `judge_pins` | map | when Lane C ran | |
| `harness_version` | string | ✅ preferred | |

#### 10.1.2 Artifact & binding

| Field | Type | Notes |
|:---|:---|:---|
| `artifact_class` | enum | closed §7.1 |
| `binding.state` | bound\|unbound\|partial | |
| `final_message_sha256` | string | prefer hash over body in telemetry sinks |
| `final_message_byte_len` | int | |
| `thread_id` / `trace_id` | string? | accept-path chain |
| `path_class_gate` / `diff_class` | string | reuse product coercion |
| `gold_mode` | off\|warn\|strict | |
| `gold_finding_codes` | string[] | codes only by default |
| `regime` | A\|B\|unknown | #204 |
| `failure_ids` / `prevention_ids` | string[] | #204 |
| `instance_kind` | A\|B\|other? | #204 |
| `session_tags` | string[] | e.g. session-12-seed |
| `provenance_label` | enum | §7.4.2 |
| `presentation_fallback_reason` | closed enum? | product telemetry reuse |
| `gold_blocked` | bool | consistency with final under mode |
| `gold_regen_attempts` | int | consistency with regeneration spans |
| `gold_self_correction_outcome` | closed enum? | product telemetry reuse |
| `harness.metric_catalog_version` | string | pin alias of catalog |

#### 10.1.3 Scores & gates (eval)

| Field | Type | Authority |
|:---|:---|:---|
| `scores[]` | ScoreResult_v1 | per metric_id |
| `family_rollups{}` | pass/warn/fail counts | brief/CI summary |
| `gate.deterministic_pass` | bool | law |
| `gate.semantic_cohort_eligible` | bool | entry only |
| `gate.golden_promotion_eligible` | bool | law stack |
| `dogfood.mode` | enum | R12 |
| `dogfood.last_score` | number? | advisory |
| `export.status` | enum | projection |
| `user_acceptance` | feedback score | provenance/edit only — **never** sole golden |
| evaluator exceptions | **Sentry breadcrumb/exception only** | ops path; not product score cardinality |

#### 10.1.4 Explicit non-fields (default deny)

| Do not emit by default | Why |
|:---|:---|
| Ambient full raw git diff (no owner profile) | secret + size + privacy |
| Ambient full system/user prompts | leakage / pin bypass |
| API keys / `.env` / tokens | secrets — **always deny** |
| Commit bodies under `public_ci` | thin by policy |
| Commit bodies / structured diffs under owner `train_rich` | **allowed** with scrub + private project/scope |
| Unlabeled antipattern bodies mixed into positive_gold | train contamination |
| Moderator harmful sample bodies without vault label | R6 / antipattern_vault only |
| Customer/third-party repo file contents without scope tag | out of scope / strip |
| Ollie chat transcripts as scores | F8 |

---

### 10.2 Payload allowlist / redaction

Align with existing `telemetry.redact_payload` instincts; eval must not open a weaker path.

#### 10.2.1 Profiles → sinks

| Sink | Max profile | Notes |
|:---|:---|:---|
| Local `ape_bundle_v1` / session / train_export on disk (dev) | owner ladder through `train_rich` | `raw_dev_unsafe` owner-only, gitignored; secrets always scrubbed |
| Committed fixtures | `default_scrub` / synthetic | no live secrets |
| CI logs | hashes + codes + gates | message subject optional truncated |
| R11 amend-brief | message + rollups + failure_ids + optional short rationales | no raw diff default |
| R12 dogfood store | message_sha + score + pin | message body local optional |
| Opik export (S4) | owner ladder (`default_scrub`…`train_rich`) | project pinned; never Default Project |
| Sentry | existing product redaction | no eval score spam |
| Promptfoo sync | #219 rules | not accept scores |

#### 10.2.2 Allowlist (export / cloud / shared logs)

**Always allow:** ids, pins, hashes, enums, gate bools, metric_id, value, passed, severity, failure_ids, gold codes, path_class labels, durations, export status.  

**Allow with care:** final subject line (truncate); short `reason` strings already scrubbed; staged **path lists** without file bodies.  

**Deny default (ambient):** diffs, file blobs, prompts, secrets, entire commit bodies to cloud, moderation raw samples. **Owner ladder may allow** bodies/structured diffs only under `train_rich` / `antipattern_vault` + scrub + private pin/scope — never as ambient default.

#### 10.2.3 Redaction rules

1. Run secret redaction before any export or CI log dump.  
2. If redaction fails closed → omit payload (`[REDACTION FAILED…]` pattern already used in product telemetry).  
3. Hashes are preferred references for cross-system join (`final_message_sha256`).  
4. Lane C rationales truncated (`rationale_short`) and scrubbed.  
5. Meta-eval corpora live in controlled paths; export optional and scrubbed.  

---

### 10.3 Failure classes

| Class | Examples | Blocks product commit accept? | Blocks `gate.deterministic_pass`? | Blocks golden promotion? | User-visible basic path? | Action |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Product failure** | Hybrid illegal; gold strict fail; path-class ceiling; hook reject | **Yes** (existing product path) | Yes | Yes | Yes (normal validators) | Fix message / product logic |
| **Eval harness failure** | bundle schema invalid; catalog unpin; metric exception; compat hash mismatch; binding incomplete on bound suite | **No** by default | **Yes** (eval/CI) | **Yes** | No (dev/CI/doctor) | Fix harness/fixtures/pins |
| **Export failure** | Opik network/auth/size/validation | **No** | **No** | **No** | No | Retry export; `export_*` class only |
| **Lab/judge failure** | judge timeout; missing LLM creds; flaky C′ | **No** | **No** | **No** | No | Skip/advisory; lab report |
| **Dogfood advisory soft-warn** | R12 red score with L1 green | **No** default | No | No | Maintainer only | L2 amend weighs; optional owner escalate |
| **Dogfood hard-block** (explicit profile) | owner-enabled painful gate | Only if owner profile says so | No (still not product Hybrid law) | No sole | Maintainer only | Documented dev profile only |
| **Privacy/redaction failure** | scrub fail on export path | **No** commit | Fail export / fail unsafe sink | No | No | Omit payload; fix scrubber |
| **Plane misuse** | Promptfoo/Sentry score written into deterministic gate | treat as harness bug | Yes (reject write) | Yes | No | Block merge of such code |

**Recording rule:** every non-success path stamps `failure_class` into experiment item or doctor output so triage doesn’t blame Hybrid for Opik outages.

---

### 10.4 Interaction with existing product telemetry

* Eval may **read** product telemetry fields (`path_class_gate`, gold findings, etc.) when binding.  
* Eval must **not** require Sentry/Opik flush success for accept.  
* Do not dual-write competing “quality scores” into generation telemetry without schema version + authority labels.  
* Prefer eval scores in bundle/experiment JSONL; generation telemetry stays generation-shaped.

---

### 10.5 v0 checklist

- [x] Telemetry planes split  
- [x] Field catalog  
- [x] Allowlist/redaction profiles  
- [x] Failure class matrix  
- [x] Product telemetry interaction  

---

### 10.6 Opik SDK config, modes, and bounded flush (FIND-022 / INT-09…12)

| Mode | Local Layer A | Opik export | Accept-path block on export fail? |
|:---|:---:|:---:|:---:|
| `off` | optional | no | n/a |
| `local_only` | yes | no | n/a |
| `mirror` | **required first** | best-effort | **never** |
| `strict_mirror` | required first | required for **eval job** green | still **never** blocks git commit accept |

**Laws:**
1. Explicit endpoint/project/environment — **no silent Default Project**.
2. Project lanes: `live` / `eval` / `ci` / `import` (see config schema).
3. Short-lived hooks must use **bounded** `flush_timeout_ms`; timeout ⇒ `export_error` class, not product fail.
4. Missing key/project/network/auth/TLS/HTTP failures classify as **export/config health only**.
5. `git-cg eval opik doctor` and `git-cg eval opik config show` are secret-safe (mask keys).

### 10.7 Two-layer durability & export queue (INT-16 / INT-17 / INT-19)

| Layer | Store | Authority |
|:---|:---|:---|
| **A** | `.eval/bundles/`, scores, topology, correlation | **SoT** for evidence, replay, promote, golden eligibility |
| **B** | Optional Opik SDK SQLite / cloud | Projection / lake UX only |

**Order:** write Layer A → enqueue `.eval/export_queue/` → optional SDK export → record export health on `opik_export` span.  
**Idempotency key suggestion:** `bundle_hash + project_lane + environment + dataset_id + redaction_profile`.  
**Commands:** `eval export status|retry|drain`.

### 10.1.5 LLM usage metadata (INT-28; advisory)

On `llm_generation` spans / bundle side-channel (nulls allowed):  
`provider`, `model`, `model_version`, `prompt_pack_id`, `prompt_pack_hash`, `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, `retry_count`, `temperature`, `max_tokens`.  
**Never** a product gate by itself.

---

## 11. Skills policy (`opik` / `instrument`)

[x] **Purpose:** skills are tactical accelerators for maintainers. They are **not** architecture SSOT and lose all conflicts with F0–F9 / this plan.

### 11.1 Role

| Skill | Role | Not role |
|:---|:---|:---|
| **`opik`** | How to connect, log traces, run vendor eval helpers, navigate Prompt Library / experiments **as mirrors** | Define commit accept law; author golden corpus; own Hybrid/gold |
| **`instrument`** | How to add Opik tracing decorators/integrations to code under explicit maintainer ask | Force instrumentation on basic-user paths; gate commits on spans |

**SSOT hierarchy:**

```text
F0–F9 + this plan (`docs/plans/opik-evaluation-harness.md`) + product modules
  > ADRs (S7)
  > metric_catalog_v0 / schema_pack_v0
  > skills (opik, instrument)
  > Opik web docs / Ollie
```

---

### 11.2 Allowed ops by slice

| Slice | `opik` skill allowed | `instrument` skill allowed |
|:---:|:---|:---|
| S0 | Reference ScoreResult shape only; no cloud bootstrap required | No product instrumentation required |
| S1 | Optional: compare vendor dataset concepts | No |
| S2 | **No** “add GEval metric” as authoritative; custom metric pattern OK if wrapping product | No |
| S3 | Thread/trace vocabulary OK; thread ≠ chat agent | Optional span emit for accept-path **dev** only, behind flags |
| S4 | REST/experiment mirror helpers OK | Optional |
| S5 | Lane C lab setup OK with pins; meta-eval patterns OK | Judge provider wiring lab-only |
| S6 | doctor/export hygiene OK; **not** required for amend-brief local path | No force-instrument on commit UX |
| S7 | Doc links OK | Doc links OK |

**Always allowed (maintainer):** read Opik docs via skill; propose mirror dashboards; draft lab rubrics labeled advisory.  
**Always disallowed:** skill-driven PR that makes Opik required for `git-cg commit` success.

---

### 11.3 Forbidden skill defaults

| Forbidden default | Why | Correct alternative |
|:---|:---|:---|
| Prompt Library as **runtime SoT** | pins live in git | git prompt-pack hash + optional mirror |
| Opik Test Suite / NL asserts as **CI sole gate** | F3/F0 | Lane A deterministic suites |
| Local Runner / online eval on **accept-path critical path** | F4/G13 | offline `git-cg eval run`; async dogfood optional |
| “Step 6 prompt migration” auto-ship from optimizer/Ollie | F8 | offline candidate + human PR + pins |
| Builtin Hallucination/Moderation/GEval as product families | F2/F3 | Families C/D/F + R6/#219 + C′ |
| Instrument-all then gate on span completeness for users | basic-user blast | R7 on bound eval captures only |
| Cloud project bootstrap as control plane | F0 | local fixtures first |
| Collapsing Promptfoo skill flows into commit scores | F7/#219 | keep Lane D |
| Treating “no LLM judge exists” as true | L2 amend exists | use R11 brief; optional R12 |
| Treating “GEval every commit” as always banned | over-read | ban sole product shape; allow R12 dogfood |
| Stripping train/session fields because non-gating | under-collect | M11 / I11 record enrichment |
| Replacing existing metrics with “one Opik score” | I10/F7 | additive planes only |
| Forcing thin redaction against owner `train_rich` | fights mission | R14 ladder; still scrub secrets |
| Skills editing SOP/gold via prompt text | F2 | change product modules + tests |

---

### 11.4 Conflict rule

```text
If skill text, Opik docs, Ollie, or a tutorial conflicts with F0–F9,
R-register constraints, metric catalog authority, or product modules
→ skill/docs lose. Implement the plan; file FIND-* if vendor capability
looks valuable inside the floor.
```

**PR review ask for skill-driven diffs:**
1. Which slice?  
2. Authority = law or advisory?  
3. Does basic commit still work offline without Opik?  
4. Pins present?  
5. Failure class correct?  

---

### 11.5 Agent / L2 amend interaction

| Actor | May do | May not do |
|:---|:---|:---|
| AI amend L2 (this workflow) | Read R11 brief; amend message under owner; reference failure_ids | Silent force-push; override owner; call Opik as sole blocker |
| Coding agents implementing slices | Follow §8 AC; use skills tactically | Open S5 as merge gate; invent metric forks |
| `opik` skill during dogfood | Help pin judges; debug export | Enable hard-block profile without owner |
| Owner | Approve profiles, file issues, push | — |

---

### 11.6 v0 checklist

- [x] Role / SSOT hierarchy  
- [x] Allowed ops by slice  
- [x] Forbidden defaults (incl. refined GEval wording)  
- [x] Conflict rule  
- [x] L2/agent interaction  


---

## 12. Risks & watchlist

[x] **Purpose:** pre-mortem the #217 implementation so agents and reviewers fail closed on known failure modes. Severity is residual risk **after** floor F0–F9 / R-locks are applied correctly.

### 12.0 How to use this section

| Field | Meaning |
|:---|:---|
| **Sev** | `P0` ship-blocker if realized · `P1` high / hard to reverse · `P2` medium / recoverable · `P3` watch / noise |
| **Class** | authority · privacy · ops · process · product-ux · economics |
| **Trigger** | What a PR/reviewer should notice |
| **Mitigation** | Design already in this plan (primary) + implementation AC |
| **Own** | Slice primarily responsible for detection/prevention |

**Default response order when a risk fires:** disable the R-item / feature flag → keep Lane A/B green → amend design if needed → never “hotfix” by making judges law.

---

### 12.1 Authority & false-green risks

| ID | Risk | Sev | Class | Trigger | Mitigation | Own |
|:---|:---|:---:|:---|:---|:---|:---:|
| **RK-A1** | **Authority inversion** — Lane C / GEval / human.* / NLP becomes sole or co-equal accept/golden law | P0 | authority | PR removes `authority=advisory`; CI job named required GEval; golden promo without A–H | F2/F3; gate composition §6.11; S5 AC; S7 ADR language; FIND-007 | S2/S5/S7 |
| **RK-A2** | **False-green Regime B** — looks-good message passes L1, fails attribution/semantic; no fixture fuel | P0 | authority | Missing `corpus.regime=B` cases; inventory-only equality as “semantic pass” | #204 Regime B fixtures S1; Family F/C evidence-surface FIND-004; L2 amend + R11 packs; never GEval sole | S1/S2/S6 |
| **RK-A3** | **Gold-rule fork** — eval reimplements `commit_gold` / Hybrid via regex/prompt instead of wrappers | P0 | authority | Duplicate string tables; scores diverge from product on same message | S2 exit risk; M-laws; custom metrics wrap product callables only | S2 |
| **RK-A4** | **Label leakage** — expected/gold/assert text enters ordinary judge prompts | P0 | authority | Judge input contains `expected_*` outside meta-eval envelope | F6; S5 AC meta-eval isolation; scrub templates | S5 |
| **RK-A5** | **Eligibility bypass** — C′/dogfood runs on deterministic-fail cohorts and is read as “overall quality” | P1 | authority | Missing `gate.semantic_cohort_eligible`; dashboards average all rows | §6.10.1; S5 forbids; doctor warns | S5/S6 |
| **RK-A6** | **HITL sole golden promote** — `human.*` alone ships golden | P1 | authority | Promo path without A–H + binding | Golden minimum §2.4; review_queue AC | S6 |
| **RK-A7** | **L2 collapsed into Opik online rule** — assistant amend replaced by unattended cloud judge gate | P0 | authority | Hook blocks on Opik/judge; “no human in loop” narrative | §2.6–2.7; §9.3; R11 local-first | S3/S6/S7 |
| **RK-A8** | **Over-ban of dogfood** — agents refuse R12 because “GEval on commit banned” | P1 | process | Skills/docs omit FIND-007 narrow ban | §0.3.5; §11.3; S7 AC wording | S7/S11 |

---

### 12.2 Privacy, telemetry & plane risks

| ID | Risk | Sev | Class | Trigger | Mitigation | Own |
|:---|:---|:---:|:---|:---|:---|:---:|
| **RK-P1** | **Payload leak** — raw diffs, full prompts, secrets, moderation samples in cloud/export | P0 | privacy | Export fixtures retain denied fields; missing scrub tests | §10 default-deny; `default_scrub`; S4 AC; G11 | S4/S10 |
| **RK-P2** | **Plane collapse** — single “quality score” mixes Opik + Promptfoo + Sentry + Hybrid | P0 | authority | Shared gate module; one dashboard KPI as merge law | F7; §9.3 collapse ban; separate buses | all / S7 |
| **RK-P3** | **Dual-write score bus** — generation telemetry and eval catalogs disagree without authority labels | P1 | ops | Unversioned quality fields on accept path | §10.4; schema version + authority on every score | S3/S10 |
| **RK-P4** | **hipdash / history DB as product authority** | P2 | authority | Eval reads hipdash previews as gold | §9.3; local-only redacted | — |
| **RK-P5** | **Failure class confusion** — export/judge outage fails product accept or CI golden | P0 | ops | `gate.deterministic_pass` depends on network | F4; §10.3 classes; S4 AC offline green | S4/S6 |
| **RK-P6** | **R6 / #219 double ownership** of moderation without scrub coordination | P2 | process | Both pillars dump unredacted samples | FIND-005; R6 off-by-default; plane note | S5/#219 |

---

### 12.3 Slice-order, process & skill risks

| ID | Risk | Sev | Class | Trigger | Mitigation | Own |
|:---|:---|:---:|:---|:---|:---|:---:|
| **RK-S1** | **Slice skip** — impl PRs before S0 pins/schemas | P0 | process | Metrics land without catalog hash / envelope | §4/§8 filing order; §14 gate | owner |
| **RK-S2** | **S5 as first CI gate** | P0 | authority | Required GEval workflow before Lane A | §4.3; S5 forbids; §8.10 | S5/S6 |
| **RK-S3** | **Page-issue explosion** — one GH issue per Opik doc page | P2 | process | Filings outside §8.8 titles | §4 option B rejected | owner |
| **RK-S4** | **Skill cargo-cult** — `opik`/`instrument` treated as architecture SSOT | P1 | process | PR cites skill over F0–F9/plan | §11 hierarchy + conflict rule | S7 |
| **RK-S5** | **Script dual-tree forever** — `scripts/*` remain shadow SoT beside `src/git_cg/eval` | P2 | ops | Two score formats in CI | §8.9/§9.2 absorption; deprecation path | S2–S6 |
| **RK-S6** | **Heavy main.py rewrite** for binding | P1 | product-ux | Broad accept-path churn, hook regressions | S3 narrow emit hooks; graph impact review | S3 |
| **RK-S7** | **Boiling-ocean #204 import** blocks S1 exit | P2 | process | S1 waits on full archive | S1 seed+import path; ramp later | S1 |
| **RK-S8** | **CLI sprawl / basic-user noise** | P1 | product-ux | `git-cg --help` forces Opik setup | G13; S6 AC hidden UX | S6 |
| **RK-S9** | **Filing without §14 / owner command** | P1 | process | Grandchildren opened mid-draft | §14 + §16; no file until green | owner |

---

### 12.4 Cloud SoT, pins & lab risks

| ID | Risk | Sev | Class | Trigger | Mitigation | Own |
|:---|:---|:---:|:---|:---|:---|:---:|
| **RK-C1** | **Cloud dataset/experiment as CI/golden SoT** | P0 | authority | CI pulls remote “latest” suite | F0/F5; local snapshot ids; doctor | S1/S4/S6 |
| **RK-C2** | **Unpinned latest** model/prompt/judge/dataset | P0 | authority | Missing pin fields; float tags | F5; doctor fails; R12 pin required | S0/S6 |
| **RK-C3** | **Scoring inside Opik task functions** as engine of record | P0 | authority | Upload-time LLM score becomes gate | S4 exit risk; local precompute first | S4 |
| **RK-C4** | **Optimizer / Ollie auto-ship** to live pins | P1 | authority | Auto-merge prompt pack from UI | F8; R5 dirty overlays only | S5/S7 |
| **RK-C5** | **Prompt Library runtime fetch on accept/CI** | P1 | authority | Network pin bypass | §11.3 forbidden; git pack hash | S4/S7 |
| **RK-C6** | **Import opik on product import path** | P1 | product-ux | `import git_cg` pulls opik | §9.2 principle 4; lazy optional | S0/S3 |
| **RK-C7** | **Resume ignores compatibility hash** → silent mix of catalogs | P1 | ops | Checkpoint loads across metric_catalog bump | §7 resume hard-fail; S6 AC | S6 |
| **RK-C8** | **R5 dirty overlay leaks to CI green** | P1 | authority | Dirty provenance absent | R5 stamps; CI rejects dirty | S5 |

---

### 12.5 R11 / R12 dogfood-specific risks

| ID | Risk | Sev | Class | Trigger | Mitigation | Own |
|:---|:---|:---:|:---|:---|:---|:---:|
| **RK-D1** | **User-visible latency** from sync dogfood on commit path | P1 | product-ux | Sync mode default; >budget stalls | R12 async+advisory preferred; +0ms async target; measure M4 | S6 |
| **RK-D2** | **Cost blow-up** always-on paid judge | P2 | economics | No sample mode; huge payloads | `sample`; message-first payload; pins/timeouts | S6 |
| **RK-D3** | **L2/judge conflict** — amend optimizes GEval prose against Hybrid/SOP | P1 | authority | Brief treated as maximize-score objective | R12 arbitration; L1 wins; L2 must not auto-rewrite solely for judge | S6/L2 |
| **RK-D4** | **Anchor bias** — last-N attachments dominate amend without L1 rollup | P2 | authority | Brief omits family scores/failure_ids | R11 schema requires L1 block first | S6 |
| **RK-D5** | **SKIP fatigue / flaky attaches** train maintainers to ignore briefs | P2 | ops | High skip rate; no doctor signal | Pin health; budgets; flake study R8 lab-only | S5/S6 |
| **RK-D6** | **Hard-block dogfood default** or sole CI fail | P0 | authority | Profile ships hard-block on for users/CI | R12 locks; AC `off` default non-maintainer | S6 |
| **RK-D7** | **Unversioned amend-brief schema** breaks L2 agents silently | P1 | ops | No `schema_version`; breaking field renames | `amend_brief_v1`; catalog projection M8 | S0/S6 |
| **RK-D8** | **Dogfood records become golden corpus without promotion rules** | P1 | authority | Rolling dogfood auto-enters golden | Separate `dogfood-rolling` dataset; promo minimum | S1/S6 |

---

### 12.6 Watchlist (ongoing signals — not all are bugs yet)

| Watch ID | Signal | Why it matters | Review cadence | Escalation |
|:---|:---|:---|:---|:---|
| **W1** | Lane A offline suite red on main | Law regression | every PR touching gold/quality/eval | block merge |
| **W2** | `gate.deterministic_pass` composition drift | False CI green/red | S2+ catalog changes | freeze catalog bump |
| **W3** | Export pending backlog / scrub violations | Privacy + operator trust | weekly dogfood | stop export; fix scrub |
| **W4** | R12 p95 latency vs budget | UX/cost | after dogfood enable; M4 baseline | force async/`sample`/`off` |
| **W5** | C′ disagreement rate vs L1 on eligible set | Judge value vs noise | after S5 | R2 meta-eval; tighten rubric or disable |
| **W6** | Golden promo count without Regime B coverage | Corpus blindness | each promo | require B fixtures |
| **W7** | Skill-driven PRs failing §11 PR ask | Cargo-cult | every skill-cited PR | request rework |
| **W8** | `import opik` appearing in product critical path | Basic-user / offline break | S3/S0 dependency audit | isolate behind optional extra |
| **W9** | #218/#219 scores referenced in Opik accept docs | Plane bleed | S7 reviews | rewrite |
| **W10** | Findings filed but undecided >7 days | Floor friction | owner review | decide or park in §13 |
| **W11** | Dual `src/git_cg/evals` vs `eval` trees | Drift | S0 | merge/rename |
| **W12** | Assistants inventing metric_ids not in catalog | Catalog fork | L2/R11 consumers | reject; catalog bump process |

---

### 12.7 Risk → slice ownership matrix (summary)

| Slice | Primary residual risks to carry in issue body |
|:---:|:---|
| S0 | RK-S1, RK-C2, RK-D7, W11 |
| S1 | RK-A2, RK-S7, RK-D8, W6 |
| S2 | RK-A1, RK-A3, W2 |
| S3 | RK-S6, RK-P3, RK-C6, RK-A7 |
| S4 | RK-P1, RK-P5, RK-C1, RK-C3 |
| S5 | RK-A4, RK-A5, RK-C4, RK-C8, W5 |
| S6 | RK-D1–D6, RK-S8, RK-A6, W3–W4 |
| S7 | RK-A8, RK-S4, RK-P2, W7, W9 |

---

### 12.8 Pre-merge red-team questions (paste into PR template later)

1. Can this change make a **basic user** need Opik, network, or a judge credential?  
2. Can **`gate.deterministic_pass`** flip for non-A–H reasons?  
3. Is any new score missing **`authority`** / pin / metric_id?  
4. Did export/scrub tests cover **denied fields**?  
5. Does dogfood stay **async+advisory** unless owner opted into sync?  
6. Would a **Regime B** false-green still be caught offline without the assistant?  
7. Are #218 / #219 surfaces still **non-owners** of this gate?  
8. If Opik is down, does **Lane A** still green and commit still work?

---

### 12.9 Training-corpus & session-thread risks (added v0.8.1)

| ID | Risk | Sev | Mitigation |
|:---|:---|:---:|:---|
| **RK-T1** | Secret exfiltration via `train_rich` | P0 | scrub + quarantine; never skip scrub for cloud |
| **RK-T2** | Label noise / wrong train_label sign | P1 | require labels for vault; don’t train on GEval alone |
| **RK-T3** | Positive/negative contamination | P0 | split datasets; antipattern_vault isolated |
| **RK-T4** | Thin-out mission (hash-only lake) | P1 | owner ladder; M11; S4 AC body profiles |
| **RK-T5** | Thread replaces other metrics | P1 | I12 additive only |
| **RK-T6** | Capture skips fails (no hard-negatives) | P1 | capture_on=fail\|all |
| **RK-T7** | Preference pairs never stored | P1 | R11/R13 write versions |
| **RK-T8** | Opik-only retention lock-in | P2 | local train_export_v1 |
| **RK-T9** | “For training” used to make GEval accept law | P0 | dual axis §2.8; F3 holds |
| **RK-T10** | Product UX/metrics regression while adding Opik | P0 | I10; tests on eval-off path |

### 12.10 v0 checklist

- [x] Authority / false-green risks  
- [x] Privacy / telemetry / plane risks  
- [x] Slice / process / skill risks  
- [x] Cloud SoT / pin / lab risks  
- [x] R11/R12 dogfood risks  
- [x] Training-corpus / thread risks  
- [x] Ongoing watchlist  
- [x] Slice ownership + PR red-team asks  

---

## 13. Open questions / parked items

[x] **Purpose:** separate **must-decide before/at filing** from **explicitly parked** work so implementation does not re-litigate closed floor items.

### 13.0 Status legend

| Status | Meaning |
|:---|:---|
| **open** | Needs owner/implementation decision; does not reopen F0–F9 |
| **parked** | Deferred by design; do not implement in S0–S4 unless new Finding |
| **resolved** | Decided in this plan / owner log — kept for traceability |

---

### 13.1 Open questions (active)

| ID | Question | Owner | Blocks | Slice | Status | Notes / options |
|:---|:---|:---|:---|:---:|:---:|:---|
| **Q1** | Exact GH filing moment: SSOT pointer on #217 (**body preferred**) then S0, or S0–S1 together? | owner | filing | 0–1 | resolved | Default recommendation: **body pointer + S0 only**; file S1 after S0 schema merged or same day if schema frozen in plan |
| **Q2** | Package path final: only `src/git_cg/eval/` vs migrate any `evals/` remnant? | impl | S0 layout | 0 | open | Plan assumes single `eval/`; confirm tree at S0 start |
| **Q3** | CI home for Lane A offline job: existing workflow vs new `eval.yml`? | owner | S6 CI recipe | 6 | open | Must remain offline/no Opik creds; start as non-required if flake unknown |
| **Q4** | R12 sync budgets: lock numbers after first M4 Max measurement, or keep §3 targets until then? | owner | soft-warn enable | 6 | open | Until measured: **async-only** dogfood default; no sync-warn default |
| **Q5** | R11 `last-N` default (1 vs 3 vs 5) and retention of `.eval/dogfood` artifacts? | owner | brief UX | 6 | open | Recommend **N=3**, gitignore dogfood bodies, keep ids/scores |
| **Q6** | ADR id: rewrite ADR-0011 vs new ADR number? | owner/docs | S7 | 7 | open | S7 title currently assumes ADR-0011 eval layer rewrite |
| **Q7** | Whether thin S6 (`eval run`/`doctor` offline) may file/implement in parallel after S1 before S2 complete? | owner | schedule | 6 | open | §8.10 allows skeleton; full R11/R12 after S2 (+ S5 pins if judges) |
| **Q8** | Seed fixture count bar for S1 exit (minimum Regime A/B matrix)? | impl | S1 AC | 1 | open | Need explicit minimum table at S1 filing (not full #204) |
| **Q9** | Public vs private posture of scrubbed export samples in Opik project naming? | owner | S4 | 4 | open | Dev project lane pin required; no Default Project |
| **Q10** | Optional machine artefact `docs/plans/opik-evaluation-harness.inclusion-map.yaml` — ship with S0 or never? | owner | none | 0 | open | Optional; markdown remains human SSOT for now |
| **Q11** | How L2 amend sessions discover brief path (`stdout` pipe vs `.eval/last_amend_brief.json`)? | owner/L2 | R11 UX | 6 | open | Support both; document one default |
| **Q12** | Hard-block dogfood profile name + storage (mise/env/gitignored config) for explicit opt-in? | impl | R12 | 6 | open | Must be impossible to enable via ambient default |
| **Q13** | Coordination note placement with #219 for R6 (issue comment vs shared docs stub)? | owner | FIND-005 | 5 | open | Before enabling R6 on |
| **Q14** | Metric catalog change-control: PR label only vs CODEOWNERS on catalog file? | owner | M-laws | 0/7 | open | At least catalog hash bump + checklist in S0 |
| **Q15** | Maintainer default redaction profile for private Opik project (`private_message` vs `train_rich`)? | owner | R14 | 4/6 | **resolved** 2026-08-13 | **`train_rich`** for private dogfood/train lake (secrets still scrubbed; not ambient/basic/CI) |
| **Q16** | Default `corpus.capture_on` for dogfood (`pass` vs `all`)? | owner | train negatives | 6 | **resolved** 2026-08-13 | **`all`** while building corpus (fail rows → hard_negative candidates; not gates) |
| **Q17** | Preference-pair retention: all L2 amends vs only when text changes? | owner | R11/R13 | 6 | **resolved** 2026-08-13 | Store preference pair **whenever bytes change**; skip no-op identical drafts |
| **Q18** | Opik project naming for train-positive vs train-negative split | owner | S4 | 4 | open | Separate datasets or metadata filter — pick at S4 |

---

### 13.2 Parked (explicit non-goals until new Finding / later epic)

| ID | Item | Why parked | Revisit when | Status |
|:---|:---|:---|:---|:---:|
| **PK1** | Prompt/agent **optimizers** auto-ship | F8; authority | offline candidate search design + git pin workflow | parked |
| **PK2** | **Ollie** as suite authoring/CI authority | F8 | never as law; compare UX only | parked |
| **PK3** | Full historical **#204 archive** completeness as S1 blocker | sizing | after seed path + promo loop works | parked |
| **PK4** | Multi-rater weighted **HITL** consensus algorithms | R4 depth | after local queue MVP | parked |
| **PK5** | Online Opik **evaluation rules** on accept-path | F3/F4 | not planned | parked |
| **PK6** | Merging **Promptfoo** into commit-accept scores | F7 / #219 | never via #217 | parked |
| **PK7** | **Sentry** as quality score bus | F7 / #218 | never via #217 | parked |
| **PK8** | Builtin **Hallucination/Moderation/GEval** as Families A–H | F2/F3 | only as C′/lab under R1/R12 | parked |
| **PK9** | **Local Runner / opik connect** as required commit UX | G13 | never required | parked |
| **PK10** | One GH issue **per Opik doc page** | §4.B | never | parked |
| **PK11** | Broad **raw diff** cloud logging **without** owner ladder + scrub | G11/R14 | ambient default still banned; `train_rich` is explicit owner profile | parked (ambient) |
| **PK12** | Agent tool-correctness / multi-turn **dialogue** metrics as commit legality | §3.3 rejects | n/a | parked |
| **PK13** | Re-litigation of closed **#118/#119** as live law | supersession | S7 notes only | parked |
| **PK14** | Cross-repo / multi-product eval graph | out of scope | separate epic | parked |
| **PK15** | End-user exposure of Opik in Raycast/CLI onboarding | G13 | never for basic path | parked |

---

### 13.3 Resolved decisions (do not reopen without constitution amendment)

| ID | Decision | Where locked | Status |
|:---|:---|:---|:---:|
| **RS1** | Decomposition **C + D escape hatch** | §4 | resolved |
| **RS2** | Floor **F0–F9** unchanged | §2 / §17.1 | resolved |
| **RS3** | R11 + R12 **active law**; FIND-001…008 **approved** | §3.5 / §17 | resolved |
| **RS4** | Narrow GEval anti-pattern (product sole/unattended/universal) — dogfood allowed | §0.3.5 / FIND-007 | resolved |
| **RS5** | Preferred dogfood **always + async + advisory** | R12 | resolved |
| **RS6** | Local snapshots / `ape_bundle_v1` = SoT; Opik = mirror | F0 / §7 / §9 | resolved |
| **RS7** | Skills are tactical, not SSOT | §11 | resolved |
| **RS8** | L2 AI amend is live interactive LLM review under owner — not Opik online rule | §2.6 | resolved |
| **RS9** | No filing grandchildren until §14 + owner command | §8.11 / §14 | resolved |
| **RS10** | Export/judge/Opik outage ≠ product accept fail | F4 / §10 | resolved |
| **RS11** | Training-corpus mission + dual axis gate vs retention | §0.3.6 / §2.8 / FIND-009 | resolved |
| **RS12** | Commit-session thread additive (R13) | FIND-011 | resolved |
| **RS13** | Owner redaction ladder + train export (R14) | FIND-013–016 | resolved |
| **RS14** | R12-MVP early; R7 on for maintainer train; M10/M11/I10–I12 | FIND-010/014/017/018 | resolved |
| **RS15** | Non-degradation of existing functionality/metrics | I10 / FIND-018 | resolved |
| **RS16** | Maintainer defaults Q15/Q16/Q17 locked | `train_rich` / `capture_on=all` / pairs-on-bytes-change | resolved |
| **RS17** | **API-surface policy (CLI-first):** CLI = primary public API; selected `git_cg.eval*` = supported maintainer/harness APIs; product internals = internal. No general-purpose Python SDK; no REST/OpenAPI; no external API-doc services. S5 = narrow harness export only; S6 = operator API map + help/usage alignment; S7 = durable Zensical/ADR docs + optional allowlist autodoc subordinate to hand-written contracts | §0.3.13 / §8.5–§8.7 / §17.1 | resolved |

---

### 13.4 Decision hygiene

1. New uncertainty → add **Q#** here (or **FIND-*** if it challenges the floor).  
2. Do not bury decisions only in chat — promote to §13.3 or §17.1.  
3. Parked items require a **Finding + owner approve** to unpark into an R-item or slice deliverable.  
4. Open Qs **do not** block finishing this design doc; they block only the slices listed in **Blocks**.  
5. Filing S0 may proceed with Q2/Q10 provisional defaults recorded in the S0 issue body.

---

### 13.5 v0 checklist

- [x] Open questions table  
- [x] Parked non-goals  
- [x] Resolved decisions trace  
- [x] Decision hygiene  
- [x] Owner resolves Q1 (filing sequence) before first `gh issue create` → [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220)  

---
## 14. Filing checklist (when leaving skeleton stage)

- [x] §2 floor filled and matches #217  
- [x] §3 R-register filled  
- [x] §4 decomposition explicitly accepted (C + D escape hatch)  
- [x] §5 inclusion maps compiled from comments  
- [x] §6 catalog compiled  
- [x] §7 schemas compiled  
- [x] §8 slice sheets compiled  
- [x] §8 each slice has Goal / Depends / Delivers / AC / Forbids  
- [x] §9 Opik mapping compiled  
- [x] §10 telemetry & privacy compiled  
- [x] §11 skills policy included  
- [x] §12 risks & watchlist compiled  
- [x] §13 open questions / parked / resolved compiled  
- [x] §0.3.6–9 + §2.8 training-corpus / dual-axis laws compiled  
- [x] R13/R14 + FIND-009…018 owner-approved and logged  
- [x] **v0.9.2 body-residual ingest** (scaffold gap, Regime pedagogy, Session-12 seed, provenance enum, aliases, 4MB/naming)  
- [x] **v0.9.3 S2b clarifications** (#227 T1–T12: gate-label, C/D dual-emit, empty/oversize, GoldReport API, C/E helper split, S2b block tuple, secret/policy-fork, joint script/test absorption, Family I out of S2b)  
- [x] SSOT pointer on #217 (**issue body preferred**; comments optional status only) → `docs/plans/opik-evaluation-harness.md` @ `0.9.5-s5-s6-s7-api-surface` ([issue body](https://github.com/Thomo1318/gitCommitGenerator/issues/217); S5 handoff on [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233); prior S2b locks on [#227](https://github.com/Thomo1318/gitCommitGenerator/issues/227))  
- [x] **S0 filed:** [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220) `eval(S0): freeze schema pack + metric catalog pins`
- [x] **Q1=A** resolved (body pointer + S0 only; S1–S7 not filed)
- [x] Owner decisions recorded on §17 FIND-* rows (approved 2026-08-12 + 2026-08-13)  
- [x] Owner resolves §13 Q1 (filing sequence); default **pointer-in-body + S0 only** → [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220)
- [x] Only then open S0 grandchild (explicit owner file command) → [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220)  

---

## 15. Compilation backlog (source → section)

> Track which analyses are already in #217 comments and where they land here.

| Source (chat / #217 comment theme) | Target section(s) | Compiled? |
|:---|:---|:---:|
| #217 issue body (lanes, D1–D6, catalog, slices) | §1 §2 §6 §7 §8 §9 | [x] core design sections landed |
| #217 issue body residual pedagogy (scaffold gap, Regime A/B table, Session-12 seed, provenance enum, F/P namespaces, what-good-looks-like, 4MB/naming, gold non-weaken, dataset aliases) | §1.6 §2.1 §3.3 §7.3.2 §7.4.* §8.1 §8.4 §9.0 §10.1 §18.14 | [x] **v0.9.2** |
| Full evaluation suite inclusion map | §5 | [x] |
| H/M cookbook restrictions (superseded by full map; keep deltas if any) | §5.4 | [x] |
| Relax/remove trade-offs | §5.5 §3 | [x] |
| Controlled relaxations appendix R1–R14 | §3 | [x] |
| Skills `opik` + `instrument` assessment | §11 | [x] |
| REST / offline / dual-plane metric maps (earlier #217 comments) | §5 §6 §9 §10 | [x] |
| Agents/threads inclusion map | §5.4 §8.3 §8.5 | [x] |
| Training-corpus mission FIND-009…018 / R13–R14 | §0.3 §2.8 §3 §6 §7 §8 §10 §12 §17 | [x] |
| Post-edit consistency audit (stale R-range / redaction / slices) | §3 §7.6 §8–§10 §13 | [x] |

---

## 16. Next actions

0. [x] **v0.9.0 #217 comment-depth ingest** — INT-01…45 / FIND-019…025 compiled into plan (§0.4, §2.9, §5.7, §6.1b/6.9b, §7.2.12–18, §8 addenda, §10.6–10.7, §18).  
0b. [x] **v0.9.1 live Daily Briefing locks** — FIND-026…028 / INT-46…52 / §18.13 (empty-output fan-out, artifact bind, prompt-drift; no SOP relax from unbound online scores).  
0c. [x] **v0.9.2 #217 body-residual ingest** — §1.6 / §7.4 pedagogy / §9.0 scaffold gap / aliases / S4 4MB+naming / body supersession §18.14.  
0d. [x] **v0.9.3 S2b clarifications** — §6.4–§6.9 / §6.11 / §8.2 / §8.9 T1–T12 locks for #227.  
0e. [x] **v0.9.4 S5 eligibility/availability split** — #233 Slice 0 locks in §6.11 / §7.2.18 / §8.5.  
0f. [x] **v0.9.5 S5/S6/S7 API-surface policy** — CLI-first; selected `git_cg.eval*` supported; internals internal; S5 narrow export; S6 operator API map + help alignment; S7 Zensical/ADR durable API docs + optional allowlist autodoc (RS17).  

1. [x] Skeleton structure locked (`v0.1.0-skeleton`).  
2. [x] **§1 mission / non-goals** compiled.  
3. [x] **§2 floor F0–F9 + lanes + gates + authority matrix** compiled.  
4. [x] **§3 R-register + activation rules + rejects** compiled.  
5. [x] **§4 decomposition** locked as working default (C + D escape hatch).  
5b. [x] **§0.3 operator notes** — Opik is dev-only; gold-standard challenge protocol + §17 findings log.  
6. [x] **§5 inclusion maps** compiled (core + metrics + agents/threads/H+M + trade-offs).  
7. [x] **§5.5** trade-off summary compiled.  
7b. [x] **§17 Findings FIND-001…005** filed for owner review (no silent drops).  
7c. [x] **§0.3.4 + §2.6** AI amend-before-push captured as live L2 review gate; FIND-006/007 + R11 candidate filed.  
7d. [x] **§0.3.5 + §2.7 + R11 extended + R12** — refined GEval-on-commit anti-pattern; dogfood profile FIND-008; amend-brief last-N GEval attachments.  
8. [x] **Owner approved** FIND-001…008 + **R11/R12 active** (2026-08-12).  
9. [x] **§6 metric catalog** v0 compiled (families A–H, C′, gates, R11/R12 projection).  
10. [x] **§7 schemas/corpus** compiled (`ape_bundle_v1`, datasets, resume, #204 encoding).  
11. [x] **§8 slice sheets** with filing-grade AC (enables S0 issue).  
11b. [x] **§9–§11** Opik mapping + telemetry/privacy + skills policy.  
12. [x] **§12 risks & watchlist**.  
13. [x] **§13 open questions / parked / resolved**.  
13b. [x] **Training-corpus mission** — FIND-009…018 / R13–R14 / dual axis / I10–I12 / M10–M11 (2026-08-13).  
14. [x] **§14 operational gate** — SSOT pointer **in #217 body** + owner Q1 decision (**Q1=A**).  
15. [x] §14 green + **explicit owner file command** → open S0 grandchild only → [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220).  
16. Optional later: `docs/plans/opik-evaluation-harness.inclusion-map.yaml` (Q10).  
17. After S0: S1 → **S2a** (unblock capture/R12-MVP) → S2b/c → S3 threads; do not open S5 as merge gate.  
18. [x] Maintainer defaults locked: Q15 `train_rich`, Q16 `capture_on=all`, Q17 pairs on bytes-change.
19. [x] Post-edit consistency audit (stale R1–R12/§7.6/thread vocab/slice R-items) applied under approve-all.
20. [ ] Remaining after §14: implement [#220](https://github.com/Thomo1318/gitCommitGenerator/issues/220) S0 schema/metric-catalog freeze (filing gate complete; delivery open).

---


## 17. Findings log (blocked improvements → review)

> Use when a gold-standard improvement collides with F0–F9 / rejects. Empty means none filed yet.

| ID | Finding | Benefit to git-cg | Blocked by | Risks | Proposed path | Owner decision |
|:---|:---|:---|:---|:---|:---|:---|
| **FIND-001** | **Earlier / first-class offline judge meta-eval (R2) as a named S5 deliverable, not “later research only”** — run HaluEval-style / craft-boundary labeled cohorts against any Lane C judge we enable, with Equals-on-label + FP/FN dashboards for developers. | Stops dashboard trust without calibration; quantifies judge fallibility before C′ noise misleads triage; gold-standard eval hygiene. | Not blocked by F0–F9 if kept lab/non-gating; only “deferred tone” in older maps. | Cost/credentials in lab; bad labels → bad calibration; temptation to promote to gate. | **Elevate R2** from vague later-lab to explicit optional S5/S6 acceptance criterion *still non-gating*. No floor change. | **approved** 2026-08-12 |
| **FIND-002** | **Structured-output / schema compliance metric as authoritative harness check (Family H / B adjacency)** — use Opik-style structured compliance ideas to validate `ape_bundle_v1`, ScoreResult envelopes, and Hybrid shape *by wrapping product validators*, not NL judges. | Stronger machine-checkable harness + envelope integrity; catches schema drift early. | None if implemented as product/schema wrappers. Blocked only if taken as generic LLM structured-output judge replacing Hybrid law. | Forked format rules if not wrapping real validators. | **Implement under S2 Family H (+ B)** as custom/local metrics; mark vendor page ✅ only in that remap. | **approved** 2026-08-12 |
| **FIND-003** | **Dev-facing “eval doctor” + optional Opik project lane hygiene** (mirror of `opik doctor` ideas): pending exports, pin resolvable, no accidental float, local suite green without network. | Faster maintainer confidence; prevents silent misconfig in dogfood. | None material — pure developer UX; must stay off basic-user path (G13/F4). | Scope creep into product CLI noise if mis-exposed. | **S6 entrypoint** `git-cg eval doctor` (or `just eval-doctor`), hidden from basic commit UX. | **approved** 2026-08-12 |
| **FIND-004** | **Limited evidence-surface diagnostic inspired by context precision/recall** — not RAG law; score whether commit claims stick to allowlisted evidence surfaces (staged paths, path-class, contract fields) with **deterministic** checks. | Stronger Regime B / attribution diagnostics beyond thin inventory equality. | Builtin ContextPrecision/Recall as LLM/RAG metrics (❌ as law). | Reintroducing judge-based “context” scoring as stealth gate. | **Fold into Family F (and maybe C) deterministic metrics in S2**; do not enable Opik ContextPrecision/Recall builtins. | **approved** 2026-08-12 |
| **FIND-005** | **Optional developer moderation/safety scan on prompt packs or sample outputs (R6)** feeding review queue — never commit block. | Extra safety net for prompt-pack changes and dogfood corpora; complementary to #219. | Accept/Hybrid gate bans remain. Sensitive payload rules. | False positives; corpus handling; plane confusion with #219. | Keep **R6 off-by-default**; coordinate ownership note with #219; scrubbed local-only default. | **approved** 2026-08-12 |
| **FIND-006** | **First-class “amend-session evidence pack”** — local, Opik-optional bundle summary (family scores, failure IDs, gold counters, path-class, optional C′ rationales) shaped for AI assistant review/amend before push. | Aligns harness with real L2 workflow; makes advisory metrics useful where the actual LLM review happens; reduces need to open Opik UI mid-amend. | None if local-first and non-blocking. Weak tension only with “no LLM authority” if pack is mistaken for auto-gate. | Over-coupling assistant prompts to unstable score schemas; noise in amend context. | **R11** + **S6** `git-cg eval amend-brief`; schema versioned; default local stdout/file; **MAY attach last-N GEval/C′** from R12 (see FIND-008). | **approved** 2026-08-12 |
| **FIND-007** | **Narrow anti-pattern + document L1/L2/L4/T3 separation** — Ban only **product-plane, universal, unattended, sole-authoritative** “GEval on every commit.” Do **not** ban maintainer high-frequency advisory/async dogfood GEval. Document so future agents neither (a) ship Opik as default commit gate, nor (b) refuse useful dev dogfood thinking all GEval-on-commit is forbidden. | Prevents duplicate product blockers **and** prevents over-reading the ban as “never judge near commits.” Protects basic-user path; keeps L2 primary interactive LLM gate; enables T3 lab signal. | — (clarifies F3/F4/G13; enables R12 without floor weaken) | If wording stays sloppy, agents will either over-build online gates or under-dogfood Lane C. | **S7 docs + §2.6–2.7 + §11 skills policy**; pair with FIND-008. | **approved** 2026-08-12 |
| **FIND-008** | **Maintainer `eval.dogfood` profile (R12)** — `off\|sample\|always\|async` Lane C GEval/C′ on git-cg developer commits while building the eval stack. Recommended default for dogfood: **`always` + `async` + advisory** → feed **R11 amend-brief** last-N attachments. Overhead budgets (async +0ms user path; sync advisory ≤~5s preferred / ≤~15s owner-accept; hard-block explicit opt-in only). Pin model/prompt/temp; message-first payload; L1 always wins arbitration. | High-frequency lab signal catches assistant drift, stabilizes rubric, produces real failure→fixture fuel, battle-tests Opik path — without making GEval product law. Matches reality that L2 already spends LLM tokens on every message. | Controlled tension with “no LLM on accept path” **only if** mis-implemented as default/sole/hard gate — mitigated by audience+authority locks. | Latency; cost; false conflict with L2 (optimize for judge prose); anchor bias; SKIP fatigue; CI flake if wrongly promoted. | Approve **R12** as S6; wire into R11 attachments; measure budgets on M4 Max before any sync-warn default; keep `off` for basic users; never sole CI/golden. | **approved** 2026-08-12 |

| **FIND-009** | **Training-corpus mission as first-class plan axis** — dogfood + L2 amend builds golden metrics/data for future train/fine-tune; Opik owner project is mirror **and** longitudinal corpus lake. | Aligns harness with actual purpose of full-history amend + Opik dogfood; stops agents from thinning “non-gate” fields. | Older “mirror-only / maximize denial” tone | If misread, could pressure gate authority or secret leak | **§0.3.6 + §2.8 dual axis**; F0 clarified; record≠gate M11 | **approved** 2026-08-13 |
| **FIND-010** | **R12-MVP early** — one pinned craft GEval (async advisory) as soon as S2a + final_message capture exists; do not wait for full S5 cohort. | Prevents starving training stream and dogfood signal during long S2/S5 | S5-after-everything reading of F9 | Premature dashboard trust | R12 addendum; still advisory; R2 readiness before “operator-ready” Lane C | **approved** 2026-08-13 |
| **FIND-011** | **Commit-session thread (R13)** — one additive thread per commit unit of work for human/agent readability and corpus join. | Single place to read full commit story; better Opik UX; train join key | Thread=”regen only” remap too narrow | Thread spam; replacing other metrics | Additive only I12; local twin; map Opik thread id | **approved** 2026-08-13 |
| **FIND-012** | **L2 preference pairs / message_versions** — store draft→amend→final (and rejects) under session thread. | Highest-value training signal already produced by workflow | Final-only F1 over-read | Schema churn; large bodies | R11/R13; redaction ladder; final still product primary | **approved** 2026-08-13 |
| **FIND-013** | **Owner redaction ladder (R14)** — replace binary thinness with profiles through `train_rich` / `antipattern_vault`. | Owner can choose train-grade retention; basic/CI stay safe | G11 absolute thin reading | Secret exfil if scrub weak | Scrub mandatory; quarantine; scope tags | **approved** 2026-08-13 |
| **FIND-014** | **Corpus capture_on pass\|fail\|all** — hard-negatives and anti-patterns collectible without being gates. | Anti-pattern training data; regime B fuel | eligibility only after deterministic pass | Mixing unlabeled neg into positive | train_label + split datasets | **approved** 2026-08-13 |
| **FIND-015** | **Anti-pattern vault protocol** — intentional + live hard_negatives with mandatory labels and restricted export. | Clean negatives for training | no first-class negative store | Contamination; unsafe samples | `antipattern_vault` profile + labels | **approved** 2026-08-13 |
| **FIND-016** | **Local `train_export_v1`** portable pack beside Opik lake. | No vendor lock-in for training exports; F0-friendly | dogfood-rolling gitignore-only | dual formats drift | schema-versioned export; pins embedded | **approved** 2026-08-13 |
| **FIND-017** | **S2 phasing S2a/S2b/S2c** + R7 default-on for maintainer train profile. | Faster first green + earlier capture without gold forks | monolith S2 | partial metrics confusion | document phase gates; M10 severity | **approved** 2026-08-13 |
| **FIND-018** | **I10 non-degradation + M10 severity parity + M11 record≠gate + F1 secondary inputs clarification.** | Protects product UX and encourages enrichment | purity-over-value agent behaviour | catalog sprawl | PR checklist; tests eval-off path | **approved** 2026-08-13 |

---
## Appendix A — Legend (page marks)

| Mark | Meaning |
|:---:|:---|
| ✅ | Import / implement under pins & local SoT |
| ⚠️ | Reshape / secondary / later |
| ❌ | Reject as accept-path / golden sole gate / CI sole law / product authority |

## Appendix B — Related references

| Ref | Role |
|:---|:---|
| #216 | Parent epic |
| #217 | Design SSOT |
| #218 | Sentry pillar |
| #219 | Promptfoo pillar |
| #204 | Failure corpus / regimes |
| #212 / #214 | Fixture / craft spine inputs |
| ADR-0010 / ADR-0011 | Observability ADRs (eval layer rewrite in S7) |
| `.agents/skills/opik` | SDK reference only |
| `.agents/skills/instrument` | Emit audit reference only |
| Opik Evaluation docs | Vendor surface under §5 |
| #23 | Early repeatable eval precursor — partial/generic; superseded in depth by #217 + this plan |
| #118 / #119 | Opik Phase D/E scaffold — closed; too shallow post-#204; supersession notes only (PK13) |
| #204 | Failure archive / Regime A/B / Session-12 evidence base |
| #212 / #214 | Acceptpath path-class spine + docs craft residual — fixture truth inputs |

**Supersession one-liner:** closed #118/#119 scaffolds and generic #23 do **not** satisfy post-#204 evaluation law; do not reopen them as live gates.

---


## 17.1 Owner decision log

| When | Decision | Scope |
|:---|:---|:---|
| 2026-08-12 | **Approve all** pending findings and R-candidates | FIND-001…008; R11; R12 |
| 2026-08-12 | R11/R12 promoted from candidate → **active law** | S6 must implement `eval amend-brief` + `eval.dogfood` |
| 2026-08-12 | FIND-007 narrow anti-pattern confirmed | Product sole GEval-on-commit banned; maintainer dogfood allowed |
| 2026-08-12 | Floor F0–F9 unchanged | No acceptance of sole LLM accept/golden authority |
| 2026-08-13 | **Approve all** training-corpus mission amendments | FIND-009…018; R13; R14; R3/R7/R11/R12 amendments; dual axis; I10–I12; M10–M11 |
| 2026-08-13 | Gate axis unchanged; corpus retention axis owner-enriched | F3/F4 hold; train_rich does not imply accept gate |
| 2026-08-13 | Non-degradation + additive threads/metrics | I10/I12 |
| 2026-08-13 | Recommended defaults locked under approve-all | Q15→`train_rich` private dogfood; Q16→`capture_on=all`; Q17→pairs on bytes-change |
| 2026-08-13 | Post-edit consistency audit fixes | R1–R14 headings/slices/docs; §7.6 ladder; thread vocab; S0/S3/S4/S6/S7 R-item alignment |
| 2026-08-13 | **Compile #217 comment-depth contracts** into plan (v0.9.0) | FIND-019…025; INT-01…45; no authority inversion; pre-R11–R14 comments reanalysed under current floor |
| 2026-08-13 | **Live Opik Daily Briefing locks** (v0.9.1) | FIND-026…028; INT-46…52; treat briefing as live-plane misconfig evidence; **no SOP/Hybrid threshold relax** from unbound online scores; fixes via eval-suite S2–S6 |
| 2026-08-13 | **#217 body-residual ingest** (v0.9.2) | Scaffold gap matrix; Regime A/B teaching; Session-12 seed AC; provenance enum; F/P ID namespaces; what-good-looks-like; dataset aliases; experiment naming; default 4MB batch; gold skeleton non-weaken; plan ▸ body on conflict; SSOT pointer prefers issue body |
| 2026-08-14 | **S2b T1–T12 clarifications** (v0.9.3) | #227 implementation locks: advisory-label (not veto-path) gate fix; C/D dual emission; empty/oversize overrides D always-emit; shared GoldReport API; C/E helper split; deterministic 68-id S2b block tuple; local secret-shape; non-vacuous policy-fork; joint `scripts/opik_metrics.py` + `tests/test_opik_metrics.py` absorption; Family I / `require_topology` deferred to S2c |
| 2026-08-19 | **S5 eligibility/availability split** (v0.9.4) | #233 Slice 0: §6.11 D4/D4′ identity-pins vs credentials; `judge_execution_available`; §8.5 spine vs D28 residuals + `lab_override` eligible-diagnostic/skip-only AC; §7.2.18 final_accept/UTF-8/pack notes; D30/D31 advisory `passed`/`reason="scored"`; offline no-network-judge default; D44 live pin honesty note |
| 2026-08-19 | **S5/S6/S7 API-surface policy** (v0.9.5) | CLI-first public API; selected `git_cg.eval*` supported; internals internal. **S5** narrow harness-facing export only (no general-purpose SDK). **S6** operator API map + generated CLI usage/help alignment + stability-tier messaging. **S7** durable Zensical API overview/CLI reference/curated Python contract pages, documentation-source policy, optional allowlist `mkdocstrings` only after exports stabilize, ADR language alignment. Non-goals: full-package autodoc, REST/OpenAPI, external API-doc services, publishing internals as SDK. Lane C′ docs keep advisory/gold-blind/promotion-immune honesty (`score_bundle` opt-in; no silent `score_case`/`score_suite` passthrough) |

**Approved finding dispositions (implementation binding):**

| ID | Disposition |
|:---|:---|
| FIND-001 | Optional S5/S6 offline judge meta-eval deliverable (R2 path); non-gating |
| FIND-002 | Structured-output compliance via local product wrappers (Families H/B); not NL Hybrid substitute |
| FIND-003 | S6 `git-cg eval doctor` (dev-only) |
| FIND-004 | Deterministic evidence-surface diagnostics (Family F/C remap); no Opik RAG builtins as law |
| FIND-005 | R6 moderation/safety scrubbed ops signal; off-by-default; coordinate #219 |
| FIND-006 | R11 amend-brief S6 deliverable |
| FIND-007 | Docs/law clarification in S7 + §2.6–2.7 + §11 |
| FIND-008 | R12 eval.dogfood S6 deliverable; default dogfood `always+async+advisory` |
| FIND-009 | Training-corpus mission + Opik owner lake dual purpose; dual axis §2.8 |
| FIND-010 | R12-MVP early after S2a |
| FIND-011 | R13 commit_session_thread additive |
| FIND-012 | message_versions + preference pairs via R11/R13 |
| FIND-013 | R14 owner redaction ladder |
| FIND-014 | corpus.capture_on pass\|fail\|all |
| FIND-015 | antipattern_vault protocol |
| FIND-016 | train_export_v1 local packs |
| FIND-017 | S2a/b/c phasing; R7 on for maintainer train |
| FIND-018 | I10 + M10 + M11 + F1 secondary-input clarity |
| FIND-019 | Family I topology/lifecycle harness law |
| FIND-020 | Deterministic no-Ollie debug loop |
| FIND-021 | diag_issue_v1 + fingerprints |
| FIND-022 | Opik config/modes/bounded flush |
| FIND-023 | Replay lineage + replay_compare_v1 |
| FIND-024 | split_group_id contamination law |
| FIND-025 | Official Opik reference matrix |
| FIND-026 | Empty/oversized eval precondition + anti-fan-out |
| FIND-027 | Live scores bind final message / product score_card |
| FIND-028 | Prompt drift without local suite pin = doctor-red |



| **FIND-019** | **Formal trace/span/thread topology + Family I lifecycle contract** — closed span taxonomy, parentage/order/required-span/terminal-state/counter consistency, correlation envelope, golden-eligibility coupling | Turns Session-12 class bugs into first-class eval fails; enables deterministic RCA | None if kept harness-law (not Hybrid prose substitute) | Over-instrumentation noise; false blocks on unbound fixtures if suite mis-set | S0 schemas → S2 validators → S3 emitters → S6 explain | **compiled v0.9.0** — implement S0–S3/S6 |
| **FIND-020** | **Deterministic no-Ollie debug loop** FIND→EXPLAIN→COMPARE→REPLAY→PROMOTE→VERIFY with CLI contracts | Maintainer/agent debug without SaaS assistant dependency | F8 (no Ollie authority) already aligns | CLI sprawl | S6 commands + local indexes | **compiled v0.9.0** |
| **FIND-021** | **`diag_issue_v1` + stable fingerprints** | Clusters recurring harness failures without raw-text LLM clustering | Privacy floor | Bad fingerprint churn | S0 schema + S6 diagnose | **compiled v0.9.0** |
| **FIND-022** | **Short-lived flush/export + project/environment modes (`git_cg_opik_config_v1`)** | Prevents hang-on-exit and Default Project pollution; fail-open export | F4 | Mis-set strict_mirror confusing eval vs accept | S4/S6 | **compiled v0.9.0** |
| **FIND-023** | **Replay lineage + `replay_compare_v1`** | Safe regression compare without mutating history | — | Pin drift → incomparable | S6 + S1 fixtures | **compiled v0.9.0** |
| **FIND-024** | **Corpus `split_group_id` contamination control** | Stops pair/replay leakage across train/test; keeps antipatterns out of positive train | — | Over-cohesion reducing effective N | S1/S6 promote + train-export | **compiled v0.9.0** |
| **FIND-025** | **Official Opik implementation-reference matrix** | Durable adopt/reject memory for agents; dated URL pins | — | Link rot | S7 refresh | **compiled v0.9.0** (§5.7) |
| **FIND-026** | **Empty/oversized evaluator precondition + anti-fan-out** — missing/empty scored artifact yields **one** classified row/health failure; remaining evaluators short-circuit; oversized payloads gated before LLM judges (no 5× `data must not be empty` / 504 retry storms) | Stops dashboard error inflation and false “quality crisis” from live Opik automation misconfig; protects harness reliability | None if kept harness/export health (not Hybrid rewrite) | Over-skipping real fails if guard too broad — require explicit class ids | S2 runner + S4 online gate + S6 doctor | **compiled v0.9.1** — owner: fix as eval-suite work, not product SOP change |
| **FIND-027** | **Live score artifact binding = final rendered message / product `score_card`** — online `header_length_ok`/`has_body`/format metrics must not score raw multi-line model dumps/JSON; dual authorities on different strings forbidden; prefer export of product deterministic card | Explains near-zero live format scores with healthy acceptance without blaming Hybrid law; restores metric truth | F1 final-artifact law already requires this | Migration: temporary disable unbound cloud rules | S2 wrap product checks · S3 bind final bytes · S4 export card | **compiled v0.9.1** |
| **FIND-028** | **Prompt/cloud drift without local suite pin is doctor-red** — cloud prompt version churn (e.g. 45 versions) without local `prompt_pack` pin + suite/snapshot result is process failure; Opik experiments optional mirror only | Closes “unvalidated prompt” briefing gap without making cloud experiments SoT | F5 pins / INT-26 | Teams ignoring doctor | S6 doctor + S7 docs | **compiled v0.9.1** |


**v0.9.0 finding dispositions:**

| ID | Disposition |
|:---|:---|
| FIND-019 | Family I + topology schemas; S0–S3/S6 |
| FIND-020 | S6 debug CLI loop; no Ollie dependency |
| FIND-021 | `diag_issue_v1` + fingerprints; S6 |
| FIND-022 | config/modes/flush; S4/S6 |
| FIND-023 | replay compare; S6 |
| FIND-024 | split_group_id law; S1/S6 |
| FIND-025 | §5.7 reference matrix; S7 maintain |
| FIND-026 | Empty/oversize precondition + anti-fan-out; S2/S4/S6 |
| FIND-027 | Live artifact bind to final message / product score_card; S2–S4 |
| FIND-028 | Prompt drift without local suite pin → doctor-red; S6/S7 |

**v0.9.3 S2b T1–T12 dispositions (#227):**

| ID | Disposition |
|:---|:---|
| T1 | Requested C/E/F/G already veto. Removing `c.`/`e.`/`f.`/`g.` from `_IGNORE_FAMILY_PREFIXES` fixes stale advisory labeling of unrequested failures only. |
| T2 | C/D dual emission from shared evidence/`GoldReport` is required. No second gold scan; no double-count. |
| T3 | Empty/oversize skips message-dependent families including mapped D. Never mint empty-input `d.strict_fail_set` pass. |
| T4 | C = `evaluate_presentation_gates`; E = `evaluate_presentation_guards`. No third presentation authority. |
| T5 | Deterministic opt-in S2b block tuple = 68 catalog-derived IDs. Warn/info excluded by default. |
| T6 | Keep `gate.semantic_cohort_eligible=False`. C is not C′. |
| T7 | Frozen catalog count is **137** by `family` field. Naive first-letter counting is invalid. |
| T8 | Absorb/demote/delete `scripts/opik_metrics.py` and `tests/test_opik_metrics.py` together. Survivor is advisory-only and outside scoring/CI/gates. |
| T9 | Local final-message-only secret-shape helper. No `git_cg.secrets` / vault / env discovery. |
| T10 | `g.no_eval_policy_fork` is a non-vacuous source/import-surface self-check. |
| T11 | Shared `GoldReport` API or runner-owned slot. Exactly one gold call per evaluable case. F consumes D. |
| T12 | Family I validators/emitters and `suite.require_topology=true` stay S2c/S3. Not #227 close-bar. |

---

## 18. #217 comment-depth contracts (v0.9.0)

> Implementation-facing expansion of INT-01…45. **Authority floor F0–F9 still wins.** This section does not grant Opik, Ollie, or optimizers product law.

### 18.1 Historical supersession (INT-34)

| Pre-R11–R14 comment idea | Superseded by |
|:---|:---|
| Regen-only thread semantics | R13 full commit-session thread + optional subchain (§2.9) |
| Opik as pure mirror-only forever | R14 owner corpus-lake **role**; local remains SoT |
| Blanket raw body/diff denial | R14 redaction ladder (`public_ci` → `train_rich` / `antipattern_vault`) |
| Semantic evaluation only on deterministic-pass rows | Separate semantic eligibility from corpus capture; failing hard negatives may be retained (`capture_on`) |
| Playground / optimizer / Ollie as control plane | Rejected (F8); retain local/pattern semantics only |
| Opaque LLM diagnostics or clustering | Deterministic fingerprints + explain (§18.3–18.4) |
| #217 body “regen/accept chains only” thread wording | R13 full commit-session thread + optional subchain (§2.9) |
| #217 body absolute thin export / no-body vibe | R14 owner ladder; ambient/basic/CI stay thin |
| #217 body “Opik mirror/compare only” forever | Dual purpose: mirror **+** owner corpus lake; local remains SoT |
| #217 body “this issue body is the design SSOT” | This plan file is living design/implementation SSOT; body = governance index |
| #217 body old follow-up title list (mixed emoji) | §8.8 formal `eval(S0)…` / `docs(S7)…` titles |

### 18.2 Operator E-LOOP SOP (INT-27)

```text
CAPTURE/OBSERVE → LOCAL SCORE → EXPLAIN/DIAGNOSE → PROMOTE/LABEL → SUITE RUN → optional MIRROR → AMEND-BRIEF/REVIEW → RESOLVE ISSUE
```

| Surface | Authority |
|:---|:---|
| Local suite + Families A–I | **Eval/CI law** |
| Local dataset snapshot | **Corpus SoT** |
| Local experiment record | Run provenance |
| Opik project/experiment UI | Projection / lake UX only |
| Human review queue | Advisory; never sole golden |
| Ollie / Playground / Optimizer | **Non-authority** |

### 18.3 Debug loop & explain contract (FIND-020 / INT-05,06,18)

**Loop:** `FIND → EXPLAIN → COMPARE → REPLAY → PROMOTE → VERIFY`.

| Command | Contract |
|:---|:---|
| `git-cg eval failures` | List failing bundles/cases with metric_ids + failure_ids |
| `git-cg eval explain <bundle\|trace>` | Emit: ids (thread/trace/bundle), artifact_class, result classes, first divergent/blame span, failure_ids, prevention_ids, path/gold/counter consistency, export state, static suggested surfaces, exact replay command, bundle path |
| `git-cg eval compare <a> <b>` | Structural + metric delta; prefer `replay_compare_v1` when lineage-linked |
| `git-cg eval replay <bundle>` | New trace/bundle; retain session thread; pin harness/catalog/prompt/model/dataset; never mutate source |
| `git-cg eval promote <bundle>` | Promotion state machine §18.8 |
| `git-cg eval suite run …` | Existing suite runner; AGG-GATE: show per-item hard fails |

**Forbidden in explain:** opaque LLM RCA identity, automatic code edits, automatic rule changes, requiring Ollie.

**Report headers (INT-29):** project_lane, environment, session_thread_id, trace_id, export_status, redaction_profile, schema_pack hash, metric_catalog hash, harness_version.

**Local dirs:** `.eval/index/`, `.eval/diagnostics/`, `.eval/issues/`, `.eval/replays/`, `.eval/export_queue/`, `.eval/bundles/`.

### 18.4 Diagnostics & blame map (FIND-021 / INT-07,08,36)

Commands: `eval diagnose`, `eval issue list|show|resolve|reopen|suppress`.  
Schema: `diag_issue_v1` (§7.2.13).

**Static blame_span → code-surface map (initial):**

| blame_span | Suggested surfaces |
|:---|:---|
| `diff_extraction` | diff collect / file summary modules |
| `path_classification` | path-class gate / intent path features |
| `intent_ranking` | `intent.py` / SOP ranker |
| `contract_resolution` | semantic contract selection |
| `llm_generation` | AI client / prompts / instructor |
| `plan_normalisation` | plan normaliser |
| `gold_evaluation` | `commit_gold` / gold report |
| `presentation_guard` | Hybrid/render guards |
| `regeneration` | regen loop / counters |
| `fallback` | skeleton/fallback paths |
| `final_render` | commit message render |
| `accept_path_finalization` | hooks / COMMIT_EDITMSG bind |
| `opik_export` | eval export / config |

### 18.5 Config & flush (FIND-022) / durability (INT-16,17,19)

See §10.6–10.7 and `git_cg_opik_config_v1`.  
**Never** block product accept on export.  
**Always** durable Layer A before mirror attempt when mode ∈ {mirror, strict_mirror, local_only capture}.

### 18.6 Score placement & METRIC-SPLIT (INT-13,45)

See §6.1b and §6.13/6.13b.  
Builtin inventory is managed as: **law local wrappers** vs **advisory C′/lab** vs **reject-as-law** (SOC/Halu/Moderation/GEval alone). Full vendor list remains §5.3 maps; polarity must be remapped before dashboard merge.

### 18.7 Two-layer durability (repeat summary)

Layer A local bundle = SoT. Layer B SDK/cloud = secondary. Export health enums must distinguish: `skipped_off`, `deferred`, `pending`, `success`, `config_error`, `auth_error`, `network_error`, `timeout`, `partial`, `replay_needed`.

### 18.8 Promotion state machine (INT-20,44)

```text
failure_or_capture
  → scrubbed_candidate
  → { fixture_lane_a | hard_negative | preference_pair | observability_fixture | quarantine | reject }
```

**Required on promote:** provenance, source bundle/thread/trace, owner, label, destination, redaction profile, contamination check (`split_group_id`), schema validation.  
**Forbidden:** silent gold mint from production accept; promote-by-popularity; Expand-with-AI synthetic rows without quarantine (INT-44).

### 18.9 AGG-GATE & experiment pins (INT-23,24)

Experiment aggregates = dashboards only.  
Per-item hard fails remain visible/binding.  
Pins required: schema pack, metric catalog, dataset/version hash, prompt pack, model/temp/rubric, graph version, git SHA, redaction profile.  
**Reject** unpinned `latest`.

### 18.10 Worked topology failure — APC Session-12 class (INT-31)

**Symptom:** product counters say `gold_regen_attempts > 0` but span tree lacks `regeneration` children; or final message bound without `accept_path_finalization`.  
**Expect:** `i.counter_span_consistent=0` and/or `i.finalization_observed=0` → eval fail → not golden-eligible; `eval explain` blames `regeneration` or `accept_path_finalization`; fingerprint clusters under those failure_ids; promote-to-observability-fixture allowed; product Hybrid pass still possible if message bytes valid (incomplete evidence ≠ prose fail).

### 18.11 Explicit non-import & Without-Ollie box (INT-35,37,41,42)

**Do not import as product/control-plane authority:**
* Ollie auto-fix or required diagnostics
* Agent/Prompt Playground as runtime SoT
* Optimizer Studio ship authority
* Unpinned cloud prompt `latest`
* Web UI annotation silently rewriting historical local scores
* Framework auto-tracers replacing declared graph (may *augment* later only under pin)

**Without-Ollie boundary (agent-facing):**  
Agents must RCA via local bundles, Family I, fingerprints, and git-pinned prompts/tests. External assistants may *read* exported traces if owner opts in; they must not be a dependency of `git-cg eval` success.

### 18.12 Parked non-MVP (INT-39,40,43)

| Item | Notes |
|:---|:---|
| Local experiment CLI matrix (variant×suite) | Nice-to-have after S6 core |
| Headless `opik endpoint` | Optional later; never required |
| Fingerprint webhooks/alerts | Notification-only; never gate |
| Optimizer algorithms under git pin | Only after metrics stable; ship via PR + green suite |

### 18.13 Live Opik Daily Briefing incident locks (v0.9.1 / FIND-026…028)

> **Owner read (2026-08-13):** symptoms are **most likely incorrect live Opik configuration / wrong scored artifact**, not a core `git-cg` Hybrid/SOP defect. They are fixed **as evaluation-suite slices land** (S2–S6), not by relaxing product law from SaaS narrative.

#### 18.13.1 Evidence snapshot (non-authoritative)

| Field | Briefing claim (as reported) |
|:---|:---|
| Window | ~7-day Daily Briefing; captured into plan 2026-08-13 |
| Activity | ~30,209 traces; ~1,292 errors (~4.3%); 10 threads; last trace “today” |
| Latency claimed | p50 ~0.18ms / p90 ~4.91ms / p99 ~700ms — treat as **span-mix suspicious**, not generation truth |
| Tokens claimed | ~9.5k avg/trace; cost tracking not configured |
| Critical | Empty/`data must not be empty` across **5** automation evaluators → **5× error multiplier** |
| Critical | `header_length_ok` ~3.3%, `has_body` ~0.1% on **raw output** (465–60k chars treated as header) |
| Secondary | Format Compliance **504** on ~60k-char outputs with retry storms |
| Process | Prompt `git_cg_system_prompt` ~45 cloud versions; **no experiment ~49 days**; dataset ~9 items |
| Gap | `user_acceptance` ~87.8% vs format-ish scores ~50% / near-zero header/body |

**Explicitly non-authority:** this table does not set thresholds, promote golden, or amend Hybrid/SOP.

#### 18.13.2 Diagnosis class

| Briefing symptom | Plan diagnosis | Product SOP change? |
|:---|:---|:---:|
| 5× evaluator errors on empty output | Missing precondition + fan-out anti-pattern (FIND-026) | **No** |
| Near-zero `header_length_ok` / `has_body` | Online metrics score **wrong artifact** (raw blob ≠ final Hybrid message / product card) (FIND-027) | **No** (not from this evidence) |
| Acceptance ≫ format | Likely binding/edit/final-bytes mismatch and/or false format fails (INT-48) | **Not yet** — investigate binding first |
| 504 on huge outputs | LLM format judges on oversized unevaluable payloads (FIND-026) | **No** |
| 45 prompt versions / stale experiments | Cloud drift without local suite pin (FIND-028); experiments are mirrors not SoT | **No** cloud-SoT restore |
| `ranking_override` low | Polarity/metadata foot-gun risk (INT-14) until catalog remap verified | **No** quality panic |

#### 18.13.3 Normative locks

1. **EMPTY-OUT / ERR-FANOUT (FIND-026, INT-46)**  
   Before any evaluator/judge family runs on a row:
   * if scored artifact empty/missing → emit **exactly one** classified failure/skip (`eval_input_empty` / `h.eval_input_nonempty=0`);
   * **do not** invoke remaining K evaluators such that one row becomes K identical exceptions;
   * record health once on the evaluation record / `opik_export` adjacency — never as Hybrid prose fail solely from empty export residue.

2. **OVERSIZE-EVAL-GUARD (FIND-026, INT-49)**  
   * Enforce max bytes for LLM judges; on oversize → `unevaluable_oversized` (classified), no 3× 504 retry storm;
   * Deterministic local wrappers may still score a parsed final message if within their own bounds.

3. **ARTIFACT-BIND-LIVE (FIND-027, INT-47/51)**  
   * Default scored artifact for format/Hybrid wrappers = **final rendered accept-path message bytes** (or fixture expected final message), not raw model JSON / instructor dump / concatenated thread text;
   * Prefer publishing product `DeterministicScoreCard` / `run_deterministic_checks` results as feedback scores over re-deriving divergent definitions in cloud automation;
   * `header_length_ok` measures the **Hybrid subject/header line** (≤72), not the entire multi-line payload;
   * `has_body` measures presence of body/trailer structure on the **parsed final message**, not “raw output has newlines somewhere in a JSON blob”;
   * If an online rule cannot bind that artifact, it must be **disabled or lab-only** until fixed — dual authorities on different strings are forbidden on bound export lanes.

4. **ACCEPT-GAP-NO-SOP-RELAX (INT-48)**  
   * `user_acceptance` ≫ online format is a **binding investigation trigger**, not a licence to weaken 72-char/body/trailer SOP;
   * Only after final-message metrics are honest may product thresholds be revisited via normal SOP/governance change.

5. **PROMPT-DRIFT-WITHOUT-SUITE (FIND-028, INT-50)**  
   * Runtime authority remains repo `prompt_pack_v1` + content hash;
   * Cloud prompt library versions are mirrors; `eval doctor` / `opik doctor` **warns or fails** when pack identity changed without local suite/snapshot result pin;
   * Optional Opik experiment runs may mirror local suites — they do **not** replace them;
   * “No cloud experiment for N days” alone is not product-red if local suites are green and pinned.

6. **Migration posture (live project)**  
   Until S2–S4 guards ship, operators **should gate/disable** unbound automation evaluators that score raw empty/huge outputs, rather than treating their error rate as commit-quality truth.

#### 18.13.4 Slice ownership

| Lock | Primary slices |
|:---|:---|
| EMPTY-OUT / fan-out / oversize | S2 runner, S4 online gate, S5 judge entry, S6 doctor |
| Artifact bind + product card export | S2 wrappers, S3 final-bytes bind, S4 feedback publish |
| Acceptance gap investigation UX | S6 explain/doctor, S7 docs |
| Prompt drift doctor | S6 doctor, S7 prompt-pack docs, INT-26 |

#### 18.13.5 Worked false-red pattern (header/body)

```text
trace.output = "<json or multi-line model dump 465..60000 chars>"
online.header_length_ok(output) → fail  // WRONG artifact
online.has_body(output) → fail          // WRONG parser

// Required:
final = bind_final_message(trace) or product_render(plan)  // COMMIT_EDITMSG bytes class
header = first_subject_line(final)
body = section_after_blank(final) + trailers
header_length_ok = len(header) <= 72    // same spirit as telemetry.run_deterministic_checks
has_body = message_has_body_or_trailers(final)
// OR simply export product score_card.header_length_ok / structured equivalents
```

---

### 18.14 #217 body residual compilation (v0.9.2)

> Completes the body→plan gap left after comment-depth ingest. Does **not** re-open body as competing SSOT.

| Body residual | Plan home | Relaxation applied |
|:---|:---|:---|
| Scaffold insufficiency table | §9.0 | none — still true until S2–S6 absorb scripts |
| Regime A/B teaching + Instance A≠B | §7.4.1 | none |
| Session-12 seven-gap seed list | §7.4.4 | gap 6 hook isolation = historical/shipped |
| Provenance enum | §7.4.2 / glossary | unbound kept; train/thread labels additive |
| F-\* / P-\* namespaces | §7.4.3 | none |
| What good looks like | §1.6 | #9 dual-axis train richness added |
| Experiment naming + ≤4MB batches | §7.3.2 / S4 | 4MB = default ceiling |
| `GOLD_SKELETON_FALLBACK_FINAL` non-weaken | §2.1 / §3.3 / Family D | **not** relaxed |
| `cm-eval-*` dataset names | §7.3.2 aliases | short ids remain stable |
| Task modes fixture_offline / acceptpath_bound / live_regen | §9.0 + suite modes | live_regen opt-in only |
| Evaluator errors → Sentry only | §10.1.3 | none |
| Body-era thin export / regen-only thread / body=SSOT | §18.1 | R13/R14/dual-axis / plan-wins |

**Conflict rule:** `docs/plans/opik-evaluation-harness.md` (this file) wins over the #217 GitHub body on design detail. The body must point here by path + version.

---

*End of v0.9.5-s5-s6-s7-api-surface — S5/S6/S7 API-surface policy locked (CLI-first public API; selected `git_cg.eval*` supported; internals internal; S5 narrow export; S6 operator API map + help alignment; S7 Zensical/ADR durable docs + optional allowlist autodoc). Prior v0.9.4 S5 eligibility/availability split + v0.9.3 S2b locks + v0.9.2 body residual + v0.9.1 briefing locks + v0.9.0 comment-depth remain locked. Post-S4 `main` (`v0.20.0`) is the contract base; implement S5 from #233 without SDK-scope creep.*

