## v0.2.0

### ✨ Features
- ✨ feat(eval): finalise promptfoo security, native release engine, and IDE boundaries (#121, #123, #124, #136)
- ✨ feat(eval): initialise promptfoo framework for local MTPLX proxy testing (#120, #134)
- ✨ feat(eval): transition to Opik-managed datasets and test suites (#119, #133)
- ✨ feat(eval): integrate deterministic Opik formatting metrics and evaluation expansion (#118, #124, #128)
- ✨ feat(telemetry): add prompt tracking and feedback scores (#117, #124, #127)
- ✨ feat(telemetry): implement comprehensive runtime tracing (Opik Phase B) (#126)
- ✨ feat(telemetry): Phase 2 Correctness and Continuity (Opik Phase A) (#115, #125)
- 📈 feat(telemetry): implement two-point tracing and evaluation rules (#99)
- ✨ feat(cli): add GUI editor support for commit messages
- ✨ feat(main): add primary language detection to system prompt

### 🐛 Bug Fixes
- 🐛 fix(eval): downgrade promptfoo failures and refine ADR history (#125)
- 🐛 fix(detect): prioritise code files over docs in language detection
- 🥅 fix(sentry): add Sentry SDK for crash reporting
- 🚑 fix(docs): escape brackets to fix Zensical strict markdown parsing (#139)

### 📝 Documentation
- 📝 docs(feature-flags): add Sentry feature flag provider analysis
- 📝 docs(llmops_comparison): add LLMOps tooling comparison report (#15)
- 📝 docs(architecture): add Opik telemetry architecture docs
- 📝 docs(todo): add research and library backlog to TODO
- 📝 docs(readme): update readme architecture and GUI editor docs
- 📝 docs(telemetry): add Opik telemetry architecture docs
- 📝 docs: fix broken shields.io license badge

### 🔐 Security & Secrets
- 🦺 docs(security): formalize IDE boundaries and 1Password `.env` mounting protocols (ADR-0013)
- 🦺 fix(security): add path traversal prevention and input validation

### 🔧 Chores & Internal
- 🔊 chore(observability): add prompt sync error logging (#124, #137)
- 🔧 chore: append global telemetry tags and update backlog (#117)
- 🍱 chore(docs): add git-cg tool screenshot
- 🔧 chore(agents): add agents config and remove scratch docs

## v0.1.0

### ✨ Features
- ✨ feat(cli): implement plain text commit output and stabilise CLI interface (#96)
- ✨ feat(regeneration): implement selective delta rendering and invariant contract enforcement (#95)
- ✨ feat(regeneration): add prompt reauthorisation, bounded directives, and 1Password fixes (#92)
- ✨ feat(tui): enable multiple issue references in review (#84)
- ✨ feat(tui): add structured issue references to interactive review flow (#81)
- ✨ feat(tui): Gum TUI integration, docs infrastructure, and commit refactor (#78)
- ✨ feat(sop): add deterministic intent metadata to gitmoji matrix
- ✨ feat(hooks): add linting and commit hooks
- 🎉 feat: initial commit of gitCommitGenerator `git-cg`

### 🐛 Bug Fixes
- 🐛 fix(core): address automated review findings and finalise release formatting (#97)
- 🥅 fix(gitops): Add graceful fallback for invalid intents
- 🐛 fix(secrets): resolve 'Vaults' object has no attribute 'list_all' in 1Password SDK

### 🏗️ Refactoring
- 🏗️ refactor(regeneration): add semantic contract resolution and plan anchoring (#94)
- 🏗️ refactor(semantic): canonicalise SOP semantics and explicit constraints (#91)
- 🏗️ refactor(core): implement deterministic diff signal extraction and intent ranking
- 🚚 refactor(core): centralise SOP loading for portable global hook support
- ♻️ refactor(main): extract system prompt builder and add logging config
- ♻️ refactor(main): restructure imports and load env early
- 🏗️ refactor(release): implement multi-strategy version injection
- ♻️ refactor(main): update main.py and add ranker tests

### 📝 Documentation
- 📝 feat(docs): add interactive table sorting to Zensical site (#93)
- 📝 docs(adr): fix unescaped brackets in ADR-0009 and update Zensical navigation
- 📝 docs(readme): update README with new architecture and features
- 📝 docs(readme): add badges and format tables in README
- 📝 docs(project): document 1Password SDK migration and roadmap
- 📝 docs(todo): add deferred architecture ideas and parametrise env script
- 📝 docs(vizvibe): add project roadmap visualization
- 📝 docs(readme): extract TODO list and update Python version
- 📝 docs(adr): add Refinement 3 for multi-issue reference review
- 📝 docs(adr): add ADR refinement 2 for issue reference metadata
- 📝 docs(todo): add multi-turn workflow task
- 📝 docs(adr): add initial architecture decision records

### 🔐 Security & Secrets
- 🔐 chore(secrets)!: add 1Password secrets resolution
- 🔐 chore(core): refactor secrets resolution with async caching
- 🔐 chore(secrets): migrate to betterleaks secret scanner
- 🔐 chore(config): Add fnox and age for secrets orchestration
- 🔐 fix(security): add TruffleHog scanning and secrets protection

### 🔧 Chores & Internal
- ✅ test(tests): add comprehensive test suite for intent, main, ranker, and sop modules
- 🔧 chore(docs): update vizvibe and include missed docs fixes
- 🔧 chore(mise): add logging env vars and secret scanner tools
- 🔧 chore(hooks): update prepare-commit-msg hook for debugging
- 🔧 chore(hk): migrate from pre-commit to hk for git hooks
- 🔊 chore(logging): set Opik console logging level to INFO
- 🔐 chore(setup): add installation script and environment configuration

### 💥 Breaking Changes
- ♻️ refactor(models)!: replace flat Commit with hierarchical CommitPlan model
- 🔐 chore(secrets)!: add 1Password secrets resolution
