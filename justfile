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

# Uninstall the tool and completions
uninstall:
    @echo "🗑 Uninstalling git-cg..."
    @sudo rm -f /usr/local/bin/git-cg
    @rm -f ~/.zfunc/_git-cg
    @echo "✅ git-cg uninstalled."

# Print reproducible S0 schema pack + metric catalog pins (offline)
eval-schema-hash:
    uv run python -c "from git_cg.eval import schema_pack_pin, metric_catalog_pin; print(schema_pack_pin()); print(metric_catalog_pin())"

# Materialize checked-in eval golden bundles + snapshots (offline)
eval-materialize:
    uv run python -m git_cg.eval.corpus.materialize

# Regenerate tests/fixtures/eval/FIXTURE_INDEX.md
eval-fixture-index:
    uv run python -m git_cg.eval.corpus.index --write

# Check docs/eval/operator_api_map.md matches live Typer tree (S6 Slice 2)
eval-api-map-check:
    uv run python -m git_cg.eval.api_map --check

# S6 Slice 7: hyperfine bench of the commit path with Lane C dogfood async on vs off.
# Maintainer evidence only — never a CI gate, never a product-accept gate.
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
