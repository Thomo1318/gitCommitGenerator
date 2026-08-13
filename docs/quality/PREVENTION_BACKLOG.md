# Prevention backlog

> **Package:** commit-message failure analysis  
> **Version:** `1.0.0-combine`  
> **Status:** P-S12-1…9 canonical; earlier P* placeholders  
> **Method:** [`METHOD.md`](./METHOD.md)

Columns: **ID · rule · blocks · status · owning issue · tests/anchors · source case**

---

## 1. Session 12 systems floor (canonical)

| ID | Rule | Blocks | Status | Owning issue | Tests / anchors | Source |
|:---|:---|:---|:---|:---|:---|:---|
| **P-S12-1** | If `presentation_fallback_reason != none` **or** body matches skeleton/fallback templates, gold-strict **must fail** (`GOLD_FALLBACK_NOT_FINAL`). | F72 | open/partial | #204 | `commit_gold` / gold_strict | S12-G1 |
| **P-S12-2** | Body denylist: `Cleared guard codes`, `Deterministic presentation fallback`, guard exhaustion / presentation-safe boilerplate. | F73 | open/partial | #204 | presentation guards | S12-G1 |
| **P-S12-3** | Force hyphenated scopes (`commit-quality`, …). Reject snake `commit_quality`. | F74 | open/partial | #204 | scope canon | S12-G1 |
| **P-S12-4** | Hard live envelope: pure tests ⇒ `test`+`NONE`; fixtures/goldens ⇒ primary `test`; pure docs ⇒ `docs`+`NONE`. | F76/F77 | open/partial | #204 | path-class gate | S12-G2–G4 |
| **P-S12-5** | Product policy adds (named laws/guards/capability tags) ⇒ primary `feat` (fix secondaries ok), SemVer ≥ `PATCH`; forbid `chore`/`NONE` collapse. | F75 | open/partial | #204 | capability ceiling | S12-G1 |
| **P-S12-6** | Characterisation/docs commits must inventory stable IDs and named surfaces (TIP-G*, V12-A*, guards, README/CHANGELOG rows). | F78 | open/partial | #204 | inventory harvest | S12 all |
| **P-S12-7** | Docs-only tips may reference prior laws by name but must not claim to add/implement product guards from earlier commits. | F77 | open/partial | #204 | attribution guards | S12-G4 |
| **P-S12-8** | Ban validate/enforce/implement framing on pure fixture pins, proof packs, docs-of-prior-work; prefer pin/lock/cover/freeze/characterise/document/record. | F79 | open/partial | #204 | craft denylist | S12-G2–G4 |
| **P-S12-9** | Message-only rebuild: disable prepare git-cg (`core.hooksPath=/dev/null` or `GIT_CG_SKIP_PREPARE=1`). `--no-verify` alone insufficient. | F80 | process doc done; product polish TBD | #204 | [`process/message-only-rewrite.md`](./process/message-only-rewrite.md) | S12 series |

---

## 2. Earlier preventions (placeholders)

| ID band | Origin | Status |
|:---|:---|:---|
| Body / slice locks | #204 body | shipped / mirror pending |
| P-S6…P-S11 | Sessions 6–11 | harvest pending |
| P-S8-9 | message-only rewrite precursor | **unified into P-S12-9 + process doc** |
| P-IB-* | Instance B dogfood | harvest pending |
| Dogfood P-G* | post-control S12 dogfood | harvest with dogfood case promote |

---

## 3. Minting rule

New P* requires:

1. One-line rule  
2. F* blocked  
3. Case pointer  
4. Status + owner  

---

## Document control

| Field | Value |
|:---|:---|
| Version | `1.0.0-combine` |
| Last updated | 2026-08-13 |
