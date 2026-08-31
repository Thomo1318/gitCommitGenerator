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
   - Plan/review meta-artifact identifiers: names derived from ephemeral plan steps, review checklists, or ticket indices (e.g. `finding_6()`, `test_finding_6()`, `step_3_helper`, `item_4_flag`, `finding_6_fix.py`). Replace them with semantic, domain-first names describing actual behavior, entity, or invariant (e.g. `validate_trailer_length()`, `test_rejects_malformed_trailer_prefix()`, `scrub_secrets.py`).
   - Domain-term consistency (anti-synonym cycling): multiple names introduced for the exact same entity across adjacent functions (e.g. `payload`, `data_dict`, `raw_event`, `msg_obj`); standardize on the repository's canonical domain term.
   - Semantic duplication (shadow utilities): newly written helper functions (e.g. `slugify()`, `clean_path()`, `parse_json_safely()`) that duplicate existing repository utilities; replace them with imports of established project utilities.
   - Process residue and tautological comments: comments that record prompt history (`# Fix for finding 6`, `# Step 3: parse input`, `# Modified per user request`) or restate obvious code (`# increment counter` above `counter += 1`, `# constructor`). Keep comments that explain _why_, non-obvious algorithms, security invariants, or contract rules.
   - Scratchpad & Chain-of-Thought leakage: private agent reasoning wrappers (`<thinking>`, `<thought>`, `<scratchpad>`) or `// Reasoning:` comments left inside source code or tests. Strip them completely.
   - Micro-helper proliferation: trivial single-use wrappers or pass-through functions (e.g. `def _get_val(d, k): return d.get(k)`) that add call stack indirection without providing abstraction or reuse value. Inline them.
   - Premature abstraction: single-implementation abstract base classes, generic interfaces, or boilerplate manager hierarchies that add complexity without concrete reuse. Flatten to direct implementations.
   - Debug echo & logging chatter: conversational debug `print()` statements and redundant function entry/exit logs (`logger.debug("Entering process_data")`, `print(f"[DEBUG] count: {c}")`).
   - Silent failure fallbacks: catch blocks that swallow real errors and return synthetic empty defaults (`except Exception: return {}` or `return []`) when failure should fail closed or propagate according to project error handling policy.
   - Abnormal defensive checks or `try/catch` on trusted/validated internal paths
   - Casts to `any` / type escape hatches used only to bypass typing
   - Deep nesting that should be early-return simplified **when behaviour-identical**
   - Single-use temps that obscure flow with no clarity gain
   - Style drift inconsistent with the surrounding file
4. Keep anything that encodes an invariant, security rationale, pin/doctor/redaction contract, or fail-closed policy — even if verbose.
5. Do not expand scope beyond the branch diff unless the user explicitly asks.
6. Run or recommend targeted tests when non-trivial logic moved.

## Semantic Domain Naming Standards (Anti-Meta Residue)

When cleaning or reviewing proposed names in code, tests, and scripts:

| Identifier Type     | Bad (Meta-Artifact Slop)                 | Good (Semantic Domain-First)                                   | Rationale                                                         |
| ------------------- | ---------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Function/Method** | `handle_finding_6()`, `fix_step_3()`     | `sanitize_commit_trailer()`, `enforce_closed_enum()`           | Verb + domain entity + action. Readable without plan context.     |
| **Variable/Const**  | `finding_6_data`, `step_3_flag`          | `redacted_token_map`, `has_valid_signature`                    | Explains content/state, not origin.                               |
| **Test Case**       | `test_finding_6()`, `test_plan_item_2()` | `test_rejects_unpinned_action()`, `test_parses_iso8601_date()` | `test_<behavior>_<condition>` reveals what invariant is verified. |
| **File/Script**     | `finding_6_fix.py`, `step_2_patch.sh`    | `validate-trailers.py`, `sync-agent-skills.sh`                 | Describes utility/tool responsibility.                            |

## Quick Checks (Pre-Commit / Pre-PR)

Run these before delivering code changes:

- Any plan or review indices (`finding_6`, `step_3`, `item_4`) in function, variable, test, or file names? Rename to domain intent.
- Any variable synonym cycling across adjacent functions? Standardize on the repo's canonical domain noun.
- Any shadow helper functions that duplicate existing repo utilities? Replace with imports.
- Any process residue comments (`# Step 1:`, `# Fix for finding 6`, `# Added as requested`) or tautological comments? Strip them.
- Any agent scratchpad tags (`<thinking>`) or CoT reasoning comments left in code? Strip them.
- Any micro-helpers that merely wrap a single stdlib call or single-implementation abstract boilerplate? Inline/flatten them.
- Any debug `print()` calls or redundant entry/exit logging chatter? Remove them.
- Any catch-all blocks swallowing errors with dummy empty defaults (`return {}`)? Ensure proper error propagation.
- Any unnecessary `any` casts or suppressed lints introduced to silence types? Provide proper typed models.
- Did you preserve all security checks, fail-closed guards, pin validations, and SOP authority matrices? (Never strip).

## Output

Report in 1–3 sentences what changed, plus a bullet list of files touched and any **refused** items (with reason).

## Related

- Router / policy entrypoint: `deslop-gate`
- Prose counterpart: `prose-deslop`
