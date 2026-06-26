# 🧑‍💻 Development Guide

Welcome to the development guide for `git-cg`. This document outlines the prerequisites, environment setup, and standard operating procedures for contributing to the repository.

---

## 🛠 Prerequisites

This repository relies on modern, declarative toolchains. Before starting, ensure you have the following package managers installed:

1. **[mise](https://mise.jdx.dev/)**: The primary environment and toolchain manager.
2. **[Homebrew](https://brew.sh/)**: For installing native dependencies like local LLM servers.

---

## 🚀 Environment Setup

The provisioning process is heavily automated, though some final manual actions are required for secrets and Git hooks.

1. **Install Runtime Dependencies**:

   ```bash
   mise install
   ```

   *This automatically installs and configures Python, `uv`, Node.js, `just`, `usage`, `hk`, `pkl`, `rtk`, and `gum` according to our `mise.toml`.*

2. **Install Inference Engines**:

   ```bash
   brew bundle
   ```

   *Installs `oMLX` and `MTPLX` for local, hardware-accelerated AI execution on Apple Silicon.*

3. **Install Git Hooks** (Manual Action Required):

   ```bash
   hk install
   ```

   *Manually configure deterministic `pre-commit` and `prepare-commit-msg` hooks.*

---

## 🔐 Secrets Management & API Keys

`git-cg` uses **fnox** in combination with 1Password to securely orchestrate secrets. 
If you do not have access to the shared 1Password vault or are running without `fnox`, you must provide the necessary API keys manually.

Create a `.env` file in the root of the project with the following (depending on your chosen engine):

```env
OPENAI_API_KEY="sk-your-openai-key"
# OR
OMLX_API_KEY="sk-your-omlx-key"
# OR
MTPLX_API_KEY="sk-your-mtplx-key"
```

> **Note on Local Models:** If you are utilizing `oMLX` or `MTPLX`, you may need a **Hugging Face token** (`HF_TOKEN`) to download gated models. You can optionally set `HF_HOME` to cache these models on external drives.

---

## 🧪 Testing

We use `pytest` for the Python test suite and `just` as our command runner.

- **Run integration smoke tests** (`just test` runs a temporary-repo commit dry run):

  ```bash
  just test
  ```

- **Run the Python test suite** (actual unit/integration tests):

  ```bash
  uv run pytest tests/
  ```

*Tests must pass before any commit can be merged. The CI pipeline will automatically run these against multiple Python versions.*

---

## 🧹 Code Quality and Linting

We enforce strict linting and formatting using `ruff` and type-checking via `pyright`.

- **Run linting** (`ruff` and `pyright`):

  ```bash
  uv run ruff check
  uv run pyright
  ```

- **Auto-format code** (`ruff`):

  ```bash
  uv run ruff format
  ```

---

## 🪝 Git Hooks (`hk`)

Our Git hooks are critical to enforcing the **Hybrid Commit Standard**.

- **`commit-msg`**: Strict validation of your commit message format. It runs `scripts/validate_commit.mjs` and enforces Gitmoji, Conventional Commits, and the 72-character limit.
- **`pre-commit`**: Automatically runs `gitleaks` and other pre-commit checks.

> **Important Editor Warning**: If you use an interactive GUI editor (like VS Code or Cursor) for your git commits, you must ensure it runs in a blocking mode (e.g., `code --wait`). Otherwise, the editor will return instantly and cause the `hk` stash mechanisms to lock the git index unexpectedly. See the "Feature Spotlight" in the README for details.

---

## 🤝 Contribution Workflow

1. Branch off `main` for your feature or fix (e.g., `feat/my-new-feature`).
2. Write tests for any new logic.
3. Commit using `git-cg` or ensure your manual commits adhere strictly to our Hybrid Commit Matrix (found in `config/gitops_agent_sop.json`).
4. Ensure `just test` and `just lint` both pass locally.
5. Push and open a Pull Request.
