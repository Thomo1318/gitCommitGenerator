# Gold standard — commit message envelope & library defaults

> **Package:** commit-message failure analysis  
> **Document:** `GOLD_STANDARD`  
> **Version:** `1.0.0-combine`  
> **Status:** skeleton active — S1–5 / #204 body law substrate (expand iteratively)  
> **Method consumer:** [`METHOD.md`](./METHOD.md) §9  
> **Sources:** #204 body · Sessions 1–5 matrices · accept/reject stacks S2→S5 · D16 / three-layer authority

---

## 0. Purpose

Define **what gold looks like** so METHOD cases can mark “standard not met” without re-deriving law from tip archaeology.

This file is **presentation / envelope law for reviewers**. Product modules remain runtime authority:

* `commit_gold` · `commit_quality` · path-class · Hybrid hooks · ranker/SOP

When code and this doc disagree, **verify code/tests**, then amend this doc.

---

## 1. Hybrid envelope (machine + human)

```text
<emoji> <cc_type>(<scope>): <subject>
```

**Hard constraints**

| Rule | Requirement |
|:---|:---|
| Subject length | ≤ 72 characters (do not weaken without explicit governance) |
| Type | Conventional Commit type from locked family |
| Scope | Hyphenated canon where series defines it (`commit-quality`, not `commit_quality`) |
| Emoji | Matrix/intent-aligned; not free decoration |
| Body | Operator-facing; **no** process-meta / guard diagnostics |
| Trailers | Issue + SemVer + Change-Types + Changelog-Groups when applicable |

### Required trailers (when issue-linked work)

```text
Refs|Resolves|Closes|Fixes|Null: #<id>
SemVer-Impact: <MAJOR|MINOR|PATCH|NONE>
Change-Types: <csv>
Changelog-Groups: <csv>
```

`Null` issue id is **always** `0` and **only** the owner may set it.

---

## 2. Three-layer authority invariant (D16 adjacency)

1. **Ranked authority immutable** for the analysis window (intent_id / rank outcome is not casually rewritten by presentation recovery).  
2. **Presentation constraints deterministic** (path-class, guards, scopes, inventory rules).  
3. **Rendered presentation final and operator-safe** (no skeleton/fallback diagnostics as the shipped body).

**Proof case:** Session 12 G1 — fallback rewrote type/SemVer/body while keeping intent identity signals → Layer 2/3 corruption (Regime A).

---

## 3. Diff-class → envelope defaults

> Defaults are **ceilings and primary families**, not excuses to ignore multi-surface inventory.

| Diff class | Primary type | SemVer default | Changelog family (typical) | Scope notes |
|:---|:---|:---|:---|:---|
| Pure `tests/**` | `test` | `NONE` | `Tests` | module under test if clear; not package dump |
| Fixtures / corpus / goldens / harness pins | `test` (docs secondary ok) | `NONE` | `Tests` (+ `Documentation` if docs paths) | `fixtures` / harness slug |
| Pure docs (`README`/`CHANGELOG`/`docs/**`) | `docs` | `NONE` | `Documentation` | `readme` / `docs` / `adr` |
| ADR only | `docs` | `NONE` | `Documentation` | `adr` |
| Product correctness / safety fix | `fix` | `PATCH` | `Fixed` | dominant module hyphen slug |
| Product capability / named law add | `feat` (fix secondaries ok) | ≥ `PATCH` (MINOR only with capability evidence) | `Added` (+ `Fixed`) | series canon scope |
| Wording-only / claim-lock on product+test | often `fix` or `test` per dominant truth | `PATCH` ceiling common | mixed | multi-surface inventory required |
| Dark-launch / carry-through | per path-class truth | no unearned MINOR | per surfaces | evidence bar D16 |
| Telemetry bool / chore-class ops | `chore` when truly non-user | `NONE` or `PATCH` per law | `Miscellaneous` carefully | do not steal test/docs |

**P-S12-4 live envelope (systems floor):**

* pure tests → `test` + `NONE`  
* fixtures corpus/goldens → primary `test`  
* pure docs → `docs` + `NONE`

---

## 4. Reject immediately if… (operator stack)

Cumulative S2→S5 style gates for human/agent amend review:

### SemVer / type

- [ ] Unearned `MAJOR` or `MINOR` without capability / breakage evidence  
- [ ] Primary `feat` on pure fix / scrub / correctness  
- [ ] Primary `fix` on pure tests or pure docs  
- [ ] `chore`/`NONE` collapse on product API/law add (see P-S12-5)

### Scope / craft

- [ ] Snake scope where hyphen canon exists (`commit_quality`, `scoped_history`)  
- [ ] Package scope `git_cg` when a dominant module/behaviour slug exists  
- [ ] Tautological path-kind scope (`docs(docs)`, `test(tests)`) when a dominant package/module slug exists (`quality`, …) — **F81 / P-S12-10**  
- [ ] Title Case subjects; vague “improve/enhance …”  
- [ ] “Add … tests” / “add guard” framing on claim-lock / wording-only  
- [ ] validate/enforce/implement verbs on pure pins, proof packs, docs-of-prior-work (F79 / P-S12-8)

### Body / inventory

- [ ] `Context:` / `Changes:` templates  
- [ ] Process-meta: `Cleared guard codes`, `Deterministic presentation fallback`, guard exhaustion prose (F73)  
- [ ] Miscellaneous-only changelog on test+docs surfaces  
- [ ] Any `Miscellaneous` on **pure docs** tips — Documentation allowlist only (**F82 / P-S12-11**)  
- [ ] Issue-governed work missing `Refs|Resolves|Closes|Fixes` trailer (**F83 / P-S12-12**)  
- [ ] Thin `Included changes` when stable IDs exist (TIP-G*, V12-A*, GUARD_*, pins)  
- [ ] Attribution to unshipped phase/product or docs claiming to implement earlier product guards (F77 / P-S12-7)  
- [ ] Primary-surface inversion (test-only inventory on product+test diff)

### Process

- [ ] Fallback/skeleton shipped as final under gold_strict (F72 / P-S12-1)  
- [ ] Message-only rewrite with prepare re-entry unmitigated (F80)

---

## 5. High-risk body contracts

When diff touches authority, secrets, redaction, hooks, SOP, or accept-path:

* Body must cover the **risk surface** (policy, redaction, freeze, failure mode) — not only “update X”.  
* Inventory must name guards/capabilities touched.  
* Do not hallucinate runtime/secret work absent from the diff (R7/R14/R20 class).

---

## 6. Inventory sufficiency

Gold inventories should:

1. Reflect **all primary surfaces** (prod/test/docs/fixtures as present).  
2. Harvest **stable IDs** when the diff is characterisation/proof/docs-of-laws.  
3. Avoid generic “update guards/tests” collapse (F78).  
4. Keep nested bullets actionable and type-tagged per Hybrid practice.

---

## 7. Claim-lock / wording-only / dark-launch

| Shape | Ceiling tendencies | Ban |
|:---|:---|:---|
| Wording-only directive drop | `PATCH`; multi-surface inventory | feat+MINOR invention; “adds guard” |
| Claim-lock tests | `test`/`fix` per truth; named claims | false feature invention |
| Dark-launch | no matrix MINOR leak without evidence | changelog echo chamber |

---

## 8. Gold vs Hybrid-parseable

**Gold** = message the project would keep.  
**Not gold** = Hybrid-valid but library-wrong (classic Regime B).

`gold_strict` that only scores shape/coherence is **insufficient** (S12 synthesis RC4).

---

## 9. Expansion backlog (substrate harvest)

- [ ] Inline full S1–5 trailer matrices with example SHAs  
- [ ] Mirror remaining #204 body anti-pattern catalogue  
- [ ] Cross-link each reject rule to F*/P* rows  
- [ ] Add worked gold snippets per diff class from promoted cases  

---

## Document control

| Field | Value |
|:---|:---|
| Version | `1.0.0-combine` |
| Status | skeleton active |
| Last updated | 2026-08-13 |
