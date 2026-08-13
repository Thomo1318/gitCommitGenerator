# Gold-miss failure analysis method

> **Package:** commit-message failure analysis  
> **Document:** `METHOD`  
> **Version:** `1.0.0-combine`  
> **Status:** active (ratification core)  
> **Genre authority:** Session 12 (Opik-bound forensic reconstruction)  
> **Substrate:** Sessions 1–11 + #204 body (law, F1–F71, matrices, tip corpus)  
> **Sources:** promoted SSOT `cases/204/session-12.md` + `session-12-synthesis.md`; archive comments `5213748048`, `5215148242`, `5215440216`, `5215611559`; dogfood `5226058599` / `5226058718` / `5226058788`  
> **Last harvest:** 2026-08-13 (S12 G1 + synthesis promoted)  
> **Companion:** [`templates/CASE_TEMPLATE.md`](./templates/CASE_TEMPLATE.md)

---

## 0. Purpose

This file is the **mandatory forensic genre** for every commit-message gold-miss review going forward.

It combines:

| Layer | Role | Authority |
|:---|:---|:---|
| **Session 12** | Depth floor, pipeline stages, regimes A/B, evidence confidence, Opik binding | Method |
| **Sessions 1–11 + #204 body** | Gold envelope, accept/reject rules, F1–F71 / R*, tip/V12-A corpus, Instance A/B | Law + IDs + history |

**Non-goals**

* Replacing product law (`ranker`, SOP, Hybrid, `commit_gold`, `commit_quality`, path-class, hooks).
* Replacing the eval harness plan ([`docs/plans/opik-evaluation-harness.md`](../plans/opik-evaluation-harness.md)).
* Dumping full S1–11 archaeology into every new case.
* Treating GitHub issue comments as living SSOT after promotion.

---

## 1. When to run this method

Run a full gold-miss case when **any** of the following is true:

1. Generated tip fails the Hybrid / gold envelope the operator would ship.
2. Message-only rewrite was required to reach gold (tree preserved).
3. Dogfood after a control still misses gold (post-control residual).
4. Eval / harness flags a miss that needs human causal reconstruction.
5. A multi-commit series shares a systems pattern (needs synthesis).

**Do not** use a Sessions 1–11 tip-table-only writeup as the final record for new work. Tables may appear *inside* a METHOD-compliant case; they are not a substitute for it.

---

## 2. Authority order

```text
1. Product law
   ranker · SOP · Hybrid · commit_gold · commit_quality · path-class · hooks
2. This package (docs/quality/)
   METHOD · GOLD_STANDARD · FAILURE_TAXONOMY · PREVENTION_BACKLOG · cases
3. #204 issue body (behavioural locks / V12-A / anti-patterns until fully mirrored)
4. #204 comment archives (intake evidence; non-authoritative after promotion)
5. Eval plan (#217 / docs/plans/opik-evaluation-harness.md) — consumer only
6. Chat / scratch (residue only)
```

**Epic split**

| Issue | Owns | Does **not** own |
|:---|:---|:---|
| **#204** | Corpus motivation + historical intake; locks in body until mirrored | Living case library after promote (paths under `docs/quality/cases/204/` win) |
| **#217** | Harness governance index + eval plan pointer | Gold-miss METHOD, F*/P* definitions, case prose (cite this package) |

Eval metrics **wrap** product authorities and **cite** package F*/P* IDs. They must not invent parallel presentation law.

---

## 3. Series classes (tag every case)

| Class | Meaning | Example |
|:---|:---|:---|
| **Instance A — precursor** | Why the epic/laws exist; historical motivation | #204 S1–5 |
| **Instance B — implementation dogfood** | Generator still misses gold *while shipping the fix* | #204 slices 0–5, S6–11 |
| **Residual close-out** | Planned tip series after a slice; trees correct, messages wrong | Session 12 G1–G4 |
| **Post-control dogfood** | After P-* controls landed; still misses (truth gap) | S12 dogfood G2–G4 |
| **Forward case** | New issue/work using this package as base | #220 S0 schema freeze |

Never collapse A, B, residual, and post-control into one bucket.

---

## 4. Two systems regimes (required)

Every case **must** assign **Regime A**, **Regime B**, or **both** (multi-group series).

### Regime A — Controls fire; recovery makes it worse

**Pattern**

* Rank/contract may be closer to truth.
* Guards, regen, and/or fallback activate.
* Final envelope is degraded (type/SemVer/body) or process-meta leaks.
* Pipeline still reports success.

**Canonical proof:** Session 12 G1  
**IDs:** F72–F75 cluster · P-S12-1/2/3/5

```text
healthy diff → plausible rank/contract
→ prompt or regen contradiction
→ guard thrash / budget exhaust
→ skeleton/fallback rewrites presentation
→ write succeeds under gold_strict
→ telemetry understates failure
```

### Regime B — Controls never fire; wrong envelope looks perfect

**Pattern**

* Path-class / envelope gates empty or ignored.
* Model emits a Hybrid-valid but library-wrong message.
* Clean accept (`ai_accepted`); gold_strict findings = 0.
* No fallback required.

**Canonical proof:** Session 12 G2–G4 (+ post-control dogfood)  
**IDs:** F76–F79 cluster · P-S12-4/6/7/8

```text
healthy extract → contaminated signals / empty path_class_gate
→ wrong type/SemVer/scope lock looks official
→ single clean generation
→ normalisers polish the wrong envelope
→ gold_strict scores shape only → accept
```

### Shared process defect

**F80 / P-S12-9** — `prepare-commit-msg` still re-enters `git-cg` on message-only rebuilds.  
`--no-verify` alone is insufficient. Use `core.hooksPath=/dev/null` or `GIT_CG_SKIP_PREPARE=1` (see [`process/message-only-rewrite.md`](./process/message-only-rewrite.md)).

---

## 5. Pipeline stages (walk in order)

Every full-depth case reconstructs failure **by stage**, not only by final subject line.

```text
1.  diff extract / file summary
2.  path-class · priors · staged_paths · claim tags
3.  semantic signals / fingerprint health
4.  rank_commit_intents
5.  contract lock (type · emoji · SemVer · changelog family)
6.  prompt assemble (incl. low-confidence skeleton / gold guidance)
7.  LLM render attempt(s)
8.  validate / guards
9.  regeneration loop (what is retained vs cleared)
10. presentation fallback / skeleton
11. final render
12. write path · hooks · prepare re-entry
13. gold_strict / accept decision
14. telemetry counters / provenance labels
```

**Analyst rule:** name the **first stage that left the gold path** and the **stage that made the miss irreversible**.

---

## 6. Mandatory case sections (depth floor)

Copy [`templates/CASE_TEMPLATE.md`](./templates/CASE_TEMPLATE.md). Do not start from a blank page or a GitHub comment skeleton.

| # | Section | Required content |
|:---:|:---|:---|
| 0 | **Open summary** | Result · path focus · severity · raw→gold SHAs · one-line diagnosis · F*/P* · regime |
| 1 | **Incident identity** | Issue, branch, base→tip, series class, tree-preservation, rewrite map |
| 2 | **Git provenance** | `Git-raw` / `Git-mid` / `Gold-final` · `Rewrite-map-confirmed` |
| 3 | **Opik identity** | project, trace/span IDs, model, window — **or** explicit `Opik-unbound` + reason |
| 4 | **Evidence confidence** | Direct vs Reconstructed per major claim |
| 5 | **Executive finding** | What failed *in the pipeline*, not only the text |
| 6 | **Diff truth** | Paths, library class, intended type/SemVer/changelog |
| 7 | **Semantic / signal health** | What extraction claimed; contamination sources |
| 8 | **Ranking vs locked contract** | Top intents, scores, skipped arbitration, locked envelope |
| 9 | **Attempt loop / fallback / clean-accept** | Per attempt; final acceptance mode |
| 10 | **Prompt / evidence channels** | Contradictions; empty `path_class_gate` / `staged_paths` / gold guidance |
| 11 | **Raw↔gold dimension table** | type, scope, subject, body, inventory, trailers, SemVer, changelog, attribution |
| 12 | **Root-cause chain** | ASCII, stage-ordered |
| 13 | **Failure + prevention IDs** | From taxonomy/backlog only (mint rows if genuinely new) |
| 14 | **Accept / gold_strict / hooks** | Including non-blocking lies and counter mismatch |
| 15 | **Corrective controls + tests** | Prompt / regen / fallback / envelope / gold_strict / telemetry |
| 16 | **Final assessment** | Severity vs series; residual risk |
| 17 | **Cross-commit synthesis** | Required when ≥2 groups (use synthesis template) |

### 6.1 Open summary minimum

```markdown
**Result:** <PASS gold | MISS gold> · Regime <A|B|A+B>  
**Path focus:** …  
**Severity:** Critical | High | Medium | Low  
**Raw → gold:** `<sha>` → `<sha>` (tree preserved: yes/no)  
**One-line diagnosis:** …  
**IDs:** F… · P… · related TIP/V12-A …
```

### 6.2 Dimension table minimum

| Dimension | Raw | Gold | Miss? |
|:---|:---|:---|:---|
| Primary type | | | |
| Scope | | | |
| Subject | | | |
| SemVer-Impact | | | |
| Change-Types | | | |
| Changelog-Groups | | | |
| Body contract | | | |
| Included changes | | | |
| Attribution | | | |
| Issue trailer | | | |
| Acceptance mode | | | |

### 6.3 Evidence confidence matrix minimum

| Claim | Confidence | Basis |
|:---|:---|:---|
| Diff/path set | Direct \| Reconstructed | git / Opik / operator note |
| Rank + contract | | |
| Attempt plans | | |
| Exact final bytes | | |
| Hook re-entry | | |
| gold_strict outcome | | |

**Hard bans**

* Invented Opik span IDs.
* Unlabelled reconstruction presented as Direct.
* Symptom-only “type was wrong” with no stage.

---

## 7. Provenance vocabulary

### 7.1 Git labels (from S1–11; required)

| Label | Meaning |
|:---|:---|
| `Git-raw` | First generator-written tip (or first observed bad tip) |
| `Git-mid` | Intermediate rewrite before gold (if any) |
| `Gold-final` | Operator-accepted gold tip |
| `Rewrite-map-confirmed` | Tree OID unchanged across raw→gold (message-only) |
| `Opik-unbound` | No trustworthy Opik bind for this tip |

### 7.2 Confidence labels (from S12; required)

| Label | Meaning |
|:---|:---|
| **Direct** | Read from git object, Opik span, or product log without inference |
| **Reconstructed** | Inferred (e.g. plan→message bytes Opik did not store); must be labelled |

Full notes: [`process/provenance-and-confidence.md`](./process/provenance-and-confidence.md).

---

## 8. Classification workflow

```text
1. Establish identity + tree preservation
2. Bind Opik or mark Opik-unbound
3. Classify diff library class via GOLD_STANDARD matrices
4. Walk pipeline stages (§5)
5. Assign Regime A and/or B
6. Fill raw↔gold dimension table
7. Attach F*/R* from FAILURE_TAXONOMY (do not invent parallel IDs)
8. Attach or propose P* in PREVENTION_BACKLOG
9. Land case under cases/<issue>/…
10. Update cases/README.md index + references/source-map.md if promoted from GitHub
11. Only then: product fix, eval fixture, or issue comment pointer back to repo path
```

### 8.1 ID minting rules

* Prefer existing F/R/P rows.
* New F* requires a row in [`FAILURE_TAXONOMY.md`](./FAILURE_TAXONOMY.md).
* New P* requires a row in [`PREVENTION_BACKLOG.md`](./PREVENTION_BACKLOG.md) and a case pointer.
* S12 extensions (F72–F80) **extend** earlier IDs; cite the extension map.
* Do not mint IDs only in issue comments.

---

## 9. What “standard not met” means

A tip **misses gold** when any of the following fails (see [`GOLD_STANDARD.md`](./GOLD_STANDARD.md)):

1. Hybrid envelope (emoji, type, scope canon, ≤72 subject).
2. Diff-class defaults (type / SemVer / changelog family).
3. Accept/reject operator rules (unearned feat/MINOR/MAJOR, docs→fix, etc.).
4. Body contract / craft bans (process-meta, Context:/Changes:, attribution bleed, …).
5. Inventory sufficiency (stable IDs, multi-surface, no generic collapse).
6. Three-layer authority invariant:
   1. Ranked authority immutable for the analysis window  
   2. Presentation constraints deterministic  
   3. Rendered presentation final and operator-safe  
7. Process honesty (`gold_strict`, fallback-not-final, telemetry ≠ success laundering).

Gold is the **message the project would keep**, not “Hybrid-parseable.”

---

## 10. Analyst anti-patterns

| Anti-pattern | Corrective |
|:---|:---|
| S1–11 table only for new work | Use this METHOD + CASE_TEMPLATE |
| Regime A described as “LLM bad” | Name contradiction → regen → fallback chain |
| Regime B described as “fallback bug” | No fallback: empty gates + clean wrong accept |
| Missing Opik section | Write `Opik-unbound` + why |
| Fabricated spans | Forbidden |
| New F* only in a chat | Taxonomy row first |
| Case without P* or residual “watch” | Incomplete |
| Treating post-control dogfood as Instance A | Wrong series class |
| `--no-verify` as sole message-only safety | F80; use process/message-only-rewrite |
| Eval metric inventing presentation law | Wrap product code; cite F*/P* |

---

## 11. Relationship to package files

| Need | Open |
|:---|:---|
| How to analyse (this file) | `METHOD.md` |
| Empty structure to fill | `templates/CASE_TEMPLATE.md` |
| Multi-group close-out | `templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md` |
| Thin deferred stub | `templates/OPEN_SUMMARY_STUB.md` |
| What gold looks like | `GOLD_STANDARD.md` |
| F*/R* definitions | `FAILURE_TAXONOMY.md` |
| P* status | `PREVENTION_BACKLOG.md` |
| TIP / V12-A / A·B map | `CORPUS.md` |
| Operator checklist | `process/gold-miss-review-checklist.md` |
| Message-only rewrite | `process/message-only-rewrite.md` |
| Promote from GitHub | `process/promotion-from-issue-comment.md` |
| Worked proofs | [`cases/204/session-12.md`](./cases/204/session-12.md) (G1) · [`session-12-synthesis.md`](./cases/204/session-12-synthesis.md) · G2–G4 pending |
| First forward case | `cases/220/s0-schema-freeze.md` |

---

## 12. Minimum viable full case (acceptance of the method)

A case is METHOD-compliant when:

* [ ] Open summary complete with regime + SHAs + one-line diagnosis  
* [ ] Series class tagged  
* [ ] Git provenance labelled  
* [ ] Opik bound **or** `Opik-unbound` explicit  
* [ ] Confidence matrix present  
* [ ] Pipeline stages addressed (at least extract → rank/contract → render/accept)  
* [ ] Raw↔gold dimension table filled  
* [ ] Stage-ordered root-cause chain present  
* [ ] F*/P* from package registries  
* [ ] gold_strict / acceptance / hook outcome stated  
* [ ] Controls + test pointers listed  
* [ ] Indexed in `cases/README.md`  

Anything less is **intake notes**, not package SSOT.

---

## 13. Session 12 → method mapping (normative examples)

| S12 element | Method location |
|:---|:---|
| G1 fallback/process-meta catastrophe | Regime A exemplar → [`cases/204/session-12.md`](./cases/204/session-12.md) |
| G2–G4 clean wrong accept | Regime B exemplar → synthesis + pending G2–G4 cases |
| F72–F80 | Taxonomy + every residual close-out checklist |
| P-S12-1…9 | Prevention backlog systems floor |
| Direct/Reconstructed matrix | §6.3 / provenance process |
| Empty `path_class_gate` / `staged_paths` | §6 §10 evidence channels |
| prepare re-entry | F80 · process/message-only-rewrite |
| Cross-commit synthesis | Template + [`cases/204/session-12-synthesis.md`](./cases/204/session-12-synthesis.md) **active** |

Sessions 1–11 supply the **law and ID substrate** this method assumes (diff-class matrices, R1–R25, F1–F71, accept/reject stacks, tip index). They do not define a weaker genre.

---

## 14. Document control

| Field | Value |
|:---|:---|
| Package version | `1.0.0-combine` |
| Method status | Active ratification core (B) |
| Scaffold status | Tree + companions (A) |
| Next content harvest | S12 G2–G4 + dogfood · substrate indexes · #220 case |
| Owners | git-cg maintainers / gold-miss reviewers |

When this file conflicts with a historical #204 comment on **procedure**, this file wins.  
When it conflicts with **product code behaviour**, verify code/tests and amend this file.
