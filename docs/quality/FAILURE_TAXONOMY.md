# Failure taxonomy

> **Package:** commit-message failure analysis  
> **Version:** `1.0.0-combine`  
> **Status:** skeleton active — full F1–F71 prose harvest pending; **F72–F80 canonical**  
> **Method:** [`METHOD.md`](./METHOD.md)

---

## 0. How to use

1. Prefer an existing ID.  
2. Tag **regime** A/B when known.  
3. New IDs need a one-line definition + first-seen + related P*.  
4. S12 IDs **extend** earlier ones — use the extension map.

---

## 1. Regimes

| Regime | Name | Summary |
|:---|:---|:---|
| **A** | Controls fire; recovery worsens | Guard/regen/fallback path destroys envelope or leaks process-meta |
| **B** | Controls never fire; wrong looks perfect | Clean accept of library-wrong Hybrid-valid message |

---

## 2. Root causes R1–R25 (index)

> Full prose lives in #204 archives until harvested. Definitions below are **short index forms**.

| ID | Short definition | Notes |
|:---|:---|:---|
| R1 | Content keywords outrank path-class | motivates empty/ignored path_class |
| R2 | SOP description leakage into presentation | ≠ process-meta fallback |
| R3 | CHANGELOG echo chamber | docs/product bleed |
| R7 | Hallucinated work absent from diff | secrets/runtime/etc. |
| R9 | feat over fix | capability bar |
| R10 | Inventory cardinality failure | under-count surfaces |
| R13 | Unearned MINOR/feat framing | D16 |
| R14 | Unshipped product-as-actor | attribution |
| R16 | Wording-only misframed as feature | claim-lock |
| R17 | Primary-surface inversion | test inventory on prod+test |
| R18 | “Add guard” framing | craft |
| R19 | Matrix MINOR leak on dark-launch | evidence bar |
| R20 | Hallucination / false actor class (broader) | |
| R21–R25 | See #204 harvest | pending inline |

*Expand remaining R* rows in next harvest.*

---

## 3. Failures F1–F71 (index stub)

| Band | Origin | Status in package |
|:---|:---|:---|
| F1–F27 | #204 body catalogue | index pending full inline |
| F28–F71 | S6–11 extensions | index pending full inline |
| F-IB01–F-IB20 | Instance B implementation dogfood | index pending |

Until full inline harvest, **do not invent replacements** — cite archive IDs and add rows here when used in new cases.

### Harvest rule

When a new case needs Fn≤71, paste a one-line definition into this file at that time (lazy materialization beats wrong paraphrases).

---

## 4. Failures F72–F80 (canonical — Session 12)

| ID | Failure mode | Regime | Prevention | Proof |
|:---|:---|:---|:---|:---|
| **F72** | Guard/skeleton fallback shipped as final | A | P-S12-1 | [S12-G1](./cases/204/session-12.md) |
| **F73** | Process meta leaked into body | A | P-S12-2 | [S12-G1](./cases/204/session-12.md) |
| **F74** | Snake scope vs series canon | A (also craft) | P-S12-3 | [S12-G1](./cases/204/session-12.md) |
| **F75** | Type/SemVer collapse on product API/law add | A | P-S12-5 | [S12-G1](./cases/204/session-12.md) |
| **F76** | fixtures/tests typed `fix` | B | P-S12-4 | [S12-G2](./cases/204/session-12-g2.md) · [S12-G3](./cases/204/session-12-g3.md) |
| **F77** | docs_only typed `fix` + attribution bleed | B | P-S12-4 / P-S12-7 | [S12-G4](./cases/204/session-12-g4.md) |
| **F78** | Inventory under-claim / generic collapse | A+B | P-S12-6 | [S12 synth](./cases/204/session-12-synthesis.md) · G2–G4 |
| **F79** | validate/enforce overclaim on pure pins | B | P-S12-8 | [S12-G2](./cases/204/session-12-g2.md)–[G4](./cases/204/session-12-g4.md) |
| **F80** | prepare-commit-msg still runs on message-only rebuild | process | P-S12-9 | [S12 synth](./cases/204/session-12-synthesis.md) |
| **F81** | Tautological path-kind scope (`docs(docs)`) vs dominant package slug (`quality`) | B | P-S12-10 | 204-QP-RB |
| **F82** | Docs-only tip ships `Miscellaneous` in Changelog-Groups | B | P-S12-11 | 204-QP-RB |
| **F83** | Issue-governed tip omits required issue trailer (`Refs`/`Resolves`/…) | B | P-S12-12 | 204-QP-RB |

### Extension map (S12 → earlier)

| S12 | Extends (non-exhaustive) |
|:---|:---|
| F72 | F55/F56/F64-class fallback/final issues |
| F73 | process-meta / diagnostic body classes |
| F74 | scope canon / snake scope |
| F75 | type/SemVer collapse; capability framing |
| F76–F77 | path-class envelope misses |
| F78 | inventory / F thin-Included lineage |
| F79 | craft overclaim / presentation-pressure verbs |
| F80 | F44 / prepare re-entry / P-S8-9 lineage |
| F81 | F74 scope-canon class (path-kind tautology, not only snake) |
| F82 | docs changelog purity / reject-stack S2–S5 |
| F83 | issue trailer obligation / Hybrid machine trailers |

---

## 5. Tags

`envelope` · `craft` · `inventory` · `fallback` · `hook` · `telemetry` · `path-class` · `attribution` · `semver` · `prompt-contradiction`

---

## Document control

| Field | Value |
|:---|:---|
| Version | `1.0.0-combine` |
| F72–F83 | F72–F80 canonical; F81–F83 minted 204-QP-RB |
| F1–F71 | skeleton / lazy harvest |
| Last updated | 2026-08-13 |
