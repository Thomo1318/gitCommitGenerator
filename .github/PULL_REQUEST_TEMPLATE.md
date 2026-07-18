## Summary

<!-- Provide a high-level description of what this PR accomplishes and why it is being implemented. -->

## Changes Made

<!-- Detail the specific technical changes made in this PR. -->

-
-

<!-- DELETE THIS SECTION IF NOT APPLICABLE -->

## 💥 BREAKING CHANGE 💥

<!-- Describe the breaking change and the migration path for users -->

## Included Changes

<!-- List the main commit headers AND the items from their "Included changes" sections (Matches git-cg output) -->

-

## Related Issues

<!-- Link to the issues this PR addresses. -->

- Closes #
- Resolves #

## SemVer Impact

<!-- Select the appropriate semantic versioning impact of this PR. -->

- [ ] **PATCH** - Bug fixes or internal refactoring with no behavioral changes.
- [ ] **MINOR** - New features added in a backwards-compatible manner.
- [ ] **MAJOR** - Breaking changes that alter existing CLI or API behavior.

**Metadata:**

- **Change Types**: <!-- e.g., feat, fix, docs, refactor, test -->
- **Changelog Groups**: <!-- e.g., Added, Changed, Fixed, Removed -->

## Verification

<!-- Ensure the following checks have been completed before requesting a review. -->

- [ ] Verified `hk` git hooks execute successfully and pass upon committing.
- [ ] New and existing unit tests pass locally (`uv run pytest`).
- [ ] No new linting warnings or typing errors (`uv run ruff check .` / `uv run pyright`).
- [ ] Manual testing performed: <!-- Briefly describe how you tested this locally -->
