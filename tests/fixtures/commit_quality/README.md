# Commit presentation quality fixtures (Issue #204 · Slice 3 + Slice 9)

Freeze of pure presentation helpers against the production SOP matrix pin:

* `derive_trailer_priors`
* `classify_diff_class` / `presentation_constraints`
* `semver_presentation_ceiling` / `dominant_presentation_cc_type`
* `min_included_change_bullets`
* `normalize_scope`
* `apply_presentation_overlay` (presentation fields only; ranked identity locked)
* `evaluate_presentation_gates` (Slice 9 ordered A-N characterisation)

| File | Role |
| --- | --- |
| `corpus.json` | P9-G1–G7 + TIP-G1–G17 + S9-E/S9-H inputs, must_present / must_not_present, SOP SHA-256 pin, `eval_harness.letter_map` A-N |
| `goldens.json` | Expected priors, constraints, ceilings, overlay snapshots per row |
| `eval_an.json` | Slice 9 legal/illegal candidate plans for ordered gate scoring |
| `README.md` | Regeneration rules |

## Slice 9 letter map

| Letter | Corpus id | Theme |
| --- | --- | --- |
| A | TIP-G2 | fixtures README authority prose → test/NONE; reject security |
| B | TIP-G3 | ADR + index → docs(adr)/NONE; reject chore/Security |
| C | TIP-G4 | usage + CHANGELOG → docs/NONE; reject runtime fix |
| D | TIP-G1 | multi-test + claim tags → test inventory |
| E | S9-E | graph_unavailable/redaction docs remain docs |
| F | TIP-G5 | main+telemetry+sentry correctness → fix/PATCH |
| G | TIP-G6 | tests + ADR rename + docs retargets |
| H | S9-H | no-gpg-sign fixture must surface signing inventory |
| I | TIP-G7 | scoped-history producer correctness |
| J | TIP-G8 | scoped-history tests + ADR claim-lock |
| K | TIP-G9 | wording-only directive drop + consider ban |
| L | TIP-G10 | semantic free-harvest hub/complex |
| M | TIP-G11 | preflight carry-through elevation |
| N | TIP-G12 | ADR mermaid + usage Related link |
| — | TIP-G13 | telemetry schema/lifecycle → feat/MINOR |
| — | TIP-G14 | pure evaluator forbids enforce/lift/mutate |
| — | TIP-G15 | Sentry reporter → fix/PATCH + named event |
| — | TIP-G16 | main wiring module scope; reject Context/Changes |
| — | TIP-G17 | tests+plan primary test; no attribution bleed |

Gate order (first failure wins):

`path_class → type → semver → no_hallucination → inventory → craft`

## Rules

1. **No live LLM** in `tests/test_commit_quality_corpus.py`.
2. **SOP drift gate:** tests fail loudly when `sop_matrix_sha256` does not equal the live matrix hash.
3. **Do not edit goldens to make tests pass** during unrelated work. Re-baseline only with reviewer sign-off after an intentional presentation-policy or SOP change.
4. Ranked `intent_id` / matrix gitmoji remain identity-locked; presentation may change type/SemVer/changelog/scope only.
5. Slice 9 candidates in `eval_an.json` use `construct=True` plans so illegal negative fixtures can bypass matrix validation while pure gates still reject them.
6. Shared factories for new 7.30 tests live in `tests/conftest.py`. Do not refactor legacy per-module helpers in this slice.

## Regenerate (reviewer-approved only)

Re-run the approved generator used for Slice 3/9, or intentionally update
`goldens.json` / `eval_an.json` after reviewing presentation deltas. Never silent-rebase the
SOP hash without a deliberate matrix change review.

Corpus rows are law from issue #204 path tables. Path spellings such as
`docs/ADRs/ADR-0163-...` are pinned even when the on-disk ADR slug differs.
