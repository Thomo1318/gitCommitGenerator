# CASE — Session 12 dogfood · G2–G4 post-control residual (Regime B)

> **Status:** active / full  
> **Copy lineage:** promoted from #204 comments [`5226058599`](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5226058599) · [`5226058718`](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5226058718) · [`5226058788`](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5226058788)  
> **Method:** [`../../METHOD.md`](../../METHOD.md)  
> **Template:** [`../../templates/CASE_TEMPLATE.md`](../../templates/CASE_TEMPLATE.md) + multi-tip series  
> **Package version:** `1.0.0-combine`  
> **Series class:** post-control-dogfood  
> **Prior residual series:** [`session-12.md`](./session-12.md) … [`session-12-synthesis.md`](./session-12-synthesis.md)  
> **Authority:** this file is package SSOT for Session 12 post-control dogfood G2–G4. GitHub comments are intake/archive only.

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: active
issue: 204
case_id: 204-S12-DF-G2G4
series_id: 204-S12-DF
series_class: post-control-dogfood
regime: B
opik: bound
sources:
  - github:issue-comment:5226058599
  - github:issue-comment:5226058718
  - github:issue-comment:5226058788
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** MISS gold · Regime **B** (all three dogfood tips)  
**Path focus:** path-class envelope / gold-strict truth / fixture corpus pins (post P-S12 controls)  
**Severity:** Critical (series-wide residual after control implementation)  
**Series class:** post-control-dogfood  
**One-line series diagnosis:** After P-S12 path-class / gold-strict / fixture controls landed in product diffs, dogfood tips still missed gold via empty `path_class_gate`, regen degradation, and fixtures-as-validation ranking — proving control gaps remain live.  
**IDs:** extends F76–F80 · P-S12 residual gaps · dogfood-local findings in bodies below  

| Group | Focus | Severity | Regime | Raw → Gold | Archive |
|:---|:---|:---|:---|:---|:---|
| DF-G2 | path-class envelope product tip | Critical | B | `727a190` → `6e71f29` | `5226058599` |
| DF-G3 | gold-strict final-truth codes | Critical | B | `7db174c` → `0374e57` | `5226058718` |
| DF-G4 | fixture corpus pins | Critical | B | `657c6e5` → `722e588` | `5226058788` |

---

## Dogfood G2 (promoted from `5226058599`)

## #204 Session 12 dogfood failure analysis — G2 (path-class envelope)

> [!NOTE]
>
> **Purpose:** Full-depth gold-miss reconstruction for **Session 12 dogfood G2** after implementation of P-S12 path-class / empty-unknown controls.
>
> **Series:** G2 (this) · G3 · G4 — separate comments, sequential.
>
> **Prior Session 12 archives:** [primary](./session-12.md) · [G3 cont](./session-12-g3.md) · [G4 cont](./session-12-g4.md) · [synth](./session-12-synthesis.md)
>
> **Scope:** Message craft only on `refactor/204-commit-presentation-quality`. Trees preserved. Untracked `docs/supportingDocumentation/commitMessageFailureAnalysis/` not part of this commit.

---

## 🧪 Incident evidence — G2 (2026-08-08)

**Result:** **G2 misses gold** on scope, subject, inventory depth, Change-Types, and Changelog-Groups. SemVer `PATCH` matched.

**One-line diagnosis:** Empty `path_class_gate` + low-confidence presentation fallback let a generic `validation_update` / `presentation` plan ship instead of the authoritative `commit-quality` fixture→test-family envelope narrative.

| Field | Value |
| --- | --- |
| Group | **G2** |
| Path focus | `commit_quality.py`, `main.py`, `regeneration.py`, quality/regen tests |
| Severity | **Critical** (envelope authority miss) |
| Raw SHA | `727a190d26d9a23d20941764dc49f4d37950d5a9` |
| Gold SHA | `6e71f29e5d6349681beb7b60f265987c5d74490b` |
| Tree (unchanged) | `9db8a37374a541c0e6fc0dcd912bd7015eeca1b2` |
| Parent | `6d86a3b7f61e72720cc3c57980a1f411e06d587a` |

### Opik identity

| Field | Value |
| --- | --- |
| Project | `gitCommitGenerator` (`019e7e59-7caf-70a6-8756-f84a55b5d5fd`) |
| Final trace | [`019fe126-e3ab-7496-a992-7ef0c61404de`](https://www.comet.com/opik/api/v1/session/redirect/projects/?trace_id=019fe126-e3ab-7496-a992-7ef0c61404de&path=aHR0cHM6Ly93d3cuY29tZXQuY29tL29waWsvYXBpLw==) |
| Generation span | `019fe126-f237-785f-afe9-56eb2f290a22` (`generate_commit_message`) |
| LLM span | `019fe126-f23d-7f78-907a-599433c308a2` (`chat_completion_create`) |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` |
| Window | gen `2026-08-08T11:34:13Z`–`11:37:40Z`; final telemetry `11:39:49Z` |
| Engine | `lmlx` · provenance `ai_accepted` |


### Full analysis — dogfood G2

### Executive finding

G2 implemented the product controls that force fixtures into the test-family envelope and treat empty/unknown path evidence as non-forcing. The **accepted message did not name those controls**. Ranking selected `validation_update` with scope `presentation`; low-confidence skeleton guidance compressed the body; gold-strict recorded **zero findings** and did not block.

### Identity / evidence table

| Axis | Actual (raw) | Gold | Match? |
| --- | --- | --- | --- |
| Emoji / type | `🦺 fix` | `🦺 fix` | ✅ |
| Scope | `presentation` | `commit-quality` | ❌ |
| Subject | `treat fixtures as tests; allow unknown paths` | `force fixtures into the test-family envelope` | ❌ |
| SemVer | `PATCH` | `PATCH` | ✅ |
| Change-Types | `fix, test, refactor` | `fix, test` | ❌ |
| Changelog-Groups | `Fixed, Tests, Changed` | `Fixed, Tests` | ❌ |
| Inventory bullets | 2 | 9 | ❌ |
| Refs | `#204` | `#204` | ✅ |

### Generation cycle

| Step | Observation |
| --- | --- |
| Diff files | `commit_quality.py`, `main.py`, `regeneration.py`, `test_commit_quality.py`, `test_regeneration_contract.py` |
| Ranked primary | `validation_update` score `100.5` (validation_hardened/added, schema_validation_changed) |
| Confidence | **low** · margin `0.5` · reasons `margin_below_low_threshold`, `mixed_intent` · path `pick_a` |
| Presentation fallback | `low_confidence` |
| `path_class_gate` | **`empty`** |
| `staged_paths` in prompt build | **`[]`** |
| Contract | locked SemVer `PATCH`; lift not applied |
| Gold-strict | mode `strict` · findings `0` · blocked `false` · regen attempts `0` |
| Scope normalise | `scope_normalised_from: none` (underscore secondary `commit_quality` never canonicalised to `commit-quality`) |
| Online scores | `format_compliance 0.0`, `has_body 0.0`, `scope_present 0.0`, `user_acceptance 1.0` |

### Direct prompt / model evidence

* Primary plan: `validation_update` / `fix` / scope **`presentation`** / `PATCH` / subject *treat fixtures as tests; allow unknown paths*.
* Secondaries: `tests_update` (`commit_quality`) + `generic_refactor` (`regeneration`) → inflated Change-Types/Changelog.
* Body summarised classification + open ceiling, but **omitted** dual-surface gates, Hybrid-safe skeleton provenance, guard-over-skeleton retry, second-chance path harvest, and the nine-bullet inventory.
* Low-confidence skeleton instructed Hybrid prose only; it did **not** force module-true scope `commit-quality` or deterministic inventory from staged files.
* Fingerprints: 5× structural; markers included `runtime_logic_changed`, `new_api`, `functional_code_changed` — product work was visible, yet path-family envelope was not authoritative.

### Causal chain

1. **Path evidence collapsed to empty** → `path_class_gate: empty` and `staged_paths: []` in `build_system_prompt`.
2. Without an authoritative fixtures/tests envelope, ranking kept **product validation** as primary.
3. Low confidence triggered **presentation skeleton fallback**, which shortened/genericised wording rather than recovering module truth.
4. Model chose scope **`presentation`** (symptom) over **`commit-quality`** (implementation home).
5. Secondary refactor intent leaked into trailers (`refactor` / `Changed`).
6. **Gold-strict failed closed-open:** `gold_findings_count: 0` despite subject/scope/inventory miss — final rendered message was not linted against gold presentation law.
7. User accepted (`user_acceptance: 1.0`) → raw tip shipped.

### Gold delta (what rewrite restored)

```text
🦺 fix(commit-quality): force fixtures into the test-family envelope
… 9 inventory bullets naming fixtures_only priors, empty-unknown,
dual-surface gates, regen envelope-before-lift, path harvest,
Hybrid skeleton, guard retry, and locks …
SemVer-Impact: PATCH
Change-Types: fix, test
Changelog-Groups: Fixed, Tests
```

Message-only amend applied; tree `9db8a373…` preserved.

### Prevention controls (G2-facing)

| ID | Control | Why |
| --- | --- | --- |
| P-G2-1 | Deterministic **path-family envelope before ranking/contract lift** | Empty gate must not default to product validation framing |
| P-G2-2 | Explicit **empty/unknown = non-forcing** (no invented NONE; no silent product clamp) | Core G2 product law must be reflected in telemetry + message |
| P-G2-3 | Canonical scope normaliser (`commit-quality`, never `commit_quality` / symptom scopes like `presentation` when module is clear) | Scope miss was half the gold delta |
| P-G2-4 | Deterministic inventory from changed files / named surfaces | 2 bullets vs 9 |
| P-G2-5 | Final-truth gold lint on **rendered** header/body/trailers, not only internal plan codes | `gold_findings_count: 0` is a control-plane bug |
| P-G2-6 | Stable Opik thread/umbrella linkage gen→final; persist accurate gold/regen counters | Online scores saw no body/scope while final plan had both |
| P-G2-7 | Skeleton/process-meta must not be the accepted final without gold block | `presentation_fallback_reason: low_confidence` shipped |

### Canonical references

* Raw: `727a190` · Gold: `6e71f29` · Tree: `9db8a373`
* Trace: `019fe126-e3ab-7496-a992-7ef0c61404de`
* Implementation homes: `src/git_cg/commit_quality.py`, `main.py` path harvest, `regeneration.py` envelope-before-lift
* Issue law: #204 Session 12 / P-S12 path-class + empty-unknown


---
## Dogfood G3 (promoted from `5226058718`)

## #204 Session 12 dogfood failure analysis — G3 (gold-strict truth)

> [!NOTE]
>
> **Purpose:** Full-depth gold-miss reconstruction for **Session 12 dogfood G3** (final-truth codes for skeleton fallback + path-class product framing).
>
> **Series:** [G2](./session-12-dogfood-g2-g4.md) · **G3 (this)** · G4 — post G2 first; replace G2 link after publish if needed.
>
> **Prior Session 12 archives:** [primary](./session-12.md) · [G3 cont](./session-12-g3.md) · [G4 cont](./session-12-g4.md) · [synth](./session-12-synthesis.md)
>
> **Scope:** Message craft only. Trees preserved through targeted rebase recovery (`0374e57`).

---

## 🧪 Incident evidence — G3 (2026-08-08)

**Result:** **G3 misses gold** on scope canonicalisation, subject specificity, body precision, and inventory. Trailers (`PATCH` / `fix, test` / `Fixed, Tests` / `Refs: #204`) matched.

**One-line diagnosis:** Regeneration **degraded** a more specific first-pass plan into a generic “harden validation rules” subject with underscore scope `commit_gold`, while gold-strict reported **zero findings** and did not block — the new final-truth codes were implemented in the diff but not enforced on the outgoing message.

| Field | Value |
| --- | --- |
| Group | **G3** |
| Path focus | `commit_gold.py`, `test_commit_gold.py`, `test_main.py` |
| Severity | **Critical** (truth-plane miss + regen regression) |
| Raw SHA | `7db174c63ac1385d87c564af793f9577f24a101f` |
| Gold SHA | `0374e57fc4b5618ba681071123733cd5321e37fe` |
| Tree (unchanged) | `6fdd76e02860ddb19dcd506c2bf07eaf7eb92bf7` |

### Opik identity

| Field | Value |
| --- | --- |
| Project | `gitCommitGenerator` (`019e7e59-7caf-70a6-8756-f84a55b5d5fd`) |
| Final trace | `019fe12e-23ea-76c8-867e-1d9a9ce10928` |
| Gen pass 1 | `019fe12e-66fc-7b85-8bb7-acc20640c945` · `11:42:22Z`–`11:45:07Z` |
| Gen pass 2 (regen) | `019fe130-ea07-7257-9b0a-d62b337ea25b` · `11:45:07Z`–`11:47:35Z` |
| Run span | `_run_commit_generation` `019fe12e-23eb-72b3-a7f1-5c8b283a6a88` · `11:42:05Z`–`11:48:10Z` |
| Final log span | `019fe136-5a9b-7f81-b81e-cc980f738fca` · `11:51:03Z` |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` |
| Flags | `gold_strict=true`, `rank_arbitrate=true`, `strict=true` |


### Full analysis — dogfood G3

### Executive finding

G3’s diff is exactly the gold-strict truth plane: `GOLD_SKELETON_FALLBACK_FINAL`, `GOLD_PROCESS_META_BODY`, path-class SemVer/type mismatch codes, fixture product framing, docs implementation claims, plus exhaustion-harness seed alignment. The **message failed to name those codes**. Worse, regeneration moved from a nearer-gold first subject to a vaguer final subject, and telemetry still looked “clean.”

### Identity / evidence table

| Axis | Actual (raw) | Gold | Match? |
| --- | --- | --- | --- |
| Emoji / type | `🦺 fix` | `🦺 fix` | ✅ |
| Scope | `commit_gold` (underscore) | `commit-gold` | ❌ |
| Subject | `harden commit message validation rules` | `fail skeleton fallback and path-class product framing` | ❌ |
| SemVer | `PATCH` | `PATCH` | ✅ |
| Change-Types | `fix, test` | `fix, test` | ✅ |
| Changelog-Groups | `Fixed, Tests` | `Fixed, Tests` | ✅ |
| Inventory | 1 bullet | 5 bullets naming codes + harness | ❌ |
| Body | generic quality/ceilings | final-truth codes + exhaustion seed | ❌ |

### Generation cycle

| Pass | Subject / body signal | Notes |
| --- | --- | --- |
| **1** | `enforce gold-strict fallback & meta phrase checks` · body names skeleton fallbacks + process-meta + path-class ceilings | **Nearer gold**; still underscore scope; no code IDs |
| **2 (final)** | `harden commit message validation rules` · generic auto-generated/low-quality + ceilings | **Regression**; inventory collapsed to one test bullet |
| Final accept | raw tip as pass 2 | `ai_accepted` |

Prior operator telemetry (series notes) recorded for the final envelope:

* `path_class_gate: empty`
* `gold_mode: strict` · `gold_findings_count: 0` · `gold_blocked: false` · `gold_regen_attempts: 0` (**counter lie** — a regen span exists)
* `contract_locked_semver: PATCH`
* `scope_normalised_from: none`
* Online: `format_compliance/has_body/scope_present = 0.0` with `user_acceptance = 1.0`

### Direct prompt / model evidence

**Pass 1 plan (better):**

* Primary: `validation_update` / `fix` / `commit_gold` / *enforce gold-strict fallback & meta phrase checks* / `PATCH`
* Body explicitly referenced skeleton fallbacks and process-meta phrasing

**Pass 2 plan (accepted):**

* Primary: same intent family, subject **genericised** to *harden commit message validation rules*
* Body dropped code-level specificity; inventory became a single `test(commit_gold)` coverage bullet
* Never emitted canonical scope `commit-gold`
* Never listed `GOLD_SKELETON_FALLBACK_FINAL`, `GOLD_PROCESS_META_BODY`, path-class codes, or the main exhaustion seed change

### Causal chain

1. Diff is pure gold-strict **product** work on `commit_gold` + tests — correct type/SemVer family.
2. Ranker/contract stayed on `validation_update` / `PATCH` (acceptable type-level).
3. **Scope normaliser absent** → `commit_gold` underscore survived both passes.
4. Guard/regen path fired (two `generate_commit_message` spans) likely reacting to process-meta / wording pressure.
5. Regen **optimised for safer generic validation prose**, erasing the specific failure modes the commit exists to name.
6. Gold-strict on the **outgoing** message did not require code-ID inventory or canonical scope → `gold_findings_count: 0`, `gold_blocked: false`.
7. `gold_regen_attempts: 0` despite a real second generation → telemetry integrity gap.
8. Accepted → raw `7db174c`.

### Gold delta (what rewrite restored)

```text
🦺 fix(commit-gold): fail skeleton fallback and path-class product framing
… body names final-truth codes …
Included changes:
- GOLD_SKELETON_FALLBACK_FINAL + PROCESS_META_BODY
- path-class SemVer ceiling and type mismatch codes
- fixture product framing + docs implementation claims
- strict fail locks
- exhaustion seed body + title-case after scope normalise
SemVer-Impact: PATCH
Change-Types: fix, test
Changelog-Groups: Fixed, Tests
```

Applied via in-progress rebase amend + continue; tree `6fdd76e0…` preserved. Final tip parent chain: `6e71f29` → `0374e57` → `722e588`.

### Prevention controls (G3-facing)

| ID | Control | Why |
| --- | --- | --- |
| P-G3-1 | Final-truth gold lint **blocks** skeleton provenance, process-meta body, path-class product framing on accept | This commit’s entire purpose |
| P-G3-2 | Regen must be **monotone w.r.t. specificity** (no genericisation of named controls) | Pass1→Pass2 regression |
| P-G3-3 | Canonical scope normaliser: `commit_gold` → `commit-gold` before gold + render | Underscore miss |
| P-G3-4 | Deterministic inventory from symbol/code deltas (`GOLD_*` constants, test names) | 1 vs 5 bullets |
| P-G3-5 | Persist accurate `gold_regen_attempts`, `gold_findings_count`, `gold_blocked` | Counter showed 0 with regen present |
| P-G3-6 | Validate **rendered** message text, not only plan schema / score_card | score_card all-true while gold-miss |
| P-G3-7 | Exhaustion harness seeds must remain multi-code after overlay scope normalise | Part of G3 product; message must cite it |

### Canonical references

* Raw: `7db174c` · Gold: `0374e57` · Tree: `6fdd76e0`
* Trace: `019fe12e-23ea-76c8-867e-1d9a9ce10928`
* Files: `src/git_cg/commit_gold.py`, `tests/test_commit_gold.py`, `tests/test_main.py`
* Codes: `GOLD_SKELETON_FALLBACK_FINAL`, `GOLD_PROCESS_META_BODY`, `GOLD_PATH_CLASS_SEMVER_CEILING`, `GOLD_PATH_CLASS_TYPE_MISMATCH`, `GOLD_FIXTURE_PRODUCT_FRAMING`, `GOLD_DOCS_IMPLEMENTATION_CLAIM`


---
## Dogfood G4 (promoted from `5226058788`)

## #204 Session 12 dogfood failure analysis — G4 (fixture corpus pins)

> [!NOTE]
>
> **Purpose:** Full-depth gold-miss reconstruction for **Session 12 dogfood G4** (TIP-G2 / P9-G5 / S9-H / V12-A letter-A fixture envelope pins).
>
> **Series:** G2 · G3 · **G4 (this)**.
>
> **Prior Session 12 archives:** [primary](./session-12.md) · [G3 cont](./session-12-g3.md) · [G4 cont](./session-12-g4.md) · [synth](./session-12-synthesis.md)
>
> **Scope:** Message craft only. Pure fixtures + claims test. Tree preserved.

---

## 🧪 Incident evidence — G4 (2026-08-08)

**Result:** **G4 misses gold** on emoji/type, SemVer, Change-Types, Changelog-Groups, subject, and inventory. Scope `fixtures` matched.

**One-line diagnosis:** Fixture paths never became an authoritative test-family envelope (`path_class_gate: empty`), so ranking kept `validation_update` / `fix` / `PATCH` and the model described “aligning evaluation fixtures” as a product validation fix instead of `✅ test` / `NONE` corpus pins.

| Field | Value |
| --- | --- |
| Group | **G4** |
| Path focus | `tests/fixtures/commit_quality/*`, `tests/test_v12_a_claims.py` |
| Severity | **Critical** (wrong type + SemVer on pure non-product) |
| Raw SHA | `657c6e5f09acfc4548a0be4ea15ffe73661d6f10` |
| Gold SHA | `722e588de1d7b99c89c0fe5c7c1337a7ef4e73e0` |
| Tree (unchanged) | `9a67ffff975ced73057c5678d58e263fad3d4d5e` |

### Opik identity

| Field | Value |
| --- | --- |
| Project | `gitCommitGenerator` (`019e7e59-7caf-70a6-8756-f84a55b5d5fd`) |
| Final trace | `019fe136-d9db-7cf4-9c7d-d93078723db6` |
| Generation / LLM span | `019fe136-db7b-7b1d-9eb0-54ce3ccd6f92` |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` |
| Window | gen `2026-08-08T11:51:36Z`–`11:55:07Z`; final telemetry `11:56:20Z` |
| Engine | `lmlx` · provenance `ai_accepted` |


### Full analysis — dogfood G4

### Executive finding

G4 is a **fixtures-only + claims-test** pin commit. Gold law is hard: `✅ test(fixtures)`, `SemVer-Impact: NONE`, `Change-Types: test, docs`, `Changelog-Groups: Tests, Documentation`, with named TIP-G2 / P9-G5 / S9-H / V12-A inventory. Actual shipped `🦺 fix` / `PATCH` / `Fixed` because path-class never gated the contract and content signals still looked like “validation.”

### Identity / evidence table

| Axis | Actual (raw) | Gold | Match? |
| --- | --- | --- | --- |
| Emoji / type | `🦺 fix` | `✅ test` | ❌ |
| Scope | `fixtures` | `fixtures` | ✅ |
| Subject | `align evaluation fixtures with test classification` | `pin fixture paths to the test/NONE corpus envelope` | ❌ |
| SemVer | `PATCH` | `NONE` | ❌ |
| Change-Types | `fix, test` | `test, docs` | ❌ |
| Changelog-Groups | `Fixed, Tests` | `Tests, Documentation` | ❌ |
| Inventory | 1 (`test(claims)`) | 5 (TIP-G2, P9-G5/S9-H, goldens, letter A, V12-A) | ❌ |

### Generation cycle

| Step | Observation |
| --- | --- |
| Diff files | `README.md`, `corpus.json`, `eval_an.json`, `goldens.json`, `test_v12_a_claims.py` under fixtures/claims |
| Ranked primary | `validation_update` **100.5** (validation_hardened/added, schema_validation_changed) |
| `tests_update` rank | **26.0** (not competitive) |
| Confidence | **medium** · margin `20.5` · path `skipped_high_medium` (no menu) |
| Presentation fallback | `none` |
| `path_class_gate` | **`empty`** |
| `staged_paths` | **`[]`** |
| Contract | `fix` / `PATCH` locked · lift not applied |
| Gold-strict | `strict` · findings `0` · blocked `false` · regen `0` |
| Semantic parse | json + markdown + python OK |
| Fingerprints | formatting_only 1 · noop 1 · structural 3 |
| Claim tags seen | `P9-A05`, `P9-B07`, `P9-B10` (not elevated to envelope authority) |
| Online scores | format/body/scope `0.0`; acceptance `1.0` |

### Direct prompt / model evidence

* Plan primary: `validation_update` / `fix` / `fixtures` / *align evaluation fixtures with test classification* / **`PATCH`** / `Fixed`
* Secondary: `tests_update` / `claims` / *update assertion expectations*
* Body correctly noticed docs→test realignment across corpus/eval/goldens, then **kept validation framing** and PATCH.
* No hard override to `✅ test` + `NONE` despite pure fixture paths.
* Named fixtures TIP-G2, P9-G5, S9-H, letter-A map absent from inventory.

### Causal chain

1. Staged paths are almost entirely under `tests/fixtures/commit_quality/` (+ one claims test).
2. Path-class gate still **`empty`** / `staged_paths: []` → fixtures_only envelope never became contract authority.
3. Content/schema tokens inside JSON goldens fired **validation_*** signals → `validation_update@100.5`.
4. Medium confidence skipped arbitration; contract stayed `fix/PATCH`.
5. Model described the symptom (“align … with test classification”) as a **fix**, not a **test/docs pin**.
6. Gold-strict path-class ceilings (added in G3) did not fire on this accept (`gold_findings_count: 0`) — either path family still unknown at gold time, or final message lint not wired to pure-fixtures type/SemVer law.
7. Accepted → raw `657c6e5`.

### Gold delta (what rewrite restored)

```text
✅ test(fixtures): pin fixture paths to the test/NONE corpus envelope
… TIP-G2, P9-G5/S9-H, atomic goldens, letter A map, V12-A claim surface …
SemVer-Impact: NONE
Change-Types: test, docs
Changelog-Groups: Tests, Documentation
```

Message-only; tree `9a67ffff…` preserved. Current branch tip: `722e588`.

### Prevention controls (G4-facing)

| ID | Control | Why |
| --- | --- | --- |
| P-G4-1 | Hard **fixtures_only → test / NONE / Tests** envelope before ranking | Stops validation_update domination on JSON goldens |
| P-G4-2 | Hard type/SemVer/changelog overrides for pure fixtures/tests/docs | `fix/PATCH/Fixed` must be impossible here |
| P-G4-3 | Deterministic inventory from fixture IDs (TIP-G2, P9-G5, S9-H, V12-A) | 1 generic bullet vs 5 named pins |
| P-G4-4 | Treat fixture README/map edits as **docs secondary**, not product docs dual-pressure | Gold `test, docs` / `Tests, Documentation` |
| P-G4-5 | Gold final-truth: pure fixtures + `fix`/`PATCH` ⇒ block | G3 codes must actually fire |
| P-G4-6 | Second-chance path harvest must populate `staged_paths` + `path_class_gate` | Both empty in telemetry |
| P-G4-7 | Claim tags / corpus row IDs should bias subject toward pin language, not “align classification” | Subject miss |

### Canonical references

* Raw: `657c6e5` · Gold: `722e588` · Tree: `9a67ffff`
* Trace: `019fe136-d9db-7cf4-9c7d-d93078723db6`
* Files: `tests/fixtures/commit_quality/{README.md,corpus.json,eval_an.json,goldens.json}`, `tests/test_v12_a_claims.py`
* Depends on G2 envelope + G3 final-truth — dogfood proves both were not yet authoritative at message accept time


---

## Package cross-links

| Need | Link |
|:---|:---|
| Residual S12 synthesis | [`session-12-synthesis.md`](./session-12-synthesis.md) |
| Later package self-dogfood | [`quality-package-regime-b.md`](./quality-package-regime-b.md) |
| METHOD post-control class | [`../../METHOD.md`](../../METHOD.md) §3 |
| Prevention backlog | [`../../PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) |

### Promotion record

| Field | Value |
|:---|:---|
| Promoted on | 2026-08-13 |
| From | #204 comments `5226058599` / `5226058718` / `5226058788` |
| SSOT rule | Package path wins |

---

## Document control

| Field | Value |
|:---|:---|
| Case ID | 204-S12-DF-G2G4 |
| Status | active / full |
| Last updated | 2026-08-13 |
