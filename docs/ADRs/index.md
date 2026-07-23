# Architecture Decision Records

Decision log for `gitCommitGenerator`. Files live alongside this index as `NNNN-slug.md`.

| ADR                                                                               | Title                                            | Status                             |
| --------------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------- |
| [0000](./0000-decision-matrix.md)                                                 | Feature Rejection & Decision Matrix              | Active running sheet               |
| [0001](./0001-adopt-adr-ecosystem.md)                                             | Adopt ADR Ecosystem                              | See file                           |
| [0002](./0002-adopt-gitleaks-and-trufflehog.md)                                   | Gitleaks / TruffleHog / BetterLeaks scanning     | See file                           |
| [0003](./0003-adopt-fnox-for-secrets-management.md)                               | Adopt fnox for Hybrid Secrets Management         | Accepted                           |
| [0004](./0004-1password-service-account-integration.md)                           | 1Password Service Account Integration            | Historical constraint              |
| [0006](./0006-1password-python-sdk-migration.md)                                  | 1Password Python SDK Migration                   | **Superseded** by 0014             |
| [0007](./0007-Integrate-gum-for-terminalnative-git-hook-tui.md)                   | gum TUI hooks                                    | See file                           |
| [0008](./0008-zensical-integration.md)                                            | Zensical                                         | See file                           |
| [0009](./0009-reconcile-deterministic-intent-ranking-with-guided-regeneration.md) | Intent ranking vs regeneration                   | See file                           |
| [0010](./0010-integrate-opik-telemetry-pipeline.md)                               | Opik telemetry                                   | See file                           |
| [0011](./0011-e2e-observability-stack.md)                                         | E2E observability                                | See file                           |
| [0012](./0012-adopt-coderabbit-and-qodo.md)                                       | CodeRabbit / Qodo                                | See file                           |
| [0013](./0013-formalise-ide-boundaries-for-1password-mounted-local-env-files.md)  | IDE boundaries for 1Password FIFO `.env`         | **Accepted** (companion to 0014)   |
| [0014](./0014-fnox-canonical-secrets-demote-1password-sdk-and-fifo-dotenv.md)     | fnox-canonical secrets; demote SDK & FIFO dotenv | **Accepted** (not yet Implemented) |

## Secrets path (normative)

See **ADR-0014** (Accepted): fnox → process env → env-first `resolve_secret()`. Do not treat ADR-0006 SDK crawl or FIFO `.env` dotenv loading as canonical.
