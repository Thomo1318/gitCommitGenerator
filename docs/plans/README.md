# Plans

Living design and implementation plans that are too large or too operational to live inside a single ADR body.

| Plan | Governing issue | Related ADRs | Notes |
|:---|:---|:---|:---|
| [Opik evaluation harness](./opik-evaluation-harness.md) | #217 (parent epic #216) · S6 impl [#246](https://github.com/Thomo1318/gitCommitGenerator/issues/246) · S7 impl [#254](https://github.com/Thomo1318/gitCommitGenerator/issues/254) | ADR-0010, ADR-0011 | Formal SSOT for the Opik commit-message evaluation harness (S0–S8) @ `0.9.8-s7-dogfood-findings-board`. S6 operator UX shipped on #246 / `v0.22.0+`. S7 user-interaction (pins, Feedback Definitions, HITL, claim matrix) is implemented offline on #254; issue close still needs PR open, CI green, and merge. S8 docs-platform / ADR rewrite deferred to [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235). Promoted from `scratch/0.OpikIntegration/opik.md`. |
| [Commit-message failure analysis](../quality/README.md) | #204 (corpus) · feeds #217 | Hybrid / commit_gold / commit_quality | **Living gold-miss SSOT** under `docs/quality/` (METHOD · F*/P* · S12 G1+synthesis cases). #204 comments = archive; #217 consumes IDs via this package + eval plan. |

## Document class rules

* **ADRs** record accepted architectural decisions and constraints.
* **Plans** compile executable slice law, acceptance criteria, findings, and filing sequence.
* GitHub issues point at plans; they do not replace them as the living SSOT for large workstreams.
* `scratch/` remains non-versioned working residue only.


## Active implementation pointers

| Workstream | Issue | Status pointer |
|:---|:---|:---|
| S7 user interaction (Opik pins / FD map / HITL / scrub / claim matrix) | [#254](https://github.com/Thomo1318/gitCommitGenerator/issues/254) | Implemented offline through S7-8 + NTH. Claim matrix: [`docs/eval/s7-claim-evidence.md`](../eval/s7-claim-evidence.md) · operator notes: [`docs/eval/README.md`](../eval/README.md) § S7. Issue close still needs PR open, CI green, and merge. Plan version `0.9.8-s7-dogfood-findings-board`. |
| S6 operator UX (CLI / doctor / amend-brief / dogfood / train-export / sessions) | [#246](https://github.com/Thomo1318/gitCommitGenerator/issues/246) | Shipped (Slices 0–8 + NTH/G02) on `v0.22.0+`. Packaging docs/CLI reference/claim pack in-tree: [`docs/eval/s6-claim-evidence.md`](../eval/s6-claim-evidence.md) · [`docs/cli/`](../cli/index.md) · census [`docs/eval/s6-slice0-landed-state-census.md`](../eval/s6-slice0-landed-state-census.md). |
| S5 Lane C′ (closed) | [#233](https://github.com/Thomo1318/gitCommitGenerator/issues/233) | Residual board: [`docs/eval/s5-slice6-residual-disposition.md`](../eval/s5-slice6-residual-disposition.md) |
| S8 docs platform / ADR rewrite (deferred) | [#235](https://github.com/Thomo1318/gitCommitGenerator/issues/235) | Durable Zensical/ADR-0011 rewrite, allowlist mkdocstrings, REST/OpenAPI. Outside S7 scope (S8-LAW-01). |
