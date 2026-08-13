# SYNTHESIS — Session 12 · cross-commit residual close-out (G1–G4)

> **Status:** active / full  
> **Copy lineage:** promoted from [#204 comment 5215611559](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215611559)  
> **Method:** [`../../METHOD.md`](../../METHOD.md) §4 regimes + §13  
> **Template:** [`../../templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md`](../../templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md)  
> **Package version:** `1.0.0-combine`  
> **Per-tip homes:** [`session-12.md`](./session-12.md) (G1) · [`session-12-g2.md`](./session-12-g2.md) (G2) · [`session-12-g3.md`](./session-12-g3.md) (G3) · [`session-12-g4.md`](./session-12-g4.md) (G4) · [`session-12-dogfood-g2-g4.md`](./session-12-dogfood-g2-g4.md) (dogfood)  
> **Related dogfood:** [`quality-package-regime-b.md`](./quality-package-regime-b.md) (later Regime B on this package)  
> **Consumer:** eval harness [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) — `session-12-seed`, F72–F80, P-S12-1…9  
> **Authority:** this file is package SSOT for Session 12 systems synthesis. GitHub comment is intake/archive only.

```yaml
package: commit-message-failure-analysis
doc: cross-commit-synthesis
version: 1.0.0-combine
status: active
issue: 204
series_id: 204-S12
series_class: residual-close-out
regime_mix: A+B
opik: bound
sources:
  - github:issue-comment:5215611559
  - github:issue-comment:5213748048
  - github:issue-comment:5215148242
  - github:issue-comment:5215440216
  - case:204/session-12.md
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** S12-G1–G4 all miss gold · regimes **A+B**  
**Class mix:** one Regime **A** fallback/process-meta catastrophe (G1) + three Regime **B** clean wrong acceptances (G2–G4)  
**Base → gold tip:** `2e965c5` → `3b96ed6` (message-only; trees preserved per tip)  
**Trees preserved per tip:** G1 `5e91ec2d…` · G2 `484ec724…` · G3 `3f4b7227…` · G4 `a49e73a7…`  
**One-line series diagnosis:** Correct 4-way split and trees; G1 destroyed a near-right feat contract via contradictory body policy → guard thrash → skeleton fallback; G2–G4 locked `fix`/`PATCH` on fixtures/tests/docs with empty `path_class_gate` and zero gold-strict findings; prepare re-entry on message-only (**F80**).  
**IDs covered:** F72–F80 · P-S12-1…9  

| Group | Path focus | Severity | Regime | Gold subject (short) | Case link |
|:---|:---|:---|:---|:---|:---|
| G1 | `src/git_cg/commit_quality.py` | Critical | **A** | `feat(commit-quality): add Session 6 scope, capability, and guard laws` | [`session-12.md`](./session-12.md) |
| G2 | fixtures / corpus / goldens | Critical | **B** | `test(fixtures): pin Session 6 corpus rows TIP-G13–G17` | [`session-12-g2.md`](./session-12-g2.md) |
| G3 | `tests/test_v12_a_claims.py` | Critical | **B** | `test(commit-quality): add V12-A named proof pack a01–a45` | [`session-12-g3.md`](./session-12-g3.md) |
| G4 | `README.md` + `CHANGELOG.md` | High | **B** | `docs(readme): document Session 6 residuals and V12-A proof pack` | [`session-12-g4.md`](./session-12-g4.md) |

### Archive open summary (promoted)

### 🧪 Session 12 cross-commit synthesis (2026-08-07)

**Result:** **S12-G1–G4 all miss gold.** Grouping was correct; every tip failed message craft / envelope / recovery law.  
**Class mix:** one **fallback/process-meta catastrophe** (G1) + three **clean wrong acceptances** (G2–G4).  
**Series:** raw `5117f60` → `db30534` → `0c7a9b7` → `f4aa2de` rewritten message-only to gold `4aa90a8` → `f5e55b7` → `19bd551` → `3b96ed6`.  
**Trees preserved per tip:** G1 `5e91ec2d…` · G2 `484ec724…` · G3 `3f4b7227…` · G4 `a49e73a7…`.

| Tip | Paths | Severity | Failure class | Gold subject (short) | Full depth |
| --- | --- | --- | --- | --- | --- |
| **G1** | `src/git_cg/commit_quality.py` | **Critical** | Fallback / process-meta | `feat(commit-quality): add Session 6 scope, capability, and guard laws` | [G1 case](./session-12.md) |
| **G2** | fixtures / corpus / goldens / harness | **Critical** | Clean wrong acceptance | `test(fixtures): pin Session 6 corpus rows TIP-G13–G17` | [G2 case](./session-12-g2.md) · [archive](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) |
| **G3** | `tests/test_v12_a_claims.py` | **Critical** | Clean wrong acceptance | `test(commit-quality): add V12-A named proof pack a01–a45` | [G3 case](./session-12-g3.md) · [archive](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215148242) |
| **G4** | `README.md` + `CHANGELOG.md` | **High** | Clean wrong acceptance + attribution bleed | `docs(readme): document Session 6 residuals and V12-A proof pack` | [G4 case](./session-12-g4.md) · [archive](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215440216) |

> [!IMPORTANT]
> ### Series one-line diagnosis:
> Session 6 residual close-out shipped **correct trees** and a **correct 4-way split**, but the generator failed two complementary ways: (1) **G1** locked the right product family then destroyed it via contradictory body policy → guard thrash → skeleton fallback with process-meta prose; (2) **G2–G4** never needed fallback — false validation/runtime/secret signals + empty `path_class_gate` locked `fix`/`PATCH` on fixtures, pure tests, and pure docs, and `gold_strict=true` accepted coherent-but-wrong envelopes with zero findings. Across G2–G4, prepare-commit-msg still re-entered `git-cg` on message-only paths (**F80**).

**IDs covered:** F72–F80 · P-S12-1…9

---

# Full systems synthesis (promoted)

> Interior of the archive HTML details block — regimes, matrices, F72–F80, P-S12-1…9, root causes, acceptance tests. Heading substance unchanged; links retargeted to package paths where promoted.

## 1. Series identity map

| Field | G1 | G2 | G3 | G4 |
| --- | --- | --- | --- | --- |
| Raw tip | `5117f60` | `db30534` | `0c7a9b7` | `f4aa2de` |
| Gold tip | `4aa90a8` | `f5e55b7` | `19bd551` | `3b96ed6` |
| Tree | `5e91ec2d…` | `484ec724…` | `3f4b7227…` | `a49e73a7…` |
| Path class (truth) | product `src/**` | fixtures/tests | pure tests | pure docs |
| Final telemetry trace | `019fda92-4f84-…` | `019fdaa0-7067-…` | `019fdaac-e249-…` | `019fdabf-61fb-…` |
| Provenance | fallback success path | `ai_accepted` | `ai_accepted` | `ai_accepted` |
| LLM attempts | 3 + skeleton fallback | 1 | 1 | 1 |
| `path_class_gate` | empty / non-authoritative | empty | empty | empty |
| `gold_strict` | on; did not block fallback final | on; 0 findings | on; 0 findings | on; 0 findings |
| Contract lift | N/A (fallback rewrote family) | reinforced PATCH | NONE→PATCH | NONE→PATCH |
| Prepare re-entry | series process issue | yes (~early exit) | yes (~6 ms) | yes (~6.5 ms) |

### Observed subjects (do not regress)

```text
S12-G1 ❌  fallback/process-meta path — chore/NONE + diagnostic body + snake scope
S12-G1 ✅  ✨ feat(commit-quality): add Session 6 scope, capability, and guard laws

S12-G2 ❌  🦺 fix(fixtures): add TIP-G13–G17 validation goldens · PATCH · ai_accepted
S12-G2 ✅  ✅ test(fixtures): pin Session 6 corpus rows TIP-G13–G17 · NONE

S12-G3 ❌  🦺 fix(test): add V12-A claim proof pack tests · PATCH · fix
S12-G3 ✅  ✅ test(commit-quality): add V12-A named proof pack a01–a45 · NONE · test

S12-G4 ❌  🦺 fix(commit-quality): add Session 6 residuals and scope law · docs-only attribution bleed
S12-G4 ✅  📝 docs(readme): document Session 6 residuals and V12-A proof pack · NONE · docs
```

---

## 2. Two failure regimes (not four unrelated bugs)

Session 12 is best understood as **two regimes** that share missing path-class authority and weak gold-strict truth checks.

### Regime A — G1: controls fire, recovery makes it worse

```text
healthy product diff
→ ranker near-tie validation_update 100.5 vs feature_addition 100.0
→ contract lock wins feature_addition / feat / MINOR
→ prompt emits contradictory body policy:
     guard bans Context:/Changes:
     low-confidence / skeleton path requires Context:/Changes:
→ attempt 1 emits banned template
→ GUARD_CONTEXT_CHANGES_TEMPLATE fires
→ retries keep prior plan + keep contradictory skeleton
→ budget exhausted
→ apply_guard_skeleton_fallback → chore/NONE + process-meta body
→ written as successful final message under gold_strict
```

**Primary defect:** self-contradictory regeneration policy + operator-visible fallback.  
**IDs:** F72 / F73 / F74 / F75 · P-S12-1 / P-S12-2 / P-S12-3 / P-S12-5

### Regime B — G2/G3/G4: controls never fire; wrong envelope looks perfect

```text
non-product tip (fixtures | pure tests | pure docs)
→ semantic/fingerprint or prose signals emit validation/runtime/secret markers
→ validation_update scores ~100.5
→ correct family (tests_update / documentation_update) stays ~21–26
→ path_class_gate empty; no claim/docs harvest; no gold guidance
→ contract locks fix / PATCH
→ contract lift reinforces PATCH from NONE
→ single LLM faithfully obeys wrong contract
   (often while internally noting “this is tests/docs”)
→ gold_findings_count = 0; scorecard green; ai_accepted
```

**Primary defect:** missing hard live path-class envelopes + signal quarantine + inventory/attribution truth in gold-strict.  
**IDs:** F76 / F77 / F78 / F79 · P-S12-4 / P-S12-6 / P-S12-7 / P-S12-8

### Shared process defect — all rebuild tips

Prepare-commit-msg still invokes `git-cg` on message-only rebuilds even with `--no-verify` / `commit_source=message` early-exit paths. Non-clobbering on G2–G4, but still **F80 / P-S12-9**.

---

## 3. Comparative matrix — what each tip got wrong

| Dimension | G1 raw | G2 raw | G3 raw | G4 raw | Gold law |
| --- | --- | --- | --- | --- | --- |
| Primary type | `chore` (after fallback; contract had been `feat`) | `fix` | `fix` | `fix` | feat / test / test / docs |
| SemVer | `NONE` (fallback) | `PATCH` | `PATCH` | `PATCH` | PATCH-or-feat family / NONE / NONE / NONE |
| Scope | snake `commit_quality` | `fixtures` | `test` | `commit-quality` | `commit-quality` / `fixtures` / `commit-quality` / `readme` |
| Body posture | process meta / skeleton | enforce validation | validate / ensure guards met | establish / clarify guards | implement laws / pin corpus / add proof pack / document prior work |
| Inventory | collapsed / missing named laws | 2 generic vs 5 TIP rows | none vs a01–a45 bands | 1 generic vs 4 docs surfaces | stable-ID / surface harvest required |
| Fallback theatre | **yes** | no | no | no | fallback must not be final |
| Attribution bleed | N/A (wrong family) | characterisation→product | characterisation→product | **docs→product** | docs/tests must not claim implement |
| Acceptance mode | fallback success | `ai_accepted` | `ai_accepted` | `ai_accepted` | block wrong envelope |

### Ranking contamination pattern (G2–G4)

| Tip | Top wrong intent | Score | Correct family | Score | Margin / confidence |
| --- | --- | --- | --- | --- | --- |
| G2 | `validation_update` | ~100.5 | `tests_update` / snapshot family | ~26 | high enough to skip useful correction |
| G3 | `validation_update` | **100.5** | `tests_update` | **26.0** | medium 20.5; still `skipped_high_medium` |
| G4 | `validation_update` | **100.5** | `documentation_update` | **21.5** | **high 38.0**; arbitration skipped |

**Invariant (observed across documented G2–G4):** once false validation markers exist and path-class is empty, `validation_update@100.5` is the Session 12 attractor for the documented non-product tips in this series. Do not generalise beyond G2–G4 without additional evidence.

### Signal sources that poisoned Regime B

| Tip | Contaminating evidence (direct) |
| --- | --- |
| G2 | Fixture JSON / harness text → validation/schema + false capability/runtime markers |
| G3 | Add-only test AST → `new_api`, `new_user_facing_capability`, `functional_code_changed`, exception-handling markers |
| G4 | Markdown/changelog prose → `runtime_logic_changed`, validation_*, `secret_reference_changed` |

Parser health was **not** the discriminator. G3/G4 parsers “succeeded.” The failure is **interpretation + envelope authority**, not extraction outage.

---

## 4. Failure ID map (F72–F80) across the series

| ID | Failure mode | G1 | G2 | G3 | G4 | Prevention |
| --- | --- | --- | --- | --- | --- | --- |
| **F72** | Guard/skeleton fallback shipped as final | ● | | | | P-S12-1 |
| **F73** | Process meta leaked into body | ● | | | | P-S12-2 |
| **F74** | Snake scope vs series canon | ● | | | | P-S12-3 |
| **F75** | Type/SemVer collapse on product API add | ● | | | | P-S12-5 |
| **F76** | fixtures/tests typed `fix` | | ● | ● | | P-S12-4 |
| **F77** | docs_only typed `fix` + attribution bleed | | | | ● | P-S12-4 / P-S12-7 |
| **F78** | Inventory under-claim / generic collapse | ● | ● | ● | ● | P-S12-6 |
| **F79** | Validation/enforce overclaim on pure pins | | ● | ● | ● | P-S12-8 |
| **F80** | prepare-commit-msg still runs on message-only rebuild | series | ● | ● | ● | P-S12-9 |

**Read across:**

* **F78 is the only content ID on all four tips** — harvest/inventory is a series-wide weakness spanning product laws, TIP rows, V12-A bands, and docs surfaces.
* **F76/F77/F79 are the Regime B cluster** — same envelope miss expressed on fixtures, tests, and docs.
* **F72–F75 are G1-local** but prove gold-strict must treat fallback/process-meta as hard failure even when earlier ranking was closer to truth.
* **F80 is process-global** for message-only rebuild methodology.

---

## 5. Prevention rules (P-S12-1…9) — systems reading

| Rule | Requirement | Closes | Why series proves it |
| --- | --- | --- | --- |
| **P-S12-1** | If `presentation_fallback_reason != none` **or** body matches skeleton/fallback templates, gold-strict **must fail** (`GOLD_SKELETON_FALLBACK_FINAL`). | F72 | G1 wrote fallback as success |
| **P-S12-2** | Body denylist: `Cleared guard codes`, `Deterministic presentation fallback`, `guard exhaustion`, `presentation-safe`, `apply staged presentation-safe changes`. | F73 | G1 process-meta leakage |
| **P-S12-3** | Force hyphenated scopes (`commit-quality`, …). Reject snake `commit_quality`. | F74 | G1 scope canon break |
| **P-S12-4** | Hard live envelope: pure `tests/**` ⇒ `test`+`NONE`; fixtures corpus/goldens ⇒ primary `test` (docs secondary); pure docs ⇒ `docs`+`NONE`. | F76 / F77 | G2–G4 attractor |
| **P-S12-5** | Product policy adds introducing named laws/guards/capability tags ⇒ primary `feat` (fix secondaries ok), SemVer ≥ `PATCH`; forbid `chore`/`NONE` collapse. | F75 | G1 fallback destroyed correct feat family |
| **P-S12-6** | Characterisation / docs commits must inventory stable IDs and named surfaces (TIP-G13–G17; V12-A01–A45; named guards/capabilities; README/CHANGELOG rows). | F78 | all four tips under-claimed |
| **P-S12-7** | Docs-only tips may reference prior laws by name but must not claim to add/implement product guards from earlier commits. | F77 | G4 “add/establish” on docs-only |
| **P-S12-8** | Ban validate/enforce/implement framing on pure fixture pins, proof packs, and docs-of-prior-work; prefer pin/lock/cover/freeze/characterise/document/record. | F79 | G2–G4 verb overclaim |
| **P-S12-9** | Message-only rebuild: primary control is `GIT_CG_SKIP_PREPARE=1` (truthy: `1`/`true`/`yes`/`on`). Under hk, `core.hooksPath=/dev/null` is unsupported as a prepare short-circuit. `--no-verify` alone is insufficient. | F80 | G2–G4 re-entry (+ rebuild methodology) |

### Control stack that would have saved the series

```text
                    ┌──────────────────────────────┐
                    │  path_class_gate (authoritative) │
                    │  product | fixtures | tests | docs │
                    └──────────────┬───────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
   product envelope         tests/fixtures envelope     docs envelope
   feat(+fix 2°)            test + NONE                 docs + NONE
   SemVer floor PATCH       forbid fix/PATCH            forbid fix/PATCH
           │                       │                       │
           └───────────┬───────────┴───────────┬───────────┘
                       ▼                       ▼
              signal quarantine          inventory harvest
         (no validation/runtime from   (TIP / V12-A / rows)
          fixture JSON, test AST,
          markdown prose alone)
                       │                       │
                       └───────────┬───────────┘
                                   ▼
                        gold_strict truth layer
              fallback≠final · no process meta · no snake scope
              no attribution bleed · no enforce-on-pins
                                   │
                                   ▼
                        contract lift ceilings
                   never raise tests/docs NONE → PATCH
```

Without the top gate, G2–G4 are overdetermined losses. Without fallback≠final, G1 remains a success-path landmine even when ranking is closer.

---

## 6. Regime comparison — why G1 is not “the same bug” as G2–G4

| Question | G1 | G2–G4 |
| --- | --- | --- |
| Did the system understand the diff class at all? | Yes (product feature posture locked) | Superficially yes; semantically no (wrong family locked) |
| Did presentation guards fire? | Yes (template ban) | No |
| Did regeneration help? | No — amplified contradiction | N/A (single attempt) |
| Was the final message Hybrid-shaped and locally coherent? | No (process meta / chore collapse) | **Yes** — that is the danger |
| Would better wording alone have fixed it? | No; policy contradiction + fallback | No; envelope/lock wrong before wording |
| Dogfood irony | Series implementing body/guard laws failed its own body/guard recovery | Series pinning/proving residual locks failed to apply those locks live |

**Complementarity:** fixing only Regime A leaves silent wrong acceptances. Fixing only Regime B leaves fallback laundering. Session 12 requires both.

---

## 7. Dogfood irony (why this series is high-value evidence)

Session 12 is the close-out that **adds and proves** the very laws the generator then violated:

| Tip content | Law being landed / pinned | Live violation on that tip |
| --- | --- | --- |
| G1 product | scope law, capability dominance, evaluator verbs, Context:/Changes ban, attribution bleed | Context:/Changes contradiction + fallback final + snake scope + chore/NONE collapse |
| G2 fixtures | TIP-G13–G17 residual pins | fixtures typed `fix`/`PATCH`; enforce overclaim; thin TIP inventory |
| G3 V12-A pack | named proof pack a01–a45; presentation purity; ranker never called | pure tests typed `fix`/`PATCH`; validate framing; no band inventory |
| G4 docs | operator residuals + scope law + V12-A pointer | docs typed `fix`/`PATCH`; claims to add/establish prior laws |

This is not archaeological nitpicking. It is **same-day dogfood** that the residual close-out’s own generator path does not yet obey residual law.

---

## 8. Cross-cutting root causes (ordered by leverage)

### RC1 — `path_class_gate` is observational, not authoritative

Empty on G2–G4 despite obvious fixtures/tests/docs-only paths. No late envelope correction after contaminated ranking.

### RC2 — signal extraction trusts prose/AST shapes over path priors

* Fixture JSON mentions validation → `validation_*`
* Test helpers/try forms → capability/runtime markers
* README/CHANGELOG describe guards/secrets → validation/secret/runtime markers

### RC3 — contract lock + lift freeze the wrong family

Once `validation_update`/`fix`/`PATCH` is locked, the LLM is instructed not to escape. Lift then promotes/holds `PATCH` from `NONE`, laundering the error as contract consistency (`contract_consistent=1` via lift on G3/G4).

### RC4 — gold_strict scores shape/coherence, not path-class truth

Zero findings on G2–G4 despite wrong type/SemVer/inventory/attribution. G1 fallback also not treated as non-final under strict gold.

### RC5 — inventory harvest is absent

No required emission of TIP IDs, V12-A bands, named guards/capabilities, or docs surfaces into Included-changes. F78 spans the whole series.

### RC6 — regeneration policy can be self-hostile (G1-only but critical)

Banned template remains required by skeleton/low-confidence guidance; retries replay the ban; fallback becomes the user-visible commit.

### RC7 — message-only rebuild still couples to prepare-commit-msg

F80 is methodological: File Method / `--no-verify` does not isolate `git-cg` from hook re-entry.

---

## 9. Minimal corrective programme (implementation order)

### P0 — stop silent wrong envelopes and fallback finals

1. **Authoritative path-class envelopes** (P-S12-4) before rank lock and again pre-accept.
2. **gold_strict hard fails** on:
   * fallback/process-meta final (P-S12-1/2)
   * path-class type/SemVer mismatch
   * docs attribution bleed (P-S12-7)
   * enforce/validate framing on pins/proof/docs-of-prior-work (P-S12-8)
3. **Contract lift ceilings:** tests/docs path class ⇒ max SemVer `NONE`.

### P1 — remove the attractor fuel

1. **Signal quarantine** by path class:
   * fixtures/tests: demote validation/capability/runtime from fixture JSON and test AST alone
   * docs: demote runtime/validation/secret from Markdown/changelog prose alone
   * enable changelog anti-signal for Unreleased bullets on docs-only tips
2. **Contradictory prompt assembly fix** (G1): never inject Context:/Changes skeleton when guard bans it; on `GUARD_CONTEXT_CHANGES_TEMPLATE`, switch body strategy instead of replaying.

### P2 — restore truthful inventory and scope canon

1. **Stable-ID / surface harvest** (P-S12-6) for TIP-G*, V12-A*, GUARD_*, CAPABILITY_*, INVALID_FINAL_SCOPES, README rows, Unreleased bullets.
2. **Scope canon** (P-S12-3/5): hyphenated module scopes; product law tips stay `commit-quality`; proof packs don’t collapse to `test`.

### P3 — rebuild methodology

1. **P-S12-9** default for message-only gold rebuilds: prefer `GIT_CG_SKIP_PREPARE=1` (hk-compatible); do not rely on `core.hooksPath=/dev/null` under hk-managed installs.

### Acceptance tests the series itself demands

| Test fixture idea | Must assert |
| --- | --- |
| G1-shaped product law add with banned template pressure | no fallback final; no process meta; feat family preserved or blocked—not chore success |
| G2-shaped TIP corpus pin | primary `test`+`NONE`; TIP-G13–G17 inventory; no enforce wording |
| G3-shaped V12-A pack add-only | primary `test`+`NONE`; a01–a45 / band inventory; no validate-as-runtime wording |
| G4-shaped README+CHANGELOG only | primary `docs`+`NONE`; no add/establish product verbs; four-surface inventory |
| Message-only rebuild | no prepare-commit-msg `git-cg` generation path |

---

## 10. What Session 12 does *not* show

* **Not a grouping failure.** 4-way split matched plan; trees per tip are clean.
* **Not an LLM-only failure.** G2–G4 models often *noticed* tests/docs and still obeyed locked wrong contracts; G1 failed in recovery policy after a reasonable feature lock.
* **Not parser outage.** Semantic/fingerprint paths were frequently “healthy.”
* **Not operator mishandling as root cause.** `ai_accepted` on G2–G4 accepted system-offered wrong envelopes under green scorecards.
* **Not a reason to weaken Hybrid trailers.** Gold rewrites preserved Refs/SemVer/Change-Types/Changelog-Groups discipline while correcting family and inventory.

---

## 11. Series verdict

Session 12 is a **complete four-tip dogfood proof** that commit presentation quality still fails closed in the wrong direction:

1. **When recovery runs (G1), it can destroy a better contract and publish internal diagnostics.**
2. **When recovery does not run (G2–G4), contaminated ranking + empty path-class + shape-only gold produces polished wrong envelopes.**
3. **Inventory harvest and attribution law are series-wide gaps (F78; F77/F79).**
4. **Message-only methodology still trips prepare-commit-msg (F80).**

The gold tip series (`4aa90a8` → `f5e55b7` → `19bd551` → `3b96ed6`) is the behavioural target. The raw series is the incident corpus. F72–F80 / P-S12-1…9 are the durable control backlog for #204 residual close-out.

### Evidence confidence (series-level)

| Claim | Confidence | Basis |
| --- | --- | --- |
| Correct grouping + tree-identical message-only gold | **Direct** | git trees + planned 4-way split |
| G1 fallback/process-meta regime | **Direct** | primary archive Opik reconstruction |
| G2–G4 clean wrong acceptance regime | **Direct** | primary + G3/G4 continuation Opik plans/raw tips |
| validation_update@~100.5 attractor on non-product tips | **Direct** | G2/G3/G4 ranked_candidates |
| empty path_class_gate on G2–G4 | **Direct** | final telemetry |
| gold_strict zero findings on wrong envelopes | **Direct** | G2–G4 telemetry |
| prepare re-entry on message-only | **Direct** | G2–G4 follow-on traces / rebuild notes |
| F72–F80 / P-S12-1…9 mapping | **Synthesised from direct** | per-tip archives above |

---

## Source map (package)

| Group | Full-depth case | GitHub archive | Opik (final telemetry family) |
|:---|:---|:---|:---|
| G1 | [`session-12.md`](./session-12.md) **active full** | [5213748048](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) | `019fda92-4f84-…` |
| G2 | [`session-12-g2.md`](./session-12-g2.md) **active full** | [5213748048](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5213748048) | `019fdaa0-7067-…` |
| G3 | [`session-12-g3.md`](./session-12-g3.md) **active full** | [5215148242](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215148242) | `019fdaac-e249-…` |
| G4 | [`session-12-g4.md`](./session-12-g4.md) **active full** | [5215440216](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215440216) | `019fdabf-61fb-…` |
| Synthesis | **this file** | [5215611559](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215611559) | series-level |

### Eval / epic pointers

| Consumer | How it uses this synthesis |
|:---|:---|
| [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) | Executive index for Opik harness; **must not** re-host F*/P* prose |
| [`docs/plans/opik-evaluation-harness.md`](../../../plans/opik-evaluation-harness.md) | `session-12-seed`, regime A/B, corpus law §7.4, F72–F80 metric wrapping |
| [`../../METHOD.md`](../../METHOD.md) | Genre + Regime A/B exemplars |
| [`../../FAILURE_TAXONOMY.md`](../../FAILURE_TAXONOMY.md) | F72–F80 |
| [`../../PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) | P-S12-1…9 |
| [#204](https://github.com/Thomo1318/gitCommitGenerator/issues/204) | Governing epic; comments = archive after promote |

### Promotion record

| Field | Value |
|:---|:---|
| Promoted on | 2026-08-13 |
| From | #204 comment `5215611559` |
| SSOT rule | Package path wins; comment retained as intake evidence |

---

## Document control

| Field | Value |
|:---|:---|
| Series ID | 204-S12 |
| Package version | `1.0.0-combine` |
| Status | active / full |
| Last updated | 2026-08-13 |
