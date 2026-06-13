## v0.1.0

### ✨ Features
- ✨ feat(cli): implement plain text commit output and stabilise CLI interface (#96)
- ✨ feat(regeneration): implement selective delta rendering and invariant contract enforcement (#95)
- ✨ feat(regeneration): add prompt reauthorisation, bounded directives, and 1Password fixes (#92)
- ✨ feat(tui): enable multiple issue references in review (#84)
- ✨ feat(tui): add structured issue references to interactive review flow (#81)
- ✨ feat(sop): add deterministic intent metadata to gitmoji matrix
- ✨ feat(hooks): add linting and commit hooks
- feat: Gum TUI integration, docs infrastructure, and commit refactor (#78)
- feat: initial commit of gitCommitGenerator

### 🐛 Bug Fixes
- 🐛 fix(core): address automated review findings and finalize release formatting (#97)
- 🥅 fix(gitops): Add graceful fallback for invalid intents
- fix(secrets): resolve 'Vaults' object has no attribute 'list_all' in 1Password SDK

### 🏗️ Refactoring
- 🏗️ refactor(regeneration): add semantic contract resolution and plan anchoring (#94)
- 🏗️ refactor(semantic): canonicalise SOP semantics and explicit constraints (#91)
- 🏗️ refactor(core): implement deterministic diff signal extraction and intent ranking
- 🚚 refactor(core): centralize SOP loading for portable global hook support
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
- 📝 docs(todo): add deferred architecture ideas and parametrize env script
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
- 🔒️ fix(security): add TruffleHog scanning and secrets protection

### 🔧 Chores & Internal
- ✅ test(tests): add comprehensive test suite for intent, main, ranker, and sop modules
- chore: update vizvibe and include missed docs fixes
- 🔧 chore(mise): add logging env vars and secret scanner tools
- 🔧 chore(hooks): update prepare-commit-msg hook for debugging
- chore: migrate from pre-commit to hk for git hooks
- 🔊 chore(logging): set Opik console logging level to INFO
- 🔐 chore(setup): add installation script and environment configuration

### 💥 Breaking Changes
- ♻️ refactor(models)!: replace flat Commit with hierarchical CommitPlan model
- 🔐 chore(secrets)!: add 1Password secrets resolution

