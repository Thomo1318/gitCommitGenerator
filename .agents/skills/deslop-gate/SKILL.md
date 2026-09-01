---
name: deslop-gate
description: Router and policy gate for deslop work. Use when the user says deslop, unslop, de-AI, remove slop, clean AI residue, or is unsure whether the target is code or prose. Classifies surface, enforces SOP bans, requires a Naming Audit for durable identifiers, and loads code-deslop or prose-deslop. Default refuse for commit messages; explicit opt-in only for draft/gold-standard commit text (no git mutation, never git-cg).
---

# deslop-gate — policy router

Single entrypoint for deslop requests in this repo. Domain logic lives in `code-deslop` and `prose-deslop`. This skill only **classifies, refuses unsafe surfaces, requires naming discipline, and dispatches**.

## Non-negotiable

- Never run `git-cg`, `git commit`, amend, rebase, reset, force-push, or trailer mutation on the repo.
- Commit **authority** remains: SOP gitmoji matrix + Hybrid standard + user-run `git-cg`.
- Never touch pin strings, content hashes, schema/metric IDs, checkpoint IDs, or machine trailer **keys** “for style”.
- Never merge code and prose cleanup into one unsupervised pass.
- If target is ambiguous, ask which surface — do not guess on commit-related paths.
- **Naming is not optional:** any pass that touches recipes, artifact paths, CLI, symbols, or docs that teach those surfaces must produce a **Naming Audit** (see child skills). Residue is **pattern-based** families A–E (stage, plan/review index, **governance taxonomy as identity**, ceremony, synonyms — any generation). **Not** a per-slice or per-issue denylist. Citations in matrices stay; identity renames.

## Triggers

Use this skill when the user says any of:

- `deslop`, `/deslop`, `unslop`, `de-AI`, `remove slop`, `clean AI residue`
- `deslop code` / `deslop prose`
- `deslop naming` / “fix recipe names” / domain-first rename passes
- `deslop commit draft` / deslop a pasted gold-standard **example** message (opt-in path)
- Unclear requests like “make this less AI” without specifying code vs prose

## Routing table

| User intent / target | Action |
|---|---|
| Branch diff, source, tests, just recipes, scripts, “code slop”, naming of symbols/recipes | Load and follow **`code-deslop`** (Naming Audit mandatory) |
| Docs, ADR, PR body, README prose, plans, chat prose | Load and follow **`prose-deslop`** (Naming Audit when operator surfaces are cited) |
| Pasted **draft / proposed / gold-standard example** commit message + explicit deslop request | Load **`prose-deslop` → Commit draft deslop** (or code-deslop’s twin section). Clean text only. **No git.** |
| Commit message on HEAD, amend request, Hybrid trailers as authority, `git-cg` output as source of truth | **Refuse** mutation — use SOP + user-run `git-cg` only |
| SOP / gitmoji matrix / semantic contract authority | **Refuse** |
| Secrets, `.env`, credential material | **Refuse** |
| Both code and prose explicitly requested | Run **sequentially** (code first, then prose on stated docs only); one shared Naming Audit at the end |
| Ambiguous | Ask: `code`, `prose`, `commit-draft` (opt-in), or `refuse` |

## Naming gate (router-level)

Before dispatch returns “done”, ensure the child skill output includes:

1. Surfaces scanned for durable names (recipes, paths, CLI, symbols, tests, docs that teach them).
2. A **Naming Audit** table, or scanned-none that lists **families A–E** checked (including governance shapes).
3. **Citation vs identity** called out when taxonomy tokens appear.
4. No unexplained **identity** leftovers matching (any digit width, any separator/`CASE`):
   - **A** stage/slice/phase/wave/milestone: `s<N>`, `slice<N>`, `phase<N>`, …
   - **B** plan/review/session: `finding_<N>`, `FIND[-_]<N>`, `INT[-_]<N>`, `item_<N>`, `step_<N>`, …
   - **C** governance-as-identity: `D<N>`, `I<N>`, `R<N>`, `E<N>`, `F-S<N>-…`, `S<N>-[A-H]<N>`, `S<N>-DOG-<N>`, `AC[-_]<N>`, `RK-…`, `NTH[-_]<N>`, `P0` / `P1` / `P2`, `DoD[-_]<N>`, …
   - **D** ceremony/scratch primary: `proof` as ticket proof, `wip`, `tmp`, `final2`, …
   - **E** synonym cycles for one entity

Do **not** implement this gate as “search for s7 and finding_6 only,” and do **not** require updating the skill when issue #246-style IDs appear (`D31`, `I6`, `E07`, `E13`, `F-S6-04`, `R4`, `FIND-003`, `INT-05`, `S6-A04`, `S6-G02`, `S7-DOG-05`, `RK-A5`, `NTH-03`, `P0`). Those are already family **B/C** shapes.

Replacement direction: **scope + behavior + entity**. Preserve matrix/ADR/issue citations.

**Operator-facing comments** (justfile/task headers): lead with the **job**, not `S<N>` / `Slice <N>` as primary orientation. Trailing `Refs: #N` is fine; slice-led banners are orientation debt when labels recycle.

If the child pass cleaned comments but left family A–D **identity** names on durable surfaces, **the gate fails** — finish renames + cascade.

**Anti-precedent:** historical residue already in the repo (`S7_tests.py`, old `finding_*` helpers, etc.) is **not** permission to mint new matching identity. “Matches existing convention” is a **fail** when the convention is family A–D residue. Only the exact pre-existing symbol you did not introduce may be preserved; siblings and extensions must be domain-first.

## Commit draft policy (relaxed, bounded)

| Request | Gate decision |
|---|---|
| “Deslop this draft commit message / gold-standard example” + pasted body | **Allow** text-only cleanup via child skill commit-draft section |
| “Fix naming in the proposed commit message” | **Allow** text-only |
| “Amend HEAD”, “run git-cg”, “commit this”, rewrite trailers in git | **Refuse** from deslop; user runs git/`git-cg` separately |
| No paste, vague “deslop the commit” | **Ask** for draft text or refuse |

Allowed draft cleanup: domain-first names, filler removal, internal path consistency.  
Forbidden: gitmoji/type authority changes, trailer key edits, issue-id invention, any git side effect.

## Procedure

1. Classify the target surface using the table above.
2. If refuse: state the reason in one short paragraph; stop.
3. If code: apply `.agents/skills/code-deslop/SKILL.md` fully (including Mandatory Naming Audit + pattern catalog (families A–E)).
4. If prose: apply `.agents/skills/prose-deslop/SKILL.md` fully (including naming + identifier preservation).
5. If commit-draft opt-in: apply the child **Commit draft deslop** section only; return cleaned text; no git.
6. Verify Naming Audit present when durable surfaces were in scope.
7. If the child reported **Catalog gaps**, include them in the gate summary and prompt the user (shape-level skill edit; no auto-write).
8. End with:
   - surface chosen
   - skills applied
   - Naming Audit summary (or scanned-none)
   - Catalog gaps (if any) + proposed generalized shapes awaiting user decision
   - files touched
   - refusals (if any)

## Mechanical enforcement

Skills alone cannot force tool use. Before claiming a naming deslop is done:

```bash
just deslop-naming-scan
```

Exit `2` means identity residue remains (families A–D). Exit `0` is necessary but not sufficient for a full deslop (comments/voice still need the skills).

## Explicit command shapes

```text
/deslop code
/deslop prose
/deslop naming          → code-deslop Naming Audit (+ prose cascade if docs in scope)
/deslop commit-draft    → opt-in text-only; requires pasted draft; never git-cg
/deslop                 → classify or ask; default never mutates commits in git
```

## Catalog feedback loop (router)

When child skills report **Catalog gaps**, the gate:

1. Surfaces them in the final gate summary (do not drop).
2. Treats unresolved identity residue as a **naming fail** even if the shape is not yet in A–E text — domain-first still applies.
3. **Never** auto-edits skills. Prompts the user with the child’s proposed **generalized** shape and waits.
4. Rejects proposals that are single-instance denylist entries; asks for shape-level wording.
5. On accept, routes a **docs-only** follow-up to edit `code-deslop/references/naming.md` (+ mirrors) as a separate explicit task — not smuggled inside an unrelated code deslop commit unless the user says so.

## Why this exists

`npx skills add …@deslop` installs different upstream skills to the same folder name and overwrites. This monorepo keeps **distinct path skills** under `dotagents` (`agents.toml`) so policy cannot float with marketplace updates.

Naming failures (stage-segment recipes, finding-index symbols, and governance-id APIs surviving “full deslop”) showed that voice/comment rules alone are insufficient — the router must treat domain-first durable names as a **pattern gate** (any generation; citation ≠ identity), not a suggestion and not a per-issue denylist.
