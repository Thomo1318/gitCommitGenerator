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
| **P-S12-1** | If `presentation_fallback_reason != none` **or** body matches skeleton/fallback templates, gold-strict **must fail** (`GOLD_SKELETON_FALLBACK_FINAL`). | F72 | open/partial | #204 | `commit_gold` / gold_strict | [S12-G1](./cases/204/session-12.md) |
| **P-S12-2** | Body denylist: `Cleared guard codes`, `Deterministic presentation fallback`, guard exhaustion / presentation-safe boilerplate. | F73 | open/partial | #204 | presentation guards | [S12-G1](./cases/204/session-12.md) |
| **P-S12-3** | Force hyphenated scopes (`commit-quality`, …). Reject snake `commit_quality`. | F74 | open/partial | #204 | scope canon | [S12-G1](./cases/204/session-12.md) |
| **P-S12-4** | Hard live envelope: pure tests ⇒ `test`+`NONE`; fixtures/goldens ⇒ primary `test`; pure docs ⇒ `docs`+`NONE`. | F76/F77 | open/partial | #204 | path-class gate | [S12-G2](./cases/204/session-12-g2.md)–[G4](./cases/204/session-12-g4.md) · [dogfood](./cases/204/session-12-dogfood-g2-g4.md) |
| **P-S12-5** | Product policy adds (named laws/guards/capability tags) ⇒ primary `feat` (fix secondaries ok), SemVer ≥ `PATCH`; forbid `chore`/`NONE` collapse. | F75 | open/partial | #204 | capability ceiling | [S12-G1](./cases/204/session-12.md) |
| **P-S12-6** | Characterisation/docs commits must inventory stable IDs and named surfaces (TIP-G*, V12-A*, guards, README/CHANGELOG rows). | F78 | open/partial | #204 | inventory harvest | [S12 synth](./cases/204/session-12-synthesis.md) |
| **P-S12-7** | Docs-only tips may reference prior laws by name but must not claim to add/implement product guards from earlier commits. | F77 | open/partial | #204 | attribution guards | [S12-G4](./cases/204/session-12-g4.md) |
| **P-S12-8** | Ban validate/enforce/implement framing on pure fixture pins, proof packs, docs-of-prior-work; prefer pin/lock/cover/freeze/characterise/document/record. | F79 | open/partial | #204 | craft denylist | [S12-G2](./cases/204/session-12-g2.md)–[G4](./cases/204/session-12-g4.md) |
| **P-S12-9** | Message-only rebuild: primary control is `GIT_CG_SKIP_PREPARE=1` (truthy: `1`/`true`/`yes`/`on`) so prepare-commit-msg generation no-ops. `--no-verify` alone is insufficient. Under hk-managed installs, `core.hooksPath=/dev/null` is **unsupported** as a prepare short-circuit. For multi-tip rebuilds, `git commit-tree` remains valid when skip/amend paths are awkward; require clean worktree before any `git reset --hard <new>` and verify tree OID unchanged. | F80 | process doc + product skip shipped; operators must still preserve commit-msg validation/telemetry discipline | #204 | [`process/message-only-rewrite.md`](./process/message-only-rewrite.md) | [S12 synth](./cases/204/session-12-synthesis.md) + [204-QP-RB](./cases/204/quality-package-regime-b.md) |
| **P-S12-10** | Path-root scope lock: dominant package slug from path (`docs/quality/**` → scope `quality`). Reject tautological `docs(docs)` when a deeper package root exists. | F81 | proposed | #204 | gold_strict / commit_quality path→scope | 204-QP-RB |
| **P-S12-11** | Docs-only changelog allowlist: pure `docs/**` tips may use `Documentation` only — reject `Miscellaneous` (and other families) unless a non-docs surface is truly present. | F82 | proposed | #204 | gold_strict changelog allowlist | 204-QP-RB |
| **P-S12-12** | Issue trailer required for issue-governed work: when branch/issue context is non-null, require `Refs` / `Resolves` / `Closes` / `Fixes: #<id>` (owner-only `Null: #0`). | F83 | proposed | #204 | trailer validators / gold_strict | 204-QP-RB |

---

## 2. Earlier preventions (placeholders)

| ID band | Origin | Status |
|:---|:---|:---|
| Body / slice locks | #204 body | shipped / mirror pending |
| P-S6…P-S11 | Sessions 6–11 | harvest pending |
| P-S8-9 | message-only rewrite precursor | **unified into P-S12-9 + process doc** |
| P-IB-* | Instance B dogfood | harvest pending |
| Dogfood P-G* | post-control S12 dogfood | harvest with dogfood case promote |
| P-S12-10…12 | quality-package Regime B self-dogfood | **minted** with [`cases/204/quality-package-regime-b.md`](./cases/204/quality-package-regime-b.md) |

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
