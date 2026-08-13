# CASE — Session 12 · G3 residual close-out (Regime B)

> **Status:** active / full  
> **Copy lineage:** promoted from [#204 comment 5215148242](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215148242)  
> **Method:** [`../../METHOD.md`](../../METHOD.md)  
> **Template:** [`../../templates/CASE_TEMPLATE.md`](../../templates/CASE_TEMPLATE.md)  
> **Package version:** `1.0.0-combine`  
> **Series:** Session 12 · Session 6 residual close-out · message-only rebuild  
> **Siblings:** [`session-12.md`](./session-12.md) · [`session-12-g2.md`](./session-12-g2.md) · [`session-12-g4.md`](./session-12-g4.md) · [`session-12-synthesis.md`](./session-12-synthesis.md)  
> **Consumer:** eval harness [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) (`session-12-seed`)  
> **Authority:** this file is package SSOT for S12-G3. The GitHub comment is intake/archive evidence only.

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: active
issue: 204
case_id: 204-S12-G3
series_id: 204-S12
series_class: residual-close-out
regime: B
opik: bound
sources:
  - github:issue-comment:5215148242
  - git:raw:0c7a9b776f863fc1fce5623a9ee7402ee2eea129
  - git:gold:19bd55135139abc842304ed08975d0143d86d1ad
  - opik:trace:019fdaac-e249-76cb-ba25-93fc59f4d657
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** MISS gold · Regime **B** (clean wrong acceptance)  
**Path focus:** `tests/test_v12_a_claims.py`  
**Severity:** Critical  
**Raw → gold:** `0c7a9b776f863fc1fce5623a9ee7402ee2eea129` → `19bd55135139abc842304ed08975d0143d86d1ad`  
**Tree preserved:** yes · tree OID `3f4b7227…`  
**One-line diagnosis:** Pure V12-A characterisation pack typed `fix`/`PATCH` under empty path-class; missing a01–a45 inventory; validate/enforce framing; gold_strict zero findings.  
**IDs:** **F76** · **F78** · **F79** · **F80** · P-S12-4 · P-S12-6 · P-S12-8 · P-S12-9  
**Series class:** residual-close-out

| Field | Value |
|:---|:---|
| Issue | #204 |
| Case ID | 204-S12-G3 |
| Reviewer | Thomo1318 / Session 12 forensic archive |
| Date | 2026-08-07 (incident) · promoted 2026-08-13 |
| Library class (intended) | pure tests · V12-A named proof pack a01–a45 |
| Acceptance mode (raw) | `ai_accepted` |

### Observed subjects (do not regress)

```text
S12-G3 ❌  🦺 fix(test): add V12-A claim proof pack tests · PATCH · fix
S12-G3 ✅  ✅ test(commit-quality): add V12-A named proof pack a01–a45 · NONE · test
```

---

## 1. Incident identity

| Field | Value |
|:---|:---|
| Governing issue | #204 |
| Child / slice | Session 12 · G3 of 4 |
| Branch | `refactor/204-commit-presentation-quality` |
| Message-only rebuild? | **yes** |
| Notes | Cleanest tests-only tip in series; still shipped fix/PATCH. |

### Rewrite map

| Role | SHA | Subject (short) | Tree OID |
|:---|:---|:---|:---|
| Git-raw | `0c7a9b776f863fc1fce5623a9ee7402ee2eea129` | fix(test) V12-A claim proof pack | `3f4b7227…` |
| Gold-final | `19bd55135139abc842304ed08975d0143d86d1ad` | test(commit-quality): add V12-A named proof pack a01–a45 | `3f4b7227…` |

**Rewrite-map-confirmed:** yes

---

# Full-depth forensic body (promoted)


**Scope for this section:** G3 only. G1/G2 live in the [primary Session 12 archive](./session-12.md). G4 full depth: [5215440216](./session-12-g4.md).

| Field | Value |
| --- | --- |
| Raw tip | `0c7a9b776f863fc1fce5623a9ee7402ee2eea129` |
| Gold tip | `19bd55135139abc842304ed08975d0143d86d1ad` |
| Tree (both) | `3f4b7227805ff2f8b3213f25d010806a3d3982ec` |
| Path | `tests/test_v12_a_claims.py` only |
| Diff | `1 file changed, 709 insertions(+)` (add-only) |
| Gold subject | `✅ test(commit-quality): add V12-A named proof pack a01–a45` |
| Raw subject | `🦺 fix(test): add V12-A claim proof pack tests` |
| Trace | `019fdaac-e249-76cb-ba25-93fc59f4d657` (`log_final_commit_telemetry`) |
| Root span | `019fdaac-e24a-7f33-8d73-621eb1ddeae5` (`_run_commit_generation`) |
| Final telemetry span | `019fdabf-3ea6-7dd9-a09e-92f33b90ff47` |
| Final telemetry time | `2026-08-07T05:43:14Z` |
| Provenance | `ai_accepted` / status `recorded` |

> Direct evidence from Opik final telemetry + generation spans, cross-checked against preserved raw Git object `0c7a9b7` and gold tip `19bd551`. Opik captured accepted `commit_plan` / `final_commit_plan` on the final telemetry span; raw Git tip bytes match that plan (scope normalised `tests`→`test`, changelog `Changed`→`Fixed`).

## Executive finding

S12-G3 was **not** a guard-exhaustion or fallback failure. It was a **clean wrong acceptance** of a pure characterisation pack under a product-validation envelope.

The system:

1. Correctly extracted a single new test file.
2. Parsed it with tree-sitter under add-only / head-missing fallback.
3. Emitted false capability and runtime markers from test-body AST patterns.
4. Ranked `validation_update` at **100.5** over `tests_update` at **26.0**.
5. Locked a deterministic contract to `fix` / `PATCH` / `validation_update`.
6. Left `path_class_gate` empty and injected **no** staged paths, claim tags, or gold guidance.
7. Allowed a single LLM attempt to obey that wrong contract faithfully.
8. Applied contract lift (`NONE` → `PATCH`) and plan normaliser, making the wrong envelope look official.
9. Fired **zero** gold findings under `gold_mode=strict`.
10. Accepted via `ai_accepted` and wrote the wrong message.

Later message-only rewrite corrected type/SemVer/scope/inventory without changing the tree.

## Identity and observed evidence

| Item | Value |
| --- | --- |
| Trace | `019fdaac-e249-76cb-ba25-93fc59f4d657` |
| Project | `gitCommitGenerator` |
| Root operation | `_run_commit_generation` |
| Root span | `019fdaac-e24a-7f33-8d73-621eb1ddeae5` |
| Diff span | `019fdaac-e427-7546-a809-ba919a6ea2de` (`extract_git_diff`) |
| Semantic span | `019fdaac-e483-78fa-a38b-a7ca57205845` (`semantic_analysis`) |
| Prompt span | `019fdaac-e6dc-7dbb-ac48-5384f9f0fe77` (`build_system_prompt`) |
| Generate span | `019fdaac-e6de-7940-90fa-fe290929fae7` (`generate_commit_message`) |
| LLM span | `019fdaac-e6e0-7722-8f31-267b196e3710` (`chat_completion_create`) |
| Final telemetry | `019fdabf-3ea6-7dd9-a09e-92f33b90ff47` |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` |
| Provider | `127.0.0.1` |
| Tokens | prompt 5,150 · completion 3,276 (reasoning 3,043) · total 8,426 |
| LLM duration | ~129.0 s |
| Attempts | **1** (no retry / no fallback) |
| Follow-on prepare | `019fdabf-323b-79f0-84f9-7fc4bb4fd628` (~6 ms early path after accept) |

## 1. Startup contract (direct Opik)

Root `_run_commit_generation` input:

```json
{
  "commit_msg_file": ".git/COMMIT_EDITMSG",
  "engine": "lmlx",
  "dry_run": false,
  "verbose": true,
  "strict": true,
  "interactive": true,
  "enable_semantic": true,
  "gold_strict": true,
  "rank_arbitrate": true,
  "blueprint": null,
  "amend_regenerate": false
}
```

**Observation:** live write path under `gold_strict=true`. Failure is “accepted wrong envelope,” not tooling outage.

## 2. What the diff actually contained

Diff extractor completed successfully:

```text
tests/test_v12_a_claims.py | 709 +++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 709 insertions(+)
```

Concrete product of the commit (from file structure + gold message):

1. **Named proof pack** with stable IDs `test_v12_a01` … `test_v12_a45` plus pack-level ranker non-invocation guard.
2. **Thin wrappers only** over pure presentation helpers and frozen corpus/eval harness:
   * path-class gates, blueprint overlay, SemVer ceilings, guards, Session 6 residuals
3. **Presentation purity invariants** stated in module docstring:
   * no live LLM
   * no `rank_commit_intents`
   * does not mutate ranked intent_id/gitmoji
4. **Claim bands** explicitly sectioned in source:
   * V12-A01–A07 core presentation
   * V12-A08–A13 path-class / security / hallucination
   * V12-A14–A21 Session 2
   * V12-A22–A26 Session 3
   * V12-A27–A32 Session 4
   * V12-A33–A38 Session 5
   * V12-A39–A45 Session 6
   * `test_v12_a_pack_never_calls_ranker`

**No extraction failure.** The system saw a pure tests-only characterisation pack.

## 3. Semantic analysis was successful — and contaminated by add-only fingerprinting

Direct semantic / fingerprint telemetry:

```text
semantic_parser_mode: tree-sitter
semantic_files_total/parsed: 1 / 1
semantic_fallback_reasons:
  - fingerprint:tests/test_v12_a_claims.py:add_only
  - head_error:tests/test_v12_a_claims.py:missing
fingerprint_class_counts: {add_only: 1}
fingerprint_markers:
  - files_added
  - exception_handling_added
  - error_handling_improved
  - try_except_added
  - new_api
  - new_user_facing_capability
  - functional_code_changed
impacts_tests / impacts_production_code: null
blast_radius_size: null
affected_flows_count: 0
risk_score: 0.0
```

**Assessment:**

* Parser “worked” on the new file, but add-only / missing-head fallback treated test AST shapes as product capability.
* `try`/`except` and helper APIs inside tests became `exception_handling_*`, `new_api`, `new_user_facing_capability`, `functional_code_changed`.
* No authoritative path-class statement that this is tests-only / characterisation-only.
* This is the upstream poison that made validation dominate tests.

## 4. Ranking vs contract (direct Opik)

From `build_system_prompt` ranked candidates + locked contract:

| Rank | intent_id | score | cc_type | semver | evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `validation_update` | **100.5** | fix | PATCH | `validation_hardened`, `validation_added`, `schema_validation_changed` |
| 2 | `feature_addition` | **80.0** | feat | MINOR | `new_api`, `new_user_facing_capability` |
| … | (breaking/security/hotfix noise) | 49→40 | … | … | empty / weak |
| low | `error_handling` | 40.5 | fix | PATCH | try/except markers (penalised by new_api) |
| **correct family** | `tests_update` | **26.0** | test | NONE | **no competitive evidence** |
| nearby test intents | `failing_test` / `mock_update` / `snapshot_update` | 29.0 / 26.5 / 26.5 | test | NONE | not selected |

Locked deterministic contract injected into the prompt:

```text
primary_intent_id: validation_update
gitmoji: 🦺
cc_type: fix
semver_impact: PATCH
changelog_group: Changed
lock_resolution: absent
```

Also observed on final telemetry:

```text
path_class_gate: empty
staged_paths: []
claim_tags: []
gold_guidance: null
concern_tags: null
blueprint_applied: false
hallucination_guard_fired: false
presentation_fallback_reason: none
ranking_confidence_level: medium
ranking_confidence_margin: 20.5
ranking_choice_path: skipped_high_medium
ranking_override: false
contract_lift_applied: true
contract_lift_from_semver: NONE
contract_locked_semver: PATCH
llm_raw_semver: PATCH
plan_persisted_semver: PATCH
plan_normaliser_applied: true
plan_normaliser_reason: contract_lift
gold_mode: strict
gold_findings_count: 0
gold_finding_codes: []
gold_blocked: false
gold_regen_attempts: 0
```

**Assessment:**

* The ranker never seriously considered the tests envelope.
* Margin 20.5 with medium confidence still skipped arbitration (`skipped_high_medium`).
* Contract lock converted a contaminated ranking into a hard generation constraint.
* Contract lift then forbade the correct SemVer (`NONE`) by promoting/holding `PATCH`.
* Empty path-class gate + empty claim harvest meant no late envelope correction.

## 5. Single generation attempt — model followed the wrong envelope faithfully

| Span | Name | Duration |
| --- | --- | --- |
| `019fdaac-e6de-...` | `generate_commit_message` | ~129.0 s |
| `019fdaac-e6e0-...` | `chat_completion_create` | ~129.0 s |

**LLM raw plan (direct):**

```text
primary: validation_update / 🦺 / fix / scope=tests
description: add V12-A claim proof pack tests
semver: PATCH
changelog_group: Changed
secondary_intents: []
```

**Post-normaliser accepted plan / final telemetry:**

```text
primary: validation_update / 🦺 / fix / scope=test
description: add V12-A claim proof pack tests
semver: PATCH
changelog_group: Fixed
secondary_intents: []
body_summary: Establishes a stable proof pack for V12-A claims to validate
  presentation overlays and corpus evaluation. Tests ensure presentation
  guards and changelog constraints are met without mutating ranked intent
  IDs or relying on live LLM calls.
```

**Exact raw Git tip message (`0c7a9b7`) — byte-confirmed:**

```text
🦺 fix(test): add V12-A claim proof pack tests

Establishes a stable proof pack for V12-A claims to validate presentation overlays and corpus evaluation. Tests ensure presentation guards and changelog constraints are met without mutating ranked intent IDs or relying on live LLM calls.

Refs: #204
SemVer-Impact: PATCH
Change-Types: fix
Changelog-Groups: Fixed
```

**Model reasoning (direct, condensed):** the model **saw** that the diff adds tests and even considered `tests_update`, then explicitly subordinated that observation to the locked validation contract (“Although it adds tests, the deterministic contract mandates validation_update…”). Scope was chosen as `tests`/`test` rather than module canon `commit-quality`. No claim-band secondaries were emitted.

**What looked “good” to the pipeline**

* Single coherent plan
* Header length OK (48 chars scored)
* Emoji/type matrix-aligned under the locked fix/validation row
* No banned Context:/Changes skeleton
* No fallback theatre (`presentation_fallback_reason=none`)
* `contract_consistent=1` via contract lift
* `user_acceptance=1` (`ai_accepted`)
* `gold_findings_count=0`

**What was actually wrong**

1. **Wrong primary type** — `fix` instead of `test`
2. **Wrong SemVer** — `PATCH` instead of `NONE`
3. **Wrong changelog** — `Fixed` instead of `Miscellaneous`
4. **Wrong scope** — path-ish `test` instead of canonical module `commit-quality`
5. **Subject under-claim** — omitted “named proof pack” and stable range `a01–a45`
6. **No Included-changes inventory** for claim bands / ranker guard
7. **Characterisation verb overclaim** — “validate … guards … are met” frames proof as enforcement
8. **Capability contamination** — false `new_api` / `new_user_facing_capability` / `functional_code_changed`
9. **Contract lift anti-correction** — reinforced `PATCH` from `NONE`
10. **gold_strict non-blocking** on pure path-class + inventory truth

Online scorecard oddities (secondary, not causal): several online scorers reported `scope_present=0`, `format_compliance=0`, `has_body=0`, `imperative_mood=0` even though the accepted plan/raw tip clearly had scope, body, and imperative subject. Final telemetry score_card still showed structural greens (`header_length_ok`, `type_valid`, `emoji_matrix_aligned`, `semver_consistent`). Net effect: weak/contradictory scoring did not block acceptance.

## 6. Normalisers made the wrong envelope look more official

Observed normaliser/lift path:

```text
contract_lift_applied: true
contract_lift_from_semver: NONE
contract_locked_semver: PATCH
llm_raw_semver: PATCH
plan_persisted_semver: PATCH
plan_normaliser_applied: true
plan_normaliser_reason: contract_lift
scope_normalised_from: none   # LLM used tests; final plan shows test
```

Effects:

* Changelog moved toward matrix/fix presentation (`Changed` → `Fixed`) while remaining in the wrong family.
* Scope collapsed to singular `test` rather than being rewritten to module canon `commit-quality`.
* SemVer stayed `PATCH` under lift even though pure tests law requires `NONE`.
* No secondary synthesis from claim-band structure.

## 7. Gold delta (what G3 should have said)

**Gold tip `19bd551` (byte-confirmed):**

```text
✅ test(commit-quality): add V12-A named proof pack a01–a45

Add stable claim IDs over pure presentation helpers and the frozen
corpus/eval harness. Thin wrappers only: path-class gates, blueprint
overlay, SemVer ceilings, guards, and Session 6 residuals. Pack asserts
rank_commit_intents is never called so proof stays presentation-pure.

Included changes:
- ✅ test(commit-quality): V12-A01–A07 core scope/priors/blueprint/low-confidence
- ✅ test(commit-quality): V12-A08–A13 path-class, security, hallucination locks
- ✅ test(commit-quality): V12-A14–A38 Sessions 2–5 ordered claim surface
- ✅ test(commit-quality): V12-A39–A45 Session 6 residual claim locks
- ✅ test(commit-quality): pack-level ranker non-invocation guard

Refs: #204
SemVer-Impact: NONE
Change-Types: test
Changelog-Groups: Miscellaneous
```

| Dimension | Raw `0c7a9b7` | Gold `19bd551` |
| --- | --- | --- |
| Emoji / type | 🦺 `fix` | ✅ `test` |
| Scope | `test` | `commit-quality` |
| Subject | add V12-A claim proof pack tests | add V12-A named proof pack a01–a45 |
| SemVer | PATCH | NONE |
| Change-Types | fix | test |
| Changelog | Fixed | Miscellaneous |
| Body posture | validate / ensure guards met | thin wrappers / characterise / assert purity |
| Inventory | none | five claim-band / guard bullets |
| Tree | `3f4b7227…` | `3f4b7227…` (identical) |

## 8. Follow-on prepare-commit-msg observation

Immediately around accept/write, trace `019fdabf-323b-79f0-84f9-7fc4bb4fd628` ran `_run_commit_generation` and exited in ~6 ms. This matches the known prepare-commit-msg re-entry class also observed on G2 (`019fdaac-a476-...`). For G3 it did **not** rewrite the accepted wrong message; it remains process evidence for **F80 / P-S12-9**.

## 9. G3-specific root cause

### Root-cause chain

```text
tests-only file added (test_v12_a_claims.py, +709)
→ semantic parser falls back on add-only / head-missing
→ false capability/runtime markers emitted
   (new_api, new_user_facing_capability, functional_code_changed,
    exception_handling_*, try_except_added)
→ validation_* signals dominate; tests_update remains ~26.0
→ path_class_gate empty; staged_paths/claim_tags/gold_guidance absent
→ contract locks validation_update / fix / PATCH
→ contract lift reinforces PATCH from NONE
→ single LLM obeys locked wrong contract (explicitly notes “although tests…”)
→ no guards / findings / fallback
→ scorecard + contract_consistent green
→ ai_accepted
→ later message-only rewrite to test/NONE + named V12-A inventory
```

### Primary defect

**Missing hard live path-class envelope for pure `tests/**` proof packs, compounded by add-only fingerprint contamination that promotes validation/capability over tests.**

### Secondary defects

1. **No stable claim-ID harvest** (`V12-A\\d+` / `test_v12_a\\d+`) → no inventory obligation.
2. **Characterisation verb overclaim** (“validate”, “ensure … met”) not banned on proof packs.
3. **Contract lift raises/holds PATCH** on tests-only paths.
4. **Scope canon missing** — path token `test` accepted instead of module `commit-quality`.
5. **gold_strict checks shape/contract consistency, not path-class truth + inventory completeness.**
6. **Ranker non-invocation / monkeypatch purity** not recognised as anti-capability evidence.

## 10. Severity

**Critical — same family as G2, more severe on pure-tests law.**

* G2 mixed fixtures/docs/harness and still should have been primary `test`.
* G3 is the cleanest possible tests-only signal and still shipped `fix`/`PATCH`.
* Wrong type+SemVer on characterisation packs poisons release notes and teaches the corpus the inverse of V12-A law.
* Maps to existing IDs: **F76/S12-5** (tests typed fix), **F78/S12-7** (missing a01–a45 inventory), **F79/S12-8** (validate/enforce overclaim), **P-S12-4/6/8**.

## 11. Corrective controls for G3

### A. Hard path-class envelope before rank lock / after render

* Pure `tests/**` (no `src/**`) ⇒ primary `test` + SemVer `NONE` + changelog `Miscellaneous`/`Tests` family.
* Forbid primary `fix`/`feat` and SemVer `PATCH`/`MINOR` from test-body semantics alone.
* Emit `GOLD_PATH_CLASS_ENVELOPE` when violated under `gold_strict`.

### B. Fingerprint / signal quarantine for tests-only additions

* On `add_only` + path under `tests/`, suppress or heavily demote:
  * `new_api`
  * `new_user_facing_capability`
  * `functional_code_changed`
  * validation/schema markers derived solely from test assertions/helpers
* Prefer tests markers / path priors over AST capability guesses.

### C. Stable-id inventory harvest

* Detect `V12-A\\d+`, `test_v12_a\\d+`, band section headers, and pack-level guards.
* Require Included-changes coverage for major bands (or explicit compact range form `a01–a45` plus residual bullets).
* Emit `GOLD_CLAIM_INVENTORY_INCOMPLETE` when missing.

### D. Characterisation verb denylist

* On pure proof packs / fixtures: ban lead framing with implement/fix/enforce/validate-as-runtime.
* Prefer add proof pack / cover / assert / characterise / lock / pin / freeze.
* Extend F79 / P-S12-8.

### E. Contract lift must not raise tests-only NONE→PATCH

* If path-class says tests-only, lift ceiling is `NONE`.
* `plan_normaliser_reason=contract_lift` must not launder a wrong family.

### F. Scope canon for commit-quality proof surfaces

* Tests that import/exercise `git_cg.commit_quality` presentation helpers should normalise scope to `commit-quality`, not `test`/`tests`.

### G. gold_strict must fail closed on envelope miss

Even when formatting checks pass, block on:

* wrong cc_type family for path class
* wrong SemVer for path class
* missing stable-ID inventory for named proof packs
* capability markers retained on tests-only diffs without product paths

## 12. Final G3 assessment

S12-G3 is a pure **envelope, fingerprint-quarantine, and evidence-harvest failure** with no fallback theatre.

Supported directly by Opik + raw Git:

* tests-only add-only diff
* false capability/runtime markers
* validation_update 100.5 ≫ tests_update 26.0
* empty path_class_gate / claim_tags / gold_guidance
* locked fix/PATCH contract + lift
* single faithful LLM emission
* zero gold findings
* `ai_accepted` raw tip byte-matches plan
* gold rewrite preserves tree and restores test/NONE + a01–a45 inventory

### Evidence confidence

| Claim | Confidence | Basis |
| --- | --- | --- |
| Diff/semantic spans healthy but contaminated | **Direct** | Opik semantic + fingerprint fields |
| Ranking/contract lock wrong family | **Direct** | prompt ranked_candidates + contract |
| Single-attempt clean acceptance | **Direct** | generate + final telemetry |
| Raw tip bytes = accepted plan | **Direct** | `git cat-file` `0c7a9b7` |
| Tree-identical gold rewrite | **Direct** | both trees `3f4b7227…` |
| Model knowingly overrode “tests” observation | **Direct** | LLM reasoning_content |
| prepare re-entry non-clobber | **Direct** | trace `019fdabf-323b-...` |

## Stop point

**S12-G3 is complete at full depth in this continuation archive.**

**Cross-commit synthesis:** [5215611559](./session-12-synthesis.md).

---

## Package cross-links

| Need | Link |
|:---|:---|
| Series synthesis | [`session-12-synthesis.md`](./session-12-synthesis.md) |
| G2 envelope sibling | [`session-12-g2.md`](./session-12-g2.md) |
| Archive intake | [comment 5215148242](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215148242) |

### Promotion record

| Field | Value |
|:---|:---|
| Promoted on | 2026-08-13 |
| From | #204 comment `5215148242` |
| SSOT rule | Package path wins |

---

## Document control

| Field | Value |
|:---|:---|
| Case ID | 204-S12-G3 |
| Status | active / full |
| Last updated | 2026-08-13 |
