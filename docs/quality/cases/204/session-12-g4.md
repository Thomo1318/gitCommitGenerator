# CASE — Session 12 · G4 residual close-out (Regime B)

> **Status:** active / full  
> **Copy lineage:** promoted from [#204 comment 5215440216](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215440216)  
> **Method:** [`../../METHOD.md`](../../METHOD.md)  
> **Template:** [`../../templates/CASE_TEMPLATE.md`](../../templates/CASE_TEMPLATE.md)  
> **Package version:** `1.0.0-combine`  
> **Series:** Session 12 · Session 6 residual close-out · message-only rebuild  
> **Siblings:** [`session-12.md`](./session-12.md) · [`session-12-g2.md`](./session-12-g2.md) · [`session-12-g3.md`](./session-12-g3.md) · [`session-12-synthesis.md`](./session-12-synthesis.md)  
> **Consumer:** eval harness [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) (`session-12-seed`)  
> **Authority:** this file is package SSOT for S12-G4. The GitHub comment is intake/archive evidence only.

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: active
issue: 204
case_id: 204-S12-G4
series_id: 204-S12
series_class: residual-close-out
regime: B
opik: bound
sources:
  - github:issue-comment:5215440216
  - git:raw:f4aa2de6c933c0b9abe0bcf33340ba4b8d51abbb
  - git:gold:3b96ed660cf90e04637298f8c7c9494dadae21ca
  - opik:trace:019fdabf-61fb-73f9-85e2-82d9835e153a
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** MISS gold · Regime **B** (clean wrong acceptance + attribution bleed)  
**Path focus:** `README.md` + `CHANGELOG.md`  
**Severity:** High  
**Raw → gold:** `f4aa2de6c933c0b9abe0bcf33340ba4b8d51abbb` → `3b96ed660cf90e04637298f8c7c9494dadae21ca`  
**Tree preserved:** yes · tree OID `a49e73a7…`  
**One-line diagnosis:** Pure docs tip accepted as `fix(commit-quality)` product add with attribution bleed (“add/establish guards”); empty path-class; thin surface inventory; gold_strict green.  
**IDs:** **F77** · **F78** · **F79** · **F80** · P-S12-4 · P-S12-6 · P-S12-7 · P-S12-8 · P-S12-9  
**Series class:** residual-close-out

| Field | Value |
|:---|:---|
| Issue | #204 |
| Case ID | 204-S12-G4 |
| Reviewer | Thomo1318 / Session 12 forensic archive |
| Date | 2026-08-07 (incident) · promoted 2026-08-13 |
| Library class (intended) | pure docs |
| Acceptance mode (raw) | `ai_accepted` |

### Observed subjects (do not regress)

```text
S12-G4 ❌  🦺 fix(commit-quality): add Session 6 residuals and scope law · docs-only attribution bleed
S12-G4 ✅  📝 docs(readme): document Session 6 residuals and V12-A proof pack · NONE · docs
```

---

## 1. Incident identity

| Field | Value |
|:---|:---|
| Governing issue | #204 |
| Child / slice | Session 12 · G4 of 4 |
| Branch | `refactor/204-commit-presentation-quality` |
| Message-only rebuild? | **yes** |
| Notes | Docs-path variant of Regime B envelope miss + F77 attribution bleed. |

### Rewrite map

| Role | SHA | Subject (short) | Tree OID |
|:---|:---|:---|:---|
| Git-raw | `f4aa2de6c933c0b9abe0bcf33340ba4b8d51abbb` | fix(commit-quality) residuals attribution bleed | `a49e73a7…` |
| Gold-final | `3b96ed660cf90e04637298f8c7c9494dadae21ca` | docs(readme): document Session 6 residuals and V12-A proof pack | `a49e73a7…` |

**Rewrite-map-confirmed:** yes

---

# Full-depth forensic body (promoted)


**Scope for this section:** G4 only. G1/G2 live in the [primary Session 12 archive](./session-12.md). G3 lives in the [G3 continuation](./session-12-g3.md).

| Field | Value |
| --- | --- |
| Raw tip | `f4aa2de6c933c0b9abe0bcf33340ba4b8d51abbb` |
| Gold tip | `3b96ed660cf90e04637298f8c7c9494dadae21ca` |
| Tree (both) | `a49e73a710be5575460af51b26a7500164127e2d` |
| Paths | `README.md`, `CHANGELOG.md` only |
| Diff | `2 files changed, 7 insertions(+)` |
| Gold subject | `📝 docs(readme): document Session 6 residuals and V12-A proof pack` |
| Raw subject | `🦺 fix(commit-quality): add Session 6 residuals and scope law` |
| Trace | `019fdabf-61fb-73f9-85e2-82d9835e153a` (`log_final_commit_telemetry`) |
| Root span | `019fdabf-61fc-767c-aed9-0ec4510c2659` (`_run_commit_generation`) |
| Final telemetry span | `019fdac3-78e2-7511-871f-74a6c8c409fa` |
| Final telemetry time | `2026-08-07T05:47:51Z` |
| Provenance | `ai_accepted` / status `recorded` |

> Direct evidence from Opik final telemetry + generation spans, cross-checked against preserved raw Git object `f4aa2de` and gold tip `3b96ed6`. Opik captured accepted `commit_plan` / `final_commit_plan` on the final telemetry span; raw Git tip bytes match that plan (changelog family rendered `Fixed, Documentation`; secondary docs inventory collapsed to one generic bullet).

## Executive finding

S12-G4 was **not** a guard-exhaustion or fallback failure. It was a **clean wrong acceptance** of a pure documentation tip under a product-validation envelope, with **attribution bleed** from earlier Session 12 product work.

The system:

1. Correctly extracted two Markdown documentation files (+7 lines).
2. Parsed both with tree-sitter successfully (no parser failure).
3. Emitted false `runtime_logic_changed` plus validation/secret ranking signals from docs prose and Unreleased changelog bullets that *describe* prior laws.
4. Ranked `validation_update` at **100.5** over correct `documentation_update` at **21.5** (margin **38.0**, confidence **high**).
5. Locked a deterministic contract to `fix` / `PATCH` / `validation_update`.
6. Left `path_class_gate` empty and injected **no** docs-only envelope, staged-path class, claim tags, or gold guidance.
7. Allowed a single LLM attempt to obey that wrong contract faithfully — even while the model’s own reasoning noted the diff is documentation.
8. Applied contract lift (`NONE` → `PATCH`) and plan normaliser, making the wrong envelope look official.
9. Fired **zero** gold findings under `gold_mode=strict`.
10. Accepted via `ai_accepted` and wrote a product claim (“add/establish Session 6 residuals and scope law”) for a tip that only documents already-landed behaviour.

Later message-only rewrite corrected type/SemVer/changelog/inventory/attribution without changing the tree.

## Identity and observed evidence

| Item | Value |
| --- | --- |
| Trace | `019fdabf-61fb-73f9-85e2-82d9835e153a` |
| Project | `gitCommitGenerator` |
| Root operation | `_run_commit_generation` |
| Root span | `019fdabf-61fc-767c-aed9-0ec4510c2659` |
| Diff span | `019fdabf-62e2-7901-8bb3-f816efec1370` (`extract_git_diff`) |
| Semantic span | `019fdabf-632c-7296-9bc4-2c61ebb0da45` (`semantic_analysis`) |
| Prompt span | `019fdabf-6342-7b49-bf32-6d49f9e0bed4` (`build_system_prompt`) |
| Generate span | `019fdabf-6343-71fe-be6c-9a9ad009d7ec` (`generate_commit_message`) |
| LLM span | `019fdabf-6345-78a5-85d5-2c5d5f2e5452` (`chat_completion_create`) |
| Final telemetry | `019fdac3-78e2-7511-871f-74a6c8c409fa` |
| Model | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` |
| Provider | `127.0.0.1` |
| Tokens | prompt 4,758 · completion 2,874 (reasoning 2,479) · total 7,632 |
| LLM duration | ~121.4 s |
| Attempts | **1** (no retry / no fallback) |
| Follow-on prepare | `019fdac3-6b86-7a13-b38c-e9e1b4675e04` (~6.5 ms; `commit_source=message`; exited in `_validate_commit_source`) |

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

**Observation:** live write path under `gold_strict=true`. Failure is “accepted wrong envelope + attribution bleed,” not tooling outage.

## 2. What the diff actually contained

Diff extractor completed successfully:

```text
CHANGELOG.md | 4 ++++
 README.md    | 3 +++
 2 files changed, 7 insertions(+)
```

Concrete product of the commit (byte-confirmed from `git show f4aa2de`):

1. **`CHANGELOG.md` Unreleased bullets** documenting already-landed #204 work:
   * Features: Session 6 presentation residuals (capability dominance, evaluator verbs, Context/Changes rejection, attribution-bleed detection, module/behaviour scope law)
   * Bug Fixes: module/behaviour scope-law fix (package/epic scopes → dominant module/behaviour slugs; path-class envelopes authoritative)
   * Tests: V12-A named proof pack + TIP-G13–G17 corpus rows
   * Documentation: README operator residuals / module-scope law / V12-A pointer
2. **`README.md` operator-table rows** documenting:
   * **Module / behaviour scope law**
   * **Session 6 message-quality residuals** (+ TIP-G13–TIP-G17 pointer)
   * **V12-A proof pack** path (`tests/test_v12_a_claims.py`) and purity guarantees

**No `src/**` paths. No tests. No runtime code.** This tip only records prior Session 12 product/fixture/proof work in operator docs and Unreleased notes.

## 3. Semantic analysis was successful — and contaminated by docs prose / changelog text

Direct semantic / fingerprint telemetry:

```text
semantic_parser_mode: tree-sitter
semantic_languages_requested/parsed: markdown / markdown
semantic_files_total/parsed: 2 / 2
semantic_files_failed: 0
semantic_fallback_reasons: none
body_similarity_min: 1.0
body_similarity_avg: 1.0
fingerprint_files_compared: 2
fingerprint_class_counts: {structural: 2}
fingerprint_markers:
  - runtime_logic_changed
impacts_tests / impacts_production_code: null
blast_radius_size: null
affected_flows_count: 0
risk_score: 0.0
parser_latency_ms: ~10.0
fingerprint_latency_ms: ~38.5
```

**Assessment:**

* Parser and fingerprint comparison were technically healthy (2/2 Markdown files, similarity 1.0, no fallback reasons).
* Despite that health, the only emitted fingerprint marker was **`runtime_logic_changed`** — absurd for a docs-only tip.
* Ranking evidence then treated Unreleased changelog / README prose about validation, guards, scope law, and secrets-adjacent wording as live product signals (`schema_validation_changed`, `validation_added`, `validation_hardened`, `secret_reference_changed`).
* No authoritative path-class statement that this is docs-only / documentation-of-prior-work.
* This is the upstream poison that made validation dominate documentation.

## 4. Ranking vs contract (direct Opik)

From `build_system_prompt` ranked candidates + locked contract:

| Rank | intent_id | score | cc_type | semver | evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `validation_update` | **100.5** | fix | PATCH | `schema_validation_changed`, `validation_added`, `validation_hardened` |
| 2 | `secrets_update` | **62.5** | chore | PATCH | `secret_reference_changed` |
| 3 | `breaking_change` | 49.0 | feat | MAJOR | empty |
| … | critical/security/business noise | 45→40 | … | … | empty / weak |
| **correct family** | `documentation_update` | **21.5** | docs | NONE | **no competitive evidence** |
| nearby docs intents | `comments_update` / `typo_fix` / `license_update` | 21.5 / 20.0 / 27.0 | docs | NONE | not selected |

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
changelog_antisignal_applied: false
ranking_confidence_level: high
ranking_confidence_margin: 38.0
ranking_choice_path: skipped_high_medium
ranking_override: false
ranking_arbitrate_effective: skipped_high_medium
contract_lift_applied: true
contract_lift_from_semver: NONE
contract_locked_semver: PATCH
llm_raw_semver: PATCH
plan_persisted_semver: PATCH
plan_normaliser_applied: true
plan_normaliser_reason: contract_lift
scope_normalised_from: none
gold_mode: strict
gold_findings_count: 0
gold_finding_codes: []
gold_blocked: false
gold_regen_attempts: 0
```

**Assessment:**

* The ranker never seriously considered the docs envelope (`documentation_update` buried at 21.5).
* High confidence + margin 38.0 skipped arbitration entirely (`skipped_high_medium`).
* Contract lock converted contaminated ranking into a hard generation constraint.
* Contract lift then forbade the correct SemVer (`NONE`) by promoting/holding `PATCH`.
* Empty path-class gate + empty claim harvest + null gold guidance meant no late docs-only correction.
* `changelog_antisignal_applied=false` confirms Unreleased bullets were **not** treated as documentation-only anti-signals.

## 5. Single generation attempt — model followed the wrong envelope faithfully

| Span | Name | Duration |
| --- | --- | --- |
| `019fdabf-6343-...` | `generate_commit_message` | ~121.4 s |
| `019fdabf-6345-...` | `chat_completion_create` | ~121.4 s |

**LLM raw plan (direct):**

```text
primary: validation_update / 🦺 / fix / scope=commit-quality
description: add Session 6 residuals and scope law
semver: PATCH
changelog_group: Changed
secondary:
  documentation_update / 📝 / docs / scope=readme
  description: document operator residuals and test proofs
  semver: NONE
  changelog_group: Documentation
```

**Post-normaliser accepted plan / final telemetry:**

```text
primary: validation_update / 🦺 / fix / scope=commit-quality
description: add Session 6 residuals and scope law
semver: PATCH
changelog_group: Fixed
secondary:
  documentation_update / 📝 / docs / scope=readme
  description: document operator residuals and test proofs
  semver: NONE
  changelog_group: Miscellaneous   # final_commit_plan partial
body_summary: Clarifies evaluator mutation-verb guards and establishes
  the module/behaviour scope law to prevent attribution bleed. Adds
  references to the V12-A proof pack for deterministic validation and
  operator guidance.
```

**Exact raw Git tip message (`f4aa2de`) — byte-confirmed:**

```text
🦺 fix(commit-quality): add Session 6 residuals and scope law

Clarifies evaluator mutation-verb guards and establishes the module/behaviour scope law to prevent attribution bleed. Adds references to the V12-A proof pack for deterministic validation and operator guidance.

Included changes:
- 📝 docs(readme): document operator residuals and test proofs

Refs: #204
SemVer-Impact: PATCH
Change-Types: fix, docs
Changelog-Groups: Fixed, Documentation
```

**Model reasoning (direct, condensed):** the model **saw** that the diff updates `CHANGELOG.md` and `README.md` and even considered documentation wording (“document Session 6 residuals…”), then explicitly subordinated that observation to the locked validation contract (“However, the contract forces `fix(validation_update)`. I will stick to the contract.”). It chose product verbs (`add`, `establishes`, `Clarifies` guards) and collapsed four documentation surfaces into one generic secondary bullet.

**What looked “good” to the pipeline**

* Single coherent plan
* Header length OK (48 chars scored)
* Emoji/type matrix-aligned under the locked fix/validation row
* No banned Context:/Changes skeleton
* No fallback theatre (`presentation_fallback_reason=none`)
* `contract_consistent=1` via contract lift
* `user_acceptance=1` (`ai_accepted`)
* `gold_findings_count=0`
* Secondary docs intent present (so the system could claim multi-surface awareness)

**What was actually wrong**

1. **Wrong primary type** — `fix` instead of `docs`
2. **Wrong SemVer** — `PATCH` instead of `NONE`
3. **Wrong changelog family** — `Fixed, Documentation` instead of `Documentation` only
4. **Attribution bleed in subject** — “add Session 6 residuals and scope law” claims product implementation on a docs-only tip
5. **Attribution bleed in body** — “establishes the module/behaviour scope law” / “Clarifies evaluator mutation-verb guards” frames documentation as implementing/clarifying runtime guards
6. **Under-inventoried docs surfaces** — one generic README bullet instead of four gold surfaces
7. **False semantic/ranking signals** — `runtime_logic_changed`, validation_*, `secret_reference_changed` from Markdown/changelog prose
8. **Empty path_class_gate** despite obvious docs-only paths
9. **Contract lift anti-correction** — reinforced `PATCH` from `NONE`
10. **gold_strict non-blocking** on docs-only type/SemVer + product-attribution truth

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
scope_normalised_from: none
changelog_antisignal_applied: false
```

Effects:

* Primary changelog moved toward matrix/fix presentation (`Changed` → `Fixed`) while remaining in the wrong family.
* SemVer stayed `PATCH` under lift even though pure docs law requires `NONE`.
* Secondary docs intent survived, but only as a thin satellite under a false product primary — exactly the attribution-bleed shape gold forbids.
* No harvest of the four distinct documentation surfaces into Included-changes.

## 7. Gold delta (what G4 should have said)

**Gold tip `3b96ed6` (byte-confirmed):**

```text
📝 docs(readme): document Session 6 residuals and V12-A proof pack

Extend the Issue #204 operator guide with module/behaviour scope law,
Session 6 message-quality residuals (capability dominance, evaluator
verbs, Context:/Changes: ban, attribution bleed), and a pointer to the
stable V12-A pack. Record matching Unreleased changelog bullets.

Included changes:
- 📝 docs(readme): module/behaviour scope law row
- 📝 docs(readme): Session 6 residual operator row + TIP-G13–G17 pointer
- 📝 docs(readme): V12-A proof pack path (test_v12_a_claims.py)
- 📝 docs(changelog): Unreleased feat/fix/test/docs entries for #204

Refs: #204
SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

| Dimension | Raw `f4aa2de` | Gold `3b96ed6` |
| --- | --- | --- |
| Emoji / type | 🦺 `fix` | 📝 `docs` |
| Scope | `commit-quality` | `readme` |
| Subject | add Session 6 residuals and scope law | document Session 6 residuals and V12-A proof pack |
| SemVer | PATCH | NONE |
| Change-Types | fix, docs | docs |
| Changelog | Fixed, Documentation | Documentation |
| Body posture | clarifies / establishes / adds (product) | extend / document / record (docs) |
| Inventory | 1 generic README bullet | 4 named docs surfaces |
| Tree | `a49e73a7…` | `a49e73a7…` (identical) |

## 8. Follow-on prepare-commit-msg observation

Immediately after accept/write, trace `019fdac3-6b86-7a13-b38c-e9e1b4675e04` ran `_run_commit_generation` with:

```text
commit_source=message
strict=false
interactive=false
gold_strict=false
duration≈6.5 ms
```

It exited through `_validate_commit_source` via `typer.Exit(code=0)` and had **no LLM span**. Same prepare-commit-msg re-entry class as G2/G3. For G4 it did **not** rewrite the accepted wrong message; it remains process evidence for **F80 / P-S12-9**.

## 9. G4-specific root cause

### Root-cause chain

```text
README.md + CHANGELOG.md only (+7 docs lines)
→ semantic parser succeeds on Markdown
→ docs prose / Unreleased bullets emit runtime/validation/secret signals
   (runtime_logic_changed; schema_validation_changed; validation_added;
    validation_hardened; secret_reference_changed)
→ validation_update 100.5 dominates documentation_update 21.5
→ path_class_gate empty; no docs-only envelope / attribution guidance
→ contract locks validation_update / fix / PATCH
→ contract lift reinforces PATCH from NONE
→ single LLM describes prior laws as being added/established
→ secondary docs inventory collapses to one generic bullet
→ no gold findings or block
→ ai_accepted
→ later message-only rewrite restores docs/NONE + four-surface inventory
```

### Primary defect

**Missing hard live path-class envelope for pure docs paths (`README.md` / `CHANGELOG.md` / `docs/**`), compounded by docs-prose fingerprint/signal contamination and no attribution guard against claiming to implement already-landed product laws.**

### Secondary defects

1. **No docs-surface inventory harvest** (named README rows + Unreleased changelog bullets) → under-claim / generic collapse (F78).
2. **Product-verb attribution bleed** (“add”, “establish”, “clarify guards”) not banned on docs-only tips (F77 / P-S12-7).
3. **Contract lift raises/holds PATCH** on docs-only paths (anti-correction).
4. **Unreleased changelog bullets treated as implementation evidence** rather than documentation content (`changelog_antisignal_applied=false`).
5. **gold_strict checks shape/contract consistency, not path-class truth + attribution law + surface inventory.**
6. **Secret/validation signals from descriptive Markdown** not quarantined when no secret/validation code paths changed.

## 10. Severity

**High — same envelope family as G2/G3; docs-path attribution-bleed variant.**

* G2/G3 proved tests/fixtures can be typed `fix`/`PATCH` under false capability/validation markers.
* G4 proves the same contamination path works on pure operator docs + changelog notes.
* Wrong type+SemVer on docs-only tips poisons release notes and re-attributes earlier product commits to the documentation tip.
* Maps to existing IDs: **F77/S12-6** (docs typed fix + attribution bleed), **F78/S12-7** (under-inventoried surfaces), **F79/S12-8** (implementation/validation framing on non-product content), **P-S12-4/6/7/8**.

## 11. Corrective controls for G4

### A. Hard docs path envelope before rank lock / after render

* Only `README.md` / `CHANGELOG.md` / `docs/**` (no `src/**`, no `tests/**`) ⇒ primary `docs` + SemVer `NONE` + changelog group `Documentation`.
* Forbid primary `fix`/`feat` and SemVer `PATCH`/`MINOR` from docs prose that merely describes prior implementation.
* Emit `GOLD_PATH_CLASS_ENVELOPE` when violated under `gold_strict`.

### B. Docs attribution guard (P-S12-7)

* On docs-only tips, detect product-implementation verbs in subject/body:
  * ban lead framing with add/implement/establish/enforce/fix/clarify-guards as if shipping product
  * require document/record/describe/link/reference/extend operator-guide wording
* Allow naming prior laws; forbid claiming this tip creates them.
* Emit `GOLD_DOCS_ATTRIBUTION_BLEED` when docs-only paths claim product authorship of earlier commits.

### C. Fingerprint / signal quarantine for Markdown-only diffs

* On pure docs paths, suppress or heavily demote:
  * `runtime_logic_changed`
  * validation/schema markers derived solely from prose
  * `secret_reference_changed` derived solely from descriptive text
* Prefer documentation markers / path priors over AST/prose capability guesses.

### D. Changelog anti-signal for Unreleased documentation bullets

* Treat added Unreleased bullets in `CHANGELOG.md` as documentation content, not live implementation evidence of the features/fixes/tests they narrate.
* Force `changelog_antisignal_applied=true` on docs-only tips that only extend Unreleased notes.

### E. Stable documentation inventory harvest (P-S12-6)

* Detect distinct README operator-table rows and distinct Unreleased changelog bullets.
* For this tip class, require Included-changes coverage of:
  * module/behaviour scope-law row
  * Session 6 residual operator row + TIP-G13–G17 pointer
  * V12-A proof-pack path
  * CHANGELOG Unreleased entries
* Emit `GOLD_DOCS_INVENTORY_INCOMPLETE` when collapsed to a generic single bullet.

### F. Contract lift must not raise docs-only NONE→PATCH

* If path-class says docs-only, lift ceiling is `NONE`.
* `plan_normaliser_reason=contract_lift` must not launder a wrong family.

### G. gold_strict must fail closed on envelope + attribution miss

Even when formatting checks pass, block on:

* wrong cc_type family for path class
* wrong SemVer for path class
* product-implementation verbs on docs-only diffs
* missing named docs-surface inventory
* runtime/validation markers retained on docs-only diffs without product paths

## 12. Final G4 assessment

S12-G4 is a pure **docs envelope, prose-signal quarantine, attribution-guard, and surface-inventory failure** with no fallback theatre.

Supported directly by Opik + raw Git:

* docs-only Markdown diff (+7)
* false runtime/validation/secret signals from prose/changelog text
* validation_update 100.5 ≫ documentation_update 21.5
* empty path_class_gate / claim_tags / gold_guidance
* locked fix/PATCH contract + lift from NONE
* single faithful LLM emission that knowingly overrode “this is docs”
* zero gold findings
* `ai_accepted` raw tip byte-matches plan
* gold rewrite preserves tree and restores docs/NONE + four-surface inventory
* prepare re-entry non-clobber (~6.5 ms)

### Evidence confidence

| Claim | Confidence | Basis |
| --- | --- | --- |
| Diff/semantic spans healthy but contaminated | **Direct** | Opik semantic + fingerprint fields |
| Ranking/contract lock wrong family | **Direct** | prompt ranked_candidates + contract |
| Single-attempt clean acceptance | **Direct** | generate + final telemetry |
| Raw tip bytes = accepted plan | **Direct** | `git show` `f4aa2de` |
| Tree-identical gold rewrite | **Direct** | both trees `a49e73a7…` |
| Model knowingly overrode “docs” observation | **Direct** | LLM reasoning_content |
| prepare re-entry non-clobber | **Direct** | trace `019fdac3-6b86-...` |
| Attribution bleed (add/establish on docs-only) | **Direct** | raw subject/body vs gold wording |

## Stop point

**S12-G4 is complete at full depth in this continuation archive.**

**Cross-commit synthesis:** [5215611559](./session-12-synthesis.md).
---

## Package cross-links

| Need | Link |
|:---|:---|
| Series synthesis | [`session-12-synthesis.md`](./session-12-synthesis.md) |
| G3 tests sibling | [`session-12-g3.md`](./session-12-g3.md) |
| Archive intake | [comment 5215440216](https://github.com/Thomo1318/gitCommitGenerator/issues/204#issuecomment-5215440216) |

### Promotion record

| Field | Value |
|:---|:---|
| Promoted on | 2026-08-13 |
| From | #204 comment `5215440216` |
| SSOT rule | Package path wins |

---

## Document control

| Field | Value |
|:---|:---|
| Case ID | 204-S12-G4 |
| Status | active / full |
| Last updated | 2026-08-13 |
