#!/usr/bin/env bash
set -e

echo "🚀 Starting git-cg installation pipeline..."

# 1. Check for mise
if ! command -v mise &> /dev/null; then
    echo "📦 Installing mise (Environment Manager)..."
    curl https://mise.run | sh
    export PATH="$HOME/.local/share/mise/bin:$HOME/.local/bin:$PATH"
fi

# 2. Run mise install
echo "📦 Installing dependencies via mise (Python, Node, uv, fnox, hk, usage)..."
mise install

# 3. Brew bundle (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &> /dev/null; then
        echo "🍎 macOS detected. Installing local inference engines (oMLX/MTPLX) via Homebrew..."
        brew bundle || echo "⚠️ brew bundle had warnings, continuing..."
    fi
fi

# 4. uv sync
echo "🐍 Syncing Python virtual environment..."
uv sync

# 5. hk install
echo "🪝 Installing Git Hooks..."
hk install

# 6. .env template
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys if you do not use fnox/1Password."
fi

echo "✅ Installation complete! You can now run 'git commit' to trigger the AI hook."
