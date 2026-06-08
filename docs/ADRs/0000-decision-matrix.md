# ADR 0000: Feature Rejection & Decision Matrix

**Date:** 2026-06-08
**Status:** Active Running Sheet

This document serves as a continuous running sheet for proposed features and architectural changes that were intentionally **rejected**. By maintaining this matrix, we preserve historical context and avoid re-litigating past decisions.

## 2026-06-08: Initial Setup & TODO Recovery

The following items were analyzed during the project's migration to a GitHub Issues-driven workflow and were explicitly rejected.

### 1. Memory Caching for SOPs / Background Daemons
**Proposal:** Keep the `sop.json` matrices or previous project states in memory (or Redis) to speed up generation between commits.
**Decision:** Rejected.
**Rationale:** `git-cg` is an ephemeral CLI script. It spins up, runs once per `git commit`, and shuts down. To keep something "in memory" between commits, we would have to run a background daemon process (a server). Parsing the 2,100 line `sop.json` from disk takes less than 2 milliseconds in Python. The LLM generation takes thousands of milliseconds. Building a complex background daemon just to save 2 milliseconds of JSON parsing is immense architectural overkill.

### 2. Database Integration (Vector DBs / SQL)
**Proposal:** Explore incorporating a database (`Redis`, `SQLite`, or Vector DBs like `Qdrant`/`Milvus`/`pgvector`) to store commit messages, diffs, and metadata to allow the tool to "learn" over time and find similar diffs.
**Decision:** Rejected.
**Rationale:** A vector DB introduces massive dependencies and infrastructure overhead for a local, lightweight CLI tool. Furthermore, matching previous commits based on vector similarity risks severe hallucinations (copy-pasting an old commit message onto a structurally similar but logically different diff).

### 3. Bubble Tea TUI
**Proposal:** Create a Terminal User Interface (TUI) using Go Charm and Bubble Tea.
**Decision:** Rejected.
**Rationale:** The tool is built in Python. Incorporating Go-based TUI libraries would require either a complete rewrite or a fragmented multi-language codebase. We will stick to Python-native libraries (like Rich/Textual) for CLI formatting if needed.

### 4. ThermalForge Fan Control Integration
**Proposal:** Incorporate `ThermalForge` directly into the project to optionally increase fan speed during LLM processing.
**Decision:** Rejected.
**Rationale:** Fan control is an OS-level/hardware-level responsibility, not a git hook's job. MTPLX/oMLX runners already handle their own thermal management or instruct users to use external tools. Bundling hardware manipulation scripts introduces unacceptable security, maintenance, and bug surface areas.

### 5. Theme Support (Dark Mode)
**Proposal:** Add dark mode / light mode toggles for the CLI output.
**Decision:** Rejected.
**Rationale:** Modern terminals handle their own color schemes natively (e.g., ANSI colors map to the user's terminal theme). Hardcoding themes in the CLI is an anti-pattern.

### 6. API Key Management / Secure Storage
**Proposal:** Add a custom keystore or secure storage vault for API keys.
**Decision:** Rejected.
**Rationale:** This reinvents the wheel. We offload secret management to robust, existing tools like 1Password and `fnox`.

---
*(Append new rejected decisions below this line)*
