---
name: prose-deslop
description: Remove AI writing patterns from prose (docs, PR bodies, ADRs, technical writing). Enforces domain-first naming for durable operator surfaces cited in prose (recipes, paths, CLI). Default: never touch commit messages/git-cg/SOP. Explicit opt-in only for desloping proposed/draft gold-standard commit message text (no git mutation).
---

# prose-deslop — technical prose anti-slop

Project-owned fork of Stephen Turner `skill-deslop`, with hard guards for `gitCommitGenerator`.

## Non-negotiable (refuse / preserve)

- Never invoke `git-cg`, `git commit`, amend, rebase, reset, force-push, or trailer mutation in the index/HEAD.
- **Commit messages (default):** do not draft, rewrite, or “improve” commit messages; point to Hybrid/SOP / `git-cg`.
- **Commit messages (explicit opt-in only):** if the user clearly asks to deslop a *proposed/draft/gold-standard example* commit message (not rewriting HEAD history), follow **Commit draft deslop** below. Still never run git/git-cg.
- Preserve exactly unless the user is explicitly renaming a durable surface and the prose must track it:
  - pin strings (`name@sha256`, 64-hex digests)
  - schema/metric/checkpoint/case/bundle IDs
  - Hybrid trailer **keys** and machine grammar (`Refs`/`Resolves`/…, `SemVer-Impact`, `Change-Types`, `Changelog-Groups`)
  - code fences that quote real source (edit only when correcting a renamed identifier the pass owns)
  - issue numbers (`#254`)
  - tables where cells are machine identifiers (update cells only as part of an explicit rename cascade)
- **Smallest defective span & technical exemption:** A rule match alone never authorizes an edit if the term is literal, quoted, attributed, or technically domain-valid (e.g. cryptographic robustness, official framework name). Only edit the smallest defective span; prefer a no-op to an uncertain edit.
- Prefer **crisp technical** register for this repo (docs/ADR/PR). Skip warm-blog voice unless the user asks.
- Do not rewrite source code; hand code residue to `code-deslop` / `deslop-gate`.
- **Naming:** durable operator names in prose follow **pattern families A–E** as `code-deslop` (stage, plan index, governance taxonomy-as-identity, ceremony, synonyms — any generation). Matrix **citations** stay; taxonomy-as-tool-name does not.

## When to Apply

- Any request to "make it sound human" or "deslop" writing
- Any prose (articles, blog posts, essays, memos, newsletters, reports) or scientific writing (manuscripts, abstracts, cover letters, grant narratives, discussion sections, peer review responses) where the user wants it to sound natural rather than AI-generated
- Editing or revising existing text where the user wants it to sound natural rather than AI-generated
- Reviewing text for AI tells

## Core Rules

### 1. Cut filler phrases

Remove throat-clearing openers ("Here's the thing:"), emphasis crutches ("Let that sink in."), business jargon ("navigate the landscape"), and meta-commentary ("In this section, we'll explore..."). See [references/phrases.md](references/phrases.md) for the full catalog.

### 2. Break formulaic structures

Avoid binary contrasts ("Not X. Y."), negative listings ("Not a X. Not a Y. A Z."), dramatic fragmentation ("Speed. That's it. That's the tradeoff."), self-posed rhetorical questions ("The result? Devastating."), and anaphora/tricolon abuse. See [references/structures.md](references/structures.md) for patterns and fixes.

### 3. Eliminate AI tropes

Watch for the full catalog of AI writing tells: "quietly" and other magic adverbs, "delve" and its cousins, the "serves as" dodge, false ranges ("from X to Y" where the range is meaningless), superficial participle analyses ("highlighting its importance"), invented concept labels ("the supervision paradox"), grandiose stakes inflation, patronizing analogies, and false vulnerability. See [references/tropes.md](references/tropes.md) for the complete list with examples.

### 4. Use active voice with human subjects

Prefer active constructions with named actors. "The complaint becomes a fix" is wrong. "The team fixed it" is right. If no specific person fits, use "we" in scientific prose or "you" in blog posts.

### 5. Be specific

No vague declaratives ("The reasons are structural"). Name the specific thing. No lazy extremes ("every," "always," "never") doing vague work. No vague attributions ("Experts argue..."). If you cannot name the expert, you do not have a source.

In scientific writing, domain terminology is fine and expected. "Weighted interval score" is precise language, not jargon. The problem is business buzzwords ("leverage," "landscape," "ecosystem") and AI vocabulary tells ("delve," "tapestry," "nuanced") leaking into technical prose.

### 6. Match register to context

In blog posts and newsletters, put the reader in the room. "You" beats "People." Specifics beat abstractions. No narrator-from-a-distance voice.

In scientific writing, maintain appropriate formality. Use "we" for your own work, cite specific authors instead of "researchers have shown," and avoid both the distant narrator ("It has long been recognized that...") and the overly casual blog voice. State claims and back them with citations.

### 7. Vary rhythm

Mix sentence lengths. Two items beat three. End paragraphs differently. No em dashes. Do not stack short punchy fragments for manufactured emphasis. Do not write listicles disguised as prose ("The first wall... The second wall...").

### 8. Trust readers

State facts directly. Skip softening, justification, hand-holding. No "Let's break this down." No "Think of it as..." No pedagogical voice unless the audience genuinely needs it. No fractal summaries (telling the reader what you are about to say, saying it, then summarizing what you said).

### 9. Watch formatting tells

No bold-first bullets (every list item starting with a bolded keyword). No unicode arrows. No em dashes. No signposted conclusions ("In conclusion..."). No "Despite these challenges..." formulas. These are strong AI signals.

### 10. Do not dilute

One point per section. Do not restate the same argument in ten different ways across thousands of words. Do not beat a single metaphor to death. Do not stack historical analogies for false authority ("Apple didn't build Uber. Facebook didn't build Spotify...").

### 11. Eliminate plan/review meta-indices **and taxonomy-as-operator-name**

Never treat process indices or delivery-cycle labels as self-standing domain concepts in durable **operator** docs. Distinguish **citation** (keep) from **identity** (rename).

**Pattern families (any generation — do not extend a per-issue list):**

| Family | Shape | Action in prose |
| --- | --- | --- |
| Plan/review index | `finding <N>`, `FIND-<N>`, `INT-<N>`, `item <N>`, `step <N>` (any N) | Name the concrete invariant/bug/change; cite id only as reference |
| Stage segment in **operator** names | `s<N>`, `slice<N>`, `phase<N>` inside recipe/path/CLI (any N) | Domain-first scope + measurement |
| Governance taxonomy as **tool/path name** | `D<N>`, `I<N>`, `E<N>`, `F-S<N>-…`, `R<N>`, `S<N>-[A-H]<N>`, `S<N>-DOG-<N>`, `RK-…`, `NTH-<N>`, `P0|P1|P2`, `AC-<N>` taught as something to run or as a module name | Name the job/invariant; keep ids in matrices/tables |
| Ceremony-primary instructions | “run the proof recipe” with no scope/measurement | Name the gate or tool job |

**Keep:** historical narrative; claim/decision/failure/risk/NTH/priority **matrices**; issue links; short “see D31” pointers.  
**Do not keep:** docs that teach a taxonomy-named or stage-named runnable surface as the durable operator path.

Catalog: [references/naming.md](references/naming.md).

### 12. Strip conversational scaffolding and paired buzzwords

Strip conversational assistant openers from technical docs, ADRs, and PR bodies ("Certainly! Below is the updated document...", "Here is the implementation plan as requested:"). Ban inflated paired buzzwords ("seamlessly integrate", "robust solution", "comprehensive mechanism", "state-of-the-art"). Start directly with the domain subject, title, or decision.

### 13. Ban tech puffery and false concessions

Ban marketing superlatives in technical writing ("blazing-fast", "rock-solid", "battle-tested", "groundbreaking", "effortless", "cutting-edge"). Replace them with concrete benchmarks, algorithmic complexity, or protocol details. Eliminate false rhetorical concessions ("To be fair...", "Admittedly..."); state constraints and tradeoffs directly.

### 14. Eliminate synonym cycling and mid-sentence colon crutches

Do not cycle through artificial synonyms for the same entity across a single paragraph or section ("the client", "the caller", "the consumer", "the subscriber"). Pick the single canonical domain noun and use it consistently. Avoid mid-sentence colons used as dramatic comparison pivots, and do not use stacked parentheticals as em-dash substitutes.

## Mandatory Naming Audit (prose surfaces)

Before finishing a prose deslop pass on docs/ADR/PR/plan text, scan for **durable names** the prose still teaches:

- task runner recipe names
- artifact paths
- CLI commands/flags
- module or script names presented as operator instructions

Apply families **A–E** (any N). Include governance shapes: `D<N>`, `I<N>`, `E<N>`, `FIND-…`, `INT-…`, `F-S…`, `S<N>-[A-H]<N>`, `S<N>-DOG-<N>`, `RK-…`, `NTH-…`, `P0|P1|P2` when used as **identity** of something to run — not when they are matrix citations.

Emit:

| Flagged | Family | Role (identity/citation) | Domain-first replacement | Doc surface | Status |
| --- | --- | --- | --- | --- | --- |

Pass rule: every **identity** hit renamed or justified; citations listed as preserved when relevant.  
Do not “deslop voice” while leaving stage- or taxonomy-named recipes as the documented operator path.

## Commit draft deslop (explicit opt-in only)

Triggers: user pastes a **proposed/draft/gold-standard example** commit message and asks to deslop/clean that draft (often to catch naming residue before `git-cg`/commit).

### Allow

- Domain-first renames inside subject/body (families A–E; stage/plan/governance identity). Preserve intentional citation refs.
- Cut AI filler, synonym cycling, throat-clearing in body prose.
- Align path/recipe mentions with the Naming Audit.

### Forbid

- Changing gitmoji or conventional `type` (SOP/`git-cg` authority).
- Inventing/deleting trailer **keys** or breaking Hybrid trailer grammar.
- Changing issue ids or `SemVer-Impact` vocabulary.
- Any git mutation, `git-cg`, amend, or silent `.git/COMMIT_EDITMSG` write.
- Rewriting an already-landed HEAD commit message as history cleanup.

### Output

One fenced `text` block with the full cleaned draft + mini Naming Audit. No git side effects.

Default without opt-in: **refuse** commit-message deslop and point to SOP + user-run `git-cg`.

## Quick Checks

Run these before delivering any prose:

- Heavy use of adverbs or -ly words? Cut them.
- Any passive voice? Find the actor, make them the subject.
- Inanimate thing doing a human verb? Name the person.
- Any "here's what/this/that" throat-clearing? Cut to the point.
- Any "not X, it's Y" contrasts? State Y directly.
- Any self-posed rhetorical question answered immediately? Fold into a statement.
- Three consecutive sentences match length? Break one.
- Paragraph ends with a punchy one-liner? Vary it.
- Em dash anywhere? Remove it. Use a comma or period or a parenthetical.
- Vague declarative ("The implications are significant")? Name the specific implication.
- Plan/review index used as the topic (`finding <N>`, `FIND-<N>`, `INT-<N>`, `step <N>`, any N)? Name the subject; keep id only as citation.
- Governance taxonomy taught as a tool/module name (`D<N>`, `E<N>`, `S<N>-[A-H]<N>`, `S<N>-DOG-<N>`, `NTH-<N>`, `RK-…`, `P0` gate, …)? Rename identity; keep matrix rows.
- Durable operator name still stage-labelled (`s<N>`, `slice<N>`, …) or ceremony-primary (“proof recipe”)? Domain-first scope + behavior.
- Naming Audit present for operator surfaces (families A–E; citation vs identity called out)?
- Commit draft touched without explicit user opt-in? Revert to refuse.
- Conversational assistant openers ("Certainly!", "Here is the summary...")? Delete and start directly with content.
- Inflated buzzword pairs ("seamlessly integrates", "robust solution")? Replace with concrete technical actions.
- Tech puffery superlatives ("blazing-fast", "rock-solid", "effortless")? Replace with verifiable metrics or algorithmic bounds.
- False concessions ("To be fair", "Admittedly")? Drop stagecraft and state tradeoffs directly.
- Synonym cycling across the same paragraph? Standardize on the canonical domain noun.
- Mid-sentence colons used as contrast pivots or parenthetical stacking? Rewrite to direct sentences.
- Are technical domain terms, quoted strings, and exact numbers preserved? (Keep intact).
- Any sentence starting with What/When/Where/Which/Who/Why/How as a crutch? Restructure.
- Meta-joiners ("The rest of this essay...")? Delete.
- "It's worth noting" or similar filler transitions? Delete.
- Same metaphor used more than twice? Replace or cut repeats.
- "Despite these challenges..." formula? Rewrite.
- Bold-first bullet pattern? Remove bold leads.
- Tricolon (three-item list)? Use two items or one.

## Scoring

When reviewing text, rate 1-10 on each dimension:

| Dimension    | Question                               |
| ------------ | -------------------------------------- |
| Directness   | Statements or announcements?           |
| Rhythm       | Varied or metronomic?                  |
| Trust        | Respects reader intelligence?          |
| Authenticity | Sounds like a specific human wrote it? |
| Density      | Anything cuttable?                     |

Below 35/50: revise.

## Reference Files

Consult these for detailed catalogs when writing or editing:

- [references/phrases.md](references/phrases.md): Phrases to remove or replace (throat-clearing, emphasis crutches, business jargon, adverbs, meta-commentary, vague declaratives)
- [references/structures.md](references/structures.md): Structural patterns to avoid (binary contrasts, negative listings, dramatic fragmentation, rhetorical setups, false agency, passive voice, rhythm problems)
- [references/tropes.md](references/tropes.md): Full catalog of AI writing tropes (word choice, sentence structure, paragraph structure, tone, formatting, composition)
- [references/examples.md](references/examples.md): Before/after transformations showing how to fix common patterns
- [references/naming.md](references/naming.md): Stage-label / recipe / path naming residue in technical docs

## Examples

See [references/examples.md](references/examples.md) for before/after transformations.

**Quick inline example (scientific writing):**

Before:

> "It's worth noting that these findings have important implications for how we navigate the challenges of forecast ensembling moving forward. Despite these challenges, this work contributes meaningfully to the growing body of literature, highlighting the need for continued evaluation."

After:

> "If individual model rankings are unstable across geography and time, ensemble methods that weight models by past performance may not improve on equal-weight approaches."

Changes: Replaced filler transition, vague declarative, "despite these challenges" formula, and superficial participle analysis with the specific implication.

**Quick inline example (blog post):**

Before:

> "Here's the thing: most bioinformatics pipelines break in production. Not because the code is bad. Because the data is bad. Let that sink in."

After:

> "Most bioinformatics pipelines break in production. The code runs fine. The data doesn't match the assumptions baked into it."

Changes: Removed opener, binary contrast, and emphasis crutch. Named the specific problem.

## Output

1. **Naming Audit** table when docs teach recipes/paths/CLI (identity vs citation); else scanned-none + families A–E checked.
2. Brief note on voice/structure residue removed.
3. Files touched.
4. Refusals (default commit refuse unless opt-in draft deslop).


## Catalog feedback loop

If prose teaches a durable operator name that is process/taxonomy-encoded but not covered by families A–E as written, follow **code-deslop → Catalog feedback loop**: rename/teach domain-first in the doc, emit a **Catalog gaps** row with a **generalized shape**, and ask before editing skills. Do not add one-off ids to a denylist.

## Related

- Router / policy entrypoint: `deslop-gate`
- Code counterpart: `code-deslop`
