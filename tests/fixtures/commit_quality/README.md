# Commit presentation quality fixtures (Issue #204 · Slice 3)

Freeze of pure presentation helpers against the production SOP matrix pin:

* `derive_trailer_priors`
* `classify_diff_class` / `presentation_constraints`
* `semver_presentation_ceiling` / `dominant_presentation_cc_type`
* `min_included_change_bullets`
* `normalize_scope`
* `apply_presentation_overlay` (presentation fields only; ranked identity locked)

| File | Role |
| --- | --- |
| `corpus.json` | P9-G1–G7 + TIP-G1–G12 inputs, must_present / must_not_present, SOP SHA-256 pin |
| `goldens.json` | Expected priors, constraints, ceilings, overlay snapshots per row |
| `README.md` | Regeneration rules |

## Rules

1. **No live LLM** in `tests/test_commit_quality_corpus.py`.
2. **SOP drift gate:** tests fail loudly when `sop_matrix_sha256` does not equal the live matrix hash.
3. **Do not edit goldens to make tests pass** during unrelated work. Re-baseline only with reviewer sign-off after an intentional presentation-policy or SOP change.
4. Ranked `intent_id` / matrix gitmoji remain identity-locked; presentation may change type/SemVer/changelog/scope only.
5. Shared factories for new 7.30 tests live in `tests/conftest.py`. Do not refactor legacy per-module helpers in this slice.

## Regenerate (reviewer-approved only)

Re-run the approved generator used for Slice 3, or intentionally update
`goldens.json` after reviewing presentation deltas. Never silent-rebase the
SOP hash without a deliberate matrix change review.

Corpus rows are law from issue #204 path tables. Path spellings such as
`docs/ADRs/ADR-0163-...` are pinned even when the on-disk ADR slug differs.
