# Git Commit Generator (git-cg) - Agent Handoff Document

## Overview
This document provides the necessary context to review and analyze the `gitCommitGenerator` (`git-cg`) project. `git-cg` is a tool that intercepts the git `prepare-commit-msg` hook to automatically generate highly contextual commit messages based on the staged diff. It is heavily optimized for local Apple Silicon execution using specialized MLX inference engines.

## Tech Stack & Architecture
- **Language**: Python (v3.14+)
- **Package Manager**: `uv`
- **Environment**: Managed by `mise` (for reproducible toolchains).
- **Secrets Management**: Zero-plaintext policy. Secrets are injected at runtime using the 1Password CLI (`op run` via `scripts/with_1p_env.sh`).
- **Git Hooks**: Managed using `jdx/hk` (configured in `hk.pkl`).
- **Inference Engines**: Supports local MLX servers like `MTPLX` (default local speed-optimized engine) and `oMLX`, as well as standard OpenAI-compatible endpoints.
- **Tracing & Evaluation**: Uses `Opik` for LLM tracing, evaluating generated outputs, and debugging prompt executions.

## Current Project State
The core functionality is operational. We recently completed a debugging session to fix string interpolation bugs where `jdx/hk` was improperly passing shell arguments, resulting in git hooks failing. It now correctly passes `{{commit_msg_file}}` and `{{source}}` to the python module, allowing local models to generate the commit message in ~1 minute on local Apple Silicon. We also recently removed `agentops` due to instrumentation conflicts with the latest OpenAI SDKs.

A comprehensive backlog of features and technical debt has been curated and prioritized into `TODO.md`.

## Analysis Objectives
As the reviewing agent, your primary objective is to evaluate the provided project state and provide a fresh perspective. 

Please perform the following:
1. **Codebase Review**: Analyze the architecture, design patterns, and python implementation for security vulnerabilities, performance bottlenecks, and code smells.
2. **Prioritization Audit**: Review the items in `TODO.md`. Are there any critical tasks we missed? Are there architectural refactors we should prioritize before expanding the feature set?
3. **Improvements**: Suggest actionable improvements for the `git-cg` prompt engineering, inference engine routing, error handling, or zero-plaintext security model.

## Provided Resources
You have been provided with:
1. `repomix-output.xmlgitCommitGenerator.xml`: A complete single-file representation of the repository's codebase.
2. `TODO.md`: The current roadmap and backlog, structured by priority.

Please read through the Repomix XML file and the TODO list, then provide a structured report detailing your findings and recommendations.
