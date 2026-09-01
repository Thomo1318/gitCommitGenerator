# git-cg justfile
# Modern task runner for the AI Git Commit Generator

# Default: show tasks
default:
    @just --list

# Install the tool and completions
install: install-binary install-completions
    @echo "🚀 git-cg installation complete!"

# Install only the binary
install-binary:
    @echo "📦 Installing git-cg binary to /usr/local/bin..."
    @sudo ln -sf "$(pwd)/bin/git-cg" /usr/local/bin/git-cg
    @echo "✅ Global binary symlink created."

# Install zsh completions to ~/.zfunc
install-completions: gen-completions
    @echo "🐚 Installing zsh completions to ~/.zfunc/_git-cg..."
    @mkdir -p ~/.zfunc
    @ln -sf "$(pwd)/completions/_git-cg" ~/.zfunc/_git-cg
    @echo "✅ Completion symlink created. Run 'reload' to apply."

# Check script syntax
lint:
    @echo "🧹 Linting script syntax..."
    @zsh -n scripts/generate_ai_commit.zsh
    @echo "✅ Syntax check passed."

# Generate markdown documentation
gen-docs:
    @echo "📖 Generating markdown documentation..."
    @mkdir -p docs
    @usage g md -f usage.kdl --out-file docs/usage.md
    @echo "✅ docs/usage.md updated."

# Generate shell completions
gen-completions:
    @echo "🐚 Generating zsh completions..."
    @mkdir -p completions
    @usage g completion zsh -f usage.kdl git-cg > completions/_git-cg
    @echo "✅ completions/_git-cg generated."

# Alias for gen-completions
completions: gen-completions

# Hook helper: Generate docs and immediately stage them
docs-hook: gen-docs gen-completions
    @git add docs/usage.md completions/_git-cg

# Run all quality checks and generation tasks
all: lint gen-docs gen-completions test

# Run a robust integration test using a temporary Git repository
test:
    @echo "🧪 Initializing robust test scenario..."
    @mkdir -p .test_repo
    @./scripts/setup_test_scenario.zsh .test_repo
    @echo "📂 Testing in temporary repo: .test_repo"
    @cd .test_repo && ../bin/git-cg commit --dry-run .git/COMMIT_EDITMSG template
    @echo "🧹 Cleaning up..."
    @rm -rf .test_repo
    @echo "✅ Robust integration test complete."


# Docstring coverage on CHANGED files only (CI-shaped patch gate, fail-under 80).
# BASE defaults to origin/main...HEAD for branches; override: just docstrings-patch main
docstrings-patch base="origin/main":
    #!/usr/bin/env bash
    set -euo pipefail
    mapfile -t files < <(
      git diff --name-only --diff-filter=ACMR "{{base}}"...HEAD -- 'src/git_cg/**/*.py'         | rg -v '^src/git_cg/evals/' || true
    )
    if [ "${#files[@]}" -eq 0 ]; then
      echo "No changed src/git_cg Python files vs {{base}} — docstring patch gate skipped."
      exit 0
    fi
    printf 'Docstring patch gate (%d file(s)):\n' "${#files[@]}"
    printf '  %s\n' "${files[@]}"
    uvx --python 3.14 --from "interrogate==1.7.0" interrogate -v --fail-under 80 "${files[@]}"

# Full-package docstring health + flat badge (not the CI push gate)
docstrings:
    uvx --python 3.14 --from "interrogate==1.7.0" interrogate src/git_cg -v --generate-badge docs/assets/badges --badge-format svg --badge-style flat

# Report missing private docstrings + safe-insert feasibility (no writes)
docstring-guard *paths:
    uv run python tools/docstring_guard.py check {{paths}}

# Apply explicit docstring manifest with parse/compile write-if-green
# Usage: just docstring-guard-apply /tmp/docs.json
# Optional dry-run: just docstring-guard-apply /tmp/docs.json 1
docstring-guard-apply manifest dry_run="":
    #!/usr/bin/env bash
    set -euo pipefail
    args=(apply --manifest "{{manifest}}")
    if [ -n "{{dry_run}}" ]; then
      args+=(--dry-run)
    fi
    uv run python tools/docstring_guard.py "${args[@]}"

# Uninstall the tool and completions
uninstall:
    @echo "🗑 Uninstalling git-cg..."
    @sudo rm -f /usr/local/bin/git-cg
    @rm -f ~/.zfunc/_git-cg
    @echo "✅ git-cg uninstalled."

# Print reproducible eval schema-pack + metric-catalog pins (offline).
# Historical: S0 pin surface. Refs: eval pins module.
eval-schema-hash:
    uv run python -c "from git_cg.eval.pins import schema_pack_pin, metric_catalog_pin; print(schema_pack_pin()); print(metric_catalog_pin())"

# Materialize checked-in eval golden bundles + snapshots (offline)
eval-materialize:
    uv run python -m git_cg.eval.corpus.materialize

# Regenerate tests/fixtures/eval/FIXTURE_INDEX.md
eval-fixture-index:
    uv run python -m git_cg.eval.corpus.index --write

# Check docs/eval/operator_api_map.md matches the live Typer command tree.
# Refs: #246 (operator API map gate).
eval-api-map-check:
    uv run python -m git_cg.eval.api_map --check

# Regenerate docs/cli from live Typer trees (mise-style overview + one page per command)
gen-cli-docs:
    uv run python tools/gen_cli_docs.py

# Offline eval claim-matrix spine (subset of eval tests; no coverage gate).
# Does not replace full CI pytest.
# Refs: #246 claim matrix.
eval-claim-matrix-spine:
    uv run pytest \
      tests/eval/test_api_map_help.py \
      tests/eval/test_checkpoint_store.py \
      tests/eval/test_compat_hash.py \
      tests/eval/test_run_orchestrator.py \
      tests/eval/test_eval_cli_run.py \
      tests/eval/test_doctor.py \
      tests/eval/test_eval_cli_doctor.py \
      tests/eval/test_eval_opik_doctor.py \
      tests/eval/test_explain.py \
      tests/eval/test_diagnose.py \
      tests/eval/test_eval_cli_explain.py \
      tests/eval/test_replay.py \
      tests/eval/test_promote.py \
      tests/eval/test_review_queue.py \
      tests/eval/test_eval_cli_replay_promote.py \
      tests/eval/test_s6_slice7.py \
      tests/eval/test_eval_cli_triage.py \
      tests/eval/mirror/test_train.py \
      -q --no-cov

# Package-scoped coverage floor for src/git_cg/eval only.
# `-o addopts=""` clears the global `--cov=src/git_cg --cov=scripts` union from
# pyproject.toml so the floor is not diluted by non-eval packages.
# Floor 80 matches the measured baseline on #254. Maintainer gate — not CI.
# Refs: #254 (coverage acceptance).
eval-package-coverage:
    uv run pytest tests/eval -o addopts="" \
      --cov=src/git_cg/eval --cov-branch --cov-report=term-missing \
      --cov-fail-under=80 -q

# Per-file coverage gate for interaction-owned eval modules (≥80% each).
# pytest-cov --cov-fail-under is aggregate-only; JSON + tools/check_per_file_coverage.py
# enforce the threshold per file. eval-package-coverage remains the primary floor.
eval-per-file-coverage:
    @echo "📊 per-file coverage gate (≥80% each owned eval module)"
    @mkdir -p .eval
    @rm -f .eval/per_file_coverage.json
    uv run pytest tests/eval -o addopts="" \
      --cov=git_cg.eval.review_queue \
      --cov=git_cg.eval.promote \
      --cov=git_cg.eval.evidence_scrub \
      --cov=git_cg.eval.feedback_definitions \
      --cov-branch \
      --cov-report=term-missing \
      --cov-report=json:.eval/per_file_coverage.json \
      -q
    uv run python tools/check_per_file_coverage.py \
      --json .eval/per_file_coverage.json \
      --fail-under 80 \
      --file src/git_cg/eval/review_queue.py \
      --file src/git_cg/eval/promote.py \
      --file src/git_cg/eval/evidence_scrub.py \
      --file src/git_cg/eval/feedback_definitions.py

# Hyperfine bench of the real commit path with dogfood async on vs off.
# Maintainer evidence only — never a CI gate, never a product-accept gate.
# Refs: #246 (dogfood async lane).
dogfood-bench runs="20":
    @echo "🔬 dogfood-bench: hyperfine {{runs}} runs ×2 (async on/off) on real commit path"
    @command -v hyperfine >/dev/null || { echo "hyperfine not installed" >&2; exit 1; }
    @mkdir -p .eval/dogfood
    @GIT_CG_EVAL_DOGFOOD_MODE=async hyperfine --warmup 2 --runs {{runs}} \
        --export-json .eval/dogfood/bench_async_on.json \
        --command-name dogfood_async_on \
        "GIT_CG_EVAL_DOGFOOD_MODE=async ./bin/git-cg commit --dry-run .git/COMMIT_EDITMSG template"
    @GIT_CG_EVAL_DOGFOOD_MODE=off hyperfine --warmup 2 --runs {{runs}} \
        --export-json .eval/dogfood/bench_async_off.json \
        --command-name dogfood_async_off \
        "GIT_CG_EVAL_DOGFOOD_MODE=off ./bin/git-cg commit --dry-run .git/COMMIT_EDITMSG template"
    @uv run python -m git_cg.eval.dogfood.bench \
        .eval/dogfood/bench_async_off.json .eval/dogfood/bench_async_on.json

# Mechanical deslop Naming Audit (families A–D identity shapes on branch diff).
# Fails closed (exit 2) when stage/plan/governance/ceremony residue is introduced
# as durable operator/code identity. Any generation — not a per-slice denylist.
# Override base: just deslop-naming-scan origin/main
# HEAD-only: just deslop-naming-scan origin/main 1
deslop-naming-scan base="origin/main" committed_only="":
    #!/usr/bin/env bash
    set -euo pipefail
    # quote() keeps parameters as data, not Bash source (CWE-78).
    args=(--base {{quote(base)}})
    if [ -n {{quote(committed_only)}} ]; then
      args+=(--no-working-tree)
    fi
    printf '🔎 deslop naming scan vs %s…\n' {{quote(base)}}
    uv run python tools/deslop_naming_scan.py "${args[@]}"

