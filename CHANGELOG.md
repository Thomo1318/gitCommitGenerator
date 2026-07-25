# Changelog

## Unreleased

## v0.6.0

### ✨ Features

- ✨ feat(semantic): integrate Phase 7 telemetry and context verification (#162)
- 📈 feat(telemetry): add optional `test_gaps_count` and Phase 7 context fields (#162)
- ♻️ refactor(semantic): add `SemanticDiffSummary` / `RiskAssessment` context models (#162)

### 🐛 Bug Fixes & Refactors

- 🥅 fix(git_cg): guard int telemetry counts against bool subclass (#162)
- 🥅 fix(git_cg): bound graph-stage fallback reasons (#162)
- 🥅 fix(semantic): graph product fail-open and telemetry normalisation (#162)
- 🥅 fix(graph_context): preserve partial query results on failure (#162)
- ⚡️ perf(cli): isolate semantic module imports on flag-off (#162)
- 🔒️ fix(deps): raise python-dotenv floor to >=1.2.2 (#177)
- 🐛 fix(fingerprints): catch missing package metadata errors (#177)

### 📝 Documentation

- 📝 docs(usage): document semantic context, fail-open summary, and telemetry (#162)
- 📝 docs(dev-guide): Phase 7 / 7.5 ownership and measurement notes (#162)
- 📝 docs(adr): add ADR-0014 for fnox canonical secrets (#177)
- 📝 docs(changelog): flatten v0.5.0 changelog entries

### ✅ Tests

- ✅ test(semantic): context, graph mapping, before/after fixtures, fallbacks (#162)
- ✅ test(telemetry): bool normalisation, malformed preflight counts, gaps count (#162)
- ✅ test(docs): development docs assertion alignment (#162)
- ✅ test(tests): coverage and error-handling improvements (#177)

### 🔧 Chores & Internal

- 🔧 chore(config): AI review tool Python 3.14 syntax config (#162)
- 🔧 chore(config): coverage layout / gitignore hygiene (#162)
- ⬆️ build(deps): bump pytest, code-review-graph; raise floors / bounds (#177)
- 📌 build(ci): pin CI actions to full commit SHAs (#177)
- 🔐 chore(dev-guide): record WP6 deferrals for pins (#177)

### 🔒️ Security / Dependencies

- 🔒️ fix(deps): raise python-dotenv floor for GHSA-mf9w-mj56-hr94 / CVE-2026-28684 (#177)
- 👷 ci(deps): stage GitHub Actions majors with full SHA pins (#177)

## v0.5.0

### ✨ Features

- ✨ feat(main): wire fingerprint enrichment into shared rank pass (#161)
- ✨ feat(telemetry): add preflight_* fields with skipped defaults (#161)
- ✨ feat(main): resolve contract before LLM with shared rank pass (#161)
- ✨ feat(regeneration): lock first-pass contract to top ranked intent (#161)
- ✨ feat(models): reject unknown LLM intent ids at schema boundary (#161)
- ✨ feat(intent): add gated closed-vocabulary marker enrichment (#161)

### 🐛 Bug Fixes & Refactors

- 🐛 fix(prompt_diff): prevent prompt diff packing length overflow (#161)
- ♻️ refactor(git_cg): centralise helpers and harden constraints (#161)
- 🚨 refactor(config): reorder imports to fix ruff E402 warnings (#161)
- 🐛 fix(telemetry): resolve final_commit_plan intent_id from matrix (#161)
- 🐛 fix(main): stop hard-slicing analysis diff before ranking (#161)

### 📝 Documentation

- 🎨 style(docs): normalise CodeRabbit docstring indentation (#161)
- 📝 Add docstrings to `feat/161-intent-engine-preservation` (#161)
- 📝 CodeRabbit Chat: Generate Unit Tests for PR Changes (#161)
- 📝 docs(fixtures): intent characterisation README (#161)
- 📝 docs: record Phase 3 vs 0.5/7/11 ownership for intent engine (#161)
- 📝 docs: document branch issue auto-detection for git-cg (#161)

### ✅ Tests

- ✅ test(tests): add markdown parser helper and fallback tests (#161)
- ✅ test(tests): align tests with refactored logic (#161)
- ✅ test(telemetry): assert trailer-authoritative changelog_group (#161)
- ✅ test(intent): derive characterisation case IDs from corpus (#161)
- ✅ test: harden Phase 3 edge coverage and fixture docs (#161)
- ✅ test(regeneration): enforce/empty-matrix/allowed-row cases (#161)
- ✅ test(models): breaking-description and empty-matrix paths (#161)
- ✅ test(main): pack_prompt_diff boundary cases (#161)
- ✅ test(main): unit tests for semantic enrichment builder (#161)
- ✅ test(telemetry): matrix lookup and reverse-parse intent resolution (#161)
- ✅ test(main): prompt packing boundary and rank independence (#161)
- ✅ test(telemetry): defaults, persistence, legacy backfill, redaction (#161)
- ✅ test(main): prompt includes locked contract text (#161)
- ✅ test(regeneration): first-pass and constraint contract cases (#161)
- ✅ test(models): strict reject vs internal coerce (#161)
- ✅ test(intent): cover flag-off stability and enrichment filters (#161)
- ✅ test(intent): freeze characterisation corpus for Phase 3 (#161)

### 🎨 Style

- 🎨 style(intent): normalise docstring indentation (#161)
- 🎨 style(main): normalise docstring indentation (#161)
- 🎨 style(models): normalise docstring indentation (#161)
- 🎨 style(regeneration): normalise docstring indentation (#161)
- 🎨 style(telemetry): normalise docstring indentation (#161)
- 🎨 style(tests): normalise enrichment and contract docstrings (#161)

### 🔧 Chores & Internal

- 🔧 chore(ruff): add known package lists (#161)

## v0.4.0

### ✨ Features

- ✨ feat(core): add Phase 1 semantic producers behind dark-launch (#159)
- ✨ feat(fingerprints): implement shape/code/text algebra and truth table (#160)
- ✨ feat(telemetry): dark-launch fingerprint metrics on commit path (#160)
- ✨ feat(main): wire HEAD/index fingerprint compare behind semantic flag (#160)
- ✨ feat(cli): add lmlx engine and evals benchmark command (#5)
- ✨ feat(evals): add evaluation and benchmarking suite (#143)
- ✨ feat(shadow_workspace): add isolated Git workspace for safe operations (#147)
- ✨ feat(git_index): add HEAD blob readers for fingerprint baselines (#160)
- ✨ feat(similarity): add rapidfuzz body-similarity helper (#160)
- 📈 feat(telemetry): record parser and graph producer metrics (#159)
- 📈 feat(telemetry): label final_commit_plan as commit_plan_partial_v1 (#157)
- 📈 feat(telemetry): attach Phase 1 metrics on final Opik trace (#159)

### 🐛 Bug Fixes & Refactors

- 🏗️ refactor(agents): standardise AI agent tooling and MCP configs (#145)
- 🐛 fix(semantic): harden parse serialisation and fp hashing (#160)
- 🐛 fix(telemetry): harden redact_payload with fail-closed checks (#148)
- 🐛 fix(shadow_workspace): add error handling and cleanup (#147)
- 🐛 fix(telemetry): join reverse-parsed body lines with real newlines (#157)
- 🐛 fix(telemetry): resolve stringified type annotation for ReviewState (#146)
- ⚡️ perf(core): batch staged blob reads and harden Phase 1 adapters (#159)
- 🥅 fix(graph): classify programming errors as GraphOutcome.ERROR (#159)
- 🦺 fix(graph): default review_context_pack include_source to false (#159)
- ⚡️ perf(secrets): cache 1Password credentials to prevent rate limiting (#143)
- ⚡️ perf(git_index): preflight batch-check before materialising blobs (#168)
- 🥅 fix(git_index): bound staged batch reads with timeout and preflight (#168)
- 🥅 fix(ai): add robust model resolution fallbacks (#159)
- 🥅 fix(client): fall back when configured model is unavailable (#159)
- 🥅 fix(metrics): isolate stage imports and scope CI OIDC (#170)
- 🥅 fix(metrics): isolate error handling per stage (#170)
- 🥅 fix(llm): catch transient network and rate-limit errors (#150)
- 🥅 fix(retries): limit graph_retry to sqlite/I/O transient failures (#157)
- 🦺 fix(semantic): harden path guards, overflow skips, and single-parse fps (#160)
- 🦺 fix(git_index): reject newlines in staged batch paths (#159)
- 🦺 fix(validation): add Null option and allow zero issue numbers (#146)
- 🦺 fix(ci): disable checkout credential persistence (#170)
- ⚡️ perf(secrets): cache 1Password credentials to prevent rate limiting (#143)
- ♻️ refactor(git_index): share batch reader via prefix parameter (#160)
- ♻️ refactor(core): decompose `_run_commit_generation` into testable helpers (#146, #151)
- ♻️ refactor(core): centralise retry logic and add telemetry (#150)
- ♻️ refactor(main): extract semantic producer metrics helper (#159, #160)
- ♻️ refactor(core): add ParseStatus and GraphOutcome StrEnums (#159)

### 🔐 Security & CI

- 🔒️ fix(telemetry): redact fallback reasons on Opik span metadata (#159)
- 🔒️ fix(telemetry): redact final Opik payloads and harden graph retries (#157)
- 🔒️ fix(security): pin scanners and replace curl|sh SBOM installs (#170)
- 🔒️ fix(telemetry): harden Phase 1 semantic telemetry and outcome enums (#159)
- 🔒️ fix(deps): raise pillow aiohttp pydantic-settings floors (#170)
- 🔐 chore(telemetry): redact PII and secrets from telemetry payloads (#148)
- 🔐 chore(ci): isolate Codecov OIDC to same-repo upload job (#170, #172)
- 🔐 chore(ci): split Codecov upload behind coverage artifact (#170)
- 🔐 chore(ci): clarify OIDC credential scope and refine test (#170, #174)
- 👷 ci(coverage): configure Codecov components and branch coverage (#169)
- 👷 ci(hooks): add read-only hk parity and Codecov OIDC upload (#170)
- 👷 ci(hooks): fetch PR base ref for hk --pr (#170)
- 👷 ci(coverage): tighten Codecov OIDC and validate timeouts (#169, #170)
- 👷 ci(security): pass PR base fetch context through env (#170)
- 👷 ci(workflows): integrate risk-scored PR review automation (#146)
- 💚 ci(workflows): pin Codecov action to immutable v4 sha (#149)
- 💚 ci(workflows): fix Codecov and standardise Python 3.14 constraints (#149)
- 🚀 chore(ci): add Anchore SBOM and vulnerability scanning to CI (#143)

### 📝 Documentation & Templates

- 📝 docs(benchmark): add lmlx benchmark plan and tables (#143)
- 📝 docs(agents): add MCP usage guides for AI assistants (#145)
- 📝 docs(ci): update workflow and test comments (#170)
- 📝 docs(instructions): update MCP tool usage guide for codebase exploration (#145)
- 📝 docs(dev): document local inference engine and GFM alerts (#143)
- 📝 docs(pr-template): revamp GitHub PR template structure (#146)
- 📝 docs(pr-template): update PR template with emojis & headings (#168)
- 📝 docs(docs): add issue and PR standards to contributor guide (#146)
- 📝 docs(ci): document mise quality tasks and CI pin contracts (#170)
- 📝 docs(ci): finish #170 nice-to-haves and component locks (#170, #174)
- 📝 docs(templates): standardise spelling to Australian English (#146)
- 📝 docs(todo): note future Gradio integration option (#159)
- 📝 docs(benchmark): add lmlx benchmark plan and tables (#143)
- 📝 docs(dev): document local inference engine and GFM alerts (#143)
- 📝 docs(agents): add MCP usage guides for AI assistants (#145)
- 📝 docs(adr): betterleaks-local / TruffleHog-CI pin posture addendum (ADR-0002) (#170)

### ✅ Tests

- ✅ test(fingerprints): truth-table, invariants, and batch metric coverage (#160)
- ✅ test(telemetry): defaults, persistence, and legacy backfill for Phase 2 fields (#160)
- ✅ test(shadow_workspace): add tests for shadow workspace isolation (#154)
- ✅ test(git_index): cover HEAD blob and staged/HEAD pairing paths (#160)
- ✅ test(similarity): cover identical, str/bytes, and divergent inputs (#160)
- ✅ test(shadow_workspace): configure Git identity for tests (#154)
- ✅ test(model): add unit tests for resolution logic (#159)
- ✅ test(core): add unit tests for extracted helpers (#146)
- ✅ test(security): lock pins, ranges, ACT, concurrency, and no curl|sh (#170)
- ✅ test(config): regression lock for constraint-dependencies floors (#170)
- ✅ test(tests): add tests for payload redaction and scorecard (#155)
- ✅ test(ci): lock OIDC job boundary and PR base-fetch env expressions (#170)
- ✅ test(pr-template): update test assertions for new headers (#146)
- ✅ test(core): cover Phase 1 semantic producers and flag wiring (#159)
- ✅ test(core): cover Phase 1 enums, flag-off gating, and telemetry redaction (#159)
- ✅ test(core): offline-mock graph adapter and fnmatch exclude coverage (#159)
- ✅ test(ci): harden hk helpers and ADR v1.4.0 contracts (#170)
- ✅ test(ci/security/project/docs): workflow and DEVELOPMENT contract locks for OIDC, forks, pins, hk skips, and nice-to-haves (#170, #174)
- ✅ test(tests): add retries and telemetry unit tests (#150, #157)
- ✅ test(tests): add tests for retries and telemetry parsing (#150)
- ✅ test(workflows): fix Codecov action version assertion (#149)
- ✅ test(localisation): tighten JSON/YAML loader types for Pyrefly (#160)
- ✅ test(localisation_config): refine template assertions (#146)
- ✅ test(fingerprints): truth-table, invariants, and batch metric coverage (#160)
- ✅ test(git_index): cover HEAD blob and staged/HEAD pairing paths (#160)
- ✅ test(similarity): cover identical, str/bytes, and divergent inputs (#160)
- ✅ test(shadow_workspace): isolation, cleanup, and identity coverage (#147)
- ✅ test(model): add unit tests for resolution logic (#159)
- ✅ test(config): regression lock for constraint-dependencies floors (#170)
- ✅ test(security): lock pins, ranges, ACT, concurrency, and no curl|sh (#170)

### 🔧 Chores & Internal

- ➕ build(deps): add rapidfuzz>=3.0.0 (#160)
- ➕ build(deps): add missing tooling and python packages (#145)
- ➕ build(deps): add httpx and tenacity dependencies (#150)
- ➕ build(deps): add rapidfuzz>=3.0.0 (#160)
- ⬆️ build(deps): bump the actions group with 2 updates (#144)
- 🔖 release(version): bump version to v0.3.0
- 📌 build(deps): enforce Python 3.14 boundaries in package metadata (#156)
- 🔧 chore(cli): add `--enable-semantic` flag and env override (#159)
- 🔧 chore(agents): configure MCP servers and skill sources (#145)
- 🔧 chore(mise): exact security/hk tool pins and canonical quality tasks (#170)
- 🔧 chore(lock): upgrade transitive security floor packages in uv.lock (#170)
- 🔧 chore(config): update installation scripts for Python 3.14 (#156)
- 🔧 chore(config): switch Opik MCP from npx to uvx (#145)
- 🔧 chore(mise): pin toolchain versions and document TruffleHog CLI (#170)
- 🔧 chore(config): update project config and dependencies (#145)
- 🔧 chore(vscode): configure npm package manager (#146)
- 🔧 chore(ide): set default python interpreter path in VSCode settings (#146)
- 🔧 chore(agents): configure MCP servers and skill sources (#145)
- 🔧 chore(config): switch Opik MCP from npx to uvx (#143)
- 🙈 chore(gitignore): update .gitignore rules (#145)
- 🙈 chore(gitignore): ignore tool caches and backup files (#145)
- 🙈 chore(gitignore): ignore shared SBOM artifacts (`bom.json` / `bom.syft.json`) (#170, #174)
- 🎨 style(codebase): fix lint warnings and standardise formatting (#108)
- 🎨 style(fingerprints): normalise docstring whitespace (#160)
- 🎨 style(docstrings): standardise docstring indentation (#146)
- 🎨 style(tests): strip trailing whitespace in hk docstring blanks (#170)
- 🎨 style(similarity): strip trailing whitespace in docstring blanks (#160)
- 🎨 style: fix ruff I001 import order for CI (opik third-party) (#170)


## v0.3.0

### 🌐 Features & UX

- 💄 ux(assets): package custom Ligatured-Hack Nerd Font suites for flawless TUI rendering
- ✨ feat(localisation): standardise repository documentation on en-AU
- ✨ feat(sop): add commit_language en-AU configuration
- 🌐 feat(prompts): inject en-AU rules into AI agent prompts
- 🌐 feat(context): inject commit language setting into agent prompts

### 🐛 Bug Fixes & Refactors

- ♻️ refactor(sop): extract deep merge utility
- 🏗️ refactor(sop): implement multi-tier SOP data merging
- 🥅 fix(config): fix validation logic and YAML parsing
- 🥅 fix(sop): validate commit language configuration
- 🐛 fix(docs): remove doctoc TOC to fix zensical strict build
- 🐛 fix(docs): revert Zensical configuration from formalize to formalise
- 🐛 fix(docs): update zensical nav for ADR-0013 formalise spelling
- 🐛 fix(docs): remove doctoc TOC from README.md
- 🦺 fix(schema): enforce locale pattern

### 📝 Documentation & Templates

- 📝 docs(github): standardise issue and PR templates
- 📝 docs(templates): add GitHub issue and PR templates
- 📝 docs(adr): align ADR tables and add en-AU localisation rule
- 📝 docs(localisation): standardise repository documentation on en-AU
- 📝 docs(readme): fix release badge caching and targeting
- 📝 docs(zensical): update site navigation and sync root documents
- 📝 docs(adr): update ADR version history
- 📝 docs(adr): rename and localise all architectural decision records
- 📝 docs(readme): standardise spelling in README and CHANGELOG
- 📝 docs(readme): switch shield to /v/tag with semver sorting and cache-busting logo param
- 📝 docs(changelog): append PR and issue numbers to sub-intents
- 📝 docs(changelog): flatten and group v0.1.0 release notes by type
- 📝 docs(changelog): flatten and group v0.2.0 release notes by type
- 📝 docs(changelog): expand v0.2.0 release notes with nested sub-intents
- 📝 docs(changelog): expand v0.1.0 breaking changes from sub-intents
- 📝 docs(changelog): add missing ADR-0013 security notes
- 📝 docs(changelog): update v0.2.0 notes with issue refs
- 📝 docs(tests): add unit tests for PR changes
- 📝 docs(tests): add docstrings to localisation modules

### 🔧 Chores & Internal

- 🔧 chore(vscode): configure spelling and fix adr link
- 🔧 chore(ci): add release workflow permissions
- 🔧 build(ide): configure VSCode spellchecker with en-AU dictionary
- 🔧 build(zensical): configure documentation validation for en-AU
- 🔧 build(gitops): set repository commit language to en-AU
- 👷 ci(release): configure automated release workflow
- 🔧 build(ignore): exclude .vscode/ from tracked stash operations
- 🔧 chore(vscode): add spell checker extensions to recommendations
- 🔧 chore(vscode): configure cSpell for Australian English
- 🔧 chore(deps): sync lockfile with v0.2.0 release bump

## v0.2.0

### ✨ Features

- ✨ feat(cli): add GUI editor support for commit messages
- ✨ feat(eval): add `FormatMetric` and enforce Tier-1 deterministic format gating (#118, #128)
- ✨ feat(eval): add Opik test suite execution and triage scripts (#119, #133)
- ✨ feat(eval): finalise `Promptfoo` security, native release engine, and IDE boundaries (#121, #123, #124, #136)
- ✨ feat(eval): initialise `Promptfoo` framework for local `MTPLX` proxy testing (#120, #134)
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
- 🚨 refactor(telemetry): resolve ruff SIM105 lint error by utilizing `contextlib.suppress`

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
- 🦺 docs(security): formalise IDE boundaries and 1Password `.env` mounting protocols (ADR-0013)
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
- 📝 docs(readme): correct typos and update `COMMIT_EDITMSG` path documentation (#92)
- 📝 docs(readme): document configuration and secrets setup
- 📝 docs(readme): document regeneration guidance actions (#92)
- 📝 docs(readme): extract TODO list and update Python version
- 📝 docs(readme): update README with new architecture and features
- 📝 docs(todo): add deferred architecture ideas and parametrise env script
- 📝 docs(todo): add multi-turn workflow task
- 📝 docs(todo): clean up TODO.md formatting
- 📝 docs(todo): cleanup completed TODO items
- 📝 docs(todo): reorganise TODO into structured issue sections
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
