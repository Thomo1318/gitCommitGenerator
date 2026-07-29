## 🎯 Summary

<!-- Provide a high-level description of what this PR accomplishes and why it is being implemented. Link primary issue/ADR. Call out feature flags / compatibility boundaries. -->

## 🗺️ Architecture / Flow

<!-- Optional. Include a Mermaid diagram (or more if warranted) when this PR introduces or changes
     a multi-step flow, feature-flagged path, or external boundary.
     Delete this entire section if N/A.
     Prefer graph TD, a short legend, and clear shapes:
     module/path, decision, external, state store. Refer to "$HOME/dev/activeProjects/gitCommitGenerator/docs/mermaid_guide.md" and "$HOME/dev/activeProjects/gitCommitGenerator/docs/mermaidLibrary.md" for guidance on types of diagrams, style, syntax, and an example library. -->

## 🛠️ Changes Made

<!-- Detail the specific technical changes made in this PR. Group by subsystem/module. Prefer bullets over commit essays. -->

-
-

<!-- DELETE THIS SECTION IF NOT APPLICABLE -->

## 💥 BREAKING CHANGE 💥

<!-- Delete if N/A. Describe the breaking change and the migration path -->

## 📦 Included Changes

<!-- List the main commit headers AND the items from their "Included changes" sections (Matches git-cg output) -->

-

## 🔗 Related Issues

- Closes #
- Resolves #
- <!-- Parent epic / milestone / deferred follow-ups -->

## 📊 SemVer Impact

<!-- Select the appropriate semantic versioning impact of this PR. -->

- [ ] **PATCH** - Bug fixes or internal refactoring with no behavioural changes.
- [ ] **MINOR** - New features added in a backwards-compatible manner.
- [ ] **MAJOR** - Breaking changes that alter existing CLI or API behavior.

**Metadata:**

- **Change Types**: <!-- e.g., feat, fix, docs, refactor, test -->
- **Changelog Groups**: <!-- e.g., Added, Changed, Fixed, Removed -->

## ⚠️ Risks / Things to Watch

<!-- Optional but recommended for core/security/telemetry PRs. -->

## ✅ Verification

<!-- Ensure the following checks have been completed before requesting a review. -->

- [ ] Verified `hk` git hooks execute successfully and pass upon committing.
- [ ] New and existing unit tests pass locally (`uv run pytest`).
- [ ] No new linting warnings or typing errors (`uv run ruff check .` / `uv run pyright`).
- [ ] Manual testing performed: <!-- Briefly describe how you tested this locally -->
