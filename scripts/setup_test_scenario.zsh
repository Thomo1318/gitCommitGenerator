#!/usr/bin/env zsh
# setup_test_scenario.zsh
# Creates a temporary Git repository with staged changes for testing git-cg.

set -e

TARGET_DIR="${1:-$(mktemp -d -t git-cg-test-XXXXXX)}"

if [[ ! -d "$TARGET_DIR" ]]; then
    mkdir -p "$TARGET_DIR"
fi

cd "$TARGET_DIR"

# Initialize Git
git init -q
git config user.email "test@example.com"
git config user.name "Test User"

# Generate a mock file using faker
if command -v faker >/dev/null 2>&1; then
    faker text > mock_change.txt
else
    # Fallback if faker is not working
    echo "This is a mock change for testing the AI commit generator." > mock_change.txt
    echo "It contains some sample text to simulate code or documentation updates." >> mock_change.txt
fi

# Stage the changes
git add mock_change.txt

# Output the path
echo "$TARGET_DIR"
