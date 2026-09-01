# Naming residue in technical prose

Companion to `code-deslop/references/naming.md`. **Pattern-based** — do not extend with each new slice, decision, finding, or risk id.

## Citation vs identity in docs

| Keep (citation) | Flag (identity taught as something to run/own) |
| --- | --- |
| ADR/issue tables: `D31`, `I6`, `E07`, `E13`, `F-S6-04`, `R4`, `FIND-003`, `INT-05`, `S6-A04`, `S6-G02`, `S7-DOG-05`, `RK-A5`, `NTH-03`, `P0` | “run `just d31-proof`”, “execute FIND-003 fix script”, “run `e07_gate`”, “P0 gate recipe” as the tool name |
| “Slice N landed HITL” history | `eval-s<N>-proof` style operator instructions |
| Claim matrix cells | Recipe/path/CLI still carrying taxonomy ids after code renamed |

## Families

Same **A–E** as code-deslop, including **C governance taxonomy as identity** (`D`/`I`/`R`/`E`/`F`/`S-…`/`DOG`/`RK`/`NTH`/`P`/`AC`/`DoD` shapes — citations keep; operator identity renames).

## Existing residue is not a teaching template

Do not document or recommend new operator names because older docs/code still show `s7_*` / `eval-s7-proof` / `S7_tests`. Teach **domain-first** names; mention legacy spellings only as migration/history (“formerly `eval-s7-proof`”).


## Replacement direction

Always: **scope + behavior + entity**. Never: which issue row, decision id, failure code, or priority cell produced it.

## Commit draft (opt-in)

Apply the same citation-vs-identity split to pasted draft messages: domain-first names in subject/body; do not strip trailer keys or matrix citations the user intentionally included as refs.
