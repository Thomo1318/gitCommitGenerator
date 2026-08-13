# Promotion from issue comment → repo SSOT

> Package version: `1.0.0-combine`  
> Why: GitHub 65k comment ceiling forced Session 12 splits; comments are not durable law.

## When to promote

* Full-depth forensic analysis that will be cited again  
* New F*/P* definitions  
* Series synthesis  
* Any forward case used as template evidence  

## Steps

1. Copy content into `docs/quality/cases/<issue>/…` using CASE_TEMPLATE / synthesis template structure.  
2. Split oversized comments into multiple case files if needed (G1, G2, … + synthesis).  
3. Register IDs in `docs/quality/FAILURE_TAXONOMY.md` / `docs/quality/PREVENTION_BACKLOG.md`.  
4. Add row to `docs/quality/cases/README.md` and `docs/quality/references/source-map.md`.  
5. Add header note on the GitHub comment (operator):

   > Superseded as SSOT by `docs/quality/cases/...`. Retained as intake evidence.

6. Do **not** delete historical comments without explicit owner permission.

## Depth policy on promote

| Material | Promote as |
|:---|:---|
| Session 12 G1–G4 + synth + dogfood | **Full** forensic cases |
| S1–11 tip novels already compacted in body | Open-summary stubs + law already in GOLD_STANDARD |
| Delivery closeouts / slice status | Usually skip (not gold-miss law) |
| New #220-class work | Full METHOD case only |

## Quality gate

Promoted case must pass METHOD §12 minimum viable full case (or be explicitly stubbed with `OPEN_SUMMARY_STUB`).
