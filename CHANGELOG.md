## v0.2.0

### ✨ Features
- ✨ feat(cli): add GUI editor support for commit messages
- ✨ feat(eval): add `FormatMetric` and enforce Tier-1 deterministic format gating
- ✨ feat(eval): add opik test suite execution and triage scripts
- ✨ feat(eval): finalise promptfoo security, native release engine, and IDE boundaries (#121, #123, #124, #136)
- ✨ feat(eval): initialise promptfoo framework for local MTPLX proxy testing (#120, #134)
- ✨ feat(eval): integrate deterministic Opik formatting metrics and evaluation expansion (#118, #124, #128)
- ✨ feat(eval): transition to Opik-managed datasets and test suites (#119, #133)
- ✨ feat(main): add primary language detection to system prompt
- ✨ feat(telemetry): Phase 2 Correctness and Continuity (Opik Phase A) (#115, #125)
- ✨ feat(telemetry): add prompt tracking and feedback scores (#117, #124, #127)
- ✨ feat(telemetry): implement comprehensive runtime tracing (Opik Phase B) (#126)
- 📈 feat(telemetry): implement two-point tracing and evaluation rules (#99)
- 📈 feat(telemetry): map provenance to numeric Opik feedback scores
- 🔗 feat(telemetry): dynamically register and link system prompts to traces

### 🐛 Bug Fixes
- 🐛 fix(detect): prioritise code files over docs in language detection
- 🐛 fix(eval): downgrade promptfoo failures and refine ADR history (#125)
- 🐛 fix(eval): harden mock patching logic and cache generations across evaluation tiers
- 🐛 fix(main): add global telemetry tags to final trace update
- 🐛 fix(main): correct Opik parameter and append global tags to trace update
- 🐛 fix(scripts): enforce explicit CI failure states
- 🐛 fix(scripts): prevent missing expected_output inserts
- 🐛 fix(telemetry): prevent Instructor client serialization crashes in opik tracker
- 🚑 fix(cli): resolve `UnboundLocalError` by fixing `subprocess` import scope shadowing
- 🚑 fix(docs): escape brackets to fix Zensical strict markdown parsing (#139)
- 🚑 fix(inference): monkeypatch `openai_client` to strip `<think>` blocks, fixing Instructor JSON parser
- 🥅 fix(cli): add commit recovery feature after hook failures
- 🥅 fix(sentry): add Sentry SDK for crash reporting

### 🏗️ Refactoring
- ♻️ refactor(eval): migrate dataset compiler to use Opik API directly
- ♻️ refactor(telemetry): update telemetry model and legacy state parsing
- 🏷️ refactor(telemetry): isolate git diff extraction into tracked span
- 🔥 refactor(test_data): delete static opik_dataset.jsonl
- 🚨 refactor(cli): resolve ruff B904 lint error for exception handling in main.py
- 🚨 refactor(telemetry): resolve ruff SIM105 lint error by utilizing contextlib.suppress

### 📝 Documentation
- 🍱 chore(docs): add git-cg tool screenshot
- 📝 docs(TODO): append incremental generation and PR description features
- 📝 docs(adr): add ADR 0012 (CodeRabbit/Qodo) and update ADRs 0002 and 0011
- 📝 docs(adr): document LLMOps stack and review request
- 📝 docs(adr): restore historical deviation rationale and add version history
- 📝 docs(adr): update checklist and hook description
- 📝 docs(architecture): add Opik telemetry architecture docs
- 📝 docs(config): add Codecov configuration file
- 📝 docs(docs): remove outdated architecture review docs
- 📝 docs(feature-flags): add Sentry feature flag provider analysis
- 📝 docs(llmops_comparison): add LLMOps tooling comparison report (#15)
- 📝 docs(main): expand generate_commit_message docstring with kwargs
- 📝 docs(readme): update README TOC and TODO tasks
- 📝 docs(readme): update readme architecture and GUI editor docs
- 📝 docs(setup): clarify secrets orchestration and IDE FIFO warning
- 📝 docs(telemetry): add Opik telemetry architecture docs
- 📝 docs(telemetry): attach rich interactive tags and repository metadata to traces
- 📝 docs(todo): add research and library backlog to TODO
- 📝 docs(viz): update vizvibe trajectory diagram
- 📝 docs: fix broken shields.io license badge

### 🔐 Security & Secrets
- ➖ remove(security): remove Snyk and adopt native CodeQL and Dependabot
- 🔐 chore(secrets): skip 1Password fetch if API key is set
- 🦺 docs(security): formalize IDE boundaries and 1Password `.env` mounting protocols (ADR-0013)
- 🦺 fix(security): add path traversal prevention and input validation
- 🦺 fix(validation): add deterministic score card checks

### 🔧 Chores & Internal
- ➕ build(deps): add sentry-sdk to project dependencies
- 👷 ci(workflow): add CI workflow with tests and coverage upload
- 💚 ci(codecov): integrate Codecov reporting and add workflow concurrency limits
- 🔊 chore(observability): add prompt sync error logging (#124, #137)
- 🔧 chore(agents): add agents config and remove scratch docs
- 🔧 chore(config): fix pyproject.toml table ordering and clean up mise.toml
- 🔧 chore(hooks): add Snyk and Codecov to pre-commit hooks
- 🔧 chore(hooks): add commit-msg hook for telemetry
- 🔧 chore: append global telemetry tags and update backlog (#117)
- 🔨 chore(scripts): refactor opik eval rule setup
- 🙈 chore(gitignore): update gitignore for agent artifacts

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
- 💥 feat(api)!: change AI response schema to CommitPlan
- 💥 feat(release)!: add machine-readable trailer parsing
- 💥 feat(api)!: remove build_generation_messages directive parameters
- 💥 feat(engine)!: change default engine to mtplx
- 🔐 chore(secrets)!: add 1Password secrets resolution
