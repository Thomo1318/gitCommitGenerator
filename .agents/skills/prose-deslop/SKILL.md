---
name: prose-deslop
description: Remove AI writing patterns from prose (docs, PR bodies, ADRs, technical writing). Use for deslop/de-AI/humanize on prose only. Never use on commit messages, git-cg output, Hybrid trailers, code diffs, pin hashes, or SOP matrices.
---

# prose-deslop — technical prose anti-slop

Project-owned fork of Stephen Turner `skill-deslop`, with hard guards for `gitCommitGenerator`.

## Non-negotiable (refuse / preserve)

- Never draft, rewrite, amend, or “improve” git commit messages.
- Never invoke `git-cg`, `git commit`, amend, rebase, or trailer edits.
- If asked to deslop a commit message: **refuse** and point to Hybrid/SOP / `git-cg`.
- Preserve exactly (do not “style”):
  - pin strings (`name@sha256`, 64-hex digests)
  - schema/metric/checkpoint/case/bundle IDs
  - Hybrid trailers (`Refs`/`Resolves`/…, `SemVer-Impact`, `Change-Types`, `Changelog-Groups`)
  - code fences, CLI flags, metric IDs, file paths, issue numbers
  - tables where cells are machine identifiers
- **Smallest defective span & technical exemption:** A rule match alone never authorizes an edit if the term is literal, quoted, attributed, or technically domain-valid (e.g. cryptographic robustness, official framework name). Only edit the smallest defective span; prefer a no-op to an uncertain edit.
- Prefer **crisp technical** register for this repo (docs/ADR/PR). Skip warm-blog voice unless the user asks.
- Do not rewrite source code; hand code residue to `code-deslop` / `deslop-gate`.

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

### 11. Eliminate plan and review meta-indices

Never use ephemeral task numbers, checklist indices, or prompt markers ("finding 6", "item 4", "step 3 of the plan", "per issue 2") as if they are self-standing domain concepts. Once the review or plan cycle finishes, these numbers lose all context. Name the concrete technical problem, invariant, or architectural change directly (e.g. "Enforced strict ISO8601 timestamp validation" instead of "Fixed finding 6").

### 12. Strip conversational scaffolding and paired buzzwords

Strip conversational assistant openers from technical docs, ADRs, and PR bodies ("Certainly! Below is the updated document...", "Here is the implementation plan as requested:"). Ban inflated paired buzzwords ("seamlessly integrate", "robust solution", "comprehensive mechanism", "state-of-the-art"). Start directly with the domain subject, title, or decision.

### 13. Ban tech puffery and false concessions

Ban marketing superlatives in technical writing ("blazing-fast", "rock-solid", "battle-tested", "groundbreaking", "effortless", "cutting-edge"). Replace them with concrete benchmarks, algorithmic complexity, or protocol details. Eliminate false rhetorical concessions ("To be fair...", "Admittedly..."); state constraints and tradeoffs directly.

### 14. Eliminate synonym cycling and mid-sentence colon crutches

Do not cycle through artificial synonyms for the same entity across a single paragraph or section ("the client", "the caller", "the consumer", "the subscriber"). Pick the single canonical domain noun and use it consistently. Avoid mid-sentence colons used as dramatic comparison pivots, and do not use stacked parentheticals as em-dash substitutes.

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
- Ephemeral plan/review index used ("finding 6", "step 3", "item 4")? Name the specific technical subject and resolution.
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

## Related

- Router / policy entrypoint: `deslop-gate`
- Code counterpart: `code-deslop`
