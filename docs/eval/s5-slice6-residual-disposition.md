# S5 Slice 6 — residual disposition board (#233 / D28)

> **Authority:** GitHub issue [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233) remains the living checkbox board.
> This note is the **named follow-up home** for deferred residuals so dispositions are not chat-only (S5-F04 / S5-G04).

**Date:** 2026-08-20  
**Branch:** `evals/233-s5-gated-lane-c-cohort-optional-judge-lab`  
**Slice 5:** Family H C′ honesty metrics shipped (D39).  
**Slice 6 exit rule:** each residual shipped **or** explicitly deferred with owner-visible home (never silent-drop).

## Disposition table

| Residual | Disposition | Evidence / home | Notes |
|:---|:---|:---|:---|
| **NTH-H / Family H C′ metrics** | **Shipped** (Slice 5) | `src/git_cg/eval/scoring/family_h.py`, Lane C evidence, tests | `h.judge_input_isolated`, `h.prompt_pack_pinned`, `h.prompt_pack_hash_known`, `h.prompt_pack_suite_fresh` |
| **Script freeze / adapters (D24 / S5-G05)** | **Shipped** (Slice 6) | `scripts/setup_opik_eval_rule.py`, `scripts/setup_opik_test_suites.py`, `scripts/eval_commit_message.py`, `scripts/opik_metrics.py` + `tests/eval/mirror/test_setup_opik_scripts_absorption.py` | Fail-closed pointers; never accept-path/CI/package authority. `compile_opik_dataset.py` already retired in S4. |
| **R2 / C-R2 / NTH-R2** `judge_meta_eval_v1` | **Deferred** | Schema retained: `schemas/eval/judge_meta_eval_v1.schema.json`. Follow-up home: this note + #233 D28 row. | DEFER OK (D15). No calibration pretence. Labels must never enter ordinary `judge_input`. Future: minimal offline Equals skeleton under lab authority only. |
| **R1 / NTH-R1** richer rubric flags | **Deferred** | Catalog IDs remain advisory off-by-default (`cprime.usefulness`, `cprime.answer_relevance`, …). Home: #233 D28 + this note. | DEFER OK (D14). Spine remains pinned GEval craft/relevance subset only. |
| **R8 / NTH-R8** flakiness hooks | **Deferred** | Catalog `cprime.flakiness_std` remains lab. Home: #233 D28 + this note. | DEFER OK (D17). Lab-only; cannot alone pass product/golden. |
| **R10 / NTH-R10** NLP diagnostics | **Deferred** | Catalog `nlp.*` remains diagnostic/lab. Home: #233 D28 + this note. | DEFER OK (D18). Never Hybrid/gold/path-class law. |
| **R6 / NTH-R6** moderation ops | **Deferred** | Catalog `ops.moderation_flag` / `ops.compliance_risk` remain ops off-by-default. Coord plane: [#219](https://github.com/Thomo1318/gitCommitGenerator/issues/219) (Promptfoo/red-team) — S5 owns scrubbed ops signal only, no Promptfoo implementation. | DEFER OK (D16). Not default cohort; scrubbed; not Hybrid blocker. |
| **R5 / NTH-R5** dirty-overlay provenance | **N/A** (defer) | No committed `.eval/overlays/` content and no suite on base branch referencing dirty-overlay provenance (D19 existence test). | DEFER OK / N/A. If overlays appear later, stamp dirty provenance and keep off accept-path/hooks/CI green. |

## Explicit non-claims

* Deferred residuals are **not** implemented calibration, moderation, NLP law, or flakiness gates.
* Script freezes do **not** remove historical files; they refuse closed and point at library SoT.
* Full maintainer dogfood UX / doctor / amend-brief remains **S6 product UX out of scope** for this S5 issue close bar (`NTH-S6-*`).
* Coverage floors (D40), README operator matrix, and plan SSOT merge remain **Slice 7** close items.

## Verification (Slice 6 script freeze)

```bash
uv run pytest tests/eval/mirror/test_setup_opik_scripts_absorption.py -q \
  -p no:cacheprovider --no-cov -o addopts=''
```
