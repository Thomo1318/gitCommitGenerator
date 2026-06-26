## v0.2.0

### ✨ Features
- ✨ feat(cli): add GUI editor support for commit messages
- ✨ feat(eval): add `FormatMetric` and enforce Tier-1 deterministic format gating (#118, #128)
- ✨ feat(eval): add opik test suite execution and triage scripts (#119, #133)
- ✨ feat(eval): finalise promptfoo security, native release engine, and IDE boundaries (#121, #123, #124, #136)
- ✨ feat(eval): initialise promptfoo framework for local MTPLX proxy testing (#120, #134)
- ✨ feat(eval): integrate deterministic Opik formatting metrics and evaluation expansion (#118, #124, #128)
- ✨ feat(eval): transition to Opik-managed datasets and test suites (#119, #133)
- ✨ feat(main): add primary language detection to system prompt
- ✨ feat(telemetry): Phase 2 Correctness and Continuity (Opik Phase A) (#115, #125)
- ✨ feat(telemetry): add prompt tracking and feedback scores (#117, #124, #127)
- ✨ feat(telemetry): implement comprehensive runtime tracing (Opik Phase B) (#126)
- 📈 feat(telemetry): implement two-point tracing and evaluation rules (#99)
- 📈 feat(telemetry): map provenance to numeric Opik feedback scores (#127)
- 🔗 feat(telemetry): dynamically register and link system prompts to traces (#127)

### 🐛 Bug Fixes
- 🐛 fix(detect): prioritise code files over docs in language detection
- 🐛 fix(eval): downgrade promptfoo failures and refine ADR history (#125)
- 🐛 fix(eval): harden mock patching logic and cache generations across evaluation tiers (#118, #128)
- 🐛 fix(main): add global telemetry tags to final trace update
- 🐛 fix(main): correct Opik parameter and append global tags to trace update (#127)
- 🐛 fix(scripts): enforce explicit CI failure states (#119, #133)
- 🐛 fix(scripts): prevent missing expected_output inserts (#119, #133)
- 🐛 fix(telemetry): prevent Instructor client serialization crashes in opik tracker (#126)
- 🚑 fix(cli): resolve `UnboundLocalError` by fixing `subprocess` import scope shadowing
- 🚑 fix(docs): escape brackets to fix Zensical strict markdown parsing (#139)
- 🚑 fix(inference): monkeypatch `openai_client` to strip `<think>` blocks, fixing Instructor JSON parser
- 🥅 fix(cli): add commit recovery feature after hook failures
- 🥅 fix(sentry): add Sentry SDK for crash reporting

### 🏗️ Refactoring
- ♻️ refactor(eval): migrate dataset compiler to use Opik API directly (#119, #133)
- ♻️ refactor(telemetry): update telemetry model and legacy state parsing (#125)
- 🏷️ refactor(telemetry): isolate git diff extraction into tracked span (#126)
- 🔥 refactor(test_data): delete static opik_dataset.jsonl (#119, #133)
- 🚨 refactor(cli): resolve ruff B904 lint error for exception handling in main.py
- 🚨 refactor(telemetry): resolve ruff SIM105 lint error by utilizing contextlib.suppress

### 📝 Documentation
- 🍱 chore(docs): add git-cg tool screenshot
- 📝 docs(TODO): append incremental generation and PR description features
- 📝 docs(adr): add ADR 0012 (CodeRabbit/Qodo) and update ADRs 0002 and 0011 (#118, #128)
- 📝 docs(adr): document LLMOps stack and review request
- 📝 docs(adr): restore historical deviation rationale and add version history
- 📝 docs(adr): update checklist and hook description
- 📝 docs(architecture): add Opik telemetry architecture docs
- 📝 docs(config): add Codecov configuration file
- 📝 docs(docs): remove outdated architecture review docs
- 📝 docs(feature-flags): add Sentry feature flag provider analysis
- 📝 docs(llmops_comparison): add LLMOps tooling comparison report (#15)
- 📝 docs(main): expand generate_commit_message docstring with kwargs (#127)
- 📝 docs(readme): update README TOC and TODO tasks
- 📝 docs(readme): update readme architecture and GUI editor docs
- 📝 docs(setup): clarify secrets orchestration and IDE FIFO warning
- 📝 docs(telemetry): add Opik telemetry architecture docs
- 📝 docs(telemetry): attach rich interactive tags and repository metadata to traces (#126)
- 📝 docs(todo): add research and library backlog to TODO
- 📝 docs(viz): update vizvibe trajectory diagram (#119, #133)
- 📝 docs: fix broken shields.io license badge

### 🔐 Security & Secrets
- ➖ remove(security): remove Snyk and adopt native CodeQL and Dependabot (#118, #128)
- 🔐 chore(secrets): skip 1Password fetch if API key is set
- 🦺 docs(security): formalize IDE boundaries and 1Password `.env` mounting protocols (ADR-0013)
- 🦺 fix(security): add path traversal prevention and input validation
- 🦺 fix(validation): add deterministic score card checks

### 🔧 Chores & Internal
- ➕ build(deps): add sentry-sdk to project dependencies
- 👷 ci(workflow): add CI workflow with tests and coverage upload
- 💚 ci(codecov): integrate Codecov reporting and add workflow concurrency limits (#118, #128)
- 🔊 chore(observability): add prompt sync error logging (#124, #137)
- 🔧 chore(agents): add agents config and remove scratch docs
- 🔧 chore(config): fix pyproject.toml table ordering and clean up mise.toml (#118, #128)
- 🔧 chore(hooks): add Snyk and Codecov to pre-commit hooks
- 🔧 chore(hooks): add commit-msg hook for telemetry
- 🔧 chore: append global telemetry tags and update backlog (#117)
- 🔨 chore(scripts): refactor opik eval rule setup
- 🙈 chore(gitignore): update gitignore for agent artifacts

## v0.1.0

### ✨ Features
- ✨ feat(cli): implement plain text commit output and stabilise CLI interface (#96)
- ✨ feat(features): document Multi-Intent Split Detection and trailers
- ✨ feat(hooks): add linting and commit hooks
- ✨ feat(intent): Add diff normalization and metrics collection
- ✨ feat(intent): add adds_public_api signal marker
- ✨ feat(regeneration): add prompt reauthorisation, bounded directives, and 1Password fixes (#92)
- ✨ feat(regeneration): implement selective delta rendering and invariant contract enforcement (#95)
- ✨ feat(sop): add deterministic intent metadata to gitmoji matrix
- ✨ feat(tui): Gum TUI integration, docs infrastructure, and commit refactor (#78)
- ✨ feat(tui): add structured issue references to interactive review flow (#81)
- ✨ feat(tui): enable multiple issue references in review (#84)
- ✨ feat(workflow): migrate TODO tasks to GitHub Issues tracker
- 🎉 feat: initial commit of gitCommitGenerator `git-cg`
- 👔 feat(models): enhance CommitIntent canonicalisation for all fields (#91)
- 📝 feat(docs): add interactive table sorting to Zensical site (#93)

### 🐛 Bug Fixes
- 🐛 fix(core): address automated review findings and finalise release formatting (#97)
- 🐛 fix(secrets): resolve 'Vaults' object has no attribute 'list_all' in 1Password SDK
- 🚑 fix(models): fix newline escaping in body summary
- 🥅 fix(cli): fix exception handling syntax (#95)
- 🥅 fix(core): add process polling and error recovery
- 🥅 fix(docs): add error handling for missing Tablesort (#94)
- 🥅 fix(gitops): Add graceful fallback for invalid intents
- 🥅 fix(main): add exception handling for AI generation (#78)
- 🥅 fix(main): add parallel_tool_calls config

### 🏗️ Refactoring
- ♻️ refactor(intent): improve test path detection patterns
- ♻️ refactor(main): extract secret resolution to dedicated module
- ♻️ refactor(main): extract system prompt builder and add logging config
- ♻️ refactor(main): restructure imports and load env early
- ♻️ refactor(main): update main.py and add ranker tests
- 🏗️ refactor(architecture): document Intent Ranker and SOP loader components
- 🏗️ refactor(core): implement deterministic diff signal extraction and intent ranking
- 🏗️ refactor(gitops): Improve candidate selection logic
- 🏗️ refactor(regeneration): add semantic contract resolution and plan anchoring (#94)
- 🏗️ refactor(release): extract changelog grouping logic and add tests (#96)
- 🏗️ refactor(release): implement multi-strategy version injection
- 🏗️ refactor(secrets): enforce allowlisting for 1Password environment exports (#92)
- 🏗️ refactor(semantic): canonicalise SOP semantics and explicit constraints (#91)
- 🔥 refactor(txt): delete temporary scratch file
- 🚚 refactor(core): centralise SOP loading for portable global hook support

### 📝 Documentation
- 🎨 style(docs): cleanup docstrings and CSS (#94)
- 💄 style(docs): add table sort indicator styles (#93, #94)
- 💬 style(main): clarify interactive mode unavailable message (#78)
- 📝 docs(adr): add ADR refinement 2 for issue reference metadata
- 📝 docs(adr): add Refinement 3 for multi-issue reference review
- 📝 docs(adr): add initial architecture decision records
- 📝 docs(adr): escape link reference brackets in ADR-0009 to fix build
- 📝 docs(adr): fix unescaped brackets in ADR-0009 and update Zensical navigation
- 📝 docs(nav): add ADR-0009 to Zensical sidebar navigation config
- 📝 docs(project): document 1Password SDK migration and roadmap
- 📝 docs(readme): add badges and format tables in README
- 📝 docs(readme): correct typos and update COMMIT_EDITMSG path documentation (#92)
- 📝 docs(readme): document configuration and secrets setup
- 📝 docs(readme): document regeneration guidance actions (#92)
- 📝 docs(readme): extract TODO list and update Python version
- 📝 docs(readme): update README with new architecture and features
- 📝 docs(todo): add deferred architecture ideas and parametrise env script
- 📝 docs(todo): add multi-turn workflow task
- 📝 docs(todo): clean up TODO.md formatting
- 📝 docs(todo): cleanup completed TODO items
- 📝 docs(todo): reorganize TODO into structured issue sections
- 📝 docs(todo): update TODO with LLM evaluation system
- 📝 docs(vizvibe): add project roadmap visualization

### 🔐 Security & Secrets
- 🔐 chore(config): Add fnox and age for secrets orchestration
- 🔐 chore(core): refactor secrets resolution with async caching
- 🔐 chore(secrets): configure gitleaks ignore rules
- 🔐 chore(secrets): document fnox and age secrets orchestration
- 🔐 chore(secrets): migrate to betterleaks secret scanner
- 🔐 chore(setup): add installation script and environment configuration
- 🔐 fix(security): add TruffleHog scanning and secrets protection
- 🦺 fix(main): add tty availability checks (#78)

### 🔧 Chores & Internal
- ✅ test(interaction): add regeneration guidance tests (#92)
- ✅ test(ranker): add ranker preference test cases
- ✅ test(regeneration): add tests for contract enforcement (#95)
- ✅ test(scripts): add evaluation and test generation scripts
- ✅ test(tests): add comprehensive test suite for intent, main, ranker, and sop modules
- ✅ test(tests): add tests for constraint derivation and canonicalisation (#91)
- ➖ build(mise): remove unused mlx dependency
- 👷 ci(config): Add hatchling build system configuration
- 👷 ci(docs): add GitHub Pages deployment workflow (#78)
- 🔊 chore(logging): set Opik console logging level to INFO
- 🔧 chore(ci): use strict mode in docs build workflow (#78)
- 🔧 chore(config): add pytest configuration with coverage
- 🔧 chore(config): update .gitignore and Brewfile dependencies
- 🔧 chore(deps): add git, mlx, and python-dotenv dependencies
- 🔧 chore(docs): update vizvibe and include missed docs fixes
- 🔧 chore(hk): migrate from pre-commit to hk for git hooks
- 🔧 chore(hooks): update prepare-commit-msg hook for debugging
- 🔧 chore(mise): add gum to toolchain and update gitignore (#78)
- 🔧 chore(mise): add logging env vars and secret scanner tools
- 🔧 chore(mise): remove git tool pinning from mise.toml
- 🔨 chore(ci): add automated documentation hook to hk and justfile (#96)
- 🔨 chore(install): add automated installation pipeline script
- 🙈 chore(gitignore): add DEV_WORKFLOW.md to gitignore
- 🙈 chore(gitignore): update ADR directory pattern (#78)
- 🙈 chore: remove agentops.log from gitignore

### 💥 Breaking Changes
- ♻️ refactor(models)!: replace flat Commit with hierarchical CommitPlan model
- 💥 feat(api)!: change AI response schema to CommitPlan
- 💥 feat(api)!: remove build_generation_messages directive parameters
- 💥 feat(engine)!: change default engine to mtplx
- 💥 feat(release)!: add machine-readable trailer parsing
- 🔐 chore(secrets)!: add 1Password secrets resolution
