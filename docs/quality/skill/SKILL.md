---
name: failure-analysis-package
description: Run METHOD-compliant gold-miss failure analysis for git-cg commit messages using docs/quality/ (cases, taxonomy, prevention, Opik binding, promotion).
when_to_use: "Use when analyzing a commit-message gold miss, filing/promoting a docs/quality case, classifying Regime A/B failures, minting F*/P* IDs, performing message-only gold rewrites, or feeding #217 eval from Session 12 seed materials. NOT for generic code review, product feature implementation without a gold-miss case, inventing parallel presentation law, or treating GitHub issue comments as living SSOT after promotion."
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, opik-mcp, code-review-graph
effort: high
version: 1.0.0-combine
---

# Failure Analysis Package — Gold-Miss Forensic Skill

> Package SSOT lives under `docs/quality/`. GitHub comments are intake/archive only after promotion. Eval (#217) **cites** this package; it must not fork gold-miss law.

## Overview

This skill enables agents to operate the commit-message failure analysis package end-to-end:

1. Detect and classify a gold miss (not merely Hybrid-parseable vs non-parseable).
2. Reconstruct the failure by pipeline stage with Opik binding (or explicit `Opik-unbound`).
3. Assign Regime A / B / A+B and series class.
4. Attach F*/R*/P* from package registries only.
5. Land durable cases under `docs/quality/cases/<issue>/…` and update indexes.
6. Optionally perform tree-preserving message-only gold rewrites without prepare re-entry.

**Package version:** `1.0.0-combine`  
**Genre authority:** Session 12 (Opik-bound forensic reconstruction)  
**Law substrate:** Sessions 1–11 + #204 body (matrices, F1–F71, accept/reject stacks)

## When to Use

✅ **Good for**
- Generated tip fails the Hybrid / gold envelope the operator would ship
- Message-only rewrite required to reach gold (tree preserved)
- Post-control dogfood still misses gold
- Multi-commit residual series needing synthesis
- Promoting #204 (or similar) comment forensics into repo SSOT
- Mapping cases into F72–F83 / P-S12-* for eval harness consumption

❌ **Not for**
- Generic PR review without a gold-miss case
- Replacing product law (`ranker`, SOP, Hybrid, `commit_gold`, `commit_quality`, path-class, hooks)
- Inventing presentation metrics inside `#217` / eval plan
- Finalising new work as S1–11 tip-table-only writeups
- Fabricating Opik span/trace IDs
- Using `--no-verify` alone as message-only rewrite safety

## Authority Order (hard)

```text
1. Product law — ranker · SOP · Hybrid · commit_gold · commit_quality · path-class · hooks
2. docs/quality/ — METHOD · GOLD_STANDARD · FAILURE_TAXONOMY · PREVENTION_BACKLOG · cases
3. #204 issue body — locks / V12-A / anti-patterns until fully mirrored
4. #204 comment archives — intake evidence; non-authoritative after promotion
5. Eval plan — docs/plans/opik-evaluation-harness.md (#217) — consumer only
6. Chat / scratch — residue only
```

**Epic split**
| Issue | Owns | Does not own |
|:---|:---|:---|
| **#204** | Corpus motivation + historical intake | Living case library after promote |
| **#217** | Harness governance + eval plan pointer | METHOD, F*/P* definitions, case prose |

## Package Map (open these, don't reinvent)

| Need | Path |
|:---|:---|
| Start here | `docs/quality/README.md` |
| Mandatory method | `docs/quality/METHOD.md` |
| What gold is | `docs/quality/GOLD_STANDARD.md` |
| Failure / root-cause IDs | `docs/quality/FAILURE_TAXONOMY.md` |
| Prevention IDs | `docs/quality/PREVENTION_BACKLOG.md` |
| TIP / V12-A / series map | `docs/quality/CORPUS.md` |
| Single-tip template | `docs/quality/templates/CASE_TEMPLATE.md` |
| Multi-group synthesis template | `docs/quality/templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md` |
| Deferred stub only | `docs/quality/templates/OPEN_SUMMARY_STUB.md` |
| Operator checklist | `docs/quality/process/gold-miss-review-checklist.md` |
| Message-only rewrite | `docs/quality/process/message-only-rewrite.md` |
| Promote from GitHub | `docs/quality/process/promotion-from-issue-comment.md` |
| Provenance labels | `docs/quality/process/provenance-and-confidence.md` |
| Comment → path map | `docs/quality/references/source-map.md` |
| Case index | `docs/quality/cases/README.md` |
| #204 map | `docs/quality/cases/204/README.md` |
| Eval consumer | `docs/plans/opik-evaluation-harness.md` |

### Normative worked proofs (read before filing new cases)

| Proof | Path | Regime / class |
|:---|:---|:---|
| S12 G1 | `docs/quality/cases/204/session-12.md` | A · residual-close-out |
| S12 G2 | `docs/quality/cases/204/session-12-g2.md` | B · residual-close-out |
| S12 G3 | `docs/quality/cases/204/session-12-g3.md` | B · residual-close-out |
| S12 G4 | `docs/quality/cases/204/session-12-g4.md` | B · residual-close-out |
| S12 synthesis | `docs/quality/cases/204/session-12-synthesis.md` | A+B · residual-close-out |
| S12 dogfood G2–G4 | `docs/quality/cases/204/session-12-dogfood-g2-g4.md` | B · post-control-dogfood |
| Quality package self-dogfood | `docs/quality/cases/204/quality-package-regime-b.md` | B · post-control-dogfood |
| Forward stub | `docs/quality/cases/220/s0-schema-freeze.md` | forward |

## Core Concepts

### Series class (tag every case — never collapse)

| Class | Meaning |
|:---|:---|
| `precursor` | Why epic/laws exist (Instance A) |
| `implementation-dogfood` | Misses while shipping the fix (Instance B) |
| `residual-close-out` | Correct trees; wrong messages after a planned split |
| `post-control-dogfood` | After P-* controls landed; still misses |
| `forward` | New work using this package as base |

### Regimes (required)

**Regime A — controls fire; recovery makes it worse**
```text
healthy diff → plausible rank/contract
→ prompt or regen contradiction
→ guard thrash / budget exhaust
→ skeleton/fallback rewrites presentation
→ write succeeds under gold_strict
→ telemetry understates failure
```
Proof: S12-G1 · IDs F72–F75 · P-S12-1/2/3/5

**Regime B — controls never fire; wrong envelope looks perfect**
```text
healthy extract → contaminated signals / empty path_class_gate
→ wrong type/SemVer/scope lock looks official
→ single clean generation
→ normalisers polish the wrong envelope
→ gold_strict scores shape only → accept
```
Proof: S12-G2–G4 + dogfood · IDs F76–F79 (+F81–F83) · P-S12-4/6/7/8 (+10–12)

**Shared process defect:** F80 / P-S12-9 — prepare-commit-msg re-enters `git-cg` on message-only rebuilds.

### Pipeline stages (walk in order)

```text
1.  diff extract / file summary
2.  path-class · priors · staged_paths · claim tags
3.  semantic signals / fingerprint health
4.  rank_commit_intents
5.  contract lock (type · emoji · SemVer · changelog family)
6.  prompt assemble (incl. low-confidence skeleton / gold guidance)
7.  LLM render attempt(s)
8.  validate / guards
9.  regeneration loop (retained vs cleared)
10. presentation fallback / skeleton
11. final render
12. write path · hooks · prepare re-entry
13. gold_strict / accept decision
14. telemetry counters / provenance labels
```

**Analyst rule:** name the **first stage that left the gold path** and the **stage that made the miss irreversible**.

### Provenance vocabulary

| Label | Meaning |
|:---|:---|
| `Git-raw` | First generator-written / first observed bad tip |
| `Git-mid` | Intermediate rewrite before gold |
| `Gold-final` | Operator-accepted gold tip |
| `Rewrite-map-confirmed` | Tree OID unchanged raw→gold |
| `Opik-unbound` | No trustworthy Opik bind (must be explicit) |
| **Direct** | Read from git object, Opik span, or product log |
| **Reconstructed** | Inferred; must be labelled in prose + matrix |

## Protocol

### Step 0 — Load law (always)

1. Read `docs/quality/README.md` decision locks.
2. Read `docs/quality/METHOD.md` §§1–12 (do not skip regime + depth floor).
3. Skim `GOLD_STANDARD.md` accept/reject stack for the diff class in play.
4. Open the closest worked proof (Regime A → G1; Regime B → G2/G3/G4/dogfood).

### Step 1 — Decide case shape

| Situation | Artefact |
|:---|:---|
| Single tip full forensic | Copy `templates/CASE_TEMPLATE.md` → `cases/<issue>/<slug>.md` |
| ≥2 groups, shared systems pattern | Per-tip cases **plus** `templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md` |
| Deferred historical only | `templates/OPEN_SUMMARY_STUB.md` (never pretend full depth) |

**Status values**
- `draft` while writing
- `active` only when METHOD §12 gate passes
- Never leave `placeholder — content promote pending` in promoted SSOT

### Step 2 — Establish identity + tree preservation

Collect before prose:

```bash
# identity
git rev-parse --abbrev-ref HEAD
git log --oneline -20

# raw / gold candidates
git show -s --format='%H%n%s%n%T' <raw_sha>
git show -s --format='%H%n%s%n%T' <gold_sha>

# confirm message-only rewrite (trees equal)
test "$(git rev-parse <raw_sha>^{tree})" = "$(git rev-parse <gold_sha>^{tree})" && echo Rewrite-map-confirmed
```

Record series class, branch, base→tip, planned split, severity.

### Step 3 — Bind Opik or mark unbound

Prefer live traces when the lab run produced them:

- Use Opik MCP / UI: project (often `gitCommitGenerator`), trace/span IDs, model, time window.
- Capture: ranked candidates, locked contract, `path_class_gate`, `staged_paths`, attempt plans, gold_strict findings, fallback reason, acceptance mode.
- If no trustworthy bind: write **`Opik-unbound`** + reason.
- **Never invent** trace/span IDs.

### Step 4 — Classify library class + gold envelope

Using `GOLD_STANDARD.md`:

1. Diff-class defaults (tests-only / fixtures / docs / product_src / mixed).
2. Intended primary type, scope canon, SemVer, changelog family.
3. Body contract + craft bans (process-meta, Context:/Changes:, attribution bleed, validate/enforce on pins).
4. Inventory sufficiency (stable IDs, multi-surface — no generic collapse).
5. Three-layer authority invariant (rank immutable · presentation deterministic · final operator-safe).

**Gold ≠ Hybrid-parseable.** Hybrid-valid + library-wrong is classic Regime B.

### Step 5 — Reconstruct by stage

Walk METHOD §5 stages. For each material stage note:

- Observation (quote evidence)
- Confidence (Direct | Reconstructed)
- Whether still on gold path

Minimum coverage: **extract → rank/contract → render/accept**.

Fill:
1. Open summary (METHOD §6.1)
2. Raw↔gold dimension table (METHOD §6.2)
3. Evidence confidence matrix (METHOD §6.3)
4. Stage-ordered root-cause chain (ASCII)
5. Ranking vs locked contract
6. Attempts / fallback / clean-accept
7. Evidence channels (`path_class_gate`, `staged_paths`, gold guidance contradictions)

### Step 6 — Assign regime + IDs

1. Regime A and/or B from pattern (not from vibes).
2. Attach F*/R* from `FAILURE_TAXONOMY.md` only.
3. Attach or propose P* in `PREVENTION_BACKLOG.md`.
4. **Minting rules**
   - Prefer existing rows.
   - New F* → taxonomy one-liner + first-seen + related P*.
   - New P* → rule · blocks F* · status · owning issue · tests/anchors · source case.
   - Do not mint IDs only in issue comments or chat.

#### Canonical S12 systems floor (quick index)

| F* | Mode | P* |
|:---|:---|:---|
| F72 | Fallback/skeleton shipped as final | P-S12-1 |
| F73 | Process-meta body leak | P-S12-2 |
| F74 | Snake scope vs series canon | P-S12-3 |
| F75 | Type/SemVer collapse on product law add | P-S12-5 |
| F76 | fixtures/tests typed `fix` | P-S12-4 |
| F77 | docs_only typed `fix` + attribution bleed | P-S12-4 / P-S12-7 |
| F78 | Inventory under-claim / generic collapse | P-S12-6 |
| F79 | validate/enforce overclaim on pure pins | P-S12-8 |
| F80 | prepare re-entry on message-only | P-S12-9 |
| F81 | Tautological path-kind scope (`docs(docs)`) | P-S12-10 |
| F82 | Docs-only ships `Miscellaneous` changelog | P-S12-11 |
| F83 | Issue-governed tip missing issue trailer | P-S12-12 |

### Step 7 — Controls, honesty, residual risk

State explicitly:

- `gold_strict` outcome and whether shape-only scoring lied
- Hook / prepare re-entry behaviour
- Telemetry vs operator truth (no success laundering)
- Corrective controls + regression test pointers (prompt / regen / fallback / envelope / gold_strict / path-class)
- Residual risk and whether post-control dogfood is still required

### Step 8 — Land package SSOT + indexes

Required on every full promote:

1. Case file under `docs/quality/cases/<issue>/…` with YAML front-matter:
   ```yaml
   package: commit-message-failure-analysis
   doc: case  # or cross-commit-synthesis
   version: 1.0.0-combine
   status: active
   issue: <n>
   case_id: <ISSUE-…>
   series_class: <class>
   regime: <A|B|A+B>
   opik: <bound|unbound>
   ```
2. Update `docs/quality/cases/README.md` table row.
3. Update issue map if present (`cases/204/README.md`, etc.).
4. If from GitHub: update `docs/quality/references/source-map.md` → **promoted**.
5. Touch `CORPUS.md` / taxonomy / prevention links when seed/proof IDs change.
6. Mark GitHub comment superseded (operator / authenticated `gh`) — do not delete:
   > Superseded as SSOT by `docs/quality/cases/...`. Retained as intake evidence.
7. Only then: product fix, eval fixture, or issue pointer **back to repo path**.

### Step 9 — Message-only gold rewrite (optional, high risk)

Follow `docs/quality/process/message-only-rewrite.md`. Hard rules:

- Tree must stay identical (`Rewrite-map-confirmed`).
- **Do not** rely on `--no-verify` alone (F80).
- Prefer `git commit-tree` / approved hooksPath or skip flag paths documented in process file.
- Under `hk`, prefer `GIT_CG_SKIP_PREPARE=1` (truthy: `1`/`true`/`yes`/`on`) for amend paths; `core.hooksPath=/dev/null` is unsupported as a prepare short-circuit. Use **commit-tree** + clean-worktree reset when object-level rebuild is required.
- Prefer the project File Method for multi-line messages:
  ```bash
  # write perfect message to .git/NEW_COMMIT_MSG then:
  git commit --amend -F .git/NEW_COMMIT_MSG   # only when amend explicitly approved
  # or commit-tree flow per process doc for multi-tip rebuilds
  ```
- File the case with raw→gold SHAs and tree OIDs.

### Step 10 — METHOD §12 gate (definition of done)

A case is package SSOT only when **all** are true:

- [ ] Open summary complete (result, regime, path focus, severity, raw→gold SHAs, one-line diagnosis, F*/P*)
- [ ] Series class tagged
- [ ] Git provenance labelled
- [ ] Opik bound **or** `Opik-unbound` explicit
- [ ] Confidence matrix present (Direct vs Reconstructed)
- [ ] Pipeline stages addressed (at least extract → rank/contract → render/accept)
- [ ] Raw↔gold dimension table filled
- [ ] Stage-ordered root-cause chain present
- [ ] F*/P* from package registries
- [ ] gold_strict / acceptance / hook outcome stated
- [ ] Controls + test pointers listed
- [ ] Indexed in `cases/README.md` (+ source-map if promoted)

Anything less = **intake notes**, not SSOT.

## Analyst Anti-Patterns (reject these)

| Anti-pattern | Corrective |
|:---|:---|
| S1–11 table only for new work | METHOD + CASE_TEMPLATE |
| Regime A = “LLM bad” | Name contradiction → regen → fallback chain |
| Regime B = “fallback bug” | No fallback: empty gates + clean wrong accept |
| Missing Opik section | `Opik-unbound` + why |
| Fabricated spans | Forbidden |
| New F* only in chat/comment | Taxonomy row first |
| Case without P* / residual watch | Incomplete |
| Post-control dogfood labelled Instance A | Wrong series class |
| `--no-verify` as sole rewrite safety | F80 · message-only-rewrite process |
| Eval metric invents presentation law | Wrap product code; cite F*/P* |
| Leaving pending/placeholder in promoted cases | Full depth or explicit stub template |
| Treating GitHub comment as living SSOT after promote | Package path wins |

## Commit Conventions for Package Docs

When committing package work (after explicit user approval to commit):

```text
📝 docs(quality): <imperative subject ≤72c with emoji+type+scope>

<body: provenance, case IDs, regime, controls, index closure>

Refs: #<issue>
SemVer-Impact: NONE
Change-Types: docs
Changelog-Groups: Documentation
```

Prefer focused commits:
1. one full case promote per commit when large
2. index/sibling closure commit after a series promote

Do not amend prior promotion commits unless a concrete defect is found and the user approves history rewrite.

## Tooling Tips

- Prefer `rg` / `fd` over `grep` / `find`.
- Prefer `trash` over `rm`.
- **Graph-first repository exploration:** before any `Read` / `Grep` / `Glob` (or equivalent) repository scans for product/code context, use code-review-graph tools (`get_minimal_context`, `semantic_search_nodes`, `query_graph`, `detect_changes`, `get_impact_radius`, `get_affected_flows`, `get_review_context`). Fall back to file scans only when the graph lacks the needed information.
- For Opik evidence: use `opik-mcp` when available; otherwise mark unbound.
- Graph tools aid blast-radius and code location; they do **not** replace METHOD forensic depth or case identity fields.
- Secrets/redaction: never paste tokens, raw `.env`, or unredacted sensitive diffs into cases.

## Quick Start Recipes

### A) New forward gold-miss (e.g. #220)

```text
1. Copy CASE_TEMPLATE → cases/220/<slug>.md
2. Fill identity + raw/gold (or single observed tip)
3. Bind Opik or Opik-unbound
4. Walk stages → regime → F*/P*
5. METHOD §12 gate
6. Index in cases/README.md
7. Link prevention/tests
```

### B) Promote GitHub comment series (Session-12 pattern)

```text
1. Read process/promotion-from-issue-comment.md
2. Split oversized comments into G1..Gn + synthesis
3. Full-depth each tip; synthesis for systems pattern
4. Update taxonomy/prevention/corpus/source-map/README
5. Supersede comments as archive evidence
6. Commit case files then index closure
```

### C) Post-control dogfood

```text
1. series_class: post-control-dogfood
2. Cite which P-* were supposed to block the miss
3. Show residual gap (truth gap vs incomplete control)
4. Keep Regime B/A honesty; don't relabel as precursor
```

## Output Contract (agent response)

When finishing an analysis task, report:

1. Case path(s) written/updated
2. Regime + series class + case_id
3. Raw→gold SHAs + tree preservation
4. F*/P* attached (and any newly minted rows)
5. Opik bind status
6. METHOD §12 gate result (pass/fail + gaps)
7. Index/source-map updates
8. Residual risks / follow-ups (product, eval, dogfood)

## Related Skills

| Skill | Use with this package when… |
|:---|:---|
| `opik` / opik-mcp | Binding traces, comparing attempts, reading spans |
| `systematic-debugging` | Broader product bug beyond presentation forensics |
| `review-changes` / `review-delta` | Code fix PR after case-driven controls |
| `verify-changes` | Proving a control actually blocks the miss |
| `technical-writer` | Prose clarity only — does not override METHOD structure |

---

## Document control

| Field | Value |
|:---|:---|
| Skill | failure-analysis-package |
| Package | commit-message-failure-analysis |
| Version | 1.0.0-combine |
| SSOT root | `docs/quality/` |
| Genre | Session 12 METHOD |
| Last aligned | 2026-08-13 (S12 G1–G4 + synthesis + dogfood active full) |
