---
name: code-deslop
description: Remove AI-generated code slop from the current branch diff. Use after agent coding passes to clean unnecessary comments, abnormal defensive checks, type escape hatches, and local style drift. Never use for commit messages, git-cg, SOP, prose docs, or security/fail-closed paths.
---

# code-deslop — branch code residue cleanup

Project-owned fork of the brianlovin `deslop` code checklist, with hard guards for `gitCommitGenerator`.

## Non-negotiable (refuse / do not touch)

- Never draft, rewrite, amend, or “improve” git commit messages.
- Never invoke `git-cg`, `git commit`, `git commit --amend`, rebase, reset, or trailer edits.
- Commit authority is SOP + `git-cg` + the user only.
- If asked to deslop a commit message or Hybrid trailers: **refuse** and point to Hybrid/SOP / `git-cg`.
- Never edit SOP matrices, gitmoji rows, or semantic-contract authority files as a “cleanup”.
- Never strip fail-closed validation, pin locks, secret redaction/scrub paths, store-integrity gates, doctor block paths, or intentional untrusted-input checks.
- Never “simplify away” closed enums, schema strictness, or security-relevant guards because they look defensive.
- Prefer behaviour-preserving minimal diffs. No drive-by refactors.

## When to use

- After an agent wrote or edited **code/tests** on the current branch.
- User asks to `code-deslop`, “remove AI code slop”, “clean branch residue”, or similar.
- Not for README/ADR/blog prose (use `prose-deslop` via `deslop-gate`).
- Not as a substitute for review, tests, or architecture decisions.

## Procedure

1. Determine diff base intentionally:
   - PR branch: merge base / PR base / `origin/main` as appropriate.
   - Default: `main` or repo default branch if no PR context.
2. Inspect only changes introduced on this branch vs that base.
3. Remove AI code residue that a careful human would not leave, including:
   - Extra comments a human would not add, or comments inconsistent with the file
   - Abnormal defensive checks or `try/catch` on trusted/validated internal paths
   - Casts to `any` / type escape hatches used only to bypass typing
   - Deep nesting that should be early-return simplified **when behaviour-identical**
   - Single-use temps that obscure flow with no clarity gain
   - Style drift inconsistent with the surrounding file
4. Keep anything that encodes an invariant, security rationale, pin/doctor/redaction contract, or fail-closed policy — even if verbose.
5. Do not expand scope beyond the branch diff unless the user explicitly asks.
6. Run or recommend targeted tests when non-trivial logic moved.

## Output

Report in 1–3 sentences what changed, plus a bullet list of files touched and any **refused** items (with reason).

## Related

- Router / policy entrypoint: `deslop-gate`
- Prose counterpart: `prose-deslop`
