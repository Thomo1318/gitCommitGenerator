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
version: "v1.0.0"
date: "2026-06-07"
created: "2026-06-07 12:00:00"
modified: "2026-06-07 12:00:00"
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

## CHANGELOG

- v1.0.0 (2026-06-07 12:00:00): Initial drafting and finalization of the two-tier secret scanning strategy using Gitleaks and TruffleHog.
