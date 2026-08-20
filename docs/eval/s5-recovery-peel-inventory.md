# S5 recovery peel inventory (D43) — Slice 0

> **Issue:** [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233)  
> **Tip evidence:** `backup/s5c-tip-c59b790` @ `c59b790`  
> **Contract base:** post-S4 `main` (`v0.20.0` @ `db8e93b`)  
> **Decision:** **peel** Lane C pack/tests/prompts/ideas onto post-S4 law — **not** rewrite-from-scratch, **not** wholesale tip reset.

## Package home

Confirmed: `src/git_cg/eval/lane_c/` (D23). No permanent dual home.

## TAKE (candidate peel surfaces)

| Path | Note |
|:---|:---|
| `src/git_cg/eval/lane_c/**` | eligibility / prompt_pack / judge / runner skeleton — rework to current issue law before merge |
| `prompts/eval/lane_c/geval_craft/rubric.md` | pinned craft rubric candidate |
| `prompts/eval/lane_c/geval_relevance/rubric.md` | pinned relevance rubric candidate |
| `tests/eval/test_lane_c.py` | eligibility + runner tests — rewrite against C-* contracts |
| `tests/eval/test_lane_c_prompt_pack.py` | pack identity tests |
| `tests/eval/test_lane_c_judge.py` | judge seam tests |
| `schemas/eval/prompt_pack_v1.schema.json` | take only if compatible with live schema-pack generator |
| `schemas/eval/judge_meta_eval_v1.schema.json` | **Shipped** R2 lab envelope (Slice 6; not product gate) |

## REFUSE

| Surface | Why |
|:---|:---|
| Tip CLI export commands / pre-S4 mirror code | Must not regress shipped S4 (`v0.20.0`) |
| Wholesale cherry-pick/reset of tip history | D43 — historical tip is not law without PR review |
| Dual package homes / cloud-latest pins | D23 / F5 |
| Pre-S4 accept-path or ranking changes | Out of S5 scope |

## Legacy scripts (freeze approach — feeds Slice 6/7)

| Script | Slice 0 disposition | Slice 6 status |
|:---|:---|:---|
| `scripts/setup_opik_eval_rule.py` | Freeze header / docs-only minimum with spine docs (D24); never accept-path authority | **Frozen** fail-closed pointer (D24 / S5-G05) |
| `scripts/setup_opik_test_suites.py` | Freeze header / docs-only minimum with spine docs (D24) | **Frozen** fail-closed pointer (D24 / S5-G05) |
| `scripts/compile_opik_dataset.py` | Already retired (S4); leave retired | Unchanged retired |
| `scripts/opik_metrics.py` / `scripts/eval_commit_message.py` | Not C′ law; do not revive as spine authority | **Frozen** fail-closed pointers (non-authority) |

Machine-checkable freeze tests: `tests/eval/mirror/test_setup_opik_scripts_absorption.py`.

Machine-checkable baseline: [`slice0_baseline.json`](./slice0_baseline.json).
