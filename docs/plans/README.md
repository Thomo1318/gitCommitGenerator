# Plans

Living design and implementation plans that are too large or too operational to live inside a single ADR body.

| Plan | Governing issue | Related ADRs | Notes |
|:---|:---|:---|:---|
| [Opik evaluation harness](./opik-evaluation-harness.md) | #217 (parent epic #216) · S6 impl [#246](https://github.com/Thomo1318/gitCommitGenerator/issues/246) | ADR-0010, ADR-0011 | Formal SSOT for the Opik commit-message evaluation harness (S0–S7) @ `0.9.6-s6-slice0-reconciliation`. S6 operator UX is **in implementation** on #246 (Slice 0 census/baseline locked). Promoted from `scratch/0.OpikIntegration/opik.md`. |
| [Commit-message failure analysis](../quality/README.md) | #204 (corpus) · feeds #217 | Hybrid / commit_gold / commit_quality | **Living gold-miss SSOT** under `docs/quality/` (METHOD · F*/P* · S12 G1+synthesis cases). #204 comments = archive; #217 consumes IDs via this package + eval plan. |

## Document class rules

* **ADRs** record accepted architectural decisions and constraints.
* **Plans** compile executable slice law, acceptance criteria, findings, and filing sequence.
* GitHub issues point at plans; they do not replace them as the living SSOT for large workstreams.
* `scratch/` remains non-versioned working residue only.


## Active implementation pointers

| Workstream | Issue | Status pointer |
|:---|:---|:---|
| S6 operator UX (CLI / doctor / amend-brief / dogfood / train-export / sessions) | [#246](https://github.com/Thomo1318/gitCommitGenerator/issues/246) | Slice 0 landed-state census: [`docs/eval/s6-slice0-landed-state-census.md`](../eval/s6-slice0-landed-state-census.md) · baseline [`docs/eval/s6-slice0-baseline.json`](../eval/s6-slice0-baseline.json). Plan version `0.9.6-s6-slice0-reconciliation`. |
| S5 Lane C′ (closed) | [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233) | Residual board: [`docs/eval/s5-slice6-residual-disposition.md`](../eval/s5-slice6-residual-disposition.md) |
