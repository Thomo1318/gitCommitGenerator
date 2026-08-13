# Gold-miss review checklist

> Derived from [`../METHOD.md`](../METHOD.md).  
> Package version: `1.0.0-combine`

## Before writing

- [ ] Copy `templates/CASE_TEMPLATE.md` (or synthesis template if ≥2 groups)
- [ ] Confirm series class: precursor | implementation-dogfood | residual-close-out | post-control-dogfood | forward
- [ ] Collect raw SHA, gold SHA, tree OID (or mark tree not preserved)
- [ ] Decide Opik bind vs `Opik-unbound`

## Open summary

- [ ] Result + regime A/B/A+B
- [ ] Path focus + severity
- [ ] Raw→gold SHAs
- [ ] One-line diagnosis
- [ ] F*/P* listed

## Reconstruction

- [ ] Diff library class from GOLD_STANDARD
- [ ] Pipeline stages walked (extract → accept)
- [ ] Ranking vs contract table
- [ ] Attempts / fallback / clean-accept documented
- [ ] Evidence channels (`path_class_gate`, `staged_paths`, guidance) checked
- [ ] Raw↔gold dimension table complete
- [ ] Stage-ordered root-cause chain
- [ ] Confidence matrix (Direct vs Reconstructed)

## IDs and close-out

- [ ] F*/R* from FAILURE_TAXONOMY (mint row if new)
- [ ] P* from PREVENTION_BACKLOG (mint row if new)
- [ ] gold_strict / hooks / telemetry honesty stated
- [ ] Controls + regression test pointers
- [ ] Case indexed in `cases/README.md`
- [ ] Source-map updated if promoted from GitHub

## Message-only gold rewrite (if doing rewrite now)

- [ ] Follow `message-only-rewrite.md` (not `--no-verify` alone)
- [ ] Tree OID unchanged after rewrite
- [ ] F80 considered
