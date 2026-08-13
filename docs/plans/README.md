# Plans

Living design and implementation plans that are too large or too operational to live inside a single ADR body.

| Plan | Governing issue | Related ADRs | Notes |
|:---|:---|:---|:---|
| [Opik evaluation harness](./opik-evaluation-harness.md) | #217 (parent epic #216) | ADR-0010, ADR-0011 | Formal SSOT for the Opik commit-message evaluation harness (S0–S7). Promoted from `scratch/0.OpikIntegration/opik.md`. |
| [Commit-message failure analysis](../quality/README.md) | #204 (corpus) · feeds #217 | Hybrid / commit_gold / commit_quality | **Living gold-miss SSOT** under `docs/quality/` (METHOD · F*/P* · S12 G1+synthesis cases). #204 comments = archive; #217 consumes IDs via this package + eval plan. |

## Document class rules

* **ADRs** record accepted architectural decisions and constraints.
* **Plans** compile executable slice law, acceptance criteria, findings, and filing sequence.
* GitHub issues point at plans; they do not replace them as the living SSOT for large workstreams.
* `scratch/` remains non-versioned working residue only.
