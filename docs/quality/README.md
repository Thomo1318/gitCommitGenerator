# Commit-message failure analysis package

> **Status:** `1.0.0-combine` — METHOD + templates ratified; substrate harvest in progress  
> **Path:** `docs/quality/`  
> **Branch origin:** `docs/quality-failure-analysis-package`  
> **Governing motivation:** #204 presentation quality + Session 12 forensic bar  
> **Consumers:** gold-miss reviewers, maintainers, agents, eval harness (#217)

---

## Mission

One versioned in-repo package that is the single place to:

1. Know what **gold** looks like  
2. **Classify** a miss (F* / R* / regime A|B)  
3. **Reconstruct** why (Opik-bound stage chain — Session 12 depth)  
4. Record **prevention** (P* → product / eval work)  
5. **Promote** cases out of GitHub comments into durable SSOT  
6. Feed **eval** without forking product law  

**GitHub issue comments** = intake + historical evidence.  
**This tree** = operating law + template + case library.

---

## Governing epics (SSOT pointers)

| Epic | Role vs this package | Authoritative paths |
|:---|:---|:---|
| **[#204](https://github.com/Thomo1318/gitCommitGenerator/issues/204)** | Presentation-quality epic + gold-miss **corpus** | This tree (`METHOD`, taxonomy, prevention, `cases/204/**`). Issue body = locks/V12-A until fully mirrored. Comments = archive after promote. |
| **[#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217)** | Opik evaluation harness **consumer** | Harness design SSOT: [`docs/plans/opik-evaluation-harness.md`](../plans/opik-evaluation-harness.md). Must **cite** F*/P*/regimes/cases here — must **not** fork gold-miss law. Issue #217 body = executive governance index. |
| Session 12 seed | Residual close-out + post-control dogfood proof pack | [`cases/204/session-12.md`](./cases/204/session-12.md) · [`session-12-g2.md`](./cases/204/session-12-g2.md) · [`session-12-g3.md`](./cases/204/session-12-g3.md) · [`session-12-g4.md`](./cases/204/session-12-g4.md) · [`session-12-synthesis.md`](./cases/204/session-12-synthesis.md) · [`session-12-dogfood-g2-g4.md`](./cases/204/session-12-dogfood-g2-g4.md) · F72–F83 · P-S12-1…12 |

**Rule:** after promotion, repo paths are living SSOT; GitHub comments remain intake evidence only (`process/promotion-from-issue-comment.md`).

---

## Start here

| If you need to… | Open |
|:---|:---|
| **Run a gold-miss review** | [`METHOD.md`](./METHOD.md) + copy [`templates/CASE_TEMPLATE.md`](./templates/CASE_TEMPLATE.md) |
| Multi-commit series close-out | [`templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md`](./templates/CROSS_COMMIT_SYNTHESIS_TEMPLATE.md) |
| Deferred historical stub only | [`templates/OPEN_SUMMARY_STUB.md`](./templates/OPEN_SUMMARY_STUB.md) |
| Operator checklist | [`process/gold-miss-review-checklist.md`](./process/gold-miss-review-checklist.md) |
| Message-only gold rewrite | [`process/message-only-rewrite.md`](./process/message-only-rewrite.md) |
| What gold looks like | [`GOLD_STANDARD.md`](./GOLD_STANDARD.md) |
| Failure / root-cause IDs | [`FAILURE_TAXONOMY.md`](./FAILURE_TAXONOMY.md) |
| Prevention backlog | [`PREVENTION_BACKLOG.md`](./PREVENTION_BACKLOG.md) |
| TIP / V12-A / Instance map | [`CORPUS.md`](./CORPUS.md) |
| Worked cases | [`cases/README.md`](./cases/README.md) |
| Comment → path map | [`references/source-map.md`](./references/source-map.md) |
| Agent skill | [`skill/SKILL.md`](./skill/SKILL.md) · local load path `.agents/skills/failure-analysis-package/SKILL.md` (symlink → package SSOT) |

---

## Authority order

```text
1. Product law — ranker · SOP · Hybrid · commit_gold · commit_quality · path-class · hooks
2. This package — METHOD · GOLD_STANDARD · taxonomy · prevention · cases
3. #204 issue body — locks / V12-A / anti-patterns (until fully mirrored)
4. #204 comment archives — intake; non-authoritative after promotion
5. Eval plan — docs/plans/opik-evaluation-harness.md (#217)
6. Chat / scratch — residue only
```

Eval metrics **wrap** product authorities and **cite** F*/P* from this package.

---

## Document classes

| Class | Files | Owns |
|:---|:---|:---|
| **Method** | `METHOD.md`, `templates/*`, `process/*` | How to analyse (S12 genre) |
| **Law** | `GOLD_STANDARD.md` | Envelope, matrices, accept/reject, D16, craft bans (S1–5 + body) |
| **Taxonomy** | `FAILURE_TAXONOMY.md`, `PREVENTION_BACKLOG.md`, `CORPUS.md` | F*/R*/P*, tip index, regimes |
| **Cases** | `cases/**` | Promoted incidents |

### Combine rule (S1–11 ∪ S12)

| Source | Role in package |
|:---|:---|
| **Session 12** | Method spine, depth floor, regimes A/B, F72–F83, P-S12-1…12, full-depth case exemplars |
| **Sessions 1–11 + body** | Gold matrices, accept/reject, F1–F71, R1–R25, TIP/V12-A index, Instance A/B, rewrite ritual precursors |

* Definitional law / matrix / ID / checklist → shared docs  
* Per-tip archaeology → stub or full case; not dumped into METHOD  
* If S12 restates procedure better → S12 wins  

---

## Layout

```text
docs/quality/
  README.md                 ← you are here
  METHOD.md                 ← mandatory forensic genre (Session 12)
  GOLD_STANDARD.md          ← envelope + matrices (S1–11 substrate)
  FAILURE_TAXONOMY.md       ← F* / R* / regimes
  PREVENTION_BACKLOG.md     ← P*
  CORPUS.md                 ← TIP / V12-A / series map
  process/
  skill/                 # agent SKILL.md (failure-analysis-package)
  templates/
  cases/
    204/                    ← presentation-quality epic corpus
    220/                    ← first forward case (S0 freeze)
  references/
```

---

## Decision locks

1. **S12 genre is mandatory** for new cases; S1–11 table-only writeups are non-compliant as final records.  
2. **Opik-unbound is allowed** if labelled; fabricated spans are not.  
3. **No new F* without taxonomy row**; no drive-by IDs only in issue comments.  
4. **Prevention without case** is backlog smell; **case without P*/test pointer** is incomplete.  
5. **Tree-preserving message-only rewrite** is the only gold-rewrite path in process docs.  
6. **Instance A ≠ B ≠ residual ≠ post-control dogfood** — always tag series class.  
7. **Comments overflow; repo does not** — long form lives here.  

---

## Workflow (short)

```text
miss detected
→ METHOD + CASE_TEMPLATE
→ identity + Git provenance
→ Opik bind or Opik-unbound
→ GOLD_STANDARD library class
→ pipeline stages → Regime A/B
→ F*/R*/P* registries
→ cases/<issue>/… + index
→ product / eval / comment pointer back to repo path
```

---

## Implementation status

| Step | Item | Status |
|:---:|:---|:---|
| B | `METHOD.md` + case templates | **done** |
| A | Tree + README + process + stubs | **done (this change)** |
| | Quality package Regime B dogfood case | **done** ([`cases/204/quality-package-regime-b.md`](./cases/204/quality-package-regime-b.md)) |
| | Promote S12 full cases | **done** — G1–G4 + synthesis + dogfood **active full** |
| | Substrate indexes (F1–F71 full prose, S1–11 stubs) | pending / skeleton |
| | `cases/220/s0-schema-freeze.md` | pending |
| | #204 / #217 pointers to this SSOT | **done** (package + eval plan + issue comment pointers) |

---

## Related docs

* [`docs/plans/README.md`](../plans/README.md) — plan class rules  
* [`docs/plans/opik-evaluation-harness.md`](../plans/opik-evaluation-harness.md) — eval design SSOT (#217); **consumes** Session-12 seed IDs / regimes from this package  
* [#204](https://github.com/Thomo1318/gitCommitGenerator/issues/204) — corpus epic (comments archive; cases live here)  
* [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) — harness governance index (not gold-miss law host)  
* [`docs/eval/README.md`](../eval/README.md) — S0 pins  
* Product: `commit_gold` / `commit_quality` / Hybrid hooks  

---

## Document control

| Field | Value |
|:---|:---|
| Package | commit-message-failure-analysis |
| Version | `1.0.0-combine` |
| Last updated | 2026-08-13 |
