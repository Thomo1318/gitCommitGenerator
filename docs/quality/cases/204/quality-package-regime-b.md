# CASE — quality package self-dogfood (Regime B four-tip series)

> **Copy lineage:** [`../../templates/CASE_TEMPLATE.md`](../../templates/CASE_TEMPLATE.md) + [`../../templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md`](../../templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md)  
> **Method:** [`../../METHOD.md`](../../METHOD.md)  
> **Package version:** `1.0.0-combine`  
> **Irony:** the commit-message failure-analysis package’s own landing series missed gold on presentation while trees and grouping were correct.

```yaml
package: commit-message-failure-analysis
doc: case
version: 1.0.0-combine
status: active
issue: 204
case_id: 204-QP-RB
series_id: 204-QP-RB-S1
series_class: post-control-dogfood
regime: B
opik: unbound
sources:
  - git:backup/quality-fa-pre-msg-rewrite
  - git:docs/quality-failure-analysis-package
  - local:operator gold rewrite 2026-08-13
last_updated: 2026-08-13
```

---

## 0. Open summary

**Result:** MISS gold · Regime **B** (all four tips)  
**Path focus:** `docs/quality/**` (+ `docs/plans/README.md` on G4)  
**Severity:** High (series-wide clean-wrong acceptance on the quality package itself)  
**Raw → gold tip:** `dfc382e9ce6d649d9c14a09506904e95e0e24b6f` → `d9a5e24b954ce63593b39d65d8aaf446c1be6ebb`  
**Trees preserved:** yes (per-tip tree OIDs identical; see rewrite map)  
**Branch / base→tip:** `docs/quality-failure-analysis-package` · `4b6dda5` (`main`) → gold tip `d9a5e24`  
**One-line diagnosis:** Hybrid-shaped, coherent `docs` messages were clean-accepted with tautological scope `docs(docs)`, generic `document …` craft, thin/missing inventories, missing `#204` trailers, and docs-only `Miscellaneous` leakage — without fallback or guard thrash.  
**IDs:** F74-ext · **F78** · F79-adj · **F81** · **F82** · **F83** · F80 (rewrite process) · **P-S12-6** · **P-S12-9** · **P-S12-10** · **P-S12-11** · **P-S12-12**  
**Series class:** post-control-dogfood (package landed after S12 method/law floor existed; generator still missed package-local gold)

| Field | Value |
|:---|:---|
| Issue | #204 |
| Case ID | 204-QP-RB |
| Reviewer | Thomo1318 / operator gold rewrite |
| Date | 2026-08-13 |
| Library class (intended) | pure docs (`docs/quality/**`, plans index pointer) |
| Acceptance mode (raw) | ai_accepted (clean; no presentation fallback observed on tips) |

### Group table

| Group | Path focus | Severity | Regime | Gold subject (short) | Raw SHA → Gold SHA |
|:---|:---|:---|:---|:---|:---|
| G1 | METHOD + README + templates | High | B | add Session 12 gold-miss METHOD and case templates | `48a46db` → `114edee` |
| G2 | process runbooks | High | B | add gold-miss operator process runbooks | `15b84f9` → `c682185` |
| G3 | GOLD/tax/prevention/corpus | High | B | pin gold envelope, F72–F80 taxonomy, and P-S12 backlog | `5bb957f` → `b43c0a5` |
| G4 | cases shelves + source-map + plans | High | B | scaffold case shelves and plans catalogue pointer | `dfc382e` → `d9a5e24` |

---

## 1. Incident identity

| Field | Value |
|:---|:---|
| Governing issue | #204 |
| Child / slice | quality package bootstrap on `docs/quality-failure-analysis-package` |
| Branch | `docs/quality-failure-analysis-package` |
| Scope of series | multi-group residual landing (4 commits) |
| Planned split | G1 method/templates · G2 process · G3 law/registries · G4 cases/plans |
| Message-only rebuild? | **yes** (trees preserved) |
| Notes | File grouping was correct and is **not** part of the miss. Backup branch: `backup/quality-fa-pre-msg-rewrite` @ raw tip `dfc382e`. |

### Rewrite map

| Role | SHA | Subject (short) | Tree OID |
|:---|:---|:---|:---|
| Git-raw G1 | `48a46db56bd647e643b67d44d20e2d39ea4a7d28` | docs(docs): document gold-miss failure analysis | `cbe83dbae7c34dc6e6d5bc7bd4516ff78c4fb32f` |
| Gold-final G1 | `114edee68f475e7c8514ad8ec0ba3bab3341f30a` | docs(quality): add Session 12 gold-miss METHOD and case templates | `cbe83dbae7c34dc6e6d5bc7bd4516ff78c4fb32f` |
| Git-raw G2 | `15b84f98b38d7c3493e1e6d99afb9801753c8cee` | docs(docs): document gold-miss review and process docs | `32a923e3149518bda5dff6c1b45787611d8cd70c` |
| Gold-final G2 | `c68218511a0835282d799c1ca4817ca893bff824` | docs(quality): add gold-miss operator process runbooks | `32a923e3149518bda5dff6c1b45787611d8cd70c` |
| Git-raw G3 | `5bb957f4579f56a5097bc2a01357ef9821cc4ffa` | docs(docs): document commit quality analysis docs | `1d5f7331b1c6a1d583ec3188c899677acdae306a` |
| Gold-final G3 | `b43c0a508b56069d32806a78564b0432ad8f1904` | docs(quality): pin gold envelope, F72–F80 taxonomy, and P-S12 backlog | `1d5f7331b1c6a1d583ec3188c899677acdae306a` |
| Git-raw G4 | `dfc382e9ce6d649d9c14a09506904e95e0e24b6f` | docs(docs): document commit quality failure analysis | `557c162b63dba2dc75e5ae99cf0ada409d660455` |
| Gold-final G4 | `d9a5e24b954ce63593b39d65d8aaf446c1be6ebb` | docs(quality): scaffold case shelves and plans catalogue pointer | `557c162b63dba2dc75e5ae99cf0ada409d660455` |

**Rewrite-map-confirmed:** yes (tree OIDs bit-identical raw↔gold for all four tips)

---

## 2. Git provenance

| Label | Value / notes |
|:---|:---|
| Git-raw | backup branch `backup/quality-fa-pre-msg-rewrite` tip series `48a46db…dfc382e` |
| Git-mid | partial rewrite attempt produced G1–G3 gold SHAs then stalled before G4 (`HEAD` had been at `b43c0a5`) |
| Gold-final | branch tip `d9a5e24` after G4 via `git commit-tree` (hook-free) |
| Tree preserved | **yes** all four |
| Notes | Rebuild used gold message files under `.git/GOLD_MSGS/g{1..4}.msg`. G4 created with `git commit-tree` + original author/committer identity from raw G4. **Environment finding (F80+):** `git -c core.hooksPath=/dev/null commit -F …` still invoked **hk** `prepare-commit-msg` → `git-cg` in this repo (hk-managed hooks, not classic `.git/hooks` path). Reliable bypass observed: **`git commit-tree`** (and/or disabling hk install path). P-S12-9 process doc updated. |

---

## 3. Opik identity

| Field | Value |
|:---|:---|
| Binding status | **Opik-unbound** for raw G1–G4 · **partial bind** only for later case-landing tip G5 |
| Reason if unbound | No Opik project/trace IDs captured for the **raw** `git-cg` generation window of G1–G4; reconstruction for those tips is git-direct + operator gold. |
| Project | `gitCommitGenerator` (G5 only) |
| Trace ID (G5 only) | `019ff96d-fd57-7787-85ff-e62704911756` |
| Root span | not inspected in this case |
| Generation / LLM spans | G5 prepare path only — not used as causal evidence for G1–G4 |
| Final / telemetry span | G5 commit-msg telemetry ran; raw tips unbound |
| Model | unbound for G1–G4 |
| Time window (UTC) | raw commits 2026-08-13 04:28–04:33Z class (local +1000 AuthorDates) |
| What Opik captured | G5 prepare/commit telemetry only (after gold rewrite of G1–G4) |
| What Opik did **not** capture | G1–G4 ranking scores, path_class_gate, attempt plans, gold_strict counters, final raw bytes |

Do **not** invent spans for G1–G4. G5 bind must not be back-ported as proof for the raw series.

---

## 4. Evidence confidence matrix

| Claim | Confidence | Basis |
|:---|:---|:---|
| Diff / path set | **Direct** | `git log --name-status main..backup/quality-fa-pre-msg-rewrite` |
| Exact final raw message bytes | **Direct** | `git log -1 --format=%B` on raw SHAs |
| Exact gold message bytes | **Direct** | gold tip series + `.git/GOLD_MSGS/*` |
| Tree preservation | **Direct** | `rev-parse raw^{tree}` == `gold^{tree}` |
| Semantic signals | Reconstructed | Opik-unbound; infer only from paths + messages |
| Ranking + scores | Reconstructed | not available |
| Locked contract | Reconstructed | pure-docs defaults from GOLD_STANDARD (docs/NONE/Documentation) |
| Prompt policy / skeleton | Reconstructed | no fallback body signatures in raw tips |
| Attempt N plans | unbound | — |
| Fallback reason / body | **Direct-negative** | raw bodies are operator-facing prose; no Cleared guard / Deterministic presentation fallback markers |
| gold_strict findings | Reconstructed | assumed pass (messages Hybrid-valid and shipped without operator reject-at-hook) |
| Hook / prepare re-entry | **Direct** (rebuild window) | mid-series rewrite required commit-tree; F80 class |
| Telemetry counters | unbound | — |

---

## 5. Executive finding

1. **Envelope family correct, package law wrong:** all raw tips used `📝 docs` + `SemVer-Impact: NONE` + `Change-Types: docs` — matching pure-docs defaults — while still missing package-local gold on scope, craft, inventory, issue trailer, and changelog purity.  
2. **Regime B clean-wrong-accept:** no fallback/skeleton (not F72), no process-meta body (not F73). Controls that would reject tautological scope, thin inventory, missing Refs, or docs-only Miscellaneous **never fired**.  
3. **Inventory collapse (F78):** G1 collapsed five paths into one vague templates bullet; G3 shipped **zero** Included changes; G4 listed only plans README + source-map while scaffolding an entire cases tree.  
4. **Scope canon miss (F81 / F74-ext):** every tip used `docs(docs)` instead of dominant module scope `quality` for `docs/quality/**`.  
5. **Issue trailer absence (F83):** G1/G2/G4 omitted `Refs: #204` despite issue-governed package work (G3 also omitted Refs).  
6. **Changelog impurity (F82):** G1/G2/G4 added `Miscellaneous` on pure Documentation tips.  
7. **Series craft sameness:** subjects were interchangeable `document …` lines; gold requires differentiated verbs (add / pin / scaffold) naming METHOD, runbooks, registries, shelves.

---

## 6. Diff truth

### Paths (raw commits)

```text
# G1 48a46db
A  docs/quality/METHOD.md
A  docs/quality/README.md
A  docs/quality/templates/CASE_TEMPLATE.md
A  docs/quality/templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md
A  docs/quality/templates/OPEN_SUMMARY_STUB.md

# G2 15b84f9
A  docs/quality/process/gold-miss-review-checklist.md
A  docs/quality/process/message-only-rewrite.md
A  docs/quality/process/promotion-from-issue-comment.md
A  docs/quality/process/provenance-and-confidence.md

# G3 5bb957f
A  docs/quality/CORPUS.md
A  docs/quality/FAILURE_TAXONOMY.md
A  docs/quality/GOLD_STANDARD.md
A  docs/quality/PREVENTION_BACKLOG.md

# G4 dfc382e
M  docs/plans/README.md
A  docs/quality/cases/204/README.md
A  docs/quality/cases/204/instance-a-precursor.md
A  docs/quality/cases/204/instance-b-slices-0-5.md
A  docs/quality/cases/204/session-12-dogfood-g2-g4.md
A  docs/quality/cases/204/session-12-g3.md
A  docs/quality/cases/204/session-12-g4.md
A  docs/quality/cases/204/session-12-synthesis.md
A  docs/quality/cases/204/session-12.md
A  docs/quality/cases/204/sessions-06-11.md
A  docs/quality/cases/220/s0-schema-freeze.md
A  docs/quality/cases/README.md
A  docs/quality/references/source-map.md
```

### Library classification

| Question | Answer |
|:---|:---|
| Intended diff class | pure docs package bootstrap |
| GOLD_STANDARD default type | `docs` |
| GOLD_STANDARD default SemVer | `NONE` |
| GOLD_STANDARD changelog family | `Documentation` **only** |
| Dominant module / scope canon | **`quality`** (path root `docs/quality/**`) |
| Stable IDs that must appear in inventory | METHOD; CASE_TEMPLATE / CROSS_COMMIT / OPEN_SUMMARY_STUB; process/*; GOLD_STANDARD; FAILURE_TAXONOMY F72–F80; PREVENTION P-S12-1…9; CORPUS; cases/204; cases/220; source-map; plans index row |
| High-risk body contract required? | yes — METHOD genre / rewrite safety (F80) / registry freeze claims must not overclaim product implementation |

### Semantic health (extractor)

| Check | Outcome |
|:---|:---|
| Diff extract completed | yes (healthy trees landed) |
| False capability / validation / secret / runtime markers? | no product runtime paths |
| Fixture/prose contamination? | n/a (docs-only) |
| `path_class_gate` | **Opik-unbound** — reconstructed: docs path-class either empty or insufficient to lock scope/`quality` / trailer / changelog purity |
| `staged_paths` | unbound |
| claim_tags / gold_guidance | unbound; raw inventories did not harvest package surface names |

---

## 7. Ranking vs locked contract

| Intent / signal | Score | Notes |
|:---|:---|:---|
| top-1 | unbound | messages imply docs intent won |
| expected gold family | docs / NONE / Documentation | matched on type+SemVer+Change-Types |

| Contract field | Locked value (recon) | Gold expectation | Match? |
|:---|:---|:---|:---:|
| type | docs | docs | ● |
| emoji / intent_id | 📝 / docs-class | 📝 docs | ● |
| SemVer | NONE | NONE | ● |
| changelog | Documentation[, Miscellaneous] | Documentation only | ◐ / ✕ on G1 G2 G4 |
| scope (if locked) | docs | **quality** | ✕ |

Arbitration skipped? unknown (Opik-unbound) — residual miss is presentation/law, not wrong primary type family.

---

## 8. Attempt loop / fallback / clean-accept

### Attempts

| Attempt | What model emitted | Guards / findings | Retained state | Outcome |
|:---:|:---|:---|:---|:---|
| 1..N | unknown (unbound) | no fallback markers in final | n/a | clean Hybrid docs tips |
| Final | tautological docs(docs) + thin inventory | apparently 0 blocking findings | accepted | **Regime B accept** |

### Final path

| Field | Value |
|:---|:---|
| Path class | **Regime B clean accept** |
| `presentation_fallback_reason` | none (observed in final bytes) |
| Acceptance mode | ai_accepted (operator shipped tips then human-gold rewritten) |
| Normalisers applied | unknown; finals are coherent prose |

---

## 9. Prompt and evidence-channel defects

| Channel | Observed | Should have been |
|:---|:---|:---|
| path_class_gate | insufficient to force package scope/changelog purity | pure docs gate + package slug `quality` |
| staged_paths | not reflected in inventories | explicit multi-file surfaces |
| gold_guidance | generic “document docs” craft | METHOD/GOLD rules: scope slug, Refs, Documentation-only, differentiated subjects |
| claim_tags / TIP harvest | package stable names under-harvested | METHOD, F72–F80, P-S12-*, case shelves |
| low-confidence skeleton | not used as final | n/a |
| body template policy | long prose OK; missing issue trailer | Refs #204 required |
| contradictions | type-family right vs package-local law wrong | gold_strict must encode package law, not only Hybrid parse |

---

## 10. Raw ↔ gold dimension table (series)

| Dimension | Raw (all/typical) | Gold | Miss? |
|:---|:---|:---|:---:|
| Primary type | docs | docs | |
| Scope | **docs** | **quality** | ● |
| Subject | generic `document …` | differentiated add/pin/scaffold + named surfaces | ● |
| SemVer-Impact | NONE | NONE | |
| Change-Types | docs | docs | |
| Changelog-Groups | Documentation[, **Miscellaneous**] | **Documentation** | ● (G1/G2/G4) |
| Body contract | long summary; weak specificity | METHOD-facing purpose + freeze claims | ◐ |
| Process-meta leak | none | none | |
| Included changes | thin / missing / inverted | full surface inventory | ● |
| Attribution | package bootstrap (OK) | package bootstrap (OK) | |
| Issue trailer | **absent** | **Refs: #204** | ● |
| Acceptance mode | clean accept | human message-only gold | ● |

### Raw messages (exact)

#### G1 raw — `48a46db`

```text
📝 docs(docs): document gold-miss failure analysis

Establishes a mandatory forensic genre for commit-message gold-miss reviews. Combines Session 12 pipeline depth with Sessions 1–11 acceptance law. Provides templates for full case analysis, cross-commit synthesis, and deferred historical stubs to standardise quality tracking.

Included changes:
- 📝 docs(templates): add case and synthesis templates

SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation, Miscellaneous
```

#### G2 raw — `15b84f9`

```text
📝 docs(docs): document gold-miss review and process docs

Establishes comprehensive process documentation for gold-miss reviews and commit rewrites. Clarifies strict rules for preserving tree OIDs during message-only amendments and mitigates hook re-entry risks. Defines workflows for promoting durable forensic analysis from transient issue comments into the repository single source of truth. Introduces standardised provenance labels and confidence matrices to ensure traceability and prevent unqualified claims in case files.

Included changes:
- 📝 docs(docs): document gold-miss review checklist
- 📝 docs(docs): document message-only rewrite guide
- 📝 docs(docs): document issue promotion workflow
- 📝 docs(docs): document provenance and confidence rules

SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation, Miscellaneous
```

#### G3 raw — `5bb957f`

```text
📝 docs(docs): document commit quality analysis docs

Establishes the foundational documentation for the commit-message quality analysis package. Introduces structured indices for the corpus, failure taxonomy, gold standard rules, and prevention backlog. Provides canonical identifiers (F72–F80, P-S12-1…9) and regime classifications to guide reviewers and agents in evaluating message envelopes and preventing common pitfalls. Maintains alignment with existing session archives and method consumers.

SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

#### G4 raw — `dfc382e`

```text
📝 docs(docs): document commit quality failure analysis

Establishes a structured documentation corpus for commit quality failure analysis under `docs/quality/`. The changes scaffold case directories for issues #204 and #220, introducing placeholder stubs for precursor instances, session slices, and forensic dogfood runs. A source map traces GitHub comment IDs to their target package paths, ensuring traceability during future promotions. The `docs/plans/README.md` index is updated to reflect the new quality analysis entry point. All artefacts follow the `1.0.0-combine` package versioning and await analytical content population.

Included changes:
- 📝 docs(plans): update README plan index
- 📝 docs(references): add source map for issue 204

SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation, Miscellaneous
```

### Gold messages (exact)

#### G1 gold — `114edee`

```text
📝 docs(quality): add Session 12 gold-miss METHOD and case templates

Introduce docs/quality as the commit-message failure-analysis SSOT.
METHOD.md freezes the forensic genre (regimes A/B, pipeline stages,
provenance/confidence, ID minting) by combining Session 12 depth with
Sessions 1–11 substrate law. Ship copy-paste case templates so new
gold-miss reviews no longer start from GitHub comment skeletons.

Included changes:
- 📝 docs(quality): package README with authority order and start-here map
- 📝 docs(quality): METHOD.md Session 12 forensic genre and depth floor
- 📝 docs(quality): CASE_TEMPLATE mandatory full-depth case skeleton
- 📝 docs(quality): CROSS_COMMIT_SYNTHESIS_TEMPLATE multi-group close-out
- 📝 docs(quality): OPEN_SUMMARY_STUB for deferred historical corpus only

Refs: #204
SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

#### G2 gold — `c682185`

```text
📝 docs(quality): add gold-miss operator process runbooks

Document the operator path that METHOD assumes: review checklist,
tree-preserving message-only rewrite (P-S8-9 ∪ F80/P-S12-9), Git and
Opik provenance labels, and promotion from issue comments into repo
SSOT after the GitHub 65k ceiling.

Included changes:
- 📝 docs(quality): gold-miss review checklist derived from METHOD
- 📝 docs(quality): message-only rewrite ritual (hooksPath / skip prepare)
- 📝 docs(quality): provenance labels and Direct vs Reconstructed confidence
- 📝 docs(quality): promote issue-comment archives into cases/ registries

Refs: #204
SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

#### G3 gold — `b43c0a5`

```text
📝 docs(quality): pin gold envelope, F72–F80 taxonomy, and P-S12 backlog

Land the shared law and ID registries METHOD cites. GOLD_STANDARD
captures Hybrid envelope, three-layer authority, diff-class defaults,
and reject-immediately stacks from S1–5/#204 body. Taxonomy freezes
canonical F72–F80 with extension maps; prevention pins P-S12-1…9;
CORPUS indexes TIP/V12-A bands and Instance A/B series classes.

Included changes:
- 📝 docs(quality): GOLD_STANDARD Hybrid envelope and diff-class defaults
- 📝 docs(quality): FAILURE_TAXONOMY regimes, R-index, F72–F80 canonical
- 📝 docs(quality): PREVENTION_BACKLOG P-S12-1…9 systems floor
- 📝 docs(quality): CORPUS tip/claim/series navigation and eval seed map

Refs: #204
SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

#### G4 gold — `d9a5e24`

```text
📝 docs(quality): scaffold case shelves and plans catalogue pointer

Reserve cases/204 and cases/220 homes for promoted forensic SSOT,
add the comment→path source map, and register the quality package in
docs/plans so eval/#217 consumers can find the gold-miss METHOD without
treating GitHub archives as living law.

Included changes:
- 📝 docs(quality): cases index and #204 epic corpus map
- 📝 docs(quality): #204 Instance A/B and S6–11 stub shelves
- 📝 docs(quality): #204 Session 12 and dogfood promote placeholders
- 📝 docs(quality): #220 S0 schema-freeze forward-case placeholder
- 📝 docs(quality): GitHub comment source-map for archive promotion
- 📝 docs(plans): link commit-message failure analysis package

Refs: #204
SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

---

## 11. Root-cause chain

```text
diff/extract (healthy docs paths; grouping correct)
→ path-class / priors insufficient for package-local scope+trailer+changelog law
→ semantic signals: docs-ish, no product poison required
→ rank locks docs/NONE/Documentation family (mostly correct ceiling)
→ prompt lacks dominant-module scope lock + issue trailer obligation + inventory harvest pressure
→ LLM single clean render: docs(docs) + document… craft + thin Included changes
→ guards/normalisers polish Hybrid shape only
→ gold_strict accepts parseable envelope (findings≈0)
→ write succeeds (Regime B)
→ operator detects miss vs CommitMessageLibrary / package gold
→ message-only rebuild (F80 risk on prepare path; final G4 via commit-tree)
```

### Primary defect

**Final-truth validation scores Hybrid parseability / family defaults, not package-local gold law** (scope slug, issue trailer, Documentation-only changelog, multi-file inventory, differentiated craft).

### Secondary defects

1. No path-root → scope map for `docs/quality/**` → `quality`.  
2. No hard reject for `Changelog-Groups` containing `Miscellaneous` on docs-only tips.  
3. No required issue trailer when branch/work is issue-scoped (`#204`).  
4. Inventory harvest does not require METHOD/registry/case surface names.  
5. Subject craft denylist lacks tautological `document … docs` / series-undifferentiated subjects.

---

## 12. Failure and prevention IDs

| ID | Applies? | Notes |
|:---|:---:|:---|
| F74 (ext) | ● | Scope not series/package canon — here tautological `docs` not snake; see **F81** mint |
| F76 | | not fixtures-as-fix |
| F77 | ◐ | docs family mostly correct; attribution OK; changelog impurity separated as **F82** |
| **F78** | ● | all tips — under-claim / missing Included changes |
| F79 (adj) | ◐ | not validate/enforce; generic document craft / sameness |
| F80 | ● | observed on rebuild path; `hooksPath=/dev/null` **insufficient vs hk** here; mitigated by `git commit-tree` |
| **F81** | ● | tautological path-root scope `docs(docs)` vs `docs(quality)` |
| **F82** | ● | docs-only `Miscellaneous` in Changelog-Groups (G1/G2/G4) |
| **F83** | ● | missing `Refs: #204` on issue-governed package tips |
| P-S12-4 | ◐ | type/SemVer docs+NONE held; incomplete without scope/changelog purity |
| **P-S12-6** | ● | inventory sufficiency |
| **P-S12-9** | ● | message-only rewrite controls |
| **P-S12-10** | ● | path-root scope lock |
| **P-S12-11** | ● | docs-only changelog allowlist |
| **P-S12-12** | ● | issue trailer required for issue-scoped work |

Registry rows minted in [`FAILURE_TAXONOMY.md`](../../FAILURE_TAXONOMY.md) / [`PREVENTION_BACKLOG.md`](../../PREVENTION_BACKLOG.md) with this case as first-seen.

---

## 13. Accept path, gold_strict, hooks

| Check | Observed | Required |
|:---|:---|:---|
| gold_strict | reconstructed pass on Hybrid shape | fail closed on F81/F82/F83/F78 package rules |
| fallback as final allowed? | no fallback used | **no** (P-S12-1) — N/A this series |
| process-meta body | absent | **no** (P-S12-2) |
| prepare-commit-msg re-entry | risk realized mid-rewrite; G4 used commit-tree | P-S12-9 |
| telemetry label vs truth | unbound | must not launder clean-accept as gold |

---

## 14. Corrective controls and tests

### Controls (by boundary)

| Boundary | Control | P* | Status |
|:---|:---|:---|:---|
| path-class envelope | `docs/quality/**` ⇒ scope `quality` (not `docs`) | P-S12-10 | proposed |
| signal quarantine | n/a heavy product poison | — | — |
| prompt construction | package-local gold_guidance: quality scope, Refs, Documentation-only | P-S12-10..12 | proposed |
| regen state | n/a (clean accept) | — | — |
| fallback fail-closed | keep P-S12-1 | P-S12-1 | existing |
| inventory / stable-id harvest | multi-file docs must list primary surfaces / registry names | P-S12-6 | strengthen |
| gold_strict | reject F81/F82/F83; reject generic document+docs subjects; require Included changes when ≥3 paths | P-S12-6/10/11/12 | proposed |
| hooks / message-only | **commit-tree** primary; hooksPath null may not stop hk; GIT_CG_SKIP_PREPARE if honoured | P-S12-9 | process doc strengthened |
| telemetry honesty | bind Opik on future package tips | — | open |

### Regression tests / fixtures

| Test or fixture | Path | Covers |
|:---|:---|:---|
| TBD path→scope fixture `docs/quality/**` | product `commit_quality` / gold_strict | F81 / P-S12-10 |
| TBD docs-only changelog allowlist | gold_strict | F82 / P-S12-11 |
| TBD issue trailer required when issue context present | trailers / gold_strict | F83 / P-S12-12 |
| TBD multi-file Included changes cardinality | inventory guards | F78 / P-S12-6 |
| This case as eval seed | `session-quality-package-dogfood` | Regime B clean-wrong |

### Eval harness linkage (if any)

| Item | Value |
|:---|:---|
| session tags | `quality-package-regime-b` · `session-12-adjacent` |
| metric families | scope_canon · inventory_sufficiency · changelog_purity · issue_trailer · craft_subject |
| expected codes | F78 · F81 · F82 · F83 · Regime B |

---

## 15. Final assessment

| Field | Value |
|:---|:---|
| Severity in series | **High** — entire four-tip landing required message-only rewrite |
| Regime confidence | **High** (Direct message+tree evidence; clean accept pattern) |
| Residual risk | Until P-S12-10..12 land in product/gold_strict, any `docs/quality/**` tip can clean-miss the same way |
| Blocks release / epic? | no product runtime block; **blocks claiming package self-hosting is dogfood-green** |
| Follow-ups | implement P-S12-10..12; bind Opik on next package tip; promote remaining S12 archive cases |

---

## 16. Cross-commit synthesis

### Regime split

* **Regime A tips:** none in raw series.  
* **Regime B tips:** G1–G4 — controls never fired; wrong looked perfect.  
* **Shared process defect:** F80 during rebuild (partial rewrite + G4 `commit-tree`).

### Comparative matrix

| Dimension | G1 raw | G2 raw | G3 raw | G4 raw | Gold law |
|:---|:---|:---|:---|:---|:---|
| type | docs | docs | docs | docs | docs |
| SemVer | NONE | NONE | NONE | NONE | NONE |
| scope | docs | docs | docs | docs | **quality** |
| inventory | 1 vague bullet | 4 weak docs(docs) bullets | **missing** | 2 of many surfaces | full surfaces |
| changelog | Doc+Misc | Doc+Misc | Documentation | Doc+Misc | Documentation |
| attribution | ok | ok | ok | ok | ok |
| Refs | missing | missing | missing | missing | Refs: #204 |
| acceptance | clean | clean | clean | clean | human gold rewrite |

### Observed subjects (do not regress)

```text
G1 ❌  📝 docs(docs): document gold-miss failure analysis
G1 ✅  📝 docs(quality): add Session 12 gold-miss METHOD and case templates
G2 ❌  📝 docs(docs): document gold-miss review and process docs
G2 ✅  📝 docs(quality): add gold-miss operator process runbooks
G3 ❌  📝 docs(docs): document commit quality analysis docs
G3 ✅  📝 docs(quality): pin gold envelope, F72–F80 taxonomy, and P-S12 backlog
G4 ❌  📝 docs(docs): document commit quality failure analysis
G4 ✅  📝 docs(quality): scaffold case shelves and plans catalogue pointer
```

### Failure ID map across series

| ID | Mode | G1 | G2 | G3 | G4 | Prevention |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| F78 | inventory | ● | ● | ● | ● | P-S12-6 |
| F81 | scope | ● | ● | ● | ● | P-S12-10 |
| F82 | changelog misc | ● | ● | | ● | P-S12-11 |
| F83 | issue trailer | ● | ● | ● | ● | P-S12-12 |
| F80 | rewrite process | series rebuild | | | ● tip finish | P-S12-9 |

### Why tips are not “the same bug” as S12 G1

Session 12 G1 was **Regime A** (fallback/skeleton destroyed envelope).  
This series is pure **Regime B**: grouping and docs family correct; package-local gold (scope/inventory/trailers/changelog/craft) failed silently.  
Closest ancestors: S12 G2–G4 / post-control dogfood pattern, now eating the **quality package itself**.

### Dogfood / residual irony

The package that defines METHOD, GOLD_STANDARD, taxonomy, and message-only rewrite ritual **could not author its own landing messages to gold** without human rewrite. High-value seed for eval: “does gold_strict enforce the law this package writes down?”

### Root causes (series-level)

| RC | Statement | Tips |
|:---|:---|:---|
| RC1 | gold_strict / accept path optimise for Hybrid shape + coarse path-class, not package-local presentation law | all |
| RC2 | scope defaults to path *kind* (`docs`) rather than dominant package slug (`quality`) | all |
| RC3 | inventory optional under clean docs accepts | G1/G3/G4 strongest |
| RC4 | issue trailer not mandatory when issue context exists | all |
| RC5 | Changelog allowlist not enforced for docs-only | G1/G2/G4 |

### Acceptance tests for the series (product must gain)

1. Fixture: staged `docs/quality/**` multi-file tip ⇒ scope must be `quality` (reject `docs`).  
2. Fixture: docs-only tip with `Changelog-Groups: Documentation, Miscellaneous` ⇒ gold_strict fail.  
3. Fixture: issue-linked docs package work without `Refs/Resolves/Closes/Fixes` ⇒ fail (unless explicit Null: #0 by owner).  
4. Fixture: ≥3 paths docs commit without Included changes (or with single collapsed bullet) ⇒ F78 fail.  
5. Subject craft: reject `document …` + scope `docs` tautology on non-meta paths.  
6. Eval seed row: this case’s raw messages vs gold messages scored Regime B.

### Priority order for fixes

1. P-S12-10 scope lock (`docs/quality/**` → `quality`).  
2. P-S12-6 inventory enforcement for multi-file docs.  
3. P-S12-11 Documentation-only changelog allowlist.  
4. P-S12-12 issue trailer requirement.  
5. Subject craft denylist / differentiation hints.  
6. Opik bind + eval metric wiring.

---

## 17. Source map

| Kind | Ref |
|:---|:---|
| GitHub comment | n/a (live forward dogfood; not archive promote) |
| Opik trace | **Opik-unbound** |
| Local notes | operator gold rewrite 2026-08-13; backup `backup/quality-fa-pre-msg-rewrite` |
| Related cases | [`session-12-dogfood-g2-g4.md`](./session-12-dogfood-g2-g4.md) (prior post-control B pattern); METHOD regimes §4 |
| Raw series | `48a46db` `15b84f9` `5bb957f` `dfc382e` |
| Gold series | `114edee` `c682185` `b43c0a5` `d9a5e24` |
