# #204 — Commit presentation quality · failure corpus map

> Epic: Phase 7.30 presentation quality  
> Issue: https://github.com/Thomo1318/gitCommitGenerator/issues/204  
> Package: `1.0.0-combine`

## Authority

* **Living SSOT:** files under `docs/quality/` (this map + cases).  
* **Epic:** [#204](https://github.com/Thomo1318/gitCommitGenerator/issues/204) — corpus governance; not the case library host after promote.  
* **Eval consumer:** [#217](https://github.com/Thomo1318/gitCommitGenerator/issues/217) + [`docs/plans/opik-evaluation-harness.md`](../../../plans/opik-evaluation-harness.md).  
* **GitHub comments:** intake/archive only once `references/source-map.md` marks promoted.

## Map

| Layer | Description | Package home | GitHub intake |
|:---|:---|:---|:---|
| Law (body) | Locks, V12-A, anti-patterns | `GOLD_STANDARD` / `CORPUS` | issue body |
| Instance A | S1–5 precursor | `instance-a-precursor.md` | `5186554544` |
| Instance B 0–5 | implementation dogfood | `instance-b-slices-0-5.md` | `5210122501` |
| S6–11 | tip audits / residuals | `sessions-06-11.md` | `5210137590` |
| **Session 12 G1** | residual close-out · Regime A exemplar | [`session-12.md`](./session-12.md) **active full** | `5213748048` |
| **Session 12 G2** | residual · Regime B exemplar | [`session-12-g2.md`](./session-12-g2.md) **active full** | `5213748048` |
| **Session 12 G3** | residual · Regime B exemplar | [`session-12-g3.md`](./session-12-g3.md) **active full** | `5215148242` |
| **Session 12 G4** | residual · Regime B exemplar | [`session-12-g4.md`](./session-12-g4.md) **active full** | `5215440216` |
| **Session 12 synthesis** | regimes A/B · F72–F80 · P-S12 systems | [`session-12-synthesis.md`](./session-12-synthesis.md) **active full** | `5215611559` |
| **S12 dogfood G2–G4** | post-control · Regime B | [`session-12-dogfood-g2-g4.md`](./session-12-dogfood-g2-g4.md) **active full** | `5226058599`… |

## Promotion priority

1. ~~Session 12 G1 + synthesis~~ **done** (method exemplars)  
2. ~~Session 12 G2 / G3 / G4 full depth~~ **done**  
3. ~~Dogfood G2–G4~~ **done**  
4. Substrate stubs for A / B / S6–11  
5. Operator: mark promoted GitHub comments superseded-as-SSOT (header note)

## Live cases (in-repo)

| Case | Regime | Status | Path |
|:---|:---|:---|:---|
| Session 12 G1 (residual) | **A** | **active full** | [`session-12.md`](./session-12.md) |
| Session 12 G2 (fixtures envelope) | **B** | **active full** | [`session-12-g2.md`](./session-12-g2.md) |
| Session 12 G3 (V12-A proof pack) | **B** | **active full** | [`session-12-g3.md`](./session-12-g3.md) |
| Session 12 G4 (docs attribution) | **B** | **active full** | [`session-12-g4.md`](./session-12-g4.md) |
| Session 12 cross-commit synthesis | **A+B** | **active full** | [`session-12-synthesis.md`](./session-12-synthesis.md) |
| Session 12 dogfood G2–G4 | **B** | **active full** | [`session-12-dogfood-g2-g4.md`](./session-12-dogfood-g2-g4.md) |
| Quality package self-dogfood four-tip series | **B** | **active full** | [`quality-package-regime-b.md`](./quality-package-regime-b.md) |

Promotion notes:

* S12 G1–G4 + synthesis + dogfood G2–G4 promoted from comments `5213748048` / `5215148242` / `5215440216` / `5215611559` / `5226058599`–`5226058788` — comments remain archive evidence; package paths are SSOT.  
* Quality-package Regime B case is native SSOT (not a GitHub comment promote). It proves clean-wrong-accept against the quality package landing messages themselves.
