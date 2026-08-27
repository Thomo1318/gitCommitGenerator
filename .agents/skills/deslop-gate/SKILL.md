---
name: deslop-gate
description: Router and policy gate for deslop work. Use when the user says deslop, unslop, de-AI, remove slop, clean AI residue, or is unsure whether the target is code or prose. Classifies surface, enforces commit/SOP bans, then loads code-deslop or prose-deslop. Never rewrites commits or invokes git-cg.
---

# deslop-gate — policy router

Single entrypoint for deslop requests in this repo. Domain logic lives in `code-deslop` and `prose-deslop`. This skill only **classifies, refuses unsafe surfaces, and dispatches**.

## Non-negotiable

- Never draft, rewrite, amend, or polish git commit messages.
- Never run `git-cg`, `git commit`, amend, rebase, reset, force-push, or trailer mutation.
- Commit authority remains: SOP gitmoji matrix + Hybrid standard + user-run `git-cg`.
- Never touch pin strings, content hashes, schema/metric IDs, checkpoint IDs, or machine trailers “for style”.
- Never merge code and prose cleanup into one unsupervised pass.
- If target is ambiguous, ask which surface — do not guess on commit-related paths.

## Triggers

Use this skill when the user says any of:

- `deslop`, `/deslop`, `unslop`, `de-AI`, `remove slop`, `clean AI residue`
- `deslop code` / `deslop prose`
- Unclear requests like “make this less AI” without specifying code vs prose

## Routing table

| User intent / target | Action |
|---|---|
| Branch diff, source, tests, “code slop” | Load and follow **`code-deslop`** |
| Docs, ADR, PR body, README prose, chat prose | Load and follow **`prose-deslop`** |
| Commit message, Hybrid subject/body/trailers, `git-cg` output | **Refuse** — use SOP + `git-cg` only |
| SOP / gitmoji matrix / semantic contract authority | **Refuse** |
| Secrets, `.env`, credential material | **Refuse** |
| Both code and prose explicitly requested | Run **sequentially** (code first, then prose on stated docs only); never one blended edit |
| Ambiguous | Ask: `code`, `prose`, or `refuse` |

## Procedure

1. Classify the target surface using the table above.
2. If refuse: state the reason in one short paragraph; stop.
3. If code: apply `.agents/skills/code-deslop/SKILL.md` fully (including its deny-list).
4. If prose: apply `.agents/skills/prose-deslop/SKILL.md` fully (including identifier preservation).
5. End with:
   - surface chosen
   - skills applied
   - files touched
   - refusals (if any)

## Explicit command shapes

```text
/deslop code
/deslop prose
/deslop           → classify or ask; never touch commits
```

## Why this exists

`npx skills add …@deslop` installs different upstream skills to the same folder name and overwrites. This monorepo keeps **distinct path skills** under `dotagents` (`agents.toml`) so policy cannot float with marketplace updates.
