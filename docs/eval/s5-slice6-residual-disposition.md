# S5 Slice 6 — residual disposition board (#233 / D28)

> **Authority:** GitHub issue [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233) remains the living checkbox board for **Slice 6 R\*** completion.
> **S8 home:** [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235) holds **unallocated** S3/S4 hygiene + leftover NTH polish only.
> This note is the **named follow-up / evidence home** so dispositions are not chat-only (S5-F04 / S5-G04).

**Date:** 2026-08-20  
**Branch:** `evals/233-s5-gated-lane-c-cohort-optional-judge-lab`  
**Slice 5:** Family H C′ honesty metrics shipped (D39).  
**Slice 6 exit rule:** each R\* residual is **shipped** on #233 (R5 may be explicit N/A with activation criterion). **Do not defer R1/R2/R6/R8/R10 to S8.**

## Disposition table

| Residual | Disposition | Evidence / home | Notes |
|:---|:---|:---|:---|
| **NTH-H / Family H C′ metrics** | **Shipped** (Slice 5) | `src/git_cg/eval/scoring/family_h.py`, Lane C evidence, tests | `h.judge_input_isolated`, `h.prompt_pack_pinned`, `h.prompt_pack_hash_known`, `h.prompt_pack_suite_fresh` |
| **Script freeze / adapters (D24 / S5-G05)** | **Shipped** (Slice 6) | `scripts/setup_opik_eval_rule.py`, `scripts/setup_opik_test_suites.py`, `scripts/eval_commit_message.py`, `scripts/opik_metrics.py` + `tests/eval/mirror/test_setup_opik_scripts_absorption.py` | Fail-closed pointers; never accept-path/CI/package authority. `compile_opik_dataset.py` already retired in S4. |
| **R2 / C-R2 / NTH-R2** `judge_meta_eval_v1` | **Shipped** | `src/git_cg/eval/lane_c/meta_eval.py`; schema `schemas/eval/judge_meta_eval_v1.schema.json`; fixture `tests/eval/fixtures/judge_meta_eval.good.json`; tests `tests/eval/test_lane_c_residuals.py` (R2). | Lab-only offline Equals + FP/FN. Labels never enter ordinary `judge_input`. Rows `authority=lab`, `passed=None`, non-gating. Never product/golden gate. |
| **R1 / NTH-R1** richer rubric flags | **Shipped** | `resolve_richer_rubric_metrics` in `lane_c/diagnostics.py`; `run_lane_c(..., richer_rubrics=)`; catalog IDs off-by-default. Tests: residual R1. | Default spine remains craft/relevance; explicit empty `metric_ids` never expands to all R1 (D13). |
| **R8 / NTH-R8** flakiness hooks | **Shipped** | `measure_flakiness` → `cprime.flakiness_std` (injectable/offline judge). Tests: residual R8. | Lab/advisory; `passed=None`; cannot alone pass product/golden. |
| **R10 / NTH-R10** NLP diagnostics | **Shipped** | `compute_nlp_diagnostics` (`nlp.levenshtein`/`bleu`/`rouge`/`bertscore`). Tests: residual R10. | Lab/diagnostic only; BERTScore honest skip when unavailable. Never Hybrid/gold/path-class law. |
| **R6 / NTH-R6** moderation ops | **Shipped** | `evaluate_moderation_ops` → scrubbed `ops.moderation_flag` / `ops.compliance_risk` (off-by-default). Coord plane: [#219](https://github.com/Thomo1318/gitCommitGenerator/issues/219). Tests: residual R6. | Scrubbed ops signal only; **no** Promptfoo implementation; `ops.*` never gate-vetoes. |
| **R5 / NTH-R5** dirty-overlay provenance | **Shipped guard / content N/A** | `src/git_cg/eval/lane_c/provenance.py` (`activate_dirty_overlay`, `overlays_exist_in_tree`). Tests: residual R5. | Activation requires `lab_only=True`; rejects accept/CI/hooks. Existence criterion: no committed `.eval/overlays/` today → content N/A; if overlays appear, stamp dirty provenance only (no raw export). |
| **Unallocated S3/S4 hygiene + non-R\* NTH polish** | **Moved to S8** | [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235) | Absorption tracker only; not a substitute for Slice 6 R\* completion. |

## Explicit non-claims

* Completing Slice 6 R\* does **not** make lab/judge/flakiness/NLP/moderation into product Hybrid or first CI/golden gates.
* Script freezes do **not** remove historical files; they refuse closed and point at library SoT.
* Full maintainer dogfood UX / doctor / amend-brief remains **S6 product UX** on #217 (`NTH-S6-*`).
* ADR/catalog authority rewrite remains **S7** on #217.
* S8/#235 is **not** the owner of R1/R2/R5/R6/R8/R10.

## Verification (Slice 6 script freeze already shipped)

```bash
uv run pytest tests/eval/mirror/test_setup_opik_scripts_absorption.py -q \
  -p no:cacheprovider --no-cov -o addopts=''
```

## Future verification (as each R\* lands)

```bash
# extend with targeted modules as implemented
uv run pytest tests/eval/test_lane_c*.py -q -p no:cacheprovider --no-cov -o addopts=''
```
