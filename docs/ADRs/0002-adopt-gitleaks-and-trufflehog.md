<!-- 🎨 HEADER IMAGE PROMPT & FILENAME
An awe-inspiring, hyper-realistic macro shot of a massive, two-tiered security shield made of dark titanium. Glowing laser scanning lines systematically sweep across a stream of floating data blocks. The words "Secret Scanner" are heavily embossed directly into the upper titanium chassis of the shield, backlit with glowing magenta neon that feels physically integrated into the machinery. Cinematic lighting, deep shadows with vibrant neon cyan and electric blue accents, volumetric dust particles. 8k resolution, octane render, architectural precision. PURE TECHNICAL GRAPHIC. NO mobile phone UI, NO status bars, NO device frames or bounding boxes. Wide aspect ratio, designed for high-fidelity technical documentation.

📋 Target Filename: adr-0002-adopt-gitleaks-and-trufflehog.jpeg
-->
<div align="center">
<img src="../assets/adr-0002-adopt-gitleaks-and-trufflehog.jpeg" alt="Header Image" style="width: 100%; max-width: 1080px; border-radius: 8px;">
</div>

# ADR-0002: Adopt Gitleaks and TruffleHog for Two-Tier Secret Scanning

```yaml
adr_number: "0002"
title: "Adopt Gitleaks and TruffleHog for Two-Tier Secret Scanning"
status: "Accepted"
version: "v1.1.0"
date: "2026-06-07"
created: "2026-06-07 12:00:00"
modified: "2026-06-18 09:35:00"
risk_level: "High"
reversibility: "Low"
security_scope: "Project"
tags: ["security", "secrets", "gitleaks", "trufflehog"]
supersedes: []
superseded_by: []
```

## 1. Introduction and Goals

This Architectural Decision Record (ADR) formalizes the decision to adopt a two-tier secret scanning strategy utilizing **Gitleaks** and **TruffleHog** for the `gitCommitGenerator` project.

As this project is intended to be a public repository, preventing credential leakage is paramount. While commercial solutions like GitGuardian and Snyk are available, a hard constraint for this project is that all tooling must be free, open-source, and highly portable for other developers.

### Core Goals
- Prevent accidental secret commits to the repository.
- Ensure all security tooling is free, open-source, and does not require paid subscriptions.
- Guarantee that any other developer can run the same security stack locally without excessive configuration overhead.

---

## 2. Architecture Constraints

- **No Paid Tiers**: The solution cannot rely on paid tiers or forced cloud subscriptions.
- **Portability**: The tools must be installable via `mise` and declared in `mise.toml` to guarantee any developer can easily replicate the security environment.
- **Performance**: Pre-commit checks must be fast enough not to disrupt the local development loop.

---

## 3. Context and Scope

We evaluated three major options: GitGuardian, Snyk, and a self-hosted/open-source approach (Gitleaks + TruffleHog).
- **GitGuardian / Snyk**: Both provide excellent secret scanning but push heavily towards their paid/cloud SaaS tiers. While free tiers exist, they introduce friction and potential account requirements for external contributors.
- **Gitleaks**: Exceptionally fast, regex-based scanner, perfect for pre-commit hooks.
- **TruffleHog**: Deep active verification scanner. Slower but highly accurate, making it ideal for CI/CD pipelines.

---

## 4. Solution Strategy

We are implementing a **Two-Tier Secret Scanning Strategy**:

### Tier 1: Local Prevention (Gitleaks)
- **Tool**: Gitleaks
- **Role**: Pre-commit hook.
- **Reasoning**: Its regex-based engine is blazing fast, providing immediate feedback to the developer before a commit is even created.

### Tier 2: Deep Verification (TruffleHog)
- **Tool**: TruffleHog
- **Role**: CI/CD Pipeline step.
- **Reasoning**: TruffleHog actively verifies found secrets against provider APIs (e.g., checking if an AWS key is actually active). This is slower but provides an ultimate safety net before code is merged into `main`.

Both tools are explicitly declared in the project's `mise.toml` to ensure they are automatically installed for any contributor.

---

## 5. Consequences

- **Pros**: 
  - 100% free and open-source.
  - Zero vendor lock-in.
  - Highly portable local setup using `mise`.
  - Perfect balance of speed (Gitleaks locally) and thoroughness (TruffleHog in CI).
- **Cons**: 
  - Requires maintaining two separate tools.
  - May require tuning `.gitleaksignore` for false positives.

---

## II. Update 1: Replacement of Snyk with Native GitHub Security Tooling and Addition of Codecov (v1.1.0)

During the continuous evolution of our CI pipeline, it was determined that Snyk—previously utilized as a pre-commit hook and a CI check—enforces severe execution limits on its free tier, even for public repositories (often flagging "private test limits" incorrectly or via shared Webhook usage). This frequently blocked valid Pull Requests and hindered developer momentum.

To address this, Snyk has been entirely removed from both the local `hk.pkl` hooks and the CI workflows. In its place, we have adopted fully native and genuinely free GitHub tooling to handle SAST and SCA workloads without compromising scan quality.

### Adopted Alternatives
1. **GitHub CodeQL (SAST)**:
   - **Role**: Replaces `snyk code test`.
   - **Reasoning**: CodeQL is an industry-leading semantic analysis engine that compiles Python to trace deep vulnerabilities. It is 100% free and unlimited for open-source repositories natively inside GitHub Actions.
2. **Dependabot (SCA)**:
   - **Role**: Replaces Snyk's dependency scanning.
   - **Reasoning**: Natively integrated into GitHub, Dependabot is completely free for all repositories. It automatically scans dependencies and opens Pull Requests to address vulnerabilities without external quota limitations.

### Addition of Codecov
While configuring the CI pipeline, **Codecov** was also integrated to handle test coverage reporting. Codecov provides free, unmetered coverage analytics for public open-source repositories.
- **Tokenless Support**: As verified by proof provided for this project, no token is needed for our public repositories to upload coverage metrics, drastically simplifying secrets management for external contributors while delivering robust visual coverage metrics directly on Pull Requests.

### References
- [GitHub CodeQL for Open Source](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [Codecov Public Repositories Documentation](https://docs.codecov.com/docs/adding-the-codecov-token)

---

## CHANGELOG

- v1.0.0 (2026-06-07 12:00:00): Initial drafting and finalization of the two-tier secret scanning strategy using Gitleaks and TruffleHog.
- v1.1.0 (2026-06-18): Replaced Snyk with GitHub CodeQL and Dependabot to resolve execution limits; documented the addition of tokenless Codecov for coverage metrics.
