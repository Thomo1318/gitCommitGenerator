# S5 claim evidence matrix (Slice 7 / D40 / S5-A…H)

> **Issue:** [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233)
> **Parent:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)
> **Branch package:** `src/git_cg/eval/lane_c/**`
> **Plan SSOT:** `docs/plans/opik-evaluation-harness.md` (`0.9.5-s5-s6-s7-api-surface`, retaining `0.9.4-s5-eligibility-split`)
> **Proof commands (offline):**
>
> ```bash
> uv run pytest tests/eval/test_lane_c*.py -q --no-cov
> uv run pytest tests/eval/test_lane_c*.py \
>   --cov=git_cg.eval.lane_c \
>   --cov-report=term-missing \
>   --cov-fail-under=80
> ```

This page is the **S5-A…H claim-evidence table**. Merge evidence is **composition/runner-path aware** (`run_lane_c` / `score_bundle` / `compose_gates`), not leaf helper tests alone.

## Dual-axis law (all claims)

| Axis | Invariant |
|:---|:---|
| Product accept / `gate.deterministic_pass` | Never blocked or flipped by C′ scores, missing creds, timeouts, or lab diagnostics |
| Lane C′ / evaluation health | May record eligibility false, availability skips, execution taxonomy codes, advisory rows |

## Slice → claim mapping

| Slice | Primary claims | Composition anchors |
|:---|:---|:---|
| **1** Eligibility + C-TAX | **S5-A**, taxonomy | `evaluate_semantic_cohort_eligibility`, `run_lane_c` skip paths, `compose_gates` deferred/active |
| **2** Prompt packs | **S5-B** | `build_prompt_pack` / `resolve_judge_pack` / hygiene / universe fingerprint |
| **3** Judge input | **S5-C** | `project_judge_input` final-accept + gold-blind + size guards |
| **4** Advisory + judge + runner | **S5-D**, **S5-E** | `make_advisory_score`, `run_pinned_judge`, `run_lane_c` invoke path |
| **5** Gates / immunity / H | **S5-D07**, Family H | `compose_gates` + `score_family_h_cprime` + poisoned-row tests |
| **6** Residuals | **S5-F**, **S5-G** | D28 table + script freeze absorption tests |
| **7** Docs + coverage | **S5-E03**, **S5-H** | `docs/eval/README.md` + this file + coverage report |

## Composition-path proof (merge gate spine)

```text
eligibility → availability → prompt_pack → project_judge_input
  → run_pinned_judge (injectable) → make_advisory_score
  → compose_gates (precomputed verdict only)
```

Implemented by `git_cg.eval.lane_c.runner.run_lane_c` and wired from
`git_cg.eval.scoring.runner.score_bundle` (Lane C′ opt-in, isolated try/except).

Primary composition tests:

* `tests/eval/test_lane_c.py` — eligibility/availability/runner/gates/immunity
* `tests/eval/test_lane_c_prompt_pack.py` — pack identity/hygiene/fingerprint
* `tests/eval/test_lane_c_judge_input.py` — final-accept + gold-blind
* `tests/eval/test_lane_c_advisory_score.py` — D30 emission + F01 footgun isolation
* `tests/eval/test_lane_c_judge.py` — pinned judge seam + secret-free evidence
* `tests/eval/test_family_h.py` — C′ honesty metrics when lane ran / not ran
* `tests/eval/mirror/test_setup_opik_scripts_absorption.py` — legacy script freeze

## Claims S5-A…H

### S5-A — eligibility / availability / taxonomy

| ID | Summary | Primary evidence |
|:---|:---|:---|
| **S5-A01** | Ineligible ⇒ no judge side effects | `test_lane_c.py::TestRunLaneC::test_ineligible_emits_skip_rows_advisory` |
| **S5-A02** | Eligible may invoke when available | `test_lane_c.py::TestRunLaneCInvoke::test_eligible_with_judge_scores_advisory` |
| **S5-A03** | `lab_override` diagnostic, zero side effects | `test_lane_c.py::TestRunLaneC::test_lab_override_diagnostic_zero_side_effects` |
| **S5-A04** | Eligibility true ≠ product/golden pass | `test_lane_c.py::TestComposeGatesLaneC::test_eligibility_true_does_not_pass_golden_or_det` |
| **S5-A05** | Missing creds ≠ ineligible | `test_lane_c.py::TestAvailability::*missing_key*`, `TestRunLaneC::test_missing_credentials_skip_not_ineligible` |
| **S5-A06** | Gate evidence separates eligible/invoked/scored; never `cprime_ran := eligible` | `test_eligible_available_does_not_set_cprime_ran`, `test_verdict_eligible_true_does_not_imply_cprime_ran` |
| **S5-A07** | Empty/error/unavailable leave invoked/scored honest | `test_empty_input_skips_without_invoke`, `test_without_judge_fn_remains_not_invoked` |
| **S5-A08** | Closed C-TAX skip/failure_id taxonomy | `TestTaxonomy::*`, runner skip rows |

### S5-B — prompt packs

| ID | Summary | Primary evidence |
|:---|:---|:---|
| **S5-B01** | `prompt_pack_v1` identity (id/version/hash) | `tests/eval/test_lane_c_prompt_pack.py` build/pin tests |
| **S5-B02** | latest/undated alias fail closed | `TestPins::*latest*`, `*undated*`; pack resolve fail-closed |
| **S5-B03** | Cloud cannot silently replace local pack bytes | local SoT + content-hash tests in prompt_pack suite |
| **S5-B04** | Family H pin fields coherent when C′ ran | `tests/eval/test_family_h.py::test_family_h_cprime_*` |
| **S5-B05** | Hash covers loaded bytes; strict UTF-8 decode | prompt_pack decode/hash tests |
| **S5-B06** | Hygiene rejects gold/expected / empty-score rubric | `lint_prompt_pack_hygiene` tests |
| **S5-B07** | Non-UTF-8 pack fails closed | decode-error tests in prompt_pack suite |
| **S5-B08** | Sampling/output-contract in pin identity | eligibility default pin identity + pack pin_refs |

### S5-C — judge input / gold-blind / final-accept

| ID | Summary | Primary evidence |
|:---|:---|:---|
| **S5-C01** | Ordinary input omits gold/expected/assert (recursive) | `tests/eval/test_lane_c_judge_input.py` isolation tests |
| **S5-C02** | Leak attempt fails closed | judge_input leak/reject tests |
| **S5-C03** | Injectable offline judge (no network) | `test_lane_c_judge.py` fake transport |
| **S5-C04** | Empty/oversize never fan-out | judge empty/oversize never-retry + runner empty skip |
| **S5-C05** | Final-accept linkage (class/sha/encoding) | judge_input final_accept projection tests |
| **S5-C06** | `diff_summary` allowlisted/bounded/gold-blind | `project_diff_summary` tests |
| **S5-C07** | R2 labeled path | **Deferred** (S5-F) — no ordinary label leak |
| **S5-C08** | Success `reason="scored"`; rationale evidence-only | `test_lane_c_advisory_score.py` |
| **S5-C09** | Docs/module framing is opt-in/lab, not accept-blocking | package docstring + README S5 section |

### S5-D — advisory authority + non-block

| ID | Summary | Primary evidence |
|:---|:---|:---|
| **S5-D01** | `authority=advisory` / `source=lane_c_judge` | advisory emission + runner scored rows |
| **S5-D02** | Missing creds → skip; Lane A still pass | availability + runner missing-key paths |
| **S5-D03** | Timeout/error ≠ Hybrid product fail | judge transport/timeout normalization + immunity tests |
| **S5-D04** | No required GEval CI job | README “never first CI gate”; no workflow added |
| **S5-D05** | Product path unchanged when Lane C off | offline deferred gate + BASE-3 posture |
| **S5-D06** | Continuous scores do not auto-`passed=True` | `make_advisory_score` forces `passed is None` |
| **S5-D07** | Poisoned C′ `passed=True` cannot promo/det | `test_poisoned_cprime_passed_true_cannot_veto_or_promote` |
| **S5-D08** | Secrets absent from signatures/evidence | judge credential view + outcome evidence tests |
| **S5-D09** | Scale stamped `geval_1_5` | advisory evidence `scale` |
| **S5-D10** | `compose_gates` never resolves secrets | `test_compose_gates_has_no_lane_c_import` |
| **S5-D11** | Unconditional empty/oversize host guard | judge never-retry empty/oversize |
| **S5-D12** | Universe fingerprint / no `latest` | prompt_pack fingerprint tests |
| **S5-D13** | Order: eligibility → pack missing → judge | runner disposition order tests |
| **S5-D14** | Retry classes bounded/classified | judge retry-once transport/parse; never empty |
| **S5-D15** | `slice0_baseline.json` machine baseline | `docs/eval/slice0_baseline.json` |
| **S5-D16** | Gate↔execution taxonomy mapping | `TestTaxonomy::*` |
| **S5-D17** | `score_bundle` isolates C′ exceptions | scoring runner try/except + immunity tests |

### S5-E — runner wiring + docs spine

| ID | Summary | Primary evidence |
|:---|:---|:---|
| **S5-E01** | Judge only on eligible+available path | runner invoke vs skip matrix in `test_lane_c.py` |
| **S5-E02** | Craft/relevance packs present | `prompts/eval/lane_c/geval_craft/rubric.md` and `prompts/eval/lane_c/geval_relevance/rubric.md` + pack tests |
| **S5-E03** | README advisory + FIND-007 + operator matrix | `docs/eval/README.md` § S5 |
| **S5-E04** | Offline `test_lane_c*.py` green | proof command above |
| **S5-E05** | pin_refs / duration / INT-28 nullable fields | judge outcome + advisory rows |
| **S5-E06** | Rubrics do not instruct empty scoring | hygiene + committed rubrics |
| **S5-E07** | Public export prefers `run_lane_c` | `lane_c/__init__.py` supported API docs |
| **S5-E08** | Import lane_c does not load openai | `test_import_lane_c_does_not_import_openai` |
| **S5-E09** | Structured transport retains usage metadata path | `JudgeTransportResult` + outcome evidence tests |

### S5-F — R2 meta-eval residual

| ID | Summary | Disposition / evidence |
|:---|:---|:---|
| **S5-F01** | `judge_meta_eval_v1` path | **Deferred** on #233 (named future lab home) |
| **S5-F02** | Equals label non-leak | N/A until R2 ships; ordinary path already gold-blind (S5-C01/C02) |
| **S5-F03** | FP/FN lab-only | Deferred with R2 |
| **S5-F04** | Deferral visible | #233 D28 residual table + README S5 residuals |

### S5-G — other residuals + board hygiene

| ID | Summary | Disposition / evidence |
|:---|:---|:---|
| **S5-G01** | R1/R6/R8/R10/R5/scripts/H | R1/R6/R8/R10 deferred w/ home; R5 N/A; scripts frozen; H shipped |
| **S5-G02** | PR links #233 + #217 + claim evidence | this file + PR body (Slice 7) |
| **S5-G03** | Closes #233 only | PR trailer policy |
| **S5-G04** | Deferrals name future home | #233 D28 + README residuals |
| **S5-G05** | Legacy scripts frozen | `tests/eval/mirror/test_setup_opik_scripts_absorption.py` |

### S5-H — coverage & public API quality

| ID | Summary | Evidence |
|:---|:---|:---|
| **S5-H01** | ≥80% coverage on `git_cg.eval.lane_c` | scoped coverage command (below) |
| **S5-H02** | Public API docstring idiom | package/module docstrings on `lane_c/**` |
| **S5-H03** | Supported export = gated runner | `__init__.py` + README supported surface |
| **S5-H04** | Coverage summarized on PR | this section + PR body |

## BASE-2 reconfirmation (Slice 7)

| Anchor | Current law | Evidence |
|:---|:---|:---|
| Deferred offline gate | `reason=semantic_cohort_deferred_offline_later_lane`, `GATE_SEMANTIC_COHORT_DEFERRED`, evidence `offline_lane_ab` + `semantic_cohort_not_evaluated` (**not** active-path `offline_s2b`) | `src/git_cg/eval/scoring/gates.py` `_compose_semantic_cohort_gate`; `test_offline_default_deferred_honest_vocabulary`; `assert "offline_s2b" not in …` |
| Active path | Precomputed eligibility/run evidence; `cprime_ran` from invoked∧scored only | gates + `run_lane_c` |
| `make_score` F01 footgun | Untouched on non-C′ paths; C′ uses `make_advisory_score` | `test_make_score_footgun_still_exists` + advisory tests |
| BindResult fields | Consumes `final_message_sha256`, `artifact_class`, `session_thread_id`, `meta.final_message_encoding`; **no** invented `bundle_id` | `judge_input.py` `JudgeInput` / projection |

## Coverage report (D40 / S5-H)

Recorded **2026-08-20** on branch `evals/233-s5-gated-lane-c-cohort-optional-judge-lab`.

```text
COMMAND:
uv run pytest tests/eval/test_lane_c*.py \
  --cov=git_cg.eval.lane_c \
  --cov-report=term-missing \
  --cov-fail-under=80

RESULT: 171 passed · Required 80% reached · Total coverage: 86.06%

Name                                     Stmts   Miss Branch BrPart  Cover
src/git_cg/eval/lane_c/advisory.py          86      2     30      2    97%
src/git_cg/eval/lane_c/availability.py      65      5     16      1    93%
src/git_cg/eval/lane_c/eligibility.py      113      3     38      3    96%
src/git_cg/eval/lane_c/judge.py            226     62     64     14    68%
src/git_cg/eval/lane_c/judge_input.py      220     26    118     23    86%
src/git_cg/eval/lane_c/prompt_pack.py      185     13     68      9    91%
src/git_cg/eval/lane_c/runner.py           209     22     82     13    88%
src/git_cg/eval/lane_c/taxonomy.py          84      9     14      2    87%
TOTAL                                     1198    142    430     67    86%

Notes:
* `judge.py` is the lowest module (68%) — live transport factory paths remain
  intentionally thin under offline injectable seams; overall package floor met.
* One file skipped due to complete coverage (`__init__.py` re-exports).
```

## PR close pack (checklist paste)

* Links **#233** + parent **#217**; does **not** close #217 / #216 / #231 / #232
* Trailers: **Closes #233 only**; `Refs: #217`
* Never first CI gate · advisory authority · gold-blind default · authz≠creds · final_accept linkage · no auto-`passed` C′ · `reason="scored"`
* Claims S5-A…H evidence summarized (this file)
* I1–I12 non-violation restated
* Deferred: R2/R1/R6/R8/R10 lab residuals; S6 doctor/amend-brief/review-queue; S7 ADR/Zensical API docs
* Coverage ≥80% on `git_cg.eval.lane_c` recorded
* Plan SSOT `0.9.5` (with retained `0.9.4` S5 locks) included in the S5 PR

## Explicitly not evidenced here

* Live network dogfood against a provider (operator-only)
* Full `git-cg eval` doctor / amend-brief / review-queue (S6)
* ADR-0011 rewrite / full Zensical API site (S7)
* R2 Equals meta-eval implementation (deferred residual)
