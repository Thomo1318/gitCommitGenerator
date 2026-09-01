# Naming residue catalog (code-deslop)

Use during the **Mandatory Naming Audit**. Naming is **pattern-based**, not a fixed list of slice numbers, finding IDs, or decision IDs. Do not maintain per-issue denylists (`s7`, `D31`, `FIND-003`…); match the *shape* of the name and whether it is **durable identity** vs **citation**.

## What goes wrong

Agents fix comments and type escapes, then ship durable operator names that still encode:

- delivery stage / slice / phase / wave / milestone **as a name segment**
- review / plan / checklist / ticket **index** as the primary identity
- **governance taxonomy IDs** from issues/ADRs (decisions, invariants, failures, risks, NTH, priority, measurement contracts) as the primary identity of code/recipes/paths
- ceremony or scratch tokens as the primary noun (`proof`, `wip`, `tmp`, `final2`)

Those names rot when the delivery cycle or issue closes. Domain-first names describe **scope + behavior + entity**, readable with zero plan/issue-taxonomy context.

## Citation vs identity (critical)

| Role | Where it belongs | Deslop action |
| --- | --- | --- |
| **Citation** | Issue bodies, claim matrices, ADR decision tables, one-line comment pointers (`# D26: …`, `Refs: #246`, `FIND-068`) | **Keep** |
| **Identity** | just recipes, artifact paths, CLI, function/class/const names, test node ids, file names, config/env keys that *are* the thing | **Rename** to domain-first |

**Rule of thumb:** if deleting the issue/ADR would make the identifier meaningless, it is identity residue. If the identifier still names a real behavior without the issue, it is fine (and a trailing citation comment is optional).

False-friend care:

- `P0`/`P1`/`P2` in issue priority tables = citation. `p0_fix()`, `run_p1_gate` = identity residue.
- `D22` in `Dependency rule (D22):` module doc = citation. `apply_d22()` = identity residue.
- `FIND-068` in a test docstring explaining *why* = citation. `test_find_068()` as the **only** name = identity residue (prefer `test_product_path_opik_stays_lazy_when_mode_off`).

## High-priority durable surfaces

Scan these before ordinary locals:

1. Task runners (`justfile`, make, npm scripts, mise tasks)
2. Artifact / report paths and filenames
3. CLI entrypoints, subcommands, public flags
4. Test module names and node ids
5. Exported constants / config keys / env vars introduced on the branch

## Pattern families (match any generation)

Treat a **new or branch-touched identifier** (identity role) as residue if it matches **any** family below. Letter-case and separator style (`_`, `-`, `/`, camelCase) do not matter. Digit width does not matter.

### A. Stage / slice / phase / wave / milestone segment

**Shape:** delivery-cycle token + optional digits, used as a *name segment* of something runnable or stored.

| Token class (non-exhaustive) | Illustrative matches |
| --- | --- |
| `s` + digits | `s6`, `s7`, `s15`, `eval-s7-proof`, `s12_gate` |
| `slice` + digits | `slice7`, `slice_7`, `slice-15`, `Slice1` |
| `phase` / `wave` / `milestone` / `sprint` / `epoch` + digits | `phase2`, `wave1`, `milestone3`, `sprint_4` |

**Action:** strip the stage segment; name **what the tool measures or does**.

### B. Plan / review / checklist / finding index (session-local)

**Shape:** process-index token + number as identity.

| Token class | Illustrative matches |
| --- | --- |
| `finding` / `find` / `FIND` / `FIND-` | `finding_6`, `FINDING_6`, `find-2`, `FIND-003`, `find_003_helper` |
| `item` / `step` / `task` | `item_4`, `step_3`, `task_2_1` |
| `fix` / `ticket` as *symbol* identity | `fix_12_helper` (not `Fixes: #12` trailers) |
| `review` + index | `review_item_2`, `cr_finding_9` |
| `INT-` / `int-` interview or internal finding codes | `INT-05`, `int_05_patch` |

**Action:** behavior + entity + condition.

### C. Governance / issue-taxonomy ID as *code* identity

IDs that are legitimate **in issues and matrices** become residue when they are the **name** of durable code. Patterns are drawn from recurring gitCommitGenerator issue grammar (e.g. #246 S6) but apply to **any** future numbering.

| Token class | Issue-side examples (citations — keep) | Identity residue examples (rename) |
| --- | --- | --- |
| Decisions | `D31`, `D22`, `D26` | `apply_d31()`, `d22_leaf_rule.py`, `test_d26_fields()` as sole name |
| Invariants | `I6`, `I-12` | `enforce_i6()`, `i6_check` |
| Failure taxonomy | `F-S6-04`, `F-S7-01`, `F12`, `F01` | `handle_f_s6_04()`, `f_s6_04_case`, `f01_gate` |
| **Errors / eval evidence IDs** | `E07`, `E12`, `E13`, `E-4`, `E3` (matrix/evidence rows) | `handle_e07()`, `e07_gate`, `run_error_e07`, `test_e12_only`, `E13_report.json` as sole name |
| Amendment / review packs | `R4`, `R-11`, `R14` | `r4_helper()`, `run_r11_gate` |
| Findings (catalog) | `FIND-003`, `FIND-068` | `fix_find_003()`, `FIND003_patch` |
| Interaction / interview codes | `INT-05` | `int05_handler` |
| Measurement / claim-matrix contracts | `S6-A04`, `S6-G02`, `S5-G05`, `S4-A`, `S7-A13`, `S7-DOG-05`, `AC-13`, `A04` | `s6_a04_metric`, `s6_g02_bench`, `s7_dog_05_case`, `ac13_floor` as API |
| Risks | `RK-A5`, `RK-S6-02`, `RK-12` | `mitigate_rk_a5()`, `rk_s6_02_flag` |
| Nice-to-have | `NTH-03`, `NTH-1` | `nth03_feature`, `enable_nth_03` |
| Priority as identity | `P0`, `P1`, `P2` in matrices | `p0_fix()`, `p1_gate`, `priority_p0_path` |
| Work-package cite (not identity) | `P0-5`, `P2-8` in plan tables | `p2_8_runner()`, `run_p0_5` as sole API name |
| DoD / AC / RR style | `DoD-3`, `AC-13`, `RR-2` | `dod3_check()` as sole API name |

**Abstract shapes to match (any N, any slice letter/number):**

```text
D<N>          I<N>         R<N>         P<N>          (as symbol segment)
E<N>          E[-_]<N>     error[-_]?E?<N>            (eval/error evidence IDs)
FIND[-_]<N>   INT[-_]<N>   NTH[-_]<N>   RK[-_][A-Z]*[-_]<N>
F[-_]S<N>[-_]<N>           F[-_]<N>
S<N>[-_][A-H]<N>?          S<N>[-_]DOG[-_]<N>
S<N>[-_]A<N>               AC[-_]<N>    A<N>
P<N>[-_]<N>                (work-package cites; identity only when primary name)
DoD[-_]<N>                 RR[-_]<N>
```

Separators optional; case-insensitive for the letter prefix.

**Errors vs failure taxonomy:** `F…` codes are failure-taxonomy rows; `E…` codes are evaluation/error **evidence** IDs (S4 offline matrix grammar and successors). Both are citations in matrices; both are residue as durable identity. Do **not** treat a product enum such as `ErrorCode.INVALID_MODE` or a vendor/schema error field as family C merely because it contains the word “error”.

**Claim-matrix letters:** `S6-A04`, `S6-G02`, `S5-H`, `S7-DOG-05` are **coordinates** in claim/evidence tables (keep). `s6_g02_metric`, `s7_dog_05_handler` as the only name of a recipe/test/API = identity residue. Bare section headers in docs (`### S6-A — …`) stay as document structure citations.

**Action:** name the invariant, failure mode, measurement, or behavior (`eval_coverage_floor`, `lazy_opik_init_when_mode_off`, `invalid_mode_config_error`, `scrub_presentation_locals`). Optional short citation may remain in a comment or docstring **after** the domain name exists.

**Do not** expand this table with every new decision/error/claim number — the shape is enough. S4/S5/S6 closed-issue grammar seeded the shapes; future `E99` / `S9-G01` are already covered.

### D. Ceremony / scratch primary token

| Token class | Illustrative matches |
| --- | --- |
| ticket-ceremony | `proof` as primary recipe meaning, `signoff`, `leftover` |
| scratch | `tmp`, `temp`, `wip`, `draft2`, `final`, `final2`, `new`, `new2`, `misc`, `stuff` |
| empty role | bare `helper` / `utils` as the *main* export with no domain noun |

### E. Synonym cycle

Two or more live names for one entity in the same patch. Standardize on one canonical domain noun.

## Worked transformations (patterns, not a closed list)

| Bad shape | Good shape | Family |
| --- | --- | --- |
| `handle_e07()` / `e07_gate` / `run_error_e07` | `invalid_mode_config_error` / domain failure + entity | C (Errors) |
| `test_e12_schema_only` as sole node id | `test_invalid_mode_emits_config_error` | C (Errors) |
| `s6_g02_bench` / `s7_dog_05_case` | `commit_path_hyperfine_bench` / domain dogfood case | C (claim-matrix) |
| `eval-s6-proof` / `S7_tests.py` (new sibling) | domain recipe / domain test module — never mint `S8_*` because `S7_*` exists | A + anti-precedent |
| `<area>-s<N>-proof` | `<area>-<scope>-<measurement>` | A+D |
| `.<dir>/s<N>_<artifact>.json` | `.<dir>/<artifact>.json` | A |
| `handle_finding_<N>()` / `fix_find_<N>()` | `<verb>_<domain_entity>()` | B |
| `test_finding_<N>()` / `test_find_<N>()` | `test_<behavior>_<condition>()` | B |
| `apply_d<N>()` / `test_d<N>_…` as sole name | domain behavior; optional `# D<N>` citation | C |
| `enforce_i<N>()` | `enforce_<invariant_name>()` | C |
| `handle_f_s<N>_<N>()` | `handle_<failure_mode>()` | C |
| `s<N>_a<N>_metric` / `ac<N>_floor` | `<domain>_<measurement>` | C |
| `mitigate_rk_…()` / `nth_<N>_feature` | domain risk control / feature name | C |
| `p<N>_gate` / `run_p<N>_fix` | `run_<scope>_<job>` | C |
| `run_s<N>_gate()` | `run_<scope>_<measurement>_gate()` | A |

Historical instance of A+D (not a special case forever):

```text
eval-s7-proof              → eval-package-coverage
eval-s7-coverage-files     → eval-per-file-coverage
.eval/s7_per_file_coverage.json → .eval/per_file_coverage.json
```

Governance instance of C (from issue-style IDs, any generation):

```text
test_find_068()            → test_product_path_opik_stays_lazy_when_mode_off  (+ docstring cite FIND-068)
apply_d26_tags()           → set_closed_presentation_tags  (+ comment cite D26)
s6_a04_contract.py         → measurement_contract_eval.py  (+ matrix still says S6-A04)
nth03_export()             → export_optional_batch_envelope
```

## Historical vs durable

| Kind | Example | Action |
| --- | --- | --- |
| Durable operator surface | task/recipe with stage or taxonomy id | **Rename** |
| Runnable symbol / artifact | function, const, path with stage/index/taxonomy id as identity | **Rename** |
| History / matrix / ADR table | “D31 decided …”, “F-S6-04”, “NTH-03”, “P0” rows | **Keep** |
| Issue links / trailers | `#246`, `Refs: #254` | **Keep** |
| One-line cite after domain name | `def scrub_presentation_locals():  # D26` | **Keep** |
| External / pin / schema IDs | vendor fields, digests | **Keep** |
| Pre-existing legacy identity **elsewhere** in the tree | `S7_tests.py`, old `eval-s7-proof` not touched this branch | **Not a template** for new names; optional later cleanup, never a consistency argument for minting `S7_Rename.py` |

### Anti-precedent rule (agents abuse this)

**Existing residue ≠ style guide.**

```text
FORBIDDEN:
  repo has S7_tests.py  →  add S7_Rename.py / s7_helper.py / test_s7_new_path.py
  nearby apply_d26_*    →  add apply_d31_gate() to “match the file”
  justfile still has eval-s7-proof on main →  add eval-s8-proof on this branch

REQUIRED:
  new identity is domain-first even if siblings are still legacy
  preserve only the exact pre-existing symbol you did not introduce (product decision)
  “consistent with surrounding code” never means “copy family A–D identity shapes”
```

## Domain-first test

If a teammate sees the name with **no** plan, slice, decision table, or failure-taxonomy context, can they tell *what it does* and *what entity it acts on*? If they only learn *which issue row produced it* (`D31`, `FIND-003`, `S6-A04`, `RK-S6-02`, `NTH-03`, `P0`), rename.

## Audit output template

```markdown
### Naming Audit

| Flagged | Family | Role | Replacement | Surface | Status |
| --- | --- | --- | --- | --- | --- |
| eval-s7-proof | A+D | identity | eval-package-coverage | just recipe | renamed |
| test_find_068 | B/C | identity | test_product_path_opik_stays_lazy_when_mode_off | test | renamed |
| D26 in matrix row | C | citation | — | ADR table | preserved (citation) |
```

Scanned-none form:

```markdown
### Naming Audit

No stage-segment, plan-index, governance-id-as-identity, or ceremony-primary identifiers introduced on this branch diff.
Families checked: A–E (including governance shapes D/I/F/FIND/INT/RK/NTH/P/AC/S<N>-A<N>).
Surfaces scanned: task runner, artifacts, CLI, symbols, tests, config keys.
Citation-only hits (if any): listed and preserved.
```

## Catalog feedback (novel shapes)

If identity residue is real under the domain-first test but **no family/token class text matches**, do not drop it.

1. Rename/disposition on the branch anyway.
2. Propose a **generalized** shape in the completion report (`E<N>` not `E07`).
3. Prefer new **token class under C** for issue-grammar letters (Errors `E<N>`, etc.) over a new family.
4. **User must approve** before editing this file or `SKILL.md`. No one-off denylist rows.

See code-deslop **Catalog feedback loop**.

## Operator-facing comments (task runners)

Recipe/Make/npm **header comments** are durable operator docs. Leading with `S6` / `S7` / `Slice 7` / bare `AC-13` as the main description is residue: those labels recycle across issues.

**Lead with domain job; trail `Refs: #N` (and optional acceptance id) after.**

Keep true matrix/ADR citations and short in-code `# D26` pointers. Do not treat a justfile banner as the same class as an issue claim-matrix cell.

