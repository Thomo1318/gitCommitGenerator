# Phrases to Remove or Replace

## Throat-Clearing Openers

Remove these. State the content directly.

- "Here's the thing:"
- "Here's what [X]"
- "Here's this [X]"
- "Here's that [X]"
- "Here's why [X]"
- "Here's the kicker"
- "Here's where it gets interesting"
- "Here's what most people miss"
- "Here's the deal"
- "The uncomfortable truth is"
- "It turns out"
- "The real [X] is"
- "Let me be clear"
- "The truth is,"
- "I'll say it again:"
- "I'm going to be honest"
- "Can we talk about"
- "Here's what I find interesting"
- "Here's the problem though"

Any "here's what/this/that" construction is throat-clearing before the point. Cut it and state the point.

## Emphasis Crutches

These add no meaning. Delete them.

- "Full stop." / "Period."
- "Let that sink in."
- "This matters because"
- "Make no mistake"
- "Here's why that matters"

## Pedagogical Hand-Holding

Phrases that assume the reader needs a teacher. Cut them.

- "Let's break this down"
- "Let's unpack this"
- "Let's explore"
- "Let's dive in"
- "Let's delve into"
- "Think of it as..."
- "Think of it like..."
- "Imagine a world where..."

## Business Jargon

Replace filler jargon with plain language **when the substitute is semantically equivalent**. Keep domain terms when they carry technical meaning (for example a real framework name, robustness contract, or system architecture label).

| Avoid (when filler)         | Use instead                        |
| --------------------------- | ---------------------------------- |
| Navigate (challenges)       | Handle, address                    |
| Unpack (analysis)           | Explain, examine                   |
| Lean into                   | Accept, embrace                    |
| Landscape (context)         | Situation, field                   |
| Game-changer                | Significant, important             |
| Double down                 | Commit, increase                   |
| Deep dive                   | Analysis, examination              |
| Take a step back            | Reconsider                         |
| Moving forward              | Next, from now                     |
| Circle back                 | Return to, revisit                 |
| On the same page            | Aligned, agreed                    |
| Leverage (verb)             | Use                                |
| Utilize                     | Use                                |
| Robust (as empty praise)    | Strong, solid, or drop             |
| Streamline                  | Simplify                           |
| Harness                     | Use, apply                         |
| Paradigm                    | Model, approach                    |
| Synergy                     | Cooperation, combined effect       |
| Ecosystem (as vague scope)  | System, field, community           |
| Framework (as filler)       | Structure, approach                |
| Seamlessly integrate (with) | Integrate with, connect to         |
| Comprehensive mechanism     | Rule, validation, check            |
| State-of-the-art            | Name specific protocol / algorithm |

## Conversational Scaffolding

Remove assistant preamble and prompt acknowledgement from documentation, ADRs, and PR bodies. Start directly with the title and domain content.

- "Certainly! Below is the updated..."
- "Here is the summary/plan as requested:"
- "Sure! In this section, we..."
- "In this PR, we have implemented..."

## AI Vocabulary Tells

Words that became dramatically overrepresented in AI-generated text. Avoid or replace.

- "delve" (use: examine, look at, explore)
- "tapestry" (use: mix, combination, range)
- "certainly" (usually deletable)
- "landscape" when meaning "field" or "situation"
- "nuanced" (use: complex, subtle, specific)

## The "Serves As" Dodge

AI often replaces a plain "is" or "are" with pompous alternatives. Prefer the simple verb **when that is the actual meaning**. Keep "represents", "marks", or "serves as" when they are the precise technical claim (for example a schema that represents a contract, or a service that serves as a fallback path).

| Avoid (when meaning "is")      | Use instead |
| ------------------------------ | ----------- |
| serves as                      | is          |
| stands as                      | is          |
| marks (when meaning "is")      | is          |
| represents (when meaning "is") | is          |

## Fancy Ways to Say "Has"

Replacing simple possession verbs with marketing copy. Use "has" or "includes".

| Avoid (when meaning "has") | Use instead         |
| -------------------------- | ------------------- |
| boasts                     | has                 |
| features                   | has, includes       |
| sports                     | has                 |
| showcases                  | provides, includes  |

## Inflated Super-Verbs

Verbs that AI models compulsively reach for to inflate ordinary software actions. Replace with plain technical verbs.

| Avoid (when inflated) | Use instead                  |
| --------------------- | ---------------------------- |
| spearhead             | lead, start                  |
| orchestrate           | coordinate, manage, run      |
| cultivate             | build, develop               |
| democratize           | make accessible, open-source |
| supercharge           | speed up, optimize           |
| unleash               | enable, release              |
| elevate               | improve, refine              |
| bolster               | strengthen, support          |
| curate                | select, organize             |
| reimagine             | redesign, rework             |

## Adverbs

Remove unnecessary adverbs, softeners, intensifiers, and hedges. Preserve words required for technical precision (for example rate-limiting policy, formally verified, or concurrent-only guarantees).

Specific offenders when they add no information:

- "really"
- "just"
- "literally"
- "genuinely"
- "honestly"
- "simply"
- "actually"
- "deeply"
- "truly"
- "fundamentally"
- "inherently"
- "inevitably"
- "interestingly"
- "importantly"
- "crucially"
- "quietly" (AI's favorite for conveying subtle importance)
- "remarkably"
- "arguably"

Also cut these filler phrases:

- "At its core"
- "In today's [X]"
- "It's worth noting"
- "It bears mentioning"
- "Notably"
- "At the end of the day"
- "When it comes to"
- "In a world where"
- "The reality is"

## Meta-Commentary

Remove self-referential asides. The text should move, not announce its own structure.

- "Hint:"
- "Plot twist:" / "Spoiler:"
- "You already know this, but"
- "But that's another post"
- "X is a feature, not a bug"
- "Dressed up as"
- "The rest of this essay explains..."
- "Let me walk you through..."
- "In this section, we'll..."
- "As we'll see..."
- "I want to explore..."
- "In conclusion" / "To sum up" / "In summary"
- "As we've seen in this section..."
- "And so we return to where we began."
- "Per finding [N]..." / "FINDING_[N]" (any N — name the concrete invariant or bug)
- "Addressing item [N] from review..." (any N — name the concrete fix)
- "As discussed in step [N]..." (any N — name the architecture step)
- "Per the implementation plan..." (name the specific requirement)
- Stage-segment recipes/paths/CLI: `s<N>`, `slice<N>`, `phase<N>` inside operator names (any N) → domain-first scope + measurement
- Ceremony-primary instructions ("run the proof recipe") → name the gate/job
- Requirement-as-tool-name (`ac<N>-gate` as a command) → name the invariant/recipe job
- Governance-as-tool-name (`D<N>` / `FIND-<N>` / `S<N>-A<N>` / `NTH-<N>` / `RK-…` / `P0` as recipe or module identity) → domain job name; keep ids in matrices
- "Addresses D<N>" / "Fixes F-S<N>-…" as the only description → name the change; id may remain as citation

## Performative Emphasis

False intimacy or manufactured sincerity:

- "creeps in"
- "I promise"
- "They exist, I promise"

## False Vulnerability

Simulated self-awareness that reads as performative:

- "And yes, I'm openly..."
- "And yes, since we're being honest..."
- "This is not a rant; it's a diagnosis"

## Telling Instead of Showing

Announcing difficulty or significance rather than demonstrating it:

- "This is genuinely hard"
- "This is what leadership actually looks like"
- "This is what X actually looks like"
- "actually matters"

## "The Truth Is Simple"

Asserting clarity instead of demonstrating it:

- "The reality is simpler"
- "History is unambiguous on this point"
- "History is clear, the metrics are clear, the examples are clear"
- "but none of them is the real story. The real story is..."

## Vague Declaratives

Sentences that announce importance without naming the specific thing. Kill these or replace with the specific thing.

- "The reasons are structural"
- "The implications are significant"
- "This is the deepest problem"
- "The stakes are high"
- "The consequences are real"

## Vague Attributions

Attributing claims to unnamed authorities. If you cannot name the source, you do not have one.

- "Experts argue that..."
- "Industry reports suggest that..."
- "Observers have cited..."
- "Several publications have noted..."

## Grandiose Stakes Inflation

Inflating every argument to world-historical significance. Scale claims to match the actual stakes.

- "This will fundamentally reshape how we think about everything."
- "will define the next era of computing"
- "something entirely new"

## Tech Puffery Superlatives

Empty marketing superlatives in technical writing. Replace with measurable specifications or drop.

| Avoid          | Use instead / specify                                   |
| -------------- | ------------------------------------------------------- |
| blazing-fast   | latency in ms, O(1) time complexity                     |
| rock-solid     | reliable, deterministic, verified                       |
| battle-tested  | tested across [X] workloads, in production since [year] |
| effortless     | automated, single-command                               |
| groundbreaking | new, initial                                            |
| cutting-edge   | name the specific protocol, library version, or model   |

## False Concessions

Simulated humility and rhetorical stagecraft before pivoting to an argument. Drop the setup and state the constraint or tradeoff directly.

- "To be fair,"
- "Admittedly,"
- "Granted,"
- "It is true that..."
- "While it is certainly true that..."
