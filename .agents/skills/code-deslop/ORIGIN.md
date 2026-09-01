# Origin

- Upstream seed: `brianlovin/agent-config` skill `deslop`
- Upstream URL: https://github.com/brianlovin/agent-config/tree/main/skills/deslop
- Captured: 2026-08-27
- Ownership: project-local path skill (`path:.agents/skills/code-deslop`)
- Do not reinstall via `npx skills add …@deslop` into this path — it collides with prose-deslop.
- Refresh policy: manual review only; re-diff upstream SKILL.md, keep project guards.

## Local hardening (2026-09-01)

- Mandatory **Naming Audit** on durable operator surfaces (recipes, paths, CLI, symbols, docs that teach them).
- **Pattern families A–E** (any generation): stage/slice/phase; plan/review/FIND/INT indices; **governance taxonomy as identity** (`D<N>`, `I<N>`, `F-S…`, `R<N>`, `S<N>-A<N>`, `RK-…`, `NTH-<N>`, `P0|P1|P2`, `AC-…`); ceremony/scratch; synonym cycles.
- **Citation vs identity:** issue/ADR/matrix tokens stay; same shapes as API/recipe/path names rename.
- **Anti-precedent:** existing family A–D identity in the tree is debt, not a template for new names (`S7_tests.py` ⇏ `S7_Rename.py`).
- **Catalog feedback loop:** novel identity shapes → completion **Catalog gaps** + user-gated skill edit (generalized shape, never one-off denylist); domain-first rename does not wait on catalog.
- **Catalog pre-seed (S4–S6 grammar → shapes):** Family C **Errors** token class (`E<N>`, `E[-_]<N>`, `error[-_]?E?<N>` as identity; matrix `E07`/`E13` remain citations); broadened measurement/claim-matrix shapes (`S<N>-[A-H]<N>`, `S<N>-DOG-<N>`); work-package cite shape `P<N>-<N>` called out. Seeded from closed-slice evidence docs — not a denylist of S4/S5/S6 issue numbers.
- **Operator comments:** justfile/task headers lead with domain job; `S<N>`/`Slice <N>` only as trailing cite — labels recycle across issues.
- **Not** a per-slice or per-issue denylist — do not add `s8`, `D99`, `FIND-100` when new issues open.
- Commit **draft** deslop opt-in (text only); still no git-cg / history mutation from deslop.
