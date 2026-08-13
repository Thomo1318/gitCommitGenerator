# CASE — Session 12 · G2 residual close-out (Regime B)

> **Status:** active / full  
> **Copy lineage:** promoted from [#204 comment 5213748048](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) (G2 section)  
> **Method:** [`../../METHOD.md`](../../METHOD.md)  
> **Template:** [`../../templates/CASE_TEMPLATE.md`](../../templates/CASE_TEMPLATE.md)  
> **Package version:** `1.0.0-combine`  
> **Series:** Session 12 · Session 6 residual close-out · message-only rebuild  
> **Siblings:** [`session-12.md`](./session-12.md) (G1) · [`session-12-g3.md`](./session-12-g3.md) · [`session-12-g4.md`](./session-12-g4.md) · [`session-12-synthesis.md`](./session-12-synthesis.md)  
> **Consumer:** eval harness [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) / [`docs/plans/opik-evaluation-harness.md`](../../../plans/opik-evaluation-harness.md) (`session-12-seed`)  
> **Authority:** this file is package SSOT for S12-G2. The GitHub comment is intake/archive evidence only.

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: active
issue: 204
case_id: 204-S12-G2
series_id: 204-S12
series_class: residual-close-out
regime: B
opik: bound
sources:
  - github:issue-comment:5213748048
  - git:raw:db30534
  - git:gold:f5e55b7
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** MISS gold · Regime **B** (clean wrong acceptance)  
**Path focus:** fixtures / corpus / goldens / harness  
**Severity:** Critical  
**Raw → gold:** `db30534` → `f5e55b7`  
**Tree preserved:** yes · tree OID `484ec724…` (message-only)  
**Branch / base→tip:** `refactor/204-commit-presentation-quality` · `2e965c5` → series gold tip `3b96ed6`  
**One-line diagnosis:** Non-product fixture/corpus pin tip ranked `validation_update` ~100.5; empty `path_class_gate` locked `fix`/`PATCH`; single LLM obeyed wrong contract; `gold_strict` zero findings — polished wrong envelope with no fallback.  
**IDs:** **F76** · **F78** · **F79** · **F80** · P-S12-4 · P-S12-6 · P-S12-8 · P-S12-9  
**Series class:** residual-close-out (Session 12 · Session 6 residual)

| Field | Value |
|:---|:---|
| Issue | #204 |
| Case ID | 204-S12-G2 |
| Reviewer | Thomo1318 / Session 12 forensic archive |
| Date | 2026-08-07 (incident) · promoted 2026-08-13 |
| Library class (intended) | fixtures/tests · TIP-G13–G17 corpus pins |
| Acceptance mode (raw) | `ai_accepted` (clean; no presentation fallback) |

### Observed subjects (do not regress)

```text
S12-G2 ❌  🦺 fix(fixtures): add TIP-G13–G17 validation goldens · PATCH · ai_accepted
S12-G2 ✅  ✅ test(fixtures): pin Session 6 corpus rows TIP-G13–G17 · NONE
```

### Package indexes

| Registry | Link |
|:---|:---|
| Failure IDs | [`../../FAILURE_TAXONOMY.md`](../../FAILURE_TAXONOMY.md) F76/F78/F79 |
| Prevention | [`../../PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) P-S12-4/6/8/9 |
| Series synthesis | [`session-12-synthesis.md`](./session-12-synthesis.md) |
| Source map | [`../../references/source-map.md`](../../references/source-map.md) |
| Method exemplar | Regime B — METHOD §4 / §13 |

---

## 1. Incident identity

| Field | Value |
|:---|:---|
| Governing issue | #204 |
| Child / slice | Session 12 · Session 6 residual close-out · G2 of 4 |
| Branch | `refactor/204-commit-presentation-quality` |
| Scope of series | multi-group residual (G1–G4); this file = G2 only |
| Planned split | G1 product laws · G2 fixtures · G3 V12-A pack · G4 docs |
| Message-only rebuild? | **yes** (tree preserved) |
| Notes | Complementary to G1: controls never fired. Not a grouping failure. |

### Rewrite map

| Role | SHA | Subject (short) | Tree OID |
|:---|:---|:---|:---|
| Git-raw | `db30534` | fix(fixtures) validation goldens / PATCH | `484ec724…` |
| Gold-final | `f5e55b7` | `test(fixtures): pin Session 6 corpus rows TIP-G13–G17` | `484ec724…` |

**Rewrite-map-confirmed:** yes (message-only; tree identical)

---

# Full-depth forensic body (promoted)

> Authoritative G2 reconstruction from comment `5213748048`. Heading levels normalised to package case style.


**Scope for this section:** G2 only. G3–G4 remain in the collapsible full analysis below until expanded to the same depth.

| Field | Value |
| --- | --- |
| Raw tip | `db30534` (`db30534227bef2d5179687f3a11d9354cf253915`) |
| Gold tip | `f5e55b7` (`f5e55b70db2b9921cee7aacfe573a4c410b23a92`) |
| Diff class | fixtures + corpus harness only |
| Paths | `tests/fixtures/commit_quality/{README.md,corpus.json,goldens.json}` · `tests/test_commit_quality_corpus.py` |
| Diff stat | 4 files · +681 / −55 |
| Gold subject | `✅ test(fixtures): pin Session 6 corpus rows TIP-G13–G17` |
| Project | `gitCommitGenerator` (`019e7e59-7caf-70a6-8756-f84a55b5d5fd`) |
| Trace | `019fdaa0-7067-75dd-be67-8cd99522b487` (`log_final_commit_telemetry`) |
| Root span | `019fdaa0-7068-7bd4-9c02-c8c8530ee7aa` (`_run_commit_generation`) |
| Window | `2026-08-07T05:09:35Z` → `05:22:50Z` (~13.3 min generation) |
| Final telemetry | `2026-08-07T05:22:58Z` |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` via `127.0.0.1` |
| Tree | Gold message-only rewrite; tree `484ec724af907e07ce860a8ddd44330fe595bcb0` preserved |

> Direct evidence from Opik final telemetry + generation spans, cross-checked against the preserved raw Git object `db30534` and gold tip `f5e55b7`. Unlike G1, Opik **did** capture the accepted `commit_plan` / `final_commit_plan` on the final telemetry span, and the raw Git tip bytes match that plan.

---

## Executive finding

S12-G2 was **not** a guard-exhaustion or fallback failure. It was a **clean wrong acceptance**.

1. Diff extraction and semantic analysis were healthy on a pure fixtures/tests surface.
2. The ranker selected `validation_update` / `fix` / `PATCH` as primary because fixture JSON text matched validation/schema signals.
3. No contract lock overrode that choice (`lock_resolution: absent`).
4. Path-class gating did not fire (`path_class_gate: empty`).
5. The model produced a coherent Hybrid-shaped message that described the work as “validation goldens” and “enforce stricter validation constraints.”
6. Gold/presentation guards did **not** fire (`hallucination_guard_fired: false`, `gold_findings_count: 0`, `gold_blocked: false`, `gold_regen_attempts: 0`).
7. Score-card checks all passed; provenance was `ai_accepted`.
8. The operator accepted the AI message without edit.
9. Gold required the opposite envelope: primary `test`, SemVer `NONE`, pin/freeze verbs, and a per-TIP inventory.

G2 is therefore the complementary failure mode to G1:

| | G1 | G2 |
| --- | --- | --- |
| Controls | Fired, then recovery destroyed quality | Never fired |
| Final path | Diagnostic fallback accepted | Clean wrong plan accepted |
| Provenance | `ai_edited_minor` | `ai_accepted` |
| Dominant miss | Fallback / process-meta / type collapse after contradiction | Path-class envelope + validation overclaim + thin TIP inventory |

---

## Identity and observed evidence

| Item | Value |
| --- | --- |
| Trace | `019fdaa0-7067-75dd-be67-8cd99522b487` |
| Root orchestration span | `019fdaa0-7068-7bd4-9c02-c8c8530ee7aa` |
| Diff span | `019fdaa0-7193-7374-8cab-65feb85d0149` |
| Semantic span | `019fdaa0-71db-7b26-bb54-cf91d3dc8cdb` |
| Prompt span | `019fdaa0-71fd-7181-bfc0-fa35fda36106` |
| Generation span | `019fdaa0-71ff-7829-84b6-ebb254f865dd` |
| LLM span | `019fdaa0-7202-7690-84a7-a341b502d4e6` |
| Final telemetry span | `019fdaac-b17e-7478-9311-41daa88c42a8` |
| Follow-on prepare hook | `019fdaac-a476-7e9e-95eb-be3b0cae0f77` (`commit_source=message` → immediate `typer.Exit(0)`) |

Generation was a **single attempt** (~176 s LLM). No retry loop. No fallback rewrite.

---

## 1. Startup contract (direct Opik)

Root input:

```json
{
  "commit_msg_file": ".git/COMMIT_EDITMSG",
  "engine": "lmlx",
  "dry_run": false,
  "verbose": true,
  "amend_regenerate": false,
  "strict": true,
  "interactive": true,
  "gui_editor": false,
  "enable_semantic": true,
  "gold_strict": true,
  "rank_arbitrate": true,
  "blueprint": null
}
```

Root output: `true` after ~795 s wall time (includes interactive accept latency after generation).

**Observation:** live write path under `gold_strict=true`. Failure is “accepted wrong envelope,” not tooling outage.

---

## 2. What the diff actually contained

Diff span `019fdaa0-7193-7374-8cab-65feb85d0149` (~21 ms) and gold/raw tree agree:

```text
tests/fixtures/commit_quality/README.md    |   7 +-
tests/fixtures/commit_quality/corpus.json  | 261 +++++++++++++++++-
tests/fixtures/commit_quality/goldens.json | 426 ++++++++++++++++++++++++++---
tests/test_commit_quality_corpus.py        |  42 +++
4 files changed, 681 insertions(+), 55 deletions(-)
```

Concrete product of the commit:

1. **Five new corpus rows:** `TIP-G13` … `TIP-G17`
2. **Matching golden snapshots** locking overlay type/SemVer/scope and `must_not_present` markers
3. **Harness extensions** in `tests/test_commit_quality_corpus.py`:
   * expected-id list extended through TIP-G17
   * Session 6 residual marker checks for mutation verbs / body templates via `evaluate_presentation_guards`
4. **README letter-map notes** documenting TIP-G13–G17 as Session 6 residuals (not A–N letter-mapped)

This is pure characterisation / fixture freeze work:

* no `src/**` product code
* no runtime enforcement surface added in this tip
* harness remains presentation-pure (no live LLM, no `rank_commit_intents`)

**No extraction failure.** The system saw fixture/test paths only.

---

## 3. Semantic analysis was successful — and misleadingly “structural”

Semantic span `019fdaa0-71db-7b26-bb54-cf91d3dc8cdb`:

```text
parser_coverage_ratio: 1.0
parser_fallback_reasons: []
body_similarity_min: 0.997661
body_similarity_avg: 0.998427
fingerprint_class_counts: {structural: 4}
risk_score: 0.5
fallback_reasons: []
```

Final telemetry also recorded fingerprint markers:

```text
runtime_logic_changed
exception_handling_added
error_handling_improved
try_except_added
new_api
new_user_facing_capability
functional_code_changed
```

and languages parsed: `json`, `markdown`, `python` (4/4 files).

**Assessment:**

* Parsing was healthy.
* Fingerprints treated fixture/test edits as structural/functional.
* Markers such as `new_api` / `new_user_facing_capability` / `runtime_logic_changed` are **false capability signals** when the only Python change is a pure test harness asserting guards on synthetic bad plans.
* This helped the ranker prefer validation/feature-like intents over `tests_update` / `snapshot_update`.

G2 is therefore partly a **semantic→signal overclaim** on test fixtures, not a parse miss.

---

## 4. Ranking vs contract (direct Opik)

From `build_system_prompt` input:

| Rank | intent_id | score | matrix type | matrix SemVer | Notable evidence |
| --- | --- | ---: | --- | --- | --- |
| 1 | `validation_update` | **100.5** | `fix` | `PATCH` | `schema_validation_changed`, `validation_added`, `validation_hardened` |
| 2 | `feature_addition` | **80.0** | `feat` | `MINOR` | `new_api`, `new_user_facing_capability` |
| 3 | `secrets_update` | 62.5 | `chore` | `PATCH` | `secret_reference_changed` |
| … | … | … | … | … | … |
| low | `snapshot_update` | 26.5 | `test` | `NONE` | *(no positive evidence listed in top set)* |
| low | `tests_update` | 26.0 | `test` | `NONE` | *(no positive evidence listed in top set)* |
| bottom | `documentation_update` | −8.5 | `docs` | `NONE` | penalised by `functional_code_changed` |

Locked/absent contract:

```text
primary_intent_id: validation_update
gitmoji: 🦺
cc_type: fix
semver_impact: PATCH
changelog_group: Changed
secondary_intent_ids: []
lock_resolution: absent
```

Also observed:

```text
staged_paths: []
claim_tags: []
concern_tags: null
gold_guidance: null
scoped_history_guidance: null
low_confidence_guidance: null
active_directives: {}
ranking_confidence_level: medium
ranking_confidence_margin: 20.5
ranking_choice_path: skipped_high_medium
ranking_override: false
path_class_gate: empty
```

**Assessment:**

* Ranker was decisive for `validation_update` (margin 20.5 over `feature_addition`).
* The correct path-class intents (`tests_update`, `snapshot_update`) scored ~26 and never competed.
* `documentation_update` was actively penalised because fingerprints claimed functional code changed.
* No contract arbitration lifted or corrected the envelope toward `test`/`NONE`.
* Empty `staged_paths` / `claim_tags` / `gold_guidance` meant the prompt never received a hard fixtures envelope or TIP-id harvest requirement.
* `path_class_gate: empty` is a direct control miss for a 4-path fixtures/tests-only diff.

---

## 5. Single generation attempt — model followed the wrong envelope faithfully

| Span | Name | Duration |
| --- | --- | --- |
| `019fdaa0-71fd-...` | `build_system_prompt` | ~1.6 ms |
| `019fdaa0-71ff-...` | `generate_commit_message` | ~176.3 s |
| `019fdaa0-7202-...` | `chat_completion_create` | ~176.3 s |

Usage: prompt 10022 / completion 3691 (reasoning 2911) / total 13713.

**Accepted plan (generation output = final telemetry `commit_plan`):**

```text
primary:
  intent_id: validation_update
  gitmoji: 🦺
  cc_type: fix
  scope: fixtures
  description: add TIP-G13–G17 validation goldens
  semver_impact: PATCH
  changelog_group: Fixed

secondary:
  - ✅ test(corpus): add corpus evaluation test harness   (NONE / Tests)
  - 📝 docs(fixtures): update README with new gate mappings (NONE / Documentation)
```

**Exact raw Git tip message (`db30534`) — byte-confirmed:**

```text
🦺 fix(fixtures): add TIP-G13–G17 validation goldens

Expands the commit quality evaluation harness with Session 6 TIP-G13–G17 cases. Updates golden outputs and corpus fixtures to enforce stricter validation constraints for telemetry, evaluator, and Sentry reporter scenarios. Includes corresponding test harness updates and README documentation to maintain traceability.

Included changes:
- ✅ test(corpus): add corpus evaluation test harness
- 📝 docs(fixtures): update README with new gate mappings

Refs: #204
SemVer-Impact: PATCH
Change-Types: fix, test, docs
Changelog-Groups: Fixed, Tests, Documentation
```

**What looked “good” to the pipeline**

* Valid Hybrid header shape
* Scope present (`fixtures`)
* Body present and grammatical
* Secondaries present
* Trailers present and internally consistent with the wrong primary
* Score card all true:
  * `header_length_ok`
  * `description_length_ok`
  * `type_valid`
  * `emoji_matrix_aligned`
  * `semver_consistent`
  * `breaking_change_complete`
* `presentation_fallback_reason: none`
* `hallucination_guard_fired: false`
* `gold_findings_count: 0` / `gold_blocked: false` / `gold_regen_attempts: 0`
* `contract_violation: false`
* Provenance: **`ai_accepted`**

**What was actually wrong**

1. **Primary type** `fix` on a fixtures/tests-only tip — gold requires `test`
2. **SemVer** `PATCH` / changelog `Fixed` — gold requires `NONE` / `Miscellaneous`
3. **Validation/enforce overclaim** — body says “enforce stricter validation constraints”; this tip only pins/characterises
4. **Thin inventory** — two generic secondaries instead of five TIP rows + must_not_present + README note
5. **Subject framing** — “validation goldens” rather than “pin Session 6 corpus rows”
6. **No pin/freeze/lock verbs** — gold law for characterisation commits
7. **Ranked identity retained as validation** even though the dominant path class is fixtures

The model’s reasoning (LLM span) shows it treated corpus/golden JSON edits as the primary “validation harness” story and demoted tests/docs to support work. That is locally coherent with the ranked contract and the false structural markers. It is globally wrong against Hybrid path-class law.

---

## 6. Normalisers made the wrong envelope look more official

Final telemetry:

```text
contract_lift_applied: true
contract_lift_from_semver: NONE
contract_locked_semver: PATCH
llm_raw_semver: PATCH
plan_persisted_semver: PATCH
plan_normaliser_applied: true
plan_normaliser_reason: contract_lift
```

Interpretation:

* Something in the plan/normaliser path still applied a **contract lift toward PATCH**.
* Final secondary changelog groups in `final_commit_plan` were normalised toward `Miscellaneous` while primary stayed `Fixed`.
* No normaliser rewrote `fix` → `test` or `PATCH` → `NONE` despite pure fixtures/tests paths.

So post-LLM machinery **stabilised** the wrong envelope rather than correcting path class.

`final_commit_plan` (partial schema) still carried:

```text
primary: fix / fixtures / add TIP-G13–G17 validation goldens / PATCH / Fixed
secondaries: test(corpus)..., docs(fixtures)...
body_summary: ... enforce stricter validation constraints ...
```

and matched the written tip.

---

## 7. Gold delta (what G2 should have said)

Gold `f5e55b7`:

```text
✅ test(fixtures): pin Session 6 corpus rows TIP-G13–G17

Freeze five presentation residuals in the commit_quality corpus against
the production SOP pin. Each row locks overlay type/SemVer/scope plus
guard-level must_not_present markers. Goldens stay atomic with corpus
inputs; harness remains pure (no live LLM, no rank_commit_intents) and
keeps ranked feature_addition + ✨ identity locked.

Included changes:
- ✅ test(fixtures): TIP-G13 telemetry schema/lifecycle → feat/MINOR
- ✅ test(fixtures): TIP-G14 evaluator forbids enforce/lift/mutate
- ✅ test(fixtures): TIP-G15 sentry reporter → fix/PATCH
- ✅ test(fixtures): TIP-G16 main wiring module scope; ban Context:/Changes:
- ✅ test(fixtures): TIP-G17 tests+plan primary test; no attribution bleed
- ✅ test(corpus): must_not_present fires GUARD_* residual markers
- 📝 docs(fixtures): letter map notes for TIP-G13–G17

Refs: #204
SemVer-Impact: NONE
Change-Types: test, docs
Changelog-Groups: Miscellaneous
```

| Dimension | Raw outcome | Gold requirement |
| --- | --- | --- |
| Primary type | `fix` | `test` |
| Emoji | `🦺` | `✅` |
| Scope | `fixtures` (ok-ish) | `fixtures` |
| Subject | add TIP-G13–G17 validation goldens | pin Session 6 corpus rows TIP-G13–G17 |
| SemVer | `PATCH` | `NONE` |
| Changelog | `Fixed` (+ Tests/Documentation) | `Miscellaneous` |
| Body verbs | expands / updates / **enforce** | freeze / pin / lock / cover |
| Inventory | 2 generic bullets | 5 TIP rows + must_not_present + README |
| Guards | none fired | should have blocked fix/PATCH + enforce framing + thin TIP inventory under gold_strict |
| Provenance | `ai_accepted` | should not have been acceptable |

---

## 8. Follow-on prepare-commit-msg observation

Immediately after accept/write, trace `019fdaac-a476-7e9e-95eb-be3b0cae0f77` ran `_run_commit_generation` with:

```text
commit_source: message
gold_strict: false
interactive: false
```

and exited via `_validate_commit_source` → `typer.Exit(0)` in ~9 ms.

This is the known prepare-commit-msg re-entry path. For G2 it did **not** clobber the message (early exit on existing message source). It remains process evidence for **F80 / P-S12-9**: hooks still invoke `git-cg` around the commit even when generation already finished. During the later message-only rebuild this same class of hook traffic is why `--no-verify` alone is insufficient.

---

## 9. G2-specific root cause

> On a pure fixtures/corpus/golden/harness diff, signal extraction and ranking over-weighted validation/schema wording inside JSON fixtures and under-weighted path class. With `path_class_gate` empty, no gold guidance, and no TIP-id harvest requirement, the model faithfully emitted a Hybrid-valid `fix`/`PATCH` “validation goldens” message. Gold-strict checks scored format/contract consistency only, so the wrong envelope was accepted with zero findings.

### Root-cause chain

```text
fixtures/tests-only diff extracted OK
→ semantic fingerprints mark structural + new_api/capability/runtime markers on harness/JSON
→ ranker: validation_update 100.5 >> tests_update/snapshot_update ~26
→ contract absent lock keeps fix/PATCH
→ path_class_gate empty; staged_paths/claim_tags/gold_guidance empty
→ single LLM attempt emits fix(fixtures) validation-goldens plan
→ body overclaims “enforce stricter validation constraints”
→ Included collapses five TIP rows to two generic support bullets
→ guards/gold findings = 0; scorecard all green
→ normaliser/contract_lift stabilises PATCH
→ operator accepts → provenance ai_accepted
→ later message-only rewrite to test/NONE pin inventory gold
```

### Primary defect

**Missing hard live path-class envelope for fixtures/corpus/goldens.**

A fixtures-only tip must not be allowed to primary as `fix`/`PATCH` merely because fixture payloads mention validation.

### Secondary defects

1. **False capability/runtime fingerprint markers** on pure test/fixture edits (`new_api`, `new_user_facing_capability`, `runtime_logic_changed`, etc.).
2. **No TIP/stable-id harvest** into required Included inventory (`TIP-G13`…`TIP-G17`, `must_not_present`, guard names).
3. **Validation/enforce verb overclaim** not banned on characterisation commits.
4. **`gold_strict` scored shape, not path-class truth** — zero findings despite wrong type/SemVer/inventory.
5. **`documentation_update` anti-signal** from `functional_code_changed` suppressed the docs-secondary honesty already weak in ranking.
6. **Contract lift / normaliser** reinforced PATCH rather than demoting to NONE for tests/fixtures.

---

## 10. Severity

**Critical — complementary to G1.**

* G1: controls fired; recovery made it worse; still succeeded.
* G2: controls never fired; wrong-but-clean message accepted as success under `gold_strict=true`.

G2 is the dogfood gap for the very Session 6 residual locks this tip is pinning: the series that adds TIP-G13–G17 characterisation still cannot present those pins under Hybrid law.

Maps to existing IDs: **F76/S12-5** (fixtures typed fix), **F78/S12-7** (thin TIP inventory), **F79/S12-8** (validate/enforce overclaim), **P-S12-4/6/8**.

---

## 11. Corrective controls for G2

### A. Hard path-class envelope before rank lock / after render

For staged paths ⊆ `tests/fixtures/**` + optional `tests/test_*corpus*` / pure harness:

```text
primary cc_type ∈ {test, docs}
primary semver = NONE
changelog ∈ {Miscellaneous, Tests, Documentation}
forbid primary fix/feat/chore with PATCH/MINOR solely from fixture payload signals
```

`path_class_gate` must not remain `empty` on this shape.

### B. Fingerprint / signal quarantine for fixtures

JSON/markdown fixture bodies must not emit production capability markers (`new_api`, `new_user_facing_capability`, `runtime_logic_changed`) into ranking unless `src/**` also changed.

Prefer fixture-specific signals:

```text
snapshot_added
corpus_row_added
golden_updated
harness_extended
```

### C. Stable-id inventory harvest

If diff adds/renames IDs matching `TIP-G\\d+`, require Included coverage (or gold finding):

```text
GOLD_TIP_INVENTORY_INCOMPLETE
```

Same family as V12-A claim-band harvest for G3.

### D. Characterisation verb denylist

On fixtures/tests_only tips, body/subject must not use:

```text
enforce
validate  (as runtime claim)
fix
implement
```

Prefer:

```text
pin / freeze / lock / cover / characterise / record
```

Emit `GOLD_CHARACTERISATION_VERB` / extend F79 controls.

### E. gold_strict must fail closed on envelope miss

Even when Hybrid shape is perfect:

```text
fixtures_only + primary fix/PATCH → gold finding → block or regenerate with test/NONE seed
```

Format scorecards are necessary, not sufficient.

---

## 12. Final G2 assessment

S12-G2 is a pure **envelope and evidence-harvest failure** with no fallback theatre.

Supported directly by Opik + raw Git:

* extraction OK: `019fdaa0-7193-7374-8cab-65feb85d0149`
* semantic OK but marker-noisy: `019fdaa0-71db-7b26-bb54-cf91d3dc8cdb`
* ranker validation_update 100.5; tests/snapshot ~26; path_class_gate empty
* single clean generation: `019fdaa0-71ff-7829-84b6-ebb254f865dd` / LLM `019fdaa0-7202-7690-84a7-a341b502d4e6`
* final plan fix/PATCH/validation goldens; guards/gold findings zero
* provenance `ai_accepted` on `019fdaa0-7067-75dd-be67-8cd99522b487`
* raw tip bytes `db30534` match the accepted plan exactly
* gold `f5e55b7` is message-only test/NONE pin inventory

Therefore G2 was caused by **missing fixtures path-class dominance + false validation/capability signals + no TIP inventory/gold envelope checks**, not by regeneration contradiction, fallback leakage, model outage, or render corruption.

### Evidence confidence

| Claim | Confidence | Basis |
| --- | --- | --- |
| Diff/semantic healthy | **Direct** | Opik spans |
| Ranker chose validation_update/fix/PATCH | **Direct** | prompt ranked_candidates + contract |
| path_class_gate empty; no gold findings | **Direct** | final telemetry metadata |
| Single attempt; no fallback | **Direct** | one generate/LLM span; presentation_fallback_reason=none |
| Exact raw COMMIT message | **Direct** | git object `db30534` matches plan |
| Fingerprint markers overclaim capability/runtime | **Direct markers, inferred causal weight** | telemetry markers + ranking evidence |
| prepare-commit-msg re-entry early-exit | **Direct** | trace `019fdaac-a476-...` |

---

## Stop point

**S12-G1 and S12-G2 are complete at full depth in this archive.**

**S12-G3 full depth** is in the continuation archive:
[Session 12 continued · S12-G3](./session-12-g3.md)

Queued next at the same depth:

1. **Synthesis:** [5215611559](./session-12-synthesis.md).
---

## Package cross-links

| Need | Link |
|:---|:---|
| Series systems reading | [`session-12-synthesis.md`](./session-12-synthesis.md) |
| Regime A sibling (G1) | [`session-12.md`](./session-12.md) |
| F76–F80 registry | [`../../FAILURE_TAXONOMY.md`](../../FAILURE_TAXONOMY.md) |
| P-S12 registry | [`../../PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) |
| Archive intake (non-SSOT) | [comment 5213748048](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) |

### Promotion record

| Field | Value |
|:---|:---|
| Promoted on | 2026-08-13 |
| From | #204 comment `5213748048` · G2 `<details>` body |
| SSOT rule | Package path wins over GitHub comment after promote |

---

## Document control

| Field | Value |
|:---|:---|
| Case ID | 204-S12-G2 |
| Package version | `1.0.0-combine` |
| Status | active / full |
| Last updated | 2026-08-13 |
