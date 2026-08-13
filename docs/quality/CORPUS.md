# Corpus index — tips, claims, series

> **Package:** commit-message failure analysis  
> **Version:** `1.0.0-combine`  
> **Status:** navigation skeleton — IDs + homes; not full tip prose  
> **Eval link:** Session 12 seed tags in `docs/plans/opik-evaluation-harness.md`

---

## 1. Instance map

| Class | Meaning | Home |
|:---|:---|:---|
| **Instance A** | Precursor motivation (why epic exists) | #204 S1–5 · `cases/204/instance-a-precursor.md` |
| **Instance B** | Misses while shipping the fix | slices 0–5 · S6–11 · `cases/204/instance-b-*.md` |
| **Residual close-out** | Correct trees; wrong messages | Session 12 G1–G4 · G1+synthesis SSOT active |
| **Post-control dogfood** | After P-* still misses | S12 dogfood G2–G4 |
| **Forward** | New work on METHOD | e.g. #220 |

---

## 2. TIP-G index (homes only)

| Band | IDs | Home |
|:---|:---|:---|
| Precursor | TIP-G1–G12 | Instance A / body |
| S6–S8 | TIP-G13–G27 | S6–11 archive · residual uses G13–G17 |
| S9 | TIP-G28–G31 | S9 notes |
| S10–S11 | residual TIPs | S6–11 archive |

*Lazy rule:* when a case cites TIP-Gn, ensure a one-line row exists here pointing at the case/comment.

---

## 3. V12-A claim bands

| Band | IDs | Role |
|:---|:---|:---|
| A01–A07 | … | proof pack bands (see #204 body / V12-A tests) |
| … | A08–A45 | full map in body / `tests/test_v12_a_claims.py` |

Session 12 G3 gold: named proof pack a01–a45.

---

## 4. Eval seed alignment

| Tag / seed | Package proof | Notes |
|:---|:---|:---|
| `session-12-seed` | [`cases/204/session-12.md`](./cases/204/session-12.md) + [`session-12-synthesis.md`](./cases/204/session-12-synthesis.md) (**active**); G2–G4 pending | regimes A/B, F72–F80, P-S12 |
| F72–F80 codes | `FAILURE_TAXONOMY.md` | harness may emit |
| P-S12-1…9 | `PREVENTION_BACKLOG.md` | control map |

Session 12 is the **seed proof pack**, not a requirement to import the entire #204 novel into eval fixtures.

---

## 5. Canonical GitHub intake (pre-promotion)

| Comment | Content |
|:---|:---|
| `5186554544` | Instance A findings |
| `5210122501` | Instance B 0→5 |
| `5210137590` | Slices 5.5→11 |
| `5213748048` | S12 primary G1+G2 · **G1 →** `cases/204/session-12.md` |
| `5215148242` | S12-G3 |
| `5215440216` | S12-G4 |
| `5215611559` | S12 synthesis · **→** `cases/204/session-12-synthesis.md` |
| `5226058599` | dogfood G2 |
| `5226058718` | dogfood G3 |
| `5226058788` | dogfood G4 |

See [`references/source-map.md`](./references/source-map.md).

---

## 6. Epic / eval pointers

| Ref | Role | Living SSOT |
|:---|:---|:---|
| [#204](https://github.com/Thomo1318/gitCommitGenerator/issues/204) | Presentation quality corpus epic | `docs/quality/**` (this package) |
| [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) | Opik harness governance index | Design: `docs/plans/opik-evaluation-harness.md`; gold-miss law: this package |
| Session 12 residual series | Method exemplars + seed tags | `cases/204/session-12.md`, `session-12-synthesis.md` |

---

## Document control

| Field | Value |
|:---|:---|
| Version | `1.0.0-combine` |
| Last updated | 2026-08-13 |
