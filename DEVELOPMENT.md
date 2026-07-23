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

   _This automatically installs and configures Python, `uv`, Node.js, `just`, `usage`, `hk`, `pkl`, `rtk`, and `gum` according to our `mise.toml`._

2. **Install Inference Engines**:

   ```bash
   brew bundle
   ```

   _Installs `oMLX` and `MTPLX` for local, hardware-accelerated AI execution on Apple Silicon._

3. **Install Git Hooks** (Manual Action Required):

   ```bash
   hk install
   ```

   _Manually configure deterministic `pre-commit` and `prepare-commit-msg` hooks._

---

## 🔐 Secrets Management & API Keys

`git-cg` uses **fnox** in combination with 1Password to securely orchestrate secrets.
If you do not have access to the shared 1Password vault or are running without `fnox`, you must provide the necessary API keys manually via exported environment variables or a separate secrets file (e.g., `.env.local` or `.secrets`).

> **Warning for IDE Users**: Do **NOT** use the root `.env` file for non-secret IDE settings (like `PYTHONPATH`). When `fnox` is active, it mounts `.env` as a named pipe (FIFO) which can cause severe CPU spikes and lockups in editors like VS Code. For non-secret IDE configuration, place your environment variables in `.vscode/python.env` (which is already configured in our workspace settings).

Example API key configuration (if running outside fnox):

```env
OPENAI_API_KEY="sk-your-openai-key"
# OR
OMLX_API_KEY="sk-your-omlx-key"
# OR
MTPLX_API_KEY="sk-your-mtplx-key"
```

> **Note on Local Models:** If you are utilizing `oMLX` or `MTPLX`, you may need a **Hugging Face token** (`HF_TOKEN`) to download gated models. You can optionally set `HF_HOME` to cache these models on external drives.

---

## 🧠 Local Inference Engine Binding (oMLX, lmlx, MTPLX)

When developing or testing with local Apple Silicon inference engines, you must adhere to **Strict Model ID Binding**.

> [!WARNING]
> **Silent Misrouting & HTTP 404s**
> These local servers act as drop-in OpenAI replacements, but they do **not** support generic model IDs (e.g., `"local"` or `"default"`).
> If the `"model"` parameter in your API JSON payload does not **exactly match** the absolute path or precise Hugging Face ID of the currently loaded model, the engine will either throw an opaque `HTTP 404: Not Found` error, or silently misroute the request to a different cached model (which can severely skew benchmarks and semantic tests).
>
> **Solution:** Always query `GET /v1/models` from the local server and use the exact `id` returned by the registry to explicitly bind your completions requests.

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

_Tests must pass before any commit can be merged. The CI pipeline will automatically run these against multiple Python versions._

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
- **`pre-commit`**: Fast local path — `ruff`, `ruff-format`, `betterleaks` (local secrets), and doc generators. Full pytest coverage is **slow-profile only** (`hk check --slow` / `mise run cov`), not default pre-commit.

> **Important Editor Warning**: If you use an interactive GUI editor (like VS Code or Cursor) for your git commits, you must ensure it runs in a blocking mode (e.g., `code --wait`). Otherwise, the editor will return instantly and cause the `hk` stash mechanisms to lock the git index unexpectedly. See the "Feature Spotlight" in the README for details.

---


---

## 📏 Canonical quality commands (`mise` vs `just`)

> **Do not redefine** `just lint` / `just test`. Their historical meanings stay:
>
> | Command | Meaning (unchanged) |
> | --- | --- |
> | `just lint` | Zsh syntax check of legacy scripts |
> | `just test` | Temporary-repo `git-cg` smoke dry-run |
>
> Canonical CI/DX commands live in **`mise`**:

| Command | Meaning |
| --- | --- |
| `mise run lint` | Read-only fast lint (CI-shaped): `hk validate` + `hk check --check --no-stage --all` with `HK_SKIP_STEPS=pytest-cov,betterleaks,gen-docs,gen-toc` |
| `mise run test` | Full project `pytest` suite |
| `mise run cov` | Slow coverage verification (`--cov=src/git_cg --cov-branch`) |
| `mise run security` | Optional local SBOM + Grant + Grype |

### `hk` profiles

* **Fast (default pre-commit):** ruff, ruff-format, betterleaks, gen-docs, gen-toc
* **Slow:** `pytest-cov` only when `hk check --slow` / `HK_PROFILE=slow`
* **CI lint:** always read-only (`--check --no-stage`); never mutates the index
* **PR CI:** `hk check --check --no-stage --pr ...` with valid base (`fetch-depth: 0`)
* **Push / `workflow_dispatch` CI:** `--all` (or verified delta) — **never** `--pr` alone
* **Version contract:** `min_hk_version = "1.45.0"`; exact `hk` pin in `mise.toml` aligned with the Pkl package amend

### Codecov upload policy

* **Same-repository** uploads only, authenticated with **OIDC** (`use_oidc: true`)
* `id-token: write` is scoped **only** to the coverage upload job
* **Fork PRs skip upload**; tests/coverage generation still run and must pass
* Eligible uploads use `fail_ci_if_error: true` (no blanket `continue-on-error`)
* Branch protection must **not** require the Codecov upload check on fork PRs (it is intentionally skipped)
* Downloaded Codecov CLI from `codecov-action` is an **accepted pin exception** (action SHA is pinned; CLI binary tracks the action release channel). A hermetic CLI version pin is optional future work only if supply-chain policy tightens further.
* **Patch 80% burn-in note:** root patch target stays `80%` with no `paths`/`flags`. Huge diffs concentrated in `src/git_cg/main.py` (`cli-main` component) can temporarily pressure patch status; prefer splitting product changes or accepting a deliberate patch miss over weakening the global target / component map.


### Security / SBOM

* TruffleHog Action is **SHA-pinned** and the scanner **version** is pinned (action SHA ≠ payload pin alone)
* Syft / Grype / Grant install via **mise exact versions** — no `curl \| sh`, no `latest` for those tools
* SBOM artifact upload uses `if: ${{ env.ACT != 'true' }}` (never `ACT: "false"` + `!env.ACT`)

### Evidence expectations (Issue #170 close-out)

Before closing pipeline hardening work, record:

1. Same-repo PR with successful OIDC Codecov upload and visible `semantic-core` / `cli-main` component signal
2. Fork PR with upload skipped and CI green
3. Security workflow success with SBOM artifact + Grype threshold


## 🤝 Contribution Workflow

1. Branch off `main` for your feature or fix, including the issue number in the branch name to enable `git-cg` auto-detection (e.g., `feat/123-my-new-feature`).
2. Write tests for any new logic.
3. Commit using `git-cg` or ensure your manual commits adhere strictly to our Hybrid Commit Matrix (found in `config/gitops_agent_sop.json`).
4. Ensure `mise run lint` and `mise run test` pass locally (and keep `just lint` / `just test` green if you touch those surfaces).
5. Push and open a Pull Request.

---

## 📝 Issue & Pull Request Standards

To maintain high visibility into architectural changes and semantic impact, all Issues and Pull Requests must adhere to the **Gold-Standard Templates**.

<details>
<summary><b>📚 Heading Breakdown Dictionary</b></summary>

A detailed guide for contributors explaining the _Why_, _What_, and _Non-negotiables_ of every heading used in our templates:

### 🎯 Summary

- **Why we use it**: To provide a rapid, high-level overview of the feature or bug.
- **What it should contain**: 1-2 sentences strictly defining the goal.
- **Non-negotiable**: Must be present in every issue type.

### 💡 Why this matters

- **Why we use it**: To justify the existence of the issue and explain the value it brings to the project.
- **What it should contain**: The problem being solved and the impact on the user or system.

### 📐 Architectural direction

- **Why we use it**: To define the technical approach or system design required for major epics.
- **What it should contain**: Key components, patterns, or architecture decisions.
- **Non-negotiable**: Must be present in all Architectural Tasks.

### ⚖️ Core decision

- **Why we use it**: To permanently record technical choices that impact the system's architecture.
- **What it should contain**: Definitive rules (e.g. "We will use pure functions for X").
- **Non-negotiable**: Must be present in all Architectural Tasks.

### 🛠️ Proposed Implementation Details / Proposed Solution

- **Why we use it**: To describe how the feature will actually work under the hood.
- **What it should contain**: Specific technical details, algorithms, or execution steps.

### 🔄 Expected workflow

- **Why we use it**: To define the step-by-step user or system flow.
- **What it should contain**: A numbered list of sequential steps.

### ✅ Expected Behaviour / Acceptance criteria

- **Why we use it**: To strictly define when the issue can be considered "done".
- **What it should contain**: A clear bulleted list of passing conditions.

### 📦 In scope / 🚫 Out of scope

- **Why we use it**: To prevent feature creep.
- **What it should contain**: Bullet points explicitly defining boundaries.

### 🔗 Milestone relation

- **Why we use it**: To track strategic architectural decisions.
- **What it should contain**: Direct links to related ADRs or Epics (e.g. Related to ADR-0005).

### 🧪 Suggested test scenarios

- **Why we use it**: To ensure features are verifiable before merge.
- **What it should contain**: Unit, integration, or manual testing strategies.

### ⚠️ Risks / things to watch

- **Why we use it**: To proactively identify regressions or security flaws.
- **What it should contain**: Potential performance impacts, security considerations, or backward-compatibility issues.

### 📂 File plan

- **Why we use it**: To outline the scope of file modifications.
- **What it should contain**: The expected file paths and descriptions of changes.
</details>

<details>
<summary><b>🌟 Gold-Standard Examples</b></summary>

When creating issues or pull requests, refer to these pristine examples of our standards in action:

- **Architectural Task**: [Issue #146](https://github.com/Thomo1318/gitCommitGenerator/issues/146)
- **Implementation Task**: [Issue #141](https://github.com/Thomo1318/gitCommitGenerator/issues/141)
- **Pull Request**: [PR #140](https://github.com/Thomo1318/gitCommitGenerator/pull/140) (and #147 once merged)

**Pull Request Requirements:**

1. **Summary & Changes**: A clear explanation of _why_ the change matters and _what_ was technically modified.
2. **Included Changes**: A comprehensive aggregation of the primary commit headers **and** the items listed under their "Included changes" sections (e.g. `♻️ refactor(core): ...` and `✅ test(core): ...`), perfectly mirroring the `git-cg` output format.
3. **Breaking Changes**: If applicable, heavily emphasize any breaking changes and migration paths.
4. **SemVer Impact**: Explicit declaration of the change's impact (PATCH, MINOR, MAJOR) and its corresponding Gitmoji metadata.
</details>

<details>
<summary><b>🏷️ Repository Labels Table</b></summary>

| Category      | Label                  | Description                                               |
| :------------ | :--------------------- | :-------------------------------------------------------- |
| **Component** | `component: core`      | AI commit generation and payload structure                |
| **Component** | `component: docs`      | Improvements or additions to documentation                |
| **Component** | `component: tui`       | `gum` interactive flow                                    |
| **Priority**  | `priority: high`       | Critical urgency, drop everything and address immediately |
| **Priority**  | `priority: low`        | Low urgency; handle when time permits                     |
| **Priority**  | `priority: medium`     | Standard urgency; handle in normal workflow               |
| **Status**    | `status: blocked`      | Waiting on upstream or an external dependency             |
| **Status**    | `status: completed`    | Work on the issue has been completed                      |
| **Status**    | `status: deferred`     | Postponed for a future milestone or release               |
| **Status**    | `status: in progress`  | Work is currently actively happening                      |
| **Status**    | `status: needs triage` | Needs prioritization or categorization                    |
| **Type**      | `type: bug`            | Something isn't working                                   |
| **Type**      | `type: chore`          | Maintenance, dependencies, tooling                        |
| **Type**      | `type: ci`             | GitHub Actions, release pipelines                         |
| **Type**      | `type: enhancement`    | New feature or request                                    |
| **Type**      | `type: refactor`       | Code structure changes                                    |
| **Type**      | `type: test`           | Unit or integration testing                               |
| **General**   | `duplicate`            | This issue or pull request already exists                 |
| **General**   | `good first issue`     | Good for newcomers                                        |
| **General**   | `help wanted`          | Extra attention is needed                                 |
| **General**   | `invalid`              | This doesn't seem right                                   |
| **General**   | `question`             | Further information is requested                          |
| **General**   | `security`             | Vulnerabilities or secrets management                     |
| **General**   | `wontfix`              | This will not be worked on                                |

</details>
