---
name: code-deslop
description: Remove AI-generated code slop from the current branch diff. Use after agent coding passes to clean unnecessary comments, abnormal defensive checks, type escape hatches, local style drift, and non-domain identifier names (stage labels, plan indices, process residue in recipes/paths/symbols). Never mutate git history or invoke git-cg. Commit-message drafts only when the user explicitly opts in.
---

# code-deslop — branch code residue cleanup

Project-owned fork of the brianlovin `deslop` code checklist, with hard guards for `gitCommitGenerator`.

## Non-negotiable (refuse / do not touch)

- Never invoke `git-cg`, `git commit`, `git commit --amend`, rebase, reset, force-push, or trailer mutation in the index/HEAD.
- Never edit SOP matrices, gitmoji rows, or semantic-contract authority files as a “cleanup”.
- Never strip fail-closed validation, pin locks, secret redaction/scrub paths, store-integrity gates, doctor block paths, or intentional untrusted-input checks.
- Never “simplify away” closed enums, schema strictness, or security-relevant guards because they look defensive.
- Prefer behaviour-preserving minimal diffs. No drive-by refactors.
- **Commit messages (default):** do not draft, rewrite, or “improve” commit messages, and do not treat Hybrid trailers as prose.
- **Commit messages (explicit opt-in only):** if the user clearly asks to deslop a *proposed/draft/gold-standard example* commit message (not HEAD, not amend), follow **Commit draft deslop** below. Still never run git/git-cg.

## When to use

- After an agent wrote or edited **code/tests/scripts/just recipes** on the current branch.
- User asks to `code-deslop`, “remove AI code slop”, “clean branch residue”, or similar.
- Not for README/ADR/blog prose (use `prose-deslop` via `deslop-gate`).
- Not as a substitute for review, tests, or architecture decisions.

## Procedure

1. Determine diff base intentionally:
   - PR branch: merge base / PR base / `origin/main` as appropriate.
   - Default: `main` or repo default branch if no PR context.
2. Inspect only changes introduced on this branch vs that base.
3. **Run Mandatory Naming Audit first** (below). Do not finish the pass without it.
4. Remove AI code residue that a careful human would not leave, including:
   - **Identifier residue (families A–E):** stage/slice/phase segments (`s<N>`, `slice<N>`, …); plan/review indices (`finding_<N>`, `FIND[-_]<N>`, `INT[-_]<N>`, `item_<N>`, …); **governance IDs as identity** (`D<N>`, `I<N>`, `R<N>`, `F-S<N>-<N>`, `S<N>-A<N>`, `RK-…`, `NTH-<N>`, `P0|P1|P2`, `AC-<N>`, …); ceremony/scratch primary tokens; synonym cycles. Replace identity with domain-first scope + behavior + entity. **Citations** in comments/matrices stay. See Mandatory Naming Audit — never a per-issue denylist.
   - Domain-term consistency (anti-synonym cycling): multiple names for the same entity across adjacent functions; standardize on the repository's canonical domain term.
   - Semantic duplication (shadow utilities): new helpers that duplicate existing repository utilities; replace with imports.
   - Process residue and tautological comments: prompt history or obvious restatement. Keep comments that explain *why*, non-obvious algorithms, security invariants, or contract rules.
   - Scratchpad & Chain-of-Thought leakage: `<thinking>`, `<thought>`, `<scratchpad>`, `// Reasoning:` — strip completely.
   - Micro-helper proliferation and premature abstraction.
   - Debug echo & logging chatter.
   - Silent failure fallbacks that should fail closed.
   - Abnormal defensive checks or `try/catch` on trusted internal paths.
   - Casts to `any` / type escape hatches used only to bypass typing.
   - Deep nesting that should be early-return simplified **when behaviour-identical**.
   - Single-use temps that obscure flow with no clarity gain.
   - Style drift inconsistent with the surrounding file.
5. Keep anything that encodes an invariant, security rationale, pin/doctor/redaction contract, or fail-closed policy — even if verbose.
6. Do not expand scope beyond the branch diff unless the user explicitly asks.
7. Run or recommend targeted tests when non-trivial logic or renames moved.
8. Emit the **Naming Audit** table in the output (required).

## Mandatory Naming Audit (do not skip)

Agents regularly skip renames when rules only show one slice or one finding id. **This section is blocking:** a deslop pass without a Naming Audit table is incomplete.

**Do not maintain a per-slice or per-finding denylist.** Match **pattern families** (any generation, any digit width, any separator/`CASE`). Full catalog: [references/naming.md](references/naming.md).

### Surfaces to scan in the branch diff

| Surface | What to inspect |
| --- | --- |
| Task runners | `justfile`, make/npm/mise script names |
| Artifact / report paths | JSON/HTML/XML under `.eval/`, `dist/`, report dirs |
| CLI | commands, subcommands, public flags |
| Symbols | functions, classes, constants, env keys introduced on branch |
| Files / scripts | new or renamed paths |
| Tests | module names and node ids |
| Comments that *define* a durable name | operator-facing recipe/path spellings |

### Flag families (any N, any generation)

Flag an introduced or branch-touched **identifier in the identity role** if it matches any family. Digit width, separators, and `CASE` do not matter.

| Family | Shape (abstract) | Illustrative hits only |
| --- | --- | --- |
| **A. Stage segment** | `s<N>`, `slice<N>`, `phase<N>`, `wave<N>`, `milestone<N>`, `sprint<N>` as name segment | `eval-s7-proof`, `s15_gate`, `slice_1_handler` |
| **B. Plan/review/session index** | `finding`/`FIND[-_]`/`find`/`item`/`step`/`task`/`INT[-_]` + N | `finding_6`, `FIND-003`, `INT-05`, `item_4`, `step_3` |
| **C. Governance taxonomy as identity** | Issue/ADR grammar used as the *name* of code/recipe/path (not as citation): `D<N>`, `I<N>`, `R<N>`, `E<N>`, `F-S<N>-<N>`, `F<N>`, `S<N>-[A-H]<N>`, `S<N>-DOG-<N>`, `AC[-_]<N>`, `A<N>`, `RK-…`, `NTH[-_]<N>`, `P0`/`P1`/`P2`, `DoD[-_]<N>` | `apply_d31()`, `handle_e07()`, `e07_gate`, `enforce_i6()`, `handle_f_s6_04()`, `s6_a04_metric`, `s6_g02_bench`, `nth03_export()`, `p0_gate`, `ac13_floor` API |
| **D. Ceremony/scratch primary** | primary noun is process theater or temp hygiene | `proof` (ticket proof), `wip`, `tmp`, `final2`, bare `helper` |
| **E. Synonym cycle** | two+ live names for one entity in the same patch | `payload` / `data_dict` / `raw_event` |

**Citation vs identity:** `D31` / `E07` / `E13` / `FIND-003` / `S6-A04` / `S6-G02` / `S7-DOG-05` / `RK-S6-02` / `NTH-03` / `P0` in issue matrices, ADR tables, or a trailing `# D26` / `# E12` comment = **citation (keep)**. The same token as recipe, path, function, test node id, or config key identity = **residue (rename)**.

Do **not** maintain a list of closed issues’ IDs. Family **C** is the whole grammar; new `D99` or `FIND-100` are already covered.

### Preserve (do not rename)

- Historical narrative that cites a shipped milestone *as history* without defining the operator surface
- Upstream/API-required strings, pin digests, schema/metric/checkpoint IDs
- Stable public APIs the branch did not introduce (product decision) — **do** rename when the branch introduced the bad name or the user asked to deslop naming on that surface
- Issue/PR numbers (`#254`)
- SOP gitmoji / Hybrid trailer keys
- **Governance citations** in issues, ADR decision tables, claim/failure/risk matrices, and short comment pointers: `D<N>`, `I<N>`, `E<N>`, `F-S<N>-…`, `R<N>`, `FIND-…`, `INT-…`, `S<N>-[A-H]<N>`, `S<N>-DOG-…`, `RK-…`, `NTH-…`, `P0|P1|P2`, `AC-…` — keep as citations; still forbid minting them as durable API/recipe/path **identity**

### Operator-facing comments (justfile / task headers) — not free citation space

A **leading** stage/slice/governance label in a durable operator comment is orientation debt, even when the recipe name is already domain-first.

Future you (or a future issue that reuses `S6` / `Slice 7`) cannot tell whether the comment means *this* delivery cycle or a recycled label.

| Bad (primary orientation = delivery cycle) | Good (primary orientation = job) |
| --- | --- |
| `# S6 offline proof spine …` | `# Offline eval claim-matrix spine (no cov). Refs: #246.` |
| `# Package-scoped eval coverage floor (S7 AC-13).` | `# Package-scoped coverage floor for src/git_cg/eval. Refs: #254.` |
| `# S6 Slice 7: hyperfine bench …` | `# Hyperfine bench of commit path, dogfood async on vs off. Refs: #246.` |
| `# Check … Typer tree (S6 Slice 2)` | `# Check operator_api_map.md vs live Typer tree. Refs: #246.` |

**Rules:**

1. **Lead with the job** (what it measures, gates, or generates).
2. **Trail citations** optionally: issue (`#254`), acceptance row (`AC-13`), or one historical milestone — after the domain sentence, not instead of it.
3. Do **not** use bare `S<N>` / `Slice <N>` as the *only* way to know what the recipe is for.
4. Matrix/ADR **tables** and one-line code pointers (`# D26`) remain valid citations; **task-runner headers** are operator docs and follow this rule.
5. Scanner may still focus on identity tokens; agents must still deslop these comments in Naming Audit / comment cleanup — treat as **fail** if a touched justfile header is still slice-led.

### Existing residue is not a naming precedent (hard ban)

Historical family A–D **identity** already in the tree does **not** authorize new matching names.

| Invalid justification | Correct rule |
| --- | --- |
| “`S7_tests.py` already exists, so `S7_Rename.py` matches convention” | **Forbidden.** Old residue is debt, not a template. |
| “Nearby helpers are `s7_*` / `finding_*` / `apply_d*`, stay consistent” | **Forbidden** for *new* identity. Consistency target is **domain-first**, not legacy residue. |
| “Style drift vs surrounding file” used to *keep or mint* stage/plan/governance identity | Style-match applies to formatting only — **never** to family A–D identity shapes. |
| “Branch didn’t invent the pattern, only extended it” | Extending the pattern **is** introducing identity residue on this branch → **rename**. |
| “Public API already used `s7_` prefix elsewhere” | Only preserve the **exact pre-existing symbol** you did not introduce. Do **not** mint siblings (`S7_Rename`, `s7_helper2`, …). |

**New / branch-touched identity** (files, recipes, paths, symbols, tests, config keys) must pass the domain-first test even when the repo still contains older `s<N>_…`, `finding_<N>`, `D<N>`, etc.

Optional: when touching a file that still bears legacy identity you are **not** asked to rename repo-wide, still give **new** symbols domain-first names; do not “rhyme” with the legacy filename.

### Disposition required per flag

| Flagged | Family | Domain-first replacement | Status |
| --- | --- | --- | --- |
| *(name)* | A–E | scope + behavior + entity | renamed / preserved+reason / deferred+reason |

**Pass rule:** zero flags, or every flag has `renamed` or an explicit preserve/defer reason.  
**Fail rule:** flags only in prose; “looks fine” without scanning task runners/paths; only checking one hard-coded slice id; **or** justifying a new family A–D identity name because similar residue already exists in the repo (`S7_tests.py` ⇏ license for `S7_Rename.py`).

### Shape → replacement (templates)

| Bad shape | Good shape |
| --- | --- |
| `<area>-s<N>-proof` | `<area>-<scope>-<measurement>` |
| `<area>-s<N>-coverage-files` | `<area>-per-file-coverage` |
| `.<dir>/s<N>_<artifact>.json` | `.<dir>/<artifact>.json` |
| `handle_finding_<N>()` / `fix_find_<N>()` / `fix_FIND_<N>()` | `<verb>_<domain_entity>()` |
| `test_finding_<N>()` / `test_find_<N>()` / `test_step_<N>_…()` | `test_<behavior>_<condition>()` (+ optional cite in docstring) |
| `S<N>_OWNED_FILES` / `SLICE_<N>_MODULES` | `OWNED_<DOMAIN>_MODULES` |
| `run_s<N>_gate()` | `run_<scope>_<measurement>_gate()` |
| `apply_d<N>()` / `enforce_i<N>()` / `handle_f_s<N>_…()` | domain behavior / invariant / failure mode |
| `s<N>_a<N>_…` / `ac<N>_floor` as API | `<domain>_<measurement_or_invariant>` |
| `nth_<N>_…` / `rk_…` / `p<N>_gate` as identity | feature / risk control / job name |

One historical instance of families A+D (not a special case to hardcode forever):

| Instance | Replacement |
| --- | --- |
| `eval-s7-proof` | `eval-package-coverage` |
| `eval-s7-coverage-files` | `eval-per-file-coverage` |
| `.eval/s7_per_file_coverage.json` | `.eval/per_file_coverage.json` |

### Rename cascade checklist

When renaming a durable identifier, update **all** branch-touched references:

1. Definition (recipe, function, constant, path)
2. Call sites / docs in scope for this pass
3. Tests, fixtures, golden strings
4. Operator echo/UI strings that teach the old name
5. Artifact path writers **and** readers

Incomplete cascade = incomplete deslop.

### Domain-first test

If a teammate sees the name with **no** plan, slice, decision, failure-taxonomy, or review context, can they tell *what it does* and *what entity it acts on*? If they only learn *which delivery cycle or issue row produced it* (`D31`, `FIND-003`, `S6-A04`, `NTH-03`, `P0`, …), rename.

## Semantic Domain Naming Standards (Anti-Meta Residue)

| Identifier Type | Bad shape | Good shape | Rationale |
| --- | --- | --- | --- |
| **Function/Method** | `handle_finding_<N>()`, `fix_step_<N>()`, `run_s<N>_proof()` | `<verb>_<domain_entity>()`, `run_<scope>_<measurement>_gate()` | Verb + domain entity + action |
| **Variable/Const** | `finding_<N>_data`, `S<N>_OWNED_FILES` | `<state_or_content>`, `OWNED_<DOMAIN>_MODULES` | Content/state, not origin/stage |
| **Test case** | `test_finding_<N>()`, `test_s<N>_proof()` | `test_<behavior>_<condition>()` | Reveals invariant under test |
| **File/Script** | `finding_<N>_fix.py`, `s<N>_gate.sh` | `<responsibility>.py` | Utility role |
| **Task recipe** | `<area>-s<N>-proof` | `<area>-<scope>-<measurement>` | Operator-facing; outlives slices |
| **Artifact path** | `s<N>_<artifact>.json` | `<artifact>.json` | Same longevity rule |
| **Governance-ID identity** | `apply_d<N>()`, `test_find_<N>()`, `nth_<N>_export` | domain verb/entity; optional `# D<N>` / docstring cite | Issue grammar ≠ API name |

**Domain-first test:** no plan/slice/review context required to understand the name.

## Commit draft deslop (explicit opt-in only)

Triggers (all required): user provides draft text **and** says to deslop/clean that draft/gold-standard **commit message example**.

### Allow

- Replace stage-segment / plan-index / governance-id-as-identity / ceremony-primary names in subject/body with domain-first names (families A–E; any N). Keep intentional citation tokens in body only when they are clearly refs, not tool names.
- Cut AI filler, synonym cycling, and throat-clearing in the **body prose**.
- Fix obvious internal inconsistency in named paths/recipes inside the draft.

### Forbid

- Changing gitmoji or `cc_type` (SOP/`git-cg` authority).
- Inventing or deleting trailer **keys**.
- Changing issue ids, `SemVer-Impact` vocabulary, or machine trailer grammar.
- Running `git commit`, `git-cg`, amend, or writing `.git/COMMIT_EDITMSG` unless the user separately and explicitly ordered that git operation.
- “Desloping” an already-accepted HEAD commit message in history.

### Output

Return the full cleaned draft in one fenced `text` block, plus a mini Naming Audit for names touched in the draft. No git side effects.

## Quick Checks (Pre-Commit / Pre-PR)

- [ ] Naming Audit table completed (families A–E; not a hard-coded slice/decision/finding list).
- [ ] Stage segment (`s<N>`, `slice<N>`, `phase<N>`, …) in **new** recipes/paths/symbols? Rename or justify **without** “matches existing sN files”.
- [ ] Plan/review index (`finding_<N>`, `FIND[-_]<N>`, `INT[-_]<N>`, `step_<N>`, …) as identity? Rename.
- [ ] Governance ID as identity (`D<N>`, `I<N>`, `R<N>`, `E<N>`, `F-S<N>-…`, `S<N>-[A-H]<N>`, `S<N>-DOG-<N>`, `RK-…`, `NTH-<N>`, `P0|P1|P2`, `AC-<N>` as API/recipe/path)? Rename; keep matrix/comment citations.
- [ ] Ceremony/scratch primary tokens (`proof` as ticket proof, `wip`, `tmp`, `final2`)? Rename.
- [ ] No new identity “rhyming” with legacy residue (`S7_tests.py` present ⇏ `S7_Rename.py` OK)?
- [ ] Novel identity shapes not in A–E text → Catalog gaps row + user prompt (shape-level), not silent ignore and not auto-edit skill?
- [ ] Rename cascade complete (definition + readers + tests + operator strings)?
- [ ] Variable synonym cycling standardized?
- [ ] Shadow helpers replaced with repo utilities?
- [ ] justfile/task headers lead with **job**, not `S<N>`/`Slice <N>`/`AC-<N>` as primary orientation (trailing Refs OK)?
- [ ] Process/tautological comments and scratchpad tags stripped?
- [ ] Micro-helpers / premature abstracts inlined or flattened when safe?
- [ ] Debug print/entry-exit chatter removed?
- [ ] No swallow-`Exception`-return-`{}` on fail-closed paths?
- [ ] No new `any` / suppressed lints to silence types?
- [ ] Security, pins, doctor, redaction, SOP authority preserved?

## Output

1. **Naming Audit** table (required; empty only if scan ran and found nothing).
1b. **Catalog gaps** table when a found identity shape is missing/ambiguous in families A–E (see Catalog feedback loop) — generalized shape + user decision; never a one-off denylist add.
2. 1–3 sentences on other residue removed.
3. Bullet list of files touched.
4. Refused items with reasons (including commit-default refuse when no opt-in).


## Catalog feedback loop (self-improve, user-gated)

The naming catalog is **pattern-based** and will miss novel shapes. When a pass finds durable **identity** residue that is clearly process/governance/ceremony-encoded but **does not fit families A–E as written**, do **not** silently ignore it and do **not** patch the skill on your own.

### On detection (during Naming Audit)

1. Still **rename** (or disposition) the branch-touched identity using the domain-first test — enforcement does not wait on catalog edits.
2. Classify the miss:
   - **Fit existing family, missing token class** — e.g. `E07` / `error_e07_gate` is family **C** (governance taxonomy) with a new *Errors* token class, not a new family.
   - **New family** — only when the *kind* of residue is unlike A–E (rare).
   - **False positive** — domain acronym, vendor id, schema enum; mark preserve and do **not** propose a catalog add.
3. Add a **Catalog gap** row in the completion report (required when any miss or uncertain match occurs).

### Completion report section (required on gaps)

```markdown
### Catalog gaps (skill feedback)

| Found identity (example) | Suspected family | Generalized shape (not the instance) | Citation vs identity | Propose skill edit? | User decision |
| --- | --- | --- | --- | --- | --- |
| `run_e07_handler` | C (errors) | `E<N>` / `error[-_]?E?<N>` as identity | identity → rename; `E07` in matrix → keep | Yes — add Errors token class under C | **accepted** (pre-seeded from S4–S6 grammar) |
```

Also include a **proposed patch sketch** (shape + 2–3 illustrative matches + one counterexample), never a single-id denylist line like “add `E07`”.

### Hard rules

| Do | Do not |
| --- | --- |
| Propose the **shape** (`E<N>`, `err[-_]\d+`) and family placement | Add one-off denylist entries (`E07`, `E08`, …) when the next id appears |
| Ask the user before editing any `SKILL.md` / `references/naming.md` | Auto-commit skill mutations mid-deslop |
| Prefer extending family **C** token classes for new issue-grammar letters | Invent family F+ for every new letter prefix |
| Keep anti-precedent: one found `E07` does not license `E08_helper.py` | Treat “catalog didn’t list it” as permission to keep identity residue |
| Record `User decision: accepted / rejected / deferred` once answered | Quietly re-prompt every session for a rejected false positive |

### After user accepts

Only when the user explicitly approves the catalog change:

1. Update `code-deslop/references/naming.md` (and SKILL family table if a token class is first-class).
2. Mirror one line in `deslop-gate` / `prose-deslop` only if the router summary lists token classes.
3. Add a mechanical scanner case **only** for the **generalized** shape (optional; prefer patterns over literals).
4. Note the update in the relevant `ORIGIN.md` as a catalog evolution bullet (shape, not ticket number).

### Example (your `Error = E07` case)

- **Wrong self-improve:** append `E07` to a deny list.
- **Right self-improve:** propose under family C: token class *Errors* — issue citation `E07`, `E-12`; identity residue `handle_e07()`, `e07_gate`, `run_error_e07`; replacement = domain failure mode + entity. User approves → catalog gains the **shape**, and `E99` is covered without another edit.
- **Pre-seed status:** Family C **Errors (`E<N>`)** and broadened claim-matrix shapes (`S<N>-[A-H]<N>`, `S<N>-DOG-<N>`) are now in `references/naming.md`, seeded from closed S4/S5/S6 evidence grammar — not as a denylist of those issue numbers.

## Related

- Router / policy entrypoint: `deslop-gate`
- Prose counterpart: `prose-deslop`
- Naming pattern catalog: [references/naming.md](references/naming.md)
- Mechanical gate: `just deslop-naming-scan` → `tools/deslop_naming_scan.py` (families A–D on branch diff; exit 2 on identity residue)
