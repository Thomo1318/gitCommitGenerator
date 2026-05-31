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

# Run all quality checks and generation tasks
all: lint gen-docs gen-completions test

# Run a robust integration test using a temporary Git repository
test:
    @echo "🧪 Initializing robust test scenario..."
    @mkdir -p .test_repo
    @./scripts/setup_test_scenario.zsh .test_repo
    @echo "📂 Testing in temporary repo: .test_repo"
    @cd .test_repo && ../bin/git-cg --dry-run .git/COMMIT_EDITMSG template
    @echo "🧹 Cleaning up..."
    @rm -rf .test_repo
    @echo "✅ Robust integration test complete."

# Uninstall the tool and completions
uninstall:
    @echo "🗑 Uninstalling git-cg..."
    @sudo rm -f /usr/local/bin/git-cg
    @rm -f ~/.zfunc/_git-cg
    @echo "✅ git-cg uninstalled."
