# Changelog

## Unreleased

### ✨ Features

- ✨ feat(core): Phase 7.25 gold-standard commit-message content quality — deterministic `commit_gold` linter (wording/coverage/coherence findings) with three-channel prompt assembly and an additive GOLD RUBRIC (#182)
- ✨ feat(commit-quality): Session 6 presentation residuals — telemetry schema capability dominance, evaluator mutation-verb guards, Context/Changes template rejection, attribution-bleed detection, and module/behaviour scope law (#204)
- ✨ feat(hooks): F80 `GIT_CG_SKIP_PREPARE` bypass so message-only rebuilds do not re-enter `prepare-commit-msg` generation (#204)

### 🐛 Bug Fixes & Refactors

- 🦺 fix(commit-quality): docs-only/tests-only craft repair avoids skeleton fallback under gold-strict (#214)
- 🦺 fix(commit-quality): broaden craft-verb catalogue for inventory/vague openers on docs/tests (#214)
- 🥅 fix(intent): close #181-class mis-rank by adding product markers to `error_handling` negative signals (feature_addition now outranks error_handling on product+error diffs) (#182)
- 🦺 fix(commit-quality): replace package/epic scopes with dominant module or behaviour slugs; keep path-class envelopes authoritative over blueprint overlays (#204)

### ✅ Tests

- ✅ test(commit-quality): lock docs/tests craft repair, mixed-set refusal, and gold-strict no-skeleton path (#214)
- ✅ test(acceptpath): freeze docs-only post-repair COMMIT_EDITMSG snapshot + catalogue locks (#214)
- ✅ test(intent): B1 characterisation fixtures (release-notes product, bugfix-pure, error-only) + golden cascade refresh via `GIT_CG_UPDATE_GOLDENS` (#182)
- ✅ test(core): B2 gold-linter tables, Claim A purity tests (A_01-A_05), and generation-path gold wiring integration (#182)
- ✅ test(commit-quality): V12-A named proof pack (`test_v12_a01`–`a45`) plus Session 6 corpus rows TIP-G13–G17 and goldens (#204)
- ✅ test(hooks): F80 `GIT_CG_SKIP_PREPARE` truthy-token matrix and no-op-before-validation coverage (#204)

### 📝 Documentation

- 📝 docs(usage): gold modes, finding codes, path-group mapping, and large-diff semantic tripwire (#182)
- 📝 docs(readme): Session 6 operator residuals, module-scope law, and V12-A proof-pack pointer for Issue #204
- 📝 docs(readme): F80 `GIT_CG_SKIP_PREPARE` operator contract, message-only rebuild example, and presentation-adjacent env table (#204)
## v0.24.0

### ✨ Features

- 👔 feat(eval-checkpoint): reclaim stale running by age bound (#256)
- 👔 feat(eval-checkpoint): durable status and authority-first GC (#256)

### 🐛 Bug Fixes

- 🐛 fix(eval-run): reclaim GC on resume no-op; reject bad bounds (#256)
- 🦺 fix(eval-review): fail closed on damaged dual identity claims (#256)
- 🦺 fix(eval-review): harden dual-field reviewer identity canon (#256)
- 💚 ci(eval-tests): re-export root factories past eval conftest shadow (#256)
- 🌑 chore(eval-run): wire opt-in stale-running reclaim gate (#256)

### ♻️ Refactors

- ♻️ refactor(eval-triage): route doctor doubles through shared factory (#256)
- ♻️ refactor(eval-doctor): alias clean_doctor_repo to shared isolation (#256)
- 🏷️ refactor(eval-schemas): add durable checkpoint status and started_at (#256)

### 📝 Documentation

- 📝 docs(eval): document bounded stale-running reclamation (#256)
- 📝 docs(usage): spell reclaim-stale-running protect semantics (#256)
- 💡 docs(eval): document root conftest re-export shadow path (#256)
- 📝 docs(pr-template): align Included Changes summary chrome (#256)
- 📝 docs(pr-template): default Included Changes to details shape (#256)
- 📝 docs(llms): auto-update llms.txt

### ✅ Tests

- ✅ test(eval-cli): lock reclaim flag help, default-off, and fail-closed (#256)
- ✅ test(eval-run): lock finalize protect under reclaim and keep (#256)
- ✅ test(eval-checkpoint): lock GC age, keep-last, and degraded inventory (#256)
- ✅ test(eval-review): lock dual-field identity canon contracts (#256)
- ✅ test(eval-checkpoint): lock stale-running reclaim contracts (#256)
- 🤡 test(eval): add shared doctor double and repo isolation (#256)
- 🧪 test(eval): re-export root Opik scrub from eval conftest (#256)

### 🏗️ Build & CI

- 👷 ci(eval): gate checkpoint store and orchestrator coverage (#256)
- 👷 ci(pr-body): wrap synced Included Changes in details (#256)
- 💚 ci(pr-body): preserve multi-comment Included Changes headers (#256)

### Miscellaneous

- Merge pull request #262 from Thomo1318/eval/256-8a-s6-foundation-residuals

## v0.23.0

### Miscellaneous

- 👷 ci(llms-txt): lock gold Hybrid bot-commit template (#254)
- 🔧 chore(sop): register CodeRabbit review-bot intent (#254)
- ✅ test(deslop-naming): add fail-closed identity residue scanner (#254)
- 🔨 chore(eval): rename coverage recipes to domain-first names (#254)
- 🔨 chore(eval): gate S7 owned files at 80% coverage each (#254)
- 🔨 chore(eval): add report-only S7 per-file coverage recipe (#254)
- 🔧 chore(eval): add eval-s7-proof coverage recipe (#254)
- ✅ test(eval): cover lane provenance and doctor diagnostics (#254)
- 🔧 chore(mise): wire betterleaks config path (#254)
- 🔧 chore(betterleaks): allowlist H65probeToken probe string (#254)
- ✅ test(eval): cover H65 masking, intent signals, and train-export (#254)
- 🙈 chore(repo): scope Opik ignore rule to repository root (#254)
- 🙈 chore(gitignore): ignore src/evals directory (#254)
- 📝 docs(just): domain-first claim-matrix spine recipe name (#254)
- 📝 docs(docs): document code and prose deslop skill checklists (#254)
- 📝 docs(adr): deslop ADR-0011 S7/S8 refinement prose (#254)
- 📝 docs(cli): tighten eval help strings in usage.kdl (#254)
- 📝 docs(cli): keep opik verify advisory across doc regen (#254)
- 📝 docs(deslop): expand code and prose residue rules (#254)
- 📝 docs(eval): expand S7 plan board and ADR S0-S8 scope (#254)
- 📝 docs(llms): auto-update llms.txt
- ✏️ docs(deslop): correct skill table pipes and guidance (#254)
- Merge pull request #255 from Thomo1318/eval/254-s7-user-interaction-opik-pins-feedback-definitions-hitl-annotation
- fix: apply CodeRabbit auto-fixes

### Tests

- 🔒️ fix(mirror): redact public config fallback tokens (#254)
- 🔒️ fix(mirror): redact mode token; enforce HTTPS endpoint (#254)
- 🔒️ fix(eval-scrub): pin short-segment JWT lookarounds (#254)
- 🔒️ fix(eval-promote): mask decision notes before audit persist (#254)
- 🔒️ fix(eval-review): mask free-text before persist; widen JWT detection (#254)
- 🐛 fix(opik-verify): route factory secrets through a module seam (#254)
- ✨ feat(eval-cli): add --case scope to amend-brief (#254)
- ✨ feat(eval-cli): add read-only checkpoint inventory command (#254)
- ✨ feat(eval-schemas): add feedback_definition_v1 schema (#254)
- 🦺 fix(deslop): fail closed when Git diff collection fails (#254)
- 🦺 fix(opik-verify): fail closed on truncated SDK listings (#254)
- 🦺 fix(eval): address CodeRabbit PR #255 review findings (#254)
- 🦺 fix(eval): lock additive-only feedback-definition migration (#254)
- 🦺 fix(eval-promote): wire advisory review rollup into promotion (#254)
- 🦺 fix(eval-promote): bind advisory approve_promote as the human leg (#254)
- 🦺 fix(eval-review): harden score vocabulary, annotations, claim locks (#254)
- 🚸 feat(eval-cli): render Opik config show as an operator summary (#254)
- 🩺 feat(eval-doctor): publish Opik exit-code credential matrix (#254)
- 🩹 fix(eval-cli): stabilize empty-queue status and retry id misses (#254)
- ✅ test(opik): assert project creation side effect (#254)
- ✅ test(intent): refresh goldens for expanded SOP matrix (#254)
- 🔧 chore(sop): register CodeRabbit review-bot intent (#254)
- ✅ test(deslop-naming): add fail-closed identity residue scanner (#254)
- ✅ test(eval): lock promote claim aliases and S8 docs guard (#254)
- ✅ test(main): lock mode-off Opik import isolation (#254)
- ✅ test(eval): guard interaction work from docs-platform surfaces (#254)
- ✅ test(eval): re-pin schema_pack_v0 content hash (#254)
- ✅ test(eval): cover feedback_definitions map drift (#254)
- 🎨 style(eval-mirror): parenthesize flush-timeout except clause (#254)
- 🌑 chore(eval-mirror): add opt-in live queue projector (#254)
- 🌑 chore(eval-opik): add advisory online verify surface (#254)
- 🌑 chore(eval-mirror): add offline queue_mirror non-SoT seam (#254)

### Changed

- 🔒️ fix(mirror): redact mode token; enforce HTTPS endpoint (#254)
- 🦺 fix(deslop): fail closed when Git diff collection fails (#254)
- 🦺 fix(opik-verify): fail closed on truncated SDK listings (#254)
- 🦺 fix(eval): address CodeRabbit PR #255 review findings (#254)
- 🦺 fix(eval): lock additive-only feedback-definition migration (#254)
- ♻️ refactor(eval): consolidate lane-pin env scrubbing in conftest (#254)
- ➕ build(dev): Add harbor and matplotlib to dev deps (#254)
- 🚸 feat(eval-cli): render Opik config show as an operator summary (#254)
- ➕ build(dev-deps): add harbor and matplotlib (#254)
- 💬 style(eval-promote): clarify ape_bundle_v1 spine and denial hints (#254)
- 🎨 style(eval): collapse export-retry branches and trim comment residue (#254)
- 🎨 style(eval-mirror): parenthesize flush-timeout except clause (#254)
- 🌑 chore(eval-mirror): add opt-in live queue projector (#254)
- 🌑 chore(eval-opik): add advisory online verify surface (#254)
- 🌑 chore(eval-mirror): add offline queue_mirror non-SoT seam (#254)

### Fixed

- 🔒️ fix(mirror): redact mode token; enforce HTTPS endpoint (#254)
- 🐛 fix(opik-verify): route factory secrets through a module seam (#254)
- 🐛 fix(deslop-naming): use single effective worktree diff (#254)
- 🐛 fix(main): defer Opik import until active mode (#254)
- ✨ feat(eval-cli): add read-only checkpoint inventory command (#254)
- 🦺 fix(opik-verify): fail closed on truncated SDK listings (#254)
- 🦺 fix(eval): address CodeRabbit PR #255 review findings (#254)
- 🦺 fix(eval-promote): wire advisory review rollup into promotion (#254)
- 🦺 fix(eval-promote): bind advisory approve_promote as the human leg (#254)
- 🦺 fix(eval-review): harden score vocabulary, annotations, claim locks (#254)
- 🦺 fix(eval): add feedback-definition map and validated loader (#254)
- 🦺 fix(intent): harden hook-path and secrets-term matching (#254)
- 🚸 feat(eval-cli): render Opik config show as an operator summary (#254)
- 🩹 fix(eval-mirror): parenthesize flush-timeout except clause (#254)
- 🩹 fix(eval-cli): stabilize empty-queue status and retry id misses (#254)
- 🌑 chore(eval-mirror): add opt-in live queue projector (#254)
- 🌑 chore(eval-mirror): add offline queue_mirror non-SoT seam (#254)

### Security

- 🔒️ fix(just): quote deslop-naming-scan recipe params (#254)
- 🔒️ fix(mirror): redact public config fallback tokens (#254)
- 🔒️ fix(mirror): redact mode token; enforce HTTPS endpoint (#254)
- 🔒️ fix(eval-scrub): pin short-segment JWT lookarounds (#254)
- 🔒️ fix(eval-promote): mask decision notes before audit persist (#254)
- 🔒️ fix(eval-review): mask free-text before persist; widen JWT detection (#254)

### Documentation

- 🦺 fix(eval): address CodeRabbit PR #255 review findings (#254)
- 🔨 chore(eval): rename coverage recipes to domain-first names (#254)
- 💬 style(eval-promote): clarify ape_bundle_v1 spine and denial hints (#254)
- 📝 docs(badges): refresh interrogate coverage badge (#254)
- 📝 docs(adr): correct S7 board grammar and PR #255 pointer (#254)
- 📝 docs(just): domain-first claim-matrix spine recipe name (#254)
- 📝 docs(deslop): require pattern Naming Audit in agent skills (#254)
- 📝 docs(docs): document code and prose deslop skill checklists (#254)
- 📝 docs(cli): tighten eval help strings in usage.kdl (#254)
- 📝 docs(eval): tighten S6/S7 status pointers (#254)
- 📝 docs(eval): align S7 status, plans, and usage.kdl surfaces (#254)
- 📝 docs(cli): keep opik verify advisory across doc regen (#254)
- 📝 docs(cli): refresh generated amend-brief help (#254)
- 📝 docs(eval): close S7 optional NTH operator surfaces (#254)
- 📝 docs(eval): add S7 claim matrix and interaction close-out (#254)
- 📝 docs(eval): document checkpoint inventory and config summary output (#254)
- 💡 docs(comments): drop tautological helper docstrings (#254)
- 🌑 chore(eval-opik): add advisory online verify surface (#254)

### Added

- 🔒️ fix(mirror): redact mode token; enforce HTTPS endpoint (#254)
- ✨ feat(eval-cli): add --case scope to amend-brief (#254)
- ✨ feat(eval-cli): add read-only checkpoint inventory command (#254)
- ✨ feat(eval-schemas): add feedback_definition_v1 schema (#254)
- ✨ feat(eval-doctor): add Opik lane-pin diagnostics (#254)
- ✨ feat(eval-mirror): add lane provenance for doctor diagnostics (#254)
- ✨ feat(eval): add train-export --root isolation override (#254)
- 🩺 feat(eval-doctor): publish Opik exit-code credential matrix (#254)

## v0.22.0

### Miscellaneous

- 👷 ci(s6-cli): retrigger full main-target checks after #249 merge (#246)
- 👷 ci(s6-docs): retrigger full main-target checks after #251 merge (#246)
- 👷 ci(workflows): auto-assign owner on issues and PRs
- 🧑‍💻 chore(agents): constrain prose-deslop rules for technical precision (#246)
- 🧑‍💻 chore(agents): add owned deslop skill suite with path registration
- 🧑‍💻 chore(sop): add dark_launch Hybrid matrix vocabulary (#246)
- ✅ test(eval): lock _click_help brief/detail split arms (#246)
- 🔧 chore(gitignore): section banners and local plan ignore (#246)
- 📝 docs(llms): auto-update llms.txt
- 📝 docs(cli): regenerate reference from wide brief help capture (#246)
- 📝 docs(docs): document dark launch governance and inventory (#246)
- 📝 docs(docs): document full CLI reference surface (#246)
- 📝 docs(eval): group eval help by workflow (#246)
- 📝 docs(eval): add docstrings across eval package (#246)
- 📝 docs(repo): tidy planning docs and unignore src/evals (#246)
- 📝 docs(eval): close PR1 docstring gate and dark_launch SOP pins (#246)
- 📝 docs(eval): land S6 Slice 9 close-out pack (#246)
- 📝 docs(badges): refresh interrogate full-tree coverage badge (#246)
- 📝 docs(docs): reconcile S6 slice 0 implementation handoff (#246)
- 📝 docs(eval): freeze S6 slice 0 baseline and landed-state census (#246)
- ✏️ docs(todo): correct tree-sitter spelling and fence language (#246)
- Merge pull request #253 from Thomo1318/pr/246-s6-cli-ux-fixtures
- Merge pull request #249 from Thomo1318/pr/246-s6-docs-tooling
- Merge pull request #251 from Thomo1318/pr/246-s6-foundation
- fix: apply CodeRabbit auto-fixes

### Fixed

- 🔒️ fix(eval): scrub free-text surfaces and fail closed on damaged rows (#246)
- 🔒️ fix(eval): secret-safe operator projection and train scrub-fail (#246)
- ✨ feat(eval-promote): lock S6-E09 denial law and audit rows (#246)
- ✨ feat(eval-dogfood): lock S6-G01–G04/G08 offline proof contracts (#246)
- ✨ feat(eval-sessions): lock session/thread show reader contract (#246)
- ✨ feat(eval-review): add local HITL review queue store (#246)
- ✨ feat(eval-promote): add closed promotion state machine (#246)
- ✨ feat(eval-replay): add offline structural replay engine (#246)
- ✨ feat(eval-cli): wire Slice 5 explain, diagnose, and issue commands (#246)
- ✨ feat(eval-diagnose): diag_issue_v1 upsert engine and lifecycle store (#246)
- ✨ feat(eval-explain): add deterministic failures/explain/compare engines (#246)
- ✨ feat(eval-cli): implement local and Opik doctor surfaces (#246)
- ✨ feat(eval-run): orchestrate suite run, resume, and recompute modes (#246)
- ✨ feat(eval-compat): add D9 suite resume compatibility hash (#246)
- ✨ feat(eval-cli): register S6 operator skeleton and envelope helpers (#246)
- ✨ feat(eval-binding): extend S6 Layer-A path helpers and containment (#246)
- 🦺 fix(docstring-guard): fail closed on unsafe same-line and apply paths (#246)
- 🦺 fix(eval): correct replay envelope and compare-source provenance (#246)
- 🦺 fix(eval-doctor): gate compat hash on pinned schema and catalog (#246)
- 🦺 fix(eval-promote): honor explicit non-synthetic meta flags (#246)
- 🦺 fix(eval-schemas): tighten S6 bounds and timestamp contracts (#246)
- 🩹 fix(cli-docs): stop truncating generated CLI help tokens (#246)
- 🩹 fix(git-index): treat empty staged reads as not ok (#246)
- 🩹 fix(eval): harden CLI emission, sampling, and triage exits (#246)
- 📝 docs(eval-dogfood): attach S6-G02(b) maintainer bench evidence (#246)

### Tests

- 🔒️ fix(eval): scrub free-text surfaces and fail closed on damaged rows (#246)
- 🔒️ fix(eval): secret-safe operator projection and train scrub-fail (#246)
- ✨ feat(docstring-guard): add docstring insertion guard (#246)
- ✨ feat(eval-review): add advisory multi-rater rollup surface (#246)
- ✨ feat(eval-ops): complete diagnose and train-export dry-run (#246)
- ✨ feat(eval-explain): add deterministic failures list filters (#246)
- ✨ feat(eval-api-map): lock S6-A08 envelope data sketches and check gate (#246)
- ✨ feat(eval-cli): surface promote denial audit on envelopes (#246)
- ✨ feat(eval-promote): lock S6-E09 denial law and audit rows (#246)
- ✨ feat(eval-dogfood): lock S6-G01–G04/G08 offline proof contracts (#246)
- ✨ feat(eval-cli): lock amend-brief --root and offline proof contracts (#246)
- ✨ feat(eval-sessions): lock session/thread show reader contract (#246)
- ✨ feat(eval-doctor): add static explain/failures deep-links (#246)
- ✨ feat(eval-schemas): re-freeze dogfood_attachment_v1 sample contract (#246)
- ✨ feat(eval-cli): wire run, resume, and recompute-scores operators (#246)
- ✨ feat(eval-run): orchestrate suite run, resume, and recompute modes (#246)
- ✨ feat(eval-checkpoint): land evaluation_checkpoint_v1 store and GC (#246)
- ✨ feat(eval-compat): add D9 suite resume compatibility hash (#246)
- ✨ feat(eval-binding): extend S6 Layer-A path helpers and containment (#246)
- ✨ feat(eval-schemas): re-freeze S6 Slice 1 contracts and pack pin (#246)
- 🦺 fix(docstring-guard): fail closed on unsafe same-line and apply paths (#246)
- 🦺 fix(eval-doctor): scope checkpoint compat to the active suite (#246)
- 🦺 fix(eval): correct replay envelope and compare-source provenance (#246)
- 🦺 fix(eval-doctor): gate compat hash on pinned schema and catalog (#246)
- 🦺 fix(eval-promote): honor explicit non-synthetic meta flags (#246)
- 🦺 fix(eval-schemas): tighten S6 bounds and timestamp contracts (#246)
- ♻️ refactor(train-export): inject optional redact_bundle seam (#246)
- ♻️ refactor(eval): make binding and Lane C package exports lazy (#246)
- 👷 ci(workflows): surface MISSED symbols on docstring PR comments
- 🩹 fix(git-index): treat empty staged reads as not ok (#246)
- 🩹 fix(eval): harden CLI emission, sampling, and triage exits (#246)
- 🧑‍💻 chore(sop): add dark_launch Hybrid matrix vocabulary (#246)
- ✅ test(eval-fixtures): re-pin core bundles to live schema pack (#246)
- ✅ test(eval): fix S6 patch-coverage harness CI failures (#246)
- ✅ test(eval): raise S6 foundation patch coverage (#246)
- ✅ test(eval): harden pin, replay, and scanner-safe fixtures (#246)
- ✅ test(eval): isolate help, hooks, and scanner-safe fixtures (#246)
- ✅ test(eval-orchestrator): lock S6-B11 per-case checkpoint cadence (#246)
- ✅ test(eval): lock Slice 7 contracts + retarget stub envelope (#246)
- ✅ test(eval-cli): lock Slice 6 replay/promote/review offline (#246)
- ✅ test(eval-cli): lock Slice 5 explain/diagnose/issue contracts offline (#246)
- ✅ test(eval-cli): lock Slice 4 doctor contracts offline (#246)
- ✅ test(eval-cli): lock S6 Slice 2 help, API map, and envelope claims (#246)
- 📸 test(eval-fixtures): refresh schema-pack goldens to live cf17 pin (#246)
- 📝 docs(eval): group eval help by workflow (#246)
- 📝 docs(eval-api-map): document single-writer operator ownership law (#246)
- 🌑 chore(eval-cli): dark-launch dogfood out of regular help (#246)

### Changed

- ✨ feat(eval-cli): add dual-axis brief/detail operator help (#246)
- 🦺 fix(docstring-guard): fail closed on unsafe same-line and apply paths (#246)
- 🦺 fix(eval-doctor): scope checkpoint compat to the active suite (#246)
- ♻️ refactor(train-export): inject optional redact_bundle seam (#246)
- ♻️ refactor(eval): make binding and Lane C package exports lazy (#246)
- ♻️ refactor(eval-scripts): freeze opik_trace_triage fail-closed (#246)
- ♻️ refactor(eval-scoring): extract shared prepare_suite_cases prelude (#246)
- 👷 ci(workflows): surface MISSED symbols on docstring PR comments
- 💄 style(cli): apply gold Typer help theme defaults (#246)
- 🎨 style(intent): satisfy ruff blank-line nesting contract (#246)
- 📝 docs(eval): close PR1 docstring gate and dark_launch SOP pins (#246)
- 🌑 chore(eval-cli): dark-launch dogfood out of regular help (#246)

### Documentation

- ✨ feat(eval-cli): add dual-axis brief/detail operator help (#246)
- ✨ feat(docstring-guard): add docstring insertion guard (#246)
- ✨ feat(eval-review): add advisory multi-rater rollup surface (#246)
- ✨ feat(eval-ops): complete diagnose and train-export dry-run (#246)
- ✨ feat(eval-explain): add deterministic failures list filters (#246)
- ✨ feat(eval-api-map): lock S6-A08 envelope data sketches and check gate (#246)
- ✨ feat(eval-dogfood): lock S6-G01–G04/G08 offline proof contracts (#246)
- ✨ feat(eval-cli): wire offline eval triage operator command (#246)
- ✨ feat(eval-cli): wire Slice 7 amend-brief, dogfood, train-export (#246)
- ✨ feat(eval-schemas): re-freeze dogfood_attachment_v1 sample contract (#246)
- ✨ feat(eval-cli): wire Slice 6 replay, promote, and review (#246)
- ✨ feat(eval-cli): wire Slice 5 explain, diagnose, and issue commands (#246)
- ✨ feat(eval-cli): implement local and Opik doctor surfaces (#246)
- ✨ feat(eval-cli): wire run, resume, and recompute-scores operators (#246)
- ✨ feat(eval-api-map): generate operator API map from live Typer tree (#246)
- ✨ feat(eval-schemas): re-freeze S6 Slice 1 contracts and pack pin (#246)
- ♻️ refactor(eval-scripts): freeze opik_trace_triage fail-closed (#246)
- 🧑‍💻 chore(agents): constrain prose-deslop rules for technical precision (#246)
- 📸 test(eval-fixtures): refresh schema-pack goldens to live cf17 pin (#246)
- 📝 docs(cli): refresh eval CLI reference for brief help copy (#246)
- 📝 docs(docs): document dark launch governance and inventory (#246)
- 📝 docs(docs): document full CLI reference surface (#246)
- 📝 docs(eval): group eval help by workflow (#246)
- 📝 docs(eval): add docstrings across eval package (#246)
- 📝 docs(repo): tidy planning docs and unignore src/evals (#246)
- 📝 docs(eval): qualify dogfood bench latency claim (#246)
- 📝 docs(eval): land S6 Slice 9 close-out pack (#246)
- 📝 docs(eval-dogfood): attach S6-G02(b) maintainer bench evidence (#246)
- 📝 docs(eval): seed S6 claim→test matrix before Slice 9 (#246)
- 📝 docs(todo): expand backlog; point docs style at standard (#246)
- 📝 docs(standards): ratify contract docstring standard (#246)
- 📝 docs(eval-api-map): document single-writer operator ownership law (#246)
- 📝 docs(eval): record Slice 8 D27 triage absorption disposition (#246)
- 📝 docs(docs): reconcile S6 slice 0 implementation handoff (#246)
- 📝 docs(eval): freeze S6 slice 0 baseline and landed-state census (#246)
- 📝 docs(development): document sticky interrogate comment layout
- 💡 docs(eval): align helper docstrings with real contracts (#246)
- 🌑 chore(eval-cli): dark-launch dogfood out of regular help (#246)

### Added

- ✨ feat(eval-cli): add dual-axis brief/detail operator help (#246)
- ✨ feat(eval-review): add advisory multi-rater rollup surface (#246)
- ✨ feat(eval-ops): complete diagnose and train-export dry-run (#246)
- ✨ feat(eval-explain): add deterministic failures list filters (#246)
- ✨ feat(eval-api-map): lock S6-A08 envelope data sketches and check gate (#246)
- ✨ feat(eval-cli): surface promote denial audit on envelopes (#246)
- ✨ feat(eval-promote): lock S6-E09 denial law and audit rows (#246)
- ✨ feat(eval-dogfood): lock S6-G01–G04/G08 offline proof contracts (#246)
- ✨ feat(eval-cli): lock amend-brief --root and offline proof contracts (#246)
- ✨ feat(eval-sessions): lock session/thread show reader contract (#246)
- ✨ feat(eval-doctor): add static explain/failures deep-links (#246)
- ✨ feat(eval-cli): wire offline eval triage operator command (#246)
- ✨ feat(eval-triage): add offline advisory triage router service (#246)
- ✨ feat(eval-cli): wire Slice 7 amend-brief, dogfood, train-export (#246)
- ✨ feat(eval): Slice 7 offline engines for brief and data capture (#246)
- ✨ feat(eval-schemas): re-freeze dogfood_attachment_v1 sample contract (#246)
- ✨ feat(eval-cli): wire Slice 6 replay, promote, and review (#246)
- ✨ feat(eval-review): add local HITL review queue store (#246)
- ✨ feat(eval-promote): add closed promotion state machine (#246)
- ✨ feat(eval-replay): add offline structural replay engine (#246)
- ✨ feat(eval-cli): wire Slice 5 explain, diagnose, and issue commands (#246)
- ✨ feat(eval-diagnose): diag_issue_v1 upsert engine and lifecycle store (#246)
- ✨ feat(eval-explain): add deterministic failures/explain/compare engines (#246)
- ✨ feat(eval-cli): implement local and Opik doctor surfaces (#246)
- ✨ feat(eval-cli): wire run, resume, and recompute-scores operators (#246)
- ✨ feat(eval-run): orchestrate suite run, resume, and recompute modes (#246)
- ✨ feat(eval-checkpoint): land evaluation_checkpoint_v1 store and GC (#246)
- ✨ feat(eval-compat): add D9 suite resume compatibility hash (#246)
- ✨ feat(eval-api-map): generate operator API map from live Typer tree (#246)
- ✨ feat(eval-cli): register S6 operator skeleton and envelope helpers (#246)
- ✨ feat(eval-binding): extend S6 Layer-A path helpers and containment (#246)
- ✨ feat(eval-schemas): re-freeze S6 Slice 1 contracts and pack pin (#246)
- ♻️ refactor(eval-scoring): extract shared prepare_suite_cases prelude (#246)

### Security

- 🔒️ fix(eval): scrub free-text surfaces and fail closed on damaged rows (#246)
- 🔒️ fix(eval): secret-safe operator projection and train scrub-fail (#246)
- ✨ feat(eval-cli): implement local and Opik doctor surfaces (#246)

## v0.21.0

### Miscellaneous

- 👷 ci(interrogate): pin local just recipes and lock fail-under gates (#233)
- 👷 ci(interrogate): gate PRs on changed-file docstring coverage
- 👷 ci(interrogate): add 3.14-pinned docstring coverage contract
- ✅ test(eval-lane-c): raise Codecov patch coverage for Lane C modules (#233)
- 📝 docs(llms): auto-update llms.txt
- 📝 Add docstrings to `evals/233-s5-gated-lane-c-cohort-optional-judge-lab`
- Merge pull request #238 from Thomo1318/evals/233-s5-gated-lane-c-cohort-optional-judge-lab

### Documentation

- ✨ feat(eval-lane-c): add repo-first prompt_pack_v1 identity (#233)
- 🦺 fix(eval-lane-c): harden meta-eval pins and honest FP/FN rates (#233)
- 👷 ci(interrogate): publish validated sticky PR coverage report (#233)
- ✅ test(eval-lane-c): tighten residual contract assertions (#233)
- ✅ test(eval-scripts): lock D24 absorption freezes (#233)
- 📝 docs(eval): reconcile S5 closeout status and coverage evidence (#233)
- 📝 docs(eval): mark Slice 6 residuals as shipped lab surfaces (#233)
- 📝 docs(interrogate): publish flat badge and operator invoke guide
- 📝 docs(eval): restore gold-standard S5 contract docstrings (#233)
- 📝 docs(eval-lane-c): constrain GEval rubrics to gold-blind projection (#233)
- 📝 docs(eval): align S5 SSOT pointer and claim-evidence paths (#233)
- 📝 docs(eval): publish S5 operator boundary and claim-evidence matrix (#233)
- 📝 docs(plans): lock v0.9.5 S5/S6/S7 API-surface policy (#233)
- 📝 docs(eval-lane-c): record Slice 4 S5c pinned GEval seam checklist (#233)
- 📝 docs(eval): lock S5 Slice 0 baseline and eligibility-split SSOT (#233)

### Tests

- ✨ feat(eval-lane-c): ship judge_meta_eval_v1 lab Equals path (#233)
- ✨ feat(eval-lane-c): Slice 1 gated cohort spine (authz, availability) (#233)
- ✨ feat(eval-scoring): optional Lane C precomputed semantic-cohort gate (#233)
- 🦺 fix(eval-lane-c): fail closed on dirty-overlay activation guards (#233)
- 🦺 fix(eval-lane-c): harden meta-eval pins and honest FP/FN rates (#233)
- 🦺 fix(eval-lane-c): keep host-guard rows uninvoked in evidence (#233)
- 🦺 fix(eval-lane-c): normalize forbidden judge-input key variants (#233)
- 👷 ci(interrogate): pin local just recipes and lock fail-under gates (#233)
- 👷 ci(interrogate): fail-closed pathspec and pin interrogate 1.7.0 (#233)
- ✅ test(eval-lane-c): tighten residual contract assertions (#233)
- ✅ test(eval-lane-c): lock Slice 6 residual contracts (#233)
- ✅ test(eval-lane-c): run import isolation in subprocess (#233)
- ✅ test(eval-scripts): align legacy Opik tests with D24 freeze (#233)
- ✅ test(eval): lock CodeRabbit S5 Lane C′ honesty contracts (#233)
- ✅ test(eval-scoring): lock Family H C' honesty and score_bundle emission (#233)
- ✅ test(eval-scoring): lock score_bundle Lane C' opt-in path (#233)
- ✅ test(eval-lane-c): lock Slice 4 judge wiring and promo immunity (#233)
- ✅ test(eval-lane-c): lock pinned judge parse and transport contracts (#233)
- ✅ test(eval-lane-c): lock advisory score and skip contracts (#233)
- ✅ test(eval-lane-c): lock gold-blind judge input contracts (#233)
- ✅ test(eval-lane-c): lock C-PACK identity and runner contracts (#233)

### Fixed

- ✨ feat(eval-lane-c): wire Slice 6 residuals into runner exports (#233)
- ✨ feat(eval-lane-c): add dirty-overlay provenance guard (#233)
- ✨ feat(eval-lane-c): add Slice 6 residual diagnostics module (#233)
- ✨ feat(eval-lane-c): ship judge_meta_eval_v1 lab Equals path (#233)
- ✨ feat(eval-scoring): emit Family H C' honesty metrics after Lane C (#233)
- ✨ feat(eval-scoring): opt-in gated Lane C' in score_bundle (#233)
- ✨ feat(eval-lane-c): wire pinned judge into gated runner (#233)
- ✨ feat(eval-lane-c): add injectable pinned judge transport (#233)
- ✨ feat(eval-lane-c): add advisory GEval score builders (#233)
- ✨ feat(eval-lane-c): add gold-blind judge input projection (#233)
- ✨ feat(eval-lane-c): wire pinned prompt packs into gated runner (#233)
- ✨ feat(eval-lane-c): add repo-first prompt_pack_v1 identity (#233)
- ✨ feat(eval-scoring): optional Lane C precomputed semantic-cohort gate (#233)
- 🦺 fix(eval-lane-c): fail closed on dirty-overlay activation guards (#233)
- 🦺 fix(eval-lane-c): keep residual diagnostics non-gating and typed (#233)
- 🦺 fix(eval-lane-c): harden meta-eval pins and honest FP/FN rates (#233)
- 🦺 fix(eval-lane-c): keep host-guard rows uninvoked in evidence (#233)
- 🦺 fix(eval-lane-c): normalize forbidden judge-input key variants (#233)
- 🦺 fix(eval-scoring): preserve C′ linkage and post-C honesty metrics (#233)
- 🦺 fix(eval-lane-c): record pack dir and honest judge invocation (#233)
- 🦺 fix(eval-lane-c): harden judge boundary pins and input hygiene (#233)
- 👷 ci(interrogate): gate PRs on changed-file docstring coverage
- 👷 ci(interrogate): add 3.14-pinned docstring coverage contract
- 📝 docs(eval-lane-c): constrain GEval rubrics to gold-blind projection (#233)
- 🔒 fix(eval): share recursive secret-key evidence scrubber (#233)

### Changed

- 🦺 fix(eval-lane-c): fail closed on dirty-overlay activation guards (#233)
- 🦺 fix(eval-lane-c): keep residual diagnostics non-gating and typed (#233)
- 🦺 fix(eval-scoring): preserve C′ linkage and post-C honesty metrics (#233)
- 🦺 fix(eval-lane-c): harden judge boundary pins and input hygiene (#233)
- ♻️ refactor(eval-scripts): freeze legacy Opik setup scripts (#233)
- 👷 ci(interrogate): fail-closed pathspec and pin interrogate 1.7.0 (#233)
- ✅ test(eval-scripts): lock D24 absorption freezes (#233)

### Added

- ✨ feat(eval-lane-c): wire Slice 6 residuals into runner exports (#233)
- ✨ feat(eval-lane-c): add dirty-overlay provenance guard (#233)
- ✨ feat(eval-lane-c): add Slice 6 residual diagnostics module (#233)
- ✨ feat(eval-lane-c): ship judge_meta_eval_v1 lab Equals path (#233)
- ✨ feat(eval-scoring): emit Family H C' honesty metrics after Lane C (#233)
- ✨ feat(eval-scoring): opt-in gated Lane C' in score_bundle (#233)
- ✨ feat(eval-lane-c): wire pinned judge into gated runner (#233)
- ✨ feat(eval-lane-c): add injectable pinned judge transport (#233)
- ✨ feat(eval-lane-c): add advisory GEval score builders (#233)
- ✨ feat(eval-lane-c): add gold-blind judge input projection (#233)
- ✨ feat(eval-lane-c): wire pinned prompt packs into gated runner (#233)
- ✨ feat(eval-lane-c): add repo-first prompt_pack_v1 identity (#233)
- ✨ feat(eval-lane-c): Slice 1 gated cohort spine (authz, availability) (#233)
- ✨ feat(eval-scoring): optional Lane C precomputed semantic-cohort gate (#233)
- 🦺 fix(eval-lane-c): harden meta-eval pins and honest FP/FN rates (#233)
- 🦺 fix(eval-lane-c): record pack dir and honest judge invocation (#233)
- 👷 ci(interrogate): publish validated sticky PR coverage report (#233)
- 👷 ci(interrogate): gate PRs on changed-file docstring coverage
- 👷 ci(interrogate): add 3.14-pinned docstring coverage contract
- 🔒 fix(eval): share recursive secret-key evidence scrubber (#233)

### Security

- 🔒 fix(eval): share recursive secret-key evidence scrubber (#233)

## v0.20.0

### Miscellaneous

- 🧪 test(eval-mirror): align proof cmd and monkeypatch fixture (#232)
- 🔧 chore(coverage): measure retired compile_opik_dataset under scripts/ (#232)
- 📝 docs(llms): auto-update llms.txt
- 📝 Add docstrings to `evals/232-non-blocking-opik-mirror-owner-corpus-lake`
- Merge pull request #236 from Thomo1318/evals/232-non-blocking-opik-mirror-owner-corpus-lake

### Changed

- 🔒️ fix(eval-mirror): R14 redaction ladder with scrub quarantine (#217)
- ✨ feat(eval-mirror): durable queue rows with claim/lease recovery (#232)
- ✨ feat(eval-mirror): freeze export_batch_v1 envelope + wire size law (#232)
- ✨ feat(eval-mirror): export_batch_v1 builder + Layer-A export queue (#217)
- ✨ feat(eval-mirror): add git_cg_opik_config_v1 resolution (#217)
- 🦺 fix(eval-mirror): preserve multi-item traces and generator notes (#232)
- 🧪 test(eval-mirror): align proof cmd and monkeypatch fixture (#232)

### Documentation

- ✨ feat(eval-mirror): export Slice 3 batch/queue/payload surfaces (#232)
- 🦺 fix(eval-mirror): close CodeRabbit doc/security/count findings (#232)
- 📝 docs(eval-mirror): freeze S4 final verification matrix (#232)
- 📝 docs(eval-mirror): restore contract-grade docstrings after CodeRabbit (#232)
- 📝 docs(eval-mirror): publish S4 claim-evidence matrix (#232)
- 📝 docs(eval-mirror): mark compile_opik_dataset absorption complete (#232)
- 📝 docs(eval-mirror): document S4 mirror bounds and Q18 train law (#232)

### Tests

- 🔒️ fix(eval-mirror): R14 redaction ladder with scrub quarantine (#217)
- ✨ feat(eval-mirror): add nested export queue operations (#232)
- ✨ feat(eval-mirror): add fail-open build_export_plan join (#232)
- ✨ feat(eval-mirror): harden authoritative score projections (#232)
- ✨ feat(eval-mirror): Q18 single-dataset owner train projection (#232)
- ✨ feat(eval-mirror): typed ExperimentPins + same-second name guard (#232)
- ✨ feat(eval-mirror): drain claimed rows via verified payload artifacts (#232)
- ✨ feat(eval-mirror): durable queue rows with claim/lease recovery (#232)
- ✨ feat(eval-mirror): freeze export_batch_v1 envelope + wire size law (#232)
- ✨ feat(eval-mirror): add content-addressed export payload store (#232)
- ✨ feat(eval-mirror): recursive R14 scrub + authority surface retain (#232)
- ✨ feat(eval-mirror): gate owner R14 profiles behind export pin (#232)
- ✨ feat(eval-mirror): re-freeze git_cg_opik_config_v1 + lane resolution (#232)
- ✨ feat(eval): add export queue drain CLI (#217)
- ✨ feat(eval-mirror): project bundle, session twin, score card to Opik (#217)
- ✨ feat(eval-mirror): experiment_v1 naming + full pin set (#217)
- ✨ feat(eval-mirror): transport protocol, lazy Opik SDK, error classes (#217)
- ✨ feat(eval-mirror): add mirror runtime secret resolution (#217)
- ✨ feat(eval-mirror): export_batch_v1 builder + Layer-A export queue (#217)
- ✨ feat(eval-mirror): add git_cg_opik_config_v1 resolution (#217)
- 🦺 fix(eval-mirror): close CodeRabbit doc/security/count findings (#232)
- 🦺 fix(ci): install betterleaks for live redaction scrub health (#232)
- 🦺 fix(eval-mirror): honest drain marks and safe train overlap checks (#232)
- 🦺 fix(eval-mirror): retain train labels and source-first session join (#232)
- 🦺 fix(eval-mirror): keep TLS default on unknown boolean env tokens (#232)
- 🦺 fix(eval-mirror): hash non-hex experiment collision suffixes (#232)
- 🦺 fix(eval-mirror): never reset live queue rows on re-enqueue (#232)
- 🦺 fix(eval-mirror): project export_batch envelopes onto Opik traces (#232)
- 🦺 fix(eval-mirror): surface invalid OPIK mode as config_error (#232)
- 🦺 fix(eval-mirror): retire compile_opik_dataset live upload path (#232)
- 🦺 fix(eval-mirror): classify transport and bound secret-safe flush (#232)
- 🦺 fix(eval-mirror): refuse unresolved git SHA on network export (#232)
- 🦺 fix(eval-mirror): drop invented self_hosted_noauth key bypass (#232)
- 🦺 fix(eval-mirror): repair invalid except syntax in resolve_git_sha (#232)
- ✅ test(eval-mirror): harden path restore and thread asserts (#232)
- ✅ test(eval-cli): lock config/export status/retry/drain branch contracts (#232)
- ✅ test(eval-mirror): close PR patch gaps across S4 library modules (#232)
- ✅ test(eval-mirror): cover retired compile script via importable path (#232)
- ✅ test(eval): rematerialize schema_pack pin after payload_ref freeze (#232)
- ✅ test(eval-mirror): prove redact→drain composition and fail-open (#232)
- ✅ test(eval): rematerialize schema_pack pin after export schema freeze (#232)
- ✅ test(eval): rematerialize schema_pack pin after opik_config freeze (#232)
- 📝 docs(eval-mirror): restore contract-grade docstrings after CodeRabbit (#232)

### Fixed

- ✨ feat(eval-mirror): add nested export queue operations (#232)
- ✨ feat(eval-mirror): add fail-open build_export_plan join (#232)
- ✨ feat(eval-mirror): harden authoritative score projections (#232)
- ✨ feat(eval-mirror): Q18 single-dataset owner train projection (#232)
- ✨ feat(eval-mirror): typed ExperimentPins + same-second name guard (#232)
- ✨ feat(eval-mirror): drain claimed rows via verified payload artifacts (#232)
- ✨ feat(eval-mirror): durable queue rows with claim/lease recovery (#232)
- ✨ feat(eval-mirror): freeze export_batch_v1 envelope + wire size law (#232)
- ✨ feat(eval-mirror): add content-addressed export payload store (#232)
- ✨ feat(eval-mirror): recursive R14 scrub + authority surface retain (#232)
- ✨ feat(eval-mirror): gate owner R14 profiles behind export pin (#232)
- ✨ feat(eval-mirror): re-freeze git_cg_opik_config_v1 + lane resolution (#232)
- ✨ feat(eval-mirror): add MirrorResult dual-axis result channel (#232)
- ✨ feat(eval): add export queue drain CLI (#217)
- ✨ feat(eval-mirror): project bundle, session twin, score card to Opik (#217)
- ✨ feat(eval-mirror): experiment_v1 naming + full pin set (#217)
- ✨ feat(eval-mirror): transport protocol, lazy Opik SDK, error classes (#217)
- ✨ feat(eval-mirror): add mirror runtime secret resolution (#217)
- 🦺 fix(eval-mirror): close CodeRabbit doc/security/count findings (#232)
- 🦺 fix(eval-mirror): preserve multi-item traces and generator notes (#232)
- 🦺 fix(ci): install betterleaks for live redaction scrub health (#232)
- 🦺 fix(eval-mirror): honest drain marks and safe train overlap checks (#232)
- 🦺 fix(eval-mirror): retain train labels and source-first session join (#232)
- 🦺 fix(eval-mirror): keep TLS default on unknown boolean env tokens (#232)
- 🦺 fix(eval-mirror): hash non-hex experiment collision suffixes (#232)
- 🦺 fix(eval-mirror): never reset live queue rows on re-enqueue (#232)
- 🦺 fix(eval-mirror): project export_batch envelopes onto Opik traces (#232)
- 🦺 fix(eval-mirror): surface invalid OPIK mode as config_error (#232)
- 🦺 fix(eval-mirror): retire compile_opik_dataset live upload path (#232)
- 🦺 fix(eval-mirror): classify transport and bound secret-safe flush (#232)
- 🦺 fix(eval-mirror): refuse unresolved git SHA on network export (#232)
- 🦺 fix(eval-mirror): drop invented self_hosted_noauth key bypass (#232)
- 🦺 fix(eval-mirror): repair invalid except syntax in resolve_git_sha (#232)
- ✅ test(eval): rematerialize schema_pack pin after payload_ref freeze (#232)

### Security

- 🔒️ fix(eval-mirror): R14 redaction ladder with scrub quarantine (#217)
- ✨ feat(eval-mirror): recursive R14 scrub + authority surface retain (#232)
- ✨ feat(eval-mirror): gate owner R14 profiles behind export pin (#232)
- ✨ feat(eval-mirror): re-freeze git_cg_opik_config_v1 + lane resolution (#232)
- 🦺 fix(ci): install betterleaks for live redaction scrub health (#232)
- 🦺 fix(eval-mirror): keep TLS default on unknown boolean env tokens (#232)
- 🦺 fix(eval-mirror): retire compile_opik_dataset live upload path (#232)
- 🦺 fix(eval-mirror): classify transport and bound secret-safe flush (#232)
- 🦺 fix(eval-mirror): drop invented self_hosted_noauth key bypass (#232)

### Added

- ✨ feat(eval-mirror): add nested export queue operations (#232)
- ✨ feat(eval-mirror): add fail-open build_export_plan join (#232)
- ✨ feat(eval-mirror): harden authoritative score projections (#232)
- ✨ feat(eval-mirror): Q18 single-dataset owner train projection (#232)
- ✨ feat(eval-mirror): typed ExperimentPins + same-second name guard (#232)
- ✨ feat(eval-mirror): export Slice 3 batch/queue/payload surfaces (#232)
- ✨ feat(eval-mirror): drain claimed rows via verified payload artifacts (#232)
- ✨ feat(eval-mirror): durable queue rows with claim/lease recovery (#232)
- ✨ feat(eval-mirror): freeze export_batch_v1 envelope + wire size law (#232)
- ✨ feat(eval-mirror): add content-addressed export payload store (#232)
- ✨ feat(eval-mirror): recursive R14 scrub + authority surface retain (#232)
- ✨ feat(eval-mirror): gate owner R14 profiles behind export pin (#232)
- ✨ feat(eval-mirror): re-freeze git_cg_opik_config_v1 + lane resolution (#232)
- ✨ feat(eval-mirror): add MirrorResult dual-axis result channel (#232)
- ✨ feat(eval-mirror): add closed ExportHealth §18.7 vocabulary (#232)
- ✨ feat(eval): add export queue drain CLI (#217)
- ✨ feat(eval-mirror): project bundle, session twin, score card to Opik (#217)
- ✨ feat(eval-mirror): experiment_v1 naming + full pin set (#217)
- ✨ feat(eval-mirror): transport protocol, lazy Opik SDK, error classes (#217)
- ✨ feat(eval-mirror): add mirror runtime secret resolution (#217)
- ✨ feat(eval-mirror): export_batch_v1 builder + Layer-A export queue (#217)
- ✨ feat(eval-mirror): add git_cg_opik_config_v1 resolution (#217)
- 🦺 fix(eval-mirror): classify transport and bound secret-safe flush (#232)
- 🦺 fix(eval-mirror): refuse unresolved git SHA on network export (#232)

## v0.19.0

### Added

- ✨ feat(eval-binding): add S3 accept-path final-bytes binder core (#231)
- ✨ feat(eval-binding): bind accept-path final bytes into ape_bundle_v1 (#231)
- ✨ feat(eval-cli): add thin git-cg eval corpus-helper sub-app (#231)
- ✨ feat(eval-binding): add D3/D10 trajectory evidence emitter (#231)
- ✨ feat(eval-scoring): wire Family H trajectory completeness sink (#231)
- ✨ feat(eval-binding): add D12/M7 message_versions hooks (#231)
- ✨ feat(eval-binding): add R13 commit_session_thread_v1 twin (#231)
- ✨ feat(eval-binding): wire accept-path emit hook into record-telemetry (#231)

### Fixed

- 🦺 fix(eval-scoring): preserve stored hash authority and card precedence (#231)
- 🦺 fix(eval-binding): stop false opik_export and path-sliced traj ids (#231)
- 🦺 fix(eval-binding): harden authority meta and Layer-A I/O (#231)
- 🦺 fix(eval-scoring): validate Family H trajectory shapes (#231)
- 🦺 fix(eval): harden S3 hash authority and trajectory completeness (#231)
- 🦺 fix(eval): resolve S2b residual pyright debt (#225)

### Changed

- ♻️ refactor(main): compute classify_edit once for telemetry (#231)

### Tests

- ✅ test(eval-binding): pin S3 accept-path binder contract (#231)
- ✅ test(eval-binding): pin S3 accept-path binder contract locks (#231)
- 🧪 test(eval): close S3 binding/CLI/Family H patch coverage gaps (#231)

### Documentation

- 📝 docs(eval): document S3 binding boundary and Layer-A capture law (#231)
- 📝 docs(eval): correct S3 CLI path; isolate encode-fixture cwd (#231)
- 📝 docs(eval): restore gold-standard S3 contract docstrings (#231)

### Miscellaneous

- 📝 Add docstrings to `evals/231-s3-binding`
- 📝 docs(llms): auto-update llms.txt
- Merge pull request #234 from Thomo1318/evals/231-s3-binding

## v0.18.0

### Miscellaneous

- 📝 Add docstrings to `evals/229-s2c-implement-family-i-topology-and-lifecycle-validators`
- 📝 docs(llms): auto-update llms.txt
- Merge pull request #230 from Thomo1318/evals/229-s2c-implement-family-i-topology-and-lifecycle-validators

### Documentation

- 🦺 fix(eval): strip session_thread_id at the encode boundary (#229)
- 🦺 fix(eval): harden Family I topology order and fingerprints (#229)
- ✅ test(eval): prove S2c N12 matrix and S2C-A–H claims (#229)
- 📝 docs(eval): mark S2b shipped and short-circuit envelope validate (#229)
- 📝 docs(eval): restore S2c runner and gate contract docs (#229)
- 📝 docs(eval): document S2c Family I topology validators (#229)

### Tests

- ✅ test(eval): lock Family I review-hardening and recovery paths (#229)
- ✅ test(eval): prove S2c N12 matrix and S2C-A–H claims (#229)
- ✅ test(eval): lock S2c Family I, gate union, and thread index (#229)

### Fixed

- 🦺 fix(eval): strip session_thread_id at the encode boundary (#229)
- 🦺 fix(eval): harden Family I topology order and fingerprints (#229)

### Added

- ✨ feat(eval): wire S2c topology gates and suite thread index (#229)
- ✨ feat(eval): add Family I topology/lifecycle scores (#229)

## v0.17.0

### Miscellaneous

- 🔧 chore(eval): demote legacy Opik format metrics to advisory (#227)
- 📝 docs(llms): auto-update llms.txt
- Merge pull request #228 from Thomo1318/evals/227-S2b-complete-product-authority-metrics-and-harden-offline-scoring

### Fixed

- ✨ feat(eval): wire S2b runner, H bundle row, and 68-ID block (#227)
- ✨ feat(eval): fan out remaining Family D gold-code metrics (#227)
- ✨ feat(eval): add shared gold slot and honest path evidence (#227)
- 🦺 fix(eval): count real gold calls; filter H injection keys (#227)
- 🦺 fix(eval): accept real Git paths; drop dead Family F work (#227)
- 🦺 fix(eval): tighten Family E banned-opener and skeleton checks (#227)
- 🦺 fix(eval): match Family C gates by exact product codes (#227)
- ✅ test(eval): harden S2b gate neutrals and patch-coverage locks (#227)
- ⚡ fix(eval): cache Family G policy/SOP audits; target SOP writes (#227)

### Tests

- ✅ test(eval): harden S2b gate neutrals and patch-coverage locks (#227)
- ✅ test(eval): lock S2b C/E/F/G fail-closed patch branches (#227)
- ✅ test(eval): lock S2b CodeRabbit hardenings offline (#227)
- 🔧 chore(eval): demote legacy Opik format metrics to advisory (#227)
- ✅ test(eval): lock S2b C/E/F/G, shared gold, and gate law (#227)

### Documentation

- 📝 docs(eval): compile S2b T1–T12 locks into harness plan v0.9.3 (#227)

### Changed

- ✨ feat(eval): wire S2b runner, H bundle row, and 68-ID block (#227)
- 🦺 fix(eval): count real gold calls; filter H injection keys (#227)
- 🦺 fix(eval): accept real Git paths; drop dead Family F work (#227)
- 🦺 fix(eval): tighten Family E banned-opener and skeleton checks (#227)
- ⚡ fix(eval): cache Family G policy/SOP audits; target SOP writes (#227)

### Added

- ✨ feat(eval): wire S2b runner, H bundle row, and 68-ID block (#227)
- ✨ feat(eval): add Families C/E/F/G product-authority scores (#227)
- ✨ feat(eval): fan out remaining Family D gold-code metrics (#227)
- ✨ feat(eval): add shared gold slot and honest path evidence (#227)

## v0.16.0

### Miscellaneous

- 📝 Add docstrings to `eval/225-s2a-offline-score-runner`
- 📝 docs(llms): auto-update llms.txt
- Merge pull request #226 from Thomo1318/eval/225-s2a-offline-score-runner

### Documentation

- 📝 docs(eval): extend DEVELOPMENT contracts to S0–S2a (#225)
- 📝 docs(eval): complete S2a scoring package docstring coverage (#225)
- 📝 docs(eval): document S2a offline Plane A score runner (#225)

### Tests

- 🦺 fix(eval): reject divergent suite_path snapshot pins (#225)
- 🦺 fix(eval): require skeleton row for golden promotion (#225)
- 🦺 fix(eval): preserve gold build errors on strict_fail_set (#225)
- 🦺 fix(eval): measure selected scored target for FIND-026 (#225)
- ✅ test(eval): lock S2a scoring package edge coverage offline (#225)
- ✅ test(eval): lock S2a score runner and gate law offline (#225)

### Fixed

- 🦺 fix(eval): reject divergent suite_path snapshot pins (#225)
- 🦺 fix(eval): require skeleton row for golden promotion (#225)
- 🦺 fix(eval): preserve gold build errors on strict_fail_set (#225)
- 🦺 fix(eval): measure selected scored target for FIND-026 (#225)

### Added

- ✨ feat(eval): add S2a offline Plane A score runner (#225)

## v0.15.0

### Miscellaneous

- 📝 docs(llms): auto-update llms.txt
- Merge pull request #224 from Thomo1318/evals/223-encode-offline-fixtures-as-ape_bundle_v1

### Fixed

- 🦺 fix(eval): harden S1 corpus encoder from CodeRabbit review (#223)

### Tests

- ✨ feat(eval): materialize checked-in ape_bundle goldens (#223)
- ✨ feat(eval): fail closed on topology and split seed probes (#223)
- 🦺 fix(eval): harden S1 corpus encoder from CodeRabbit review (#223)
- ✅ test(eval): lock corpus package edge coverage offline (#223)
- ✅ test(fixtures): expand 204-archive offline ramp seeds (#223)
- ✅ test(eval): lock corpus encoder, isolation, and snapshots (#223)
- ✅ test(fixtures): pin S1 seed matrix and core suite (#223)
- 📝 docs(eval): add fixture index and archive golden workflows (#223)

### Documentation

- ✨ feat(eval): materialize checked-in ape_bundle goldens (#223)
- 🦺 fix(eval): harden S1 corpus encoder from CodeRabbit review (#223)
- ✅ test(fixtures): expand 204-archive offline ramp seeds (#223)
- ✅ test(fixtures): pin S1 seed matrix and core suite (#223)
- 📝 docs(dev): point offline eval section at S0–S1 corpus (#223)
- 📝 docs(eval): add fixture index and archive golden workflows (#223)
- 📝 docs(eval): document S1 fixture encoder and seed boundary (#223)

### Added

- ✨ feat(eval): materialize checked-in ape_bundle goldens (#223)
- ✨ feat(eval): add offline corpus encoder for ape_bundle_v1 (#223)
- 📝 docs(eval): add fixture index and archive golden workflows (#223)

### Changed

- ✨ feat(eval): fail closed on topology and split seed probes (#223)

## v0.14.0

### Miscellaneous

- 📝 docs(llms): auto-update llms.txt
- 📝 docs(eval): document dual-axis pins and hash recipe (#220)
- Merge pull request #222 from Thomo1318/evals/220-freeze-schema-pack-metric-catalog-pins

### Documentation

- 📝 docs(development): link offline S0 eval contracts (#220)
- 📝 docs(eval): document dual-axis pins and hash recipe (#220)

### Tests

- 🥅 fix(eval): harden S0 pin, isolation, and export contracts (#220)
- ✅ test(eval): lock schema_pack loader error and cache branches (#220)
- ✅ test(eval): lock S0 schema pack and catalog pins offline (#220)

### Changed

- 🥅 fix(eval): close residual CodeRabbit S0 contract gaps (#220)

### Fixed

- 🥅 fix(eval): close residual CodeRabbit S0 contract gaps (#220)
- 🥅 fix(eval): harden S0 pin, isolation, and export contracts (#220)

### Build

- 🥅 fix(eval): close residual CodeRabbit S0 contract gaps (#220)

### Added

- ✨ feat(eval): add offline contract package and metric catalog (#220)
- ✨ feat(schemas): freeze offline eval schema pack v0 (#220)

## v0.13.2

### Miscellaneous

- 📝 docs(llms): auto-update llms.txt
- Merge pull request #221 from Thomo1318/docs/quality-failure-analysis-package
- 🔧 chore(agents): trust comet-ml and register Opik skills

### Documentation

- 📝 docs(plans): mark §14 filing gate complete (#217)
- 📝 docs(skill): require graph-first skill exploration (#204)
- 📝 docs(cases): close #204 case SSOT and markdown hygiene (#204)
- 📝 docs(quality): align prevention IDs and promotion gates (#204)
- 📝 docs(quality): harden message-only rewrite controls (#204)
- 📝 docs(quality): point package indexes at Session 12 SSOT (#204)
- 📝 docs(quality): add failure-analysis-package agent skill (#204)
- 📝 docs(quality): close Session 12 promotion indexes (#204)
- 📝 docs(quality): promote Session 12 post-control dogfood G2–G4 (#204)
- 📝 docs(quality): promote Session 12 G4 Regime B gold-miss case (#204)
- 📝 docs(quality): promote Session 12 G3 Regime B gold-miss case (#204)
- 📝 docs(quality): promote Session 12 G2 Regime B gold-miss case (#204)
- 📝 docs(quality): point #204 and #217 at gold-miss package SSOT (#204)
- 📝 docs(quality): promote Session 12 residual series synthesis (#204)
- 📝 docs(quality): promote Session 12 G1 Regime A gold-miss case (#204)
- 📝 docs(quality): record Regime B self-dogfood on package landing (#204)
- 📝 docs(quality): scaffold case shelves and plans catalogue pointer (#204)
- 📝 docs(quality): pin gold envelope, F72–F80 taxonomy, and P-S12 backlog (#204)
- 📝 docs(quality): add gold-miss operator process runbooks (#204)
- 📝 docs(quality): add Session 12 gold-miss METHOD and case templates (#204)
- 📝 docs(plans): ingest #217 body residual (#217)
- 📝 docs(plans): promote Opik evaluation harness SSOT from scratch (#217)

## v0.13.1

### Miscellaneous

- 📝 docs(llms): auto-update llms.txt
- Merge pull request #215 from Thomo1318/fix/214-docs-only-gold-strict-craft-avoids-skeleton-fallback

### Fixed

- 🦺 fix(commit-quality): narrow extended body craft emission to Provides/Includes (#214)
- 🦺 fix(main): preserve security-noun repair operator copy (#214)
- 🦺 fix(commit-quality): lock punctuated openers and extended body craft (#214)
- 🦺 fix(commit-quality): broaden craft-verb catalogue for docs/tests (#214)
- 🦺 fix(commit-quality): docs-only craft repair avoids skeleton fallback (#214)

### Tests

- 🦺 fix(commit-quality): narrow extended body craft emission to Provides/Includes (#214)
- 🦺 fix(commit-quality): lock punctuated openers and extended body craft (#214)
- 🦺 fix(commit-quality): broaden craft-verb catalogue for docs/tests (#214)
- 🦺 fix(commit-quality): docs-only craft repair avoids skeleton fallback (#214)
- ✅ test(acceptpath): freeze docs-only post-repair COMMIT_EDITMSG snapshot (#214)

### Documentation

- ✅ test(acceptpath): freeze docs-only post-repair COMMIT_EDITMSG snapshot (#214)
- 📝 docs(docs): note #214 craft catalogue and post-repair snapshot (#214)
- 📝 docs(docs): document changelog for commit-quality fixes (#214)

## v0.13.0

### Miscellaneous

- ✅ test(promptfoo): harden Slice 9 ban assertion contracts (#213)
- ✅ test(commit-quality): add V12-A named proof pack a01–a45 (#204)
- ✅ test(fixtures): pin Session 6 corpus rows TIP-G13–G17 (#204)
- 📝 docs(usage): mark preflight PATHS optional and repeatable (#204)
- 📝 docs(llms): auto-update llms.txt
- Merge pull request #213 from Thomo1318/refactor/204-commit-presentation-quality
- Add Promptfoo Code Scan workflow (#210)

### Fixed

- ✨ feat(gitmoji-norm): add shared VS/confusable normaliser (#204)
- ✨ feat(commit-quality): add Session 6 scope, capability, and guard laws (#204)
- ✨ feat(commit_quality): parse validate and apply CommitBlueprint (#204)
- ✨ feat(main): wire contract lifecycle observability end-to-end (#204)
- ✨ feat(regeneration): evaluate locked contract lifecycle snapshot (#204)
- ✨ feat(telemetry): add contract lifecycle closed-vocab fields (#204)
- ✨ feat(main): wire low-confidence presentation posture (#204)
- ✨ feat(commit-quality): add low-confidence presentation posture (#204)
- ✨ feat(telemetry): add closed presentation fallback reason (#204)
- ✨ feat(presentation): wire overlay and changelog anti-signal (#204)
- 🦺 fix(commit-gold): ignore orphan breaking descriptions (#212)
- 🦺 fix(acceptpath): contain pack paths and clarify LMLX parity (#212)
- 🦺 fix(gitmoji-norm): reject empty normalised equivalence operands (#213)
- 🦺 fix(commit-quality): lean stub fill to missing test/docs families (#204)
- 🦺 fix(commit-gold): ignore rationale in path-class wording (#204)
- 🦺 fix(main): preserve blueprint rejection control flow (#204)
- 🦺 fix(commit-quality): clear breaking flags after SemVer demotion (#204)
- 🦺 fix(commit-gold): scope final truth checks to rendered wording (#204)
- 🦺 fix(ci): exclude Lob detector and pin blueprint help width (#204)
- 🦺 fix(commit-quality): auto-repair security-noun guard failures (#204)
- 🦺 fix(telemetry): handle betterleaks non-zero exit codes (#212)
- 🦺 fix(main): enforce standard git for analysis path (#212)
- 🦺 fix(commit-gold): fail skeleton fallback and path-class product framing (#204)
- 🦺 fix(commit-quality): force fixtures into the test-family envelope (#204)
- 🦺 fix(intent): quarantine product markers on pure non-product diffs (#204)
- 🦺 fix(scope-canon): report none for identity scope normalisation (#204)
- 🦺 fix(sentry): emit commit_plan_contract_violation with closed tags (#204)
- 🦺 fix(main): wire contract-lift telemetry after presentation (#204)
- 🦺 fix(regeneration): lift plan SemVer to locked contract floor (#204)
- 🦺 fix(commit-gold): tolerate legal presentation overlay fields (#204)
- ♻️ refactor(intent): unify product-marker quarantine policy (#204)
- ✅ test(commit_quality): cover high-risk checklist injection (#204)
- 🔊 chore(telemetry): track blueprint_applied without payload leakage (#204)

### Tests

- ✨ feat(commit-gold): lint breaking compatibility contradictions (#212)
- ✨ feat(gitmoji-norm): add shared VS/confusable normaliser (#204)
- ✨ feat(main): add read-only diff-class preflight command (#204)
- ✨ feat(commit-gold): lint missing high-risk theme coverage (#204)
- ✨ feat(commit-quality): hard-merge stubs into multi-surface secondaries (#204)
- ✨ feat(scope-canon): export shared scope canon helpers (#204)
- ✨ feat(hooks): add GIT_CG_SKIP_PREPARE for message-only rebuilds (#204)
- ✨ feat(main): wire low-confidence presentation posture (#204)
- ✨ feat(telemetry): add closed presentation fallback reason (#204)
- ✨ feat(commit-quality): seed included-change stub inventory (#204)
- ✨ feat(commit-quality): apply path-class presentation overlay (#204)
- ✨ feat(commit-quality): derive path-class presentation priors (#204)
- ✨ feat(scope-canon): normalise product scopes before render (#204)
- 🦺 fix(commit-gold): ignore orphan breaking descriptions (#212)
- 🦺 fix(acceptpath): contain pack paths and clarify LMLX parity (#212)
- 🦺 fix(gitmoji-norm): reject empty normalised equivalence operands (#213)
- 🦺 fix(commit-quality): lean stub fill to missing test/docs families (#204)
- 🦺 fix(commit-gold): ignore rationale in path-class wording (#204)
- 🦺 fix(main): preserve blueprint rejection control flow (#204)
- 🦺 fix(commit-quality): clear breaking flags after SemVer demotion (#204)
- 🦺 fix(commit-gold): scope final truth checks to rendered wording (#204)
- 🦺 fix(ci): exclude Lob detector and pin blueprint help width (#204)
- 🦺 fix(commit-quality): auto-repair security-noun guard failures (#204)
- 🦺 fix(telemetry): handle betterleaks non-zero exit codes (#212)
- 🦺 fix(main): enforce standard git for analysis path (#212)
- 🦺 fix(commit-gold): fail skeleton fallback and path-class product framing (#204)
- 🦺 fix(commit-quality): force fixtures into the test-family envelope (#204)
- 🦺 fix(intent): quarantine product markers on pure non-product diffs (#204)
- 🦺 fix(scope-canon): report none for identity scope normalisation (#204)
- 🦺 fix(regeneration): lift plan SemVer to locked contract floor (#204)
- 🦺 fix(commit-gold): tolerate legal presentation overlay fields (#204)
- ♻️ refactor(intent): unify product-marker quarantine policy (#204)
- ✅ test(promptfoo): require feat headers for TIP-G10/G11 (#204)
- ✅ test(acceptpath): share bakeoff fixture pack helpers (#212)
- ✅ test(acceptpath): complete informational LMLX artifact parity (#212)
- ✅ test(promptfoo): harden Slice 9 ban assertion contracts (#213)
- ✅ test(security): require exact TruffleHog extra_args tokens (#204)
- ✅ test(promptfoo): lock live-LLM cases A-N for Slice 9 (#204)
- ✅ test(ci): harden blueprint help and Lob exclude locks (#204)
- ✅ test(commit-quality): harden presentation harness contracts (#204)
- ✅ test(acceptpath): cover path-harvest characterisation matrix (#212)
- ✅ test(fixtures): add accept-path dogfood fixtures (#212)
- ✅ test(fixtures): pin fixture paths to the test/NONE corpus envelope (#204)
- ✅ test(telemetry): cover D26 presentation main-path wiring (#204)
- ✅ test(commit-quality): wire Slice 9 A-N and S9-E/H gate coverage (#204)
- ✅ test(guards): cover Slice 8 harvest guards skeleton and shared budget (#204)
- ✅ test(blueprint): cover Slice 7 schema parse apply and CLI surface (#204)
- ✅ test(commit_quality): cover high-risk checklist injection (#204)
- ✅ test(contract-lifecycle): cover Slice 5.5 lifecycle and Sentry guards (#204)
- ✅ test(commit-quality): freeze presentation corpus under tip-law goldens (#204)
- 📝 docs(fixtures): pin Slice 9 A-N eval harness and S9 goldens (#204)

### Documentation

- ✨ feat(main): add read-only diff-class preflight command (#204)
- ✨ feat(telemetry): wire D26 presentation fields and operator docs (#204)
- ✨ feat(main): inject high-risk checklist into system prompt (#204)
- 🦺 fix(acceptpath): contain pack paths and clarify LMLX parity (#212)
- 🦺 fix(main): enforce standard git for analysis path (#212)
- 🦺 fix(scope-canon): report none for identity scope normalisation (#204)
- ✅ test(acceptpath): share bakeoff fixture pack helpers (#212)
- ✅ test(fixtures): add accept-path dogfood fixtures (#212)
- ✅ test(fixtures): pin fixture paths to the test/NONE corpus envelope (#204)
- ✅ test(commit_quality): cover high-risk checklist injection (#204)
- ✅ test(contract-lifecycle): cover Slice 5.5 lifecycle and Sentry guards (#204)
- ✅ test(commit-quality): freeze presentation corpus under tip-law goldens (#204)
- 📝 docs(usage): mark preflight PATHS optional and repeatable (#204)
- 📝 docs(readme): correct the usage guide link (#204)
- 📝 docs(readme): document F80 GIT_CG_SKIP_PREPARE operator contract (#204)
- 📝 docs(readme): document Session 6 residuals and V12-A proof pack (#204)
- 📝 docs(readme): refresh TOC for presentation-quality guide (#204)
- 📝 docs(fixtures): pin Slice 9 A-N eval harness and S9 goldens (#204)
- 📝 docs(usage): document --blueprint on root and commit (#204)
- 📝 docs(commit-quality): mark Slice 5.5 committed and point to Session 6 (#204)

### Changed

- ✨ feat(commit-gold): lint breaking compatibility contradictions (#212)
- ✨ feat(gitmoji-norm): add shared VS/confusable normaliser (#204)
- ✨ feat(commit-gold): lint missing high-risk theme coverage (#204)
- ✨ feat(commit-quality): hard-merge stubs into multi-surface secondaries (#204)
- ✨ feat(scope-canon): export shared scope canon helpers (#204)
- ✨ feat(telemetry): wire D26 presentation fields and operator docs (#204)
- ✨ feat(main): wire claim harvest and shared-budget presentation guards (#204)
- ✨ feat(main): wire --blueprint through generation and telemetry (#204)
- ✨ feat(main): wire contract lifecycle observability end-to-end (#204)
- ✨ feat(main): wire scope canon and presentation priors into context (#204)
- 🦺 fix(ci): exclude Lob detector and pin blueprint help width (#204)
- 🦺 fix(main): wire contract-lift telemetry after presentation (#204)
- ♻️ refactor(intent): unify product-marker quarantine policy (#204)
- ✅ test(commit-quality): freeze presentation corpus under tip-law goldens (#204)
- 🔊 chore(telemetry): track hallucination_guard_fired without payloads (#204)
- 🔊 chore(telemetry): track blueprint_applied without payload leakage (#204)

### Added

- ✨ feat(main): add read-only diff-class preflight command (#204)
- ✨ feat(hooks): add GIT_CG_SKIP_PREPARE for message-only rebuilds (#204)
- ✨ feat(commit-quality): add Session 6 scope, capability, and guard laws (#204)
- ✨ feat(telemetry): wire D26 presentation fields and operator docs (#204)
- ✨ feat(commit_quality): add Slice 9 ordered pure gate evaluator (#204)
- ✨ feat(main): wire claim harvest and shared-budget presentation guards (#204)
- ✨ feat(commit_quality): add hallucination craft guards and claim harvest (#204)
- ✨ feat(main): wire --blueprint through generation and telemetry (#204)
- ✨ feat(commit_quality): parse validate and apply CommitBlueprint (#204)
- ✨ feat(models): add frozen CommitBlueprint presentation schema (#204)
- ✨ feat(main): inject high-risk checklist into system prompt (#204)
- ✨ feat(commit_quality): add high-risk body checklist themes (#204)
- ✨ feat(main): wire contract lifecycle observability end-to-end (#204)
- ✨ feat(regeneration): evaluate locked contract lifecycle snapshot (#204)
- ✨ feat(telemetry): add contract lifecycle closed-vocab fields (#204)
- ✨ feat(main): wire low-confidence presentation posture (#204)
- ✨ feat(commit-quality): add low-confidence presentation posture (#204)
- ✨ feat(telemetry): add closed presentation fallback reason (#204)
- ✨ feat(commit-quality): seed included-change stub inventory (#204)
- ✨ feat(presentation): wire overlay and changelog anti-signal (#204)
- ✨ feat(commit-quality): apply path-class presentation overlay (#204)
- ✨ feat(main): wire scope canon and presentation priors into context (#204)
- ✨ feat(commit-quality): derive path-class presentation priors (#204)
- ✨ feat(scope-canon): normalise product scopes before render (#204)
- 🦺 fix(commit-quality): auto-repair security-noun guard failures (#204)
- 🦺 fix(main): wire contract-lift telemetry after presentation (#204)

## v0.12.0

### ✨ Features

- ✨ feat(scoped-hist): add scoped history producers for split and rename (#163)
- ✨ feat(main): wire scoped-history Policy B, Channel-4, and OR-merge (#163)
- ✨ feat(intent): allow Phase 9 structural enrichment markers (#163)
- ✨ feat(semantic): harvest hub and complex callers from payloads (#163)
- ✨ feat(scoped-history): thread preflight group count into split evidence (#163)

### 🐛 Bug Fixes & Refactors

- 🔒 fix(telemetry): redact scoped-history text; coerce enums (#163)
- 🐛 fix(telemetry): preserve scoped-history error signals (#163)
- ♻️ refactor(scoped-history): harden bands and CLI markers (#163)
- 🐛 fix(scoped-history): lock NUL rename parse and fail-open fallbacks (#163)
- 🐛 fix(scoped-history): drop directive verbs from split guidance (#163)
- 🔒️ fix(security): raise SBOM floors for Grype high CVEs (#163)

### 📝 Documentation

- 📝 docs(adr): record scoped reasoning history decisions (#163)
- 📝 docs(adr): accept and index ADR-0163 scoped history (#163)
- 📝 docs(phase9): document Policy B and scoped-history DX (#163)
- 📝 docs(adr): diagram Policy B scoped-history architecture (#163)
- 📝 docs(fixtures): add scoped-history behavior matrix (#163)
- 📝 docs(pr-template): require Mermaid state diagram on every PR

### ✅ Tests

- ✅ test(scoped-history): cover split, rename, structural, fixtures (#163)
- ✅ test(semantic): claim Policy B shadow lifetime and flag-off defaults (#163)
- ✅ test(scoped-history): close Phase 9 coverage and claim gaps (#163)
- ✅ test(scoped-history): lock Phase 9 claims and ADR path (#163)
- ✅ test(scoped-history): lock CLI, public-api, and authority claims (#163)
- ✅ test(config): lock raised SBOM security floors (#163)
- ✅ test(config): parse UV security floors by specifier (#163)

### 🔧 Chores & Internal

- 📝 docs(llms): auto-update llms.txt
- Merge pull request #205 from Thomo1318/refactor/163-scoped-reasoning-history-removal-of-legacy-hacks
- Merge pull request #203 from Thomo1318/docs/pr-template-require-state-diagram

## v0.11.0

### ✨ Features

- ✨ feat(commit_gold): add subject inventory and P6 split guidance (#191)
- ✨ feat(main): bound gold self-correction and add v1.1 telemetry (#191)

### 🐛 Bug Fixes & Refactors

- 🦺 fix(gold): address PR #202 review findings (#191)

### 📝 Documentation

- 📝 docs(usage): document gold linter v1.1 behaviour (#191)

### ✅ Tests

- ✅ test(test_main): add split_preferred flag to gold split test (#191)

### 🔧 Chores & Internal

- 📝 docs(llms): auto-update llms.txt
- Merge pull request #202 from Thomo1318/feat/191-gold-linter-v1.1

## v0.10.0

### Miscellaneous

- ✅ test(main): strip ANSI before usage.kdl help flag checks (#195)
- 📝 docs(tui): correct back-edge direction and harden review tests (#195)
- 📝 docs(tui): document ranking-confidence arbitration flow (#195)
- 📝 docs(cli): surface rank-arbitrate and gold-strict flags (#195)
- 📝 docs(llms): auto-update llms.txt
- Merge pull request #200 from Thomo1318/feat/195-ranking-confidence-arbitration-tui

### Documentation

- 📝 docs(tui): correct back-edge direction and harden review tests (#195)
- 📝 docs(tui): sync arbitration storyboard labels and usage reference (#195)

### Fixed

- ✨ feat(interaction): add GumOutcome probes and confidence status lines (#195)
- 🦺 fix(flags): align empty rank-arbitrate and Sentry DSN precedence (#195)
- 🦺 fix(main): isolate REGEN presentation and gold_blocked source (#195)
- 🥅 fix(interaction): narrow gum cancel and end options with -- (#195)
- 🦺 fix(arbitrate): bound cancel thrash and drop lock asserts (#195)
- 🦺 fix(main): force arbitration abort exit and sync gold_blocked codes (#195)
- 🥅 fix(sentry): ignore host-injected ambient DSN pollution (#195)
- 🥅 fix(tui): dedupe still-Low arbitration status strip (#195)
- 🥅 fix(regeneration): honour locked intent with closed lock_resolution (#195)

### Changed

- 🦺 fix(flags): align empty rank-arbitrate and Sentry DSN precedence (#195)
- 🦺 fix(main): isolate REGEN presentation and gold_blocked source (#195)
- 🦺 fix(arbitrate): bound cancel thrash and drop lock asserts (#195)
- 🦺 fix(main): force arbitration abort exit and sync gold_blocked codes (#195)
- 🦺 fix(commit_gold): enforce SemVer, scope, and title checks (#195)
- 🦺 fix(commit): enforce F7 changelog-group reachability in gold lint (#195)
- ♻️ refactor(ranking): freeze RankingConfidence.reasons as tuple (#195)

### Added

- 🔐 chore(secrets): allowlist GIT_CG_SENTRY_DSN for export (#195)
- ✨ feat(main): wire ranking confidence into generate-path arbitration (#195)
- ✨ feat(arbitrate): add pre-LLM intent arbitration stack (#195)
- ✨ feat(interaction): add GumOutcome probes and confidence status lines (#195)
- ✨ feat(telemetry): persist ranking confidence and gold-mode fields (#195)
- ✨ feat(flags): add ranking arbitration mode resolver (#195)
- ✨ feat(intent): add RankingConfidence policy module (#195)
- 🥅 fix(sentry): ignore host-injected ambient DSN pollution (#195)
- 🥅 fix(regeneration): honour locked intent with closed lock_resolution (#195)

### Security

- 🔐 chore(secrets): allowlist GIT_CG_SENTRY_DSN for export (#195)

## v0.9.0

### Miscellaneous

- 👷 ci(llms): auto-generate root llms.txt map via pinned brief
- ✅ test(semantic): cover Phase 7.5 shadow fail-open and telemetry matrix (#180)
- 📝 docs(semantic): note POSIX hardlinks for shadow clone --local (#180)
- 📝 docs(semantic): record Policy A index-only refresh, R9 template guard (#180)
- 📝 docs(llms): auto-update llms.txt
- 📝 docs(todo): capture backlog research and integration notes
- 📝 docs(tui): add Mermaid TUI storyboard guide for agents
- 📝 docs(dev): document offline Promptfoo eval entrypoint
- 📝 docs(adr): formalise Promptfoo Phase 8.5 metrics boundary
- 📝 docs(templates): add Telemetry sections and relative mermaid paths
- Merge pull request #199 from Thomo1318/feat/180-staged-index-shadow-isolation-for-semantic-refresh
- Merge pull request #198 from Thomo1318/hygiene/repo-docs-telemetry-tui-guide
- Merge pull request #197 from Thomo1318/hotfix/llms-brief-primary-language
- Merge pull request #196 from Thomo1318/docs/llms-txt-brief-ci

### Fixed

- 🚑 fix(ci): drop brief -tracked so llms.txt primary language is Python
- 🥅 fix(semantic): preserve fallback reasons, drop dead shadow root (#180)
- 🥅 fix(semantic): shadow fail-open stages, persist Phase 7.5 telemetry (#180)

### Changed

- 🥅 fix(semantic): preserve fallback reasons, drop dead shadow root (#180)

### Added

- ✨ feat(semantic): fold shadow clone/sync latency into graph build ms (#180)
- ✨ feat(shadow): add shadow_workspace_index_only for Policy A refresh (#180)
- 🥅 fix(semantic): shadow fail-open stages, persist Phase 7.5 telemetry (#180)

## v0.8.0

### Added

- ✨ feat(commit): add --gold-strict CLI flag for gold strict mode (#182)
- ✨ feat(gold): show findings as checklist in interactive review (#182)
- ✨ feat(core): wire gold lint + additive rubric into generation (#182)
- ✨ feat(core): add deterministic commit-message gold linter (#182)
- 🔀 merge(182): Phase 7.25 gold-standard commit message content quality (#182 / #158)

### Fixed

- 🐛 fix(commit_gold): stop single-file diffs failing strict gold checks (#182)
- 🐛 fix(intent): add product negatives to error_handling matrix row (#182)
- 🦺 fix(schema): collapse changelog groups to Miscellaneous taxonomy (#182)
- 🔀 merge(182): Phase 7.25 gold-standard commit message content quality (#182 / #158)

### Miscellaneous

- ✅ test(tests): pin gold surface-mode display before review menu (#182)
- ✅ test(tests): enforce collapsed taxonomy in schema and ranker tests (#182)
- ✅ test(tests): pin gold linter edge cases and harness isolation (#182)
- 📝 docs(mermaid): document error handling and regen lifecycle (#182)
- 📝 docs(pr-template): update PR template with Mermaid diagram guidance (#182)
- 📝 docs(schema): narrow changelog-group collapse to docs and tests (#182)
- 📝 Add docstrings to `feat/182-gold-standard-commit-message-content-quality`
- 🔀 merge(182): Phase 7.25 gold-standard commit message content quality (#182 / #158)

### Changed

- 🦺 fix(schema): collapse changelog groups to Miscellaneous taxonomy (#182)
- ⏪ revert(docstrings): restore normative gold documentation (#182)
- ♻️ refactor(commit_gold): return distinct surface count directly (#182)

### Documentation

- 📝 docs(usage): document gold lint modes and coverage mapping (#182)
- 📝 docs(changelog): restore issue refs on v0.7.0 bullets (#181)

### Tests

- ✨ feat(core): wire gold lint + additive rubric into generation (#182)
- ✨ feat(core): add deterministic commit-message gold linter (#182)
- 🐛 fix(intent): add product negatives to error_handling matrix row (#182)
- ✅ test(changelog): re-anchor #177 entries to v0.6.0 section

## v0.7.1

### 🐛 Bug Fixes

- 🥅 fix(release): harden package version injection contracts (#181)
- 🥅 fix(release): canonical package bump and issue-ref changelog bullets (#181)

### ✅ Tests

- 🥅 fix(release): harden package version injection contracts (#181)
- 🥅 fix(release): canonical package bump and issue-ref changelog bullets (#181)
- ✅ test(docs): bound Unreleased bullets to next version heading (#181)

### Miscellaneous

- Merge pull request #187 from Thomo1318/fix/release-canonical-package-bump-and-issue-refs

## v0.7.0

### ✨ Features

- ✨ feat(release): expand gold-standard release note headings (#181)
- ✨ feat(release): emit gold-standard GitHub release notes (#181)
- 🥅 fix(release): handle release flag validation and errors (#181)

### 💥 Breaking Changes

- 🏗️ refactor(adr): document observability hierarchy and resources
- 🥅 fix(release): normalise gold theme gate and harden section mapping (#181)

### 🐛 Bug Fixes

- ✨ feat(release): expand gold-standard release note headings (#181)
- 🥅 fix(models): keep issue refs contiguous with machine trailers (#181)
- 🥅 fix(release): normalise gold theme gate and harden section mapping (#181)
- 🥅 fix(sop): align changelog_group vocabulary across schema and hooks (#181)
- 🥅 fix(release): fix changelog grouping and priority sorting (#181)
- 🥅 fix(release): strip commit lines in release script (#181)
- 🥅 fix(release): handle unresolved repo slug and docs URL (#181)
- 🥅 fix(release): abort release on repo detection failure (#181)
- 🥅 fix(release): fix changelog regex and defer repo detection (#181)
- 🥅 fix(release): handle release flag validation and errors (#181)
- 🦺 fix(agents): add validation rules for agent skills

### ♻️ Refactors

- 🏗️ refactor(adr): document observability hierarchy and resources

### 📝 Documentation

- 🔖 release: cut v0.7.0 vocabulary contract and gold headings (#181)
- 📝 docs(zensical): add custom site stylesheet polish (#181)
- 📝 docs(mermaid): qualify GitHub renderer limits and option count (#181)
- 📝 docs(mermaid): route capstone FLAGS edge through NOTES_PATH (#181)
- 📝 CodeRabbit Chat: Add Generated Unit Tests for PR Changes
- 📝 Add docstrings to `fix/181-followup-release-notes-vocabulary-gold-headings`
- 📝 docs(review): fix mermaid fences and ADR changelog ordering (#181)
- 📝 docs(changelog): align examples and ADR with closed vocabulary (#181)
- 📝 CodeRabbit Chat: Generate Unit Tests for PR Changes
- 📝 docs(readme): align changelog group labels with SOP taxonomy (#181)
- 📝 docs(usage): reposition Flags under release usage (#181)
- 📝 Add docstrings to `feat/181-gold-standard-release-notes`
- 📝 docs(todo): enforce sd instead of sed in TODO

### ✅ Tests

- ✨ feat(release): expand gold-standard release note headings (#181)
- 🥅 fix(models): keep issue refs contiguous with machine trailers (#181)
- 🥅 fix(release): normalise gold theme gate and harden section mapping (#181)
- 🥅 fix(sop): align changelog_group vocabulary across schema and hooks (#181)
- 🥅 fix(release): fix changelog grouping and priority sorting (#181)
- ✅ test(docs): harden matrix cell and gold-heading assertions (#181)
- ✅ test(bun): strengthen lockfile JSONC and integrity checks (#181)
- ✅ test(release): raise release.py coverage above 80% (#181)
- ✅ test(changelog): update tests for v0.6.0 changelog shift (#181)
- 🎨 style(release): detab bot docstrings and restore ruff/hk hygiene (#181)
- 📝 docs(review): fix mermaid fences and ADR changelog ordering (#181)

### 🎨 Style

- 🎨 style(release): detab bot docstrings and restore ruff/hk hygiene (#181)

### 🏗️ Build & CI

- 👷 ci(workflows): harden PR included-changes sync (#181)
- 👷 ci(workflows): add PR included changes sync (#181)

### 🔧 Chores & Internal

- 🥅 fix(sop): align changelog_group vocabulary across schema and hooks (#181)
- 🔖 release: cut v0.7.0 vocabulary contract and gold headings (#181)
- 🔧 chore(lock): sync uv.lock package version to 0.6.0
- 🙈 chore(gitignore): add backup file patterns to gitignore

### Miscellaneous

- Merge pull request #186 from Thomo1318/fix/181-followup-release-notes-vocabulary-gold-headings

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
