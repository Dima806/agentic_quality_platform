#!/usr/bin/env bash
# Provision a standard 2-CPU GitHub Codespace for the Agentic Quality Platform.
#
# Run once per fresh container (via `make setup`). This replaces a custom
# .devcontainer on purpose: provisioning stays in version control, not in
# container config. Idempotent — safe to re-run.
set -euo pipefail

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

# 1. Node runtime (Codespaces ships one; fail clearly if somehow absent).
say "Checking Node runtime"
if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is required but not found. Install Node 18+ and re-run." >&2
    exit 1
fi
node --version
npm --version

# 2. Browser-automation MCP server + headless browser with OS dependencies.
#    The browser runs headless and one context at a time (2-CPU budget).
say "Installing Playwright MCP server"
npm install -g @playwright/mcp@latest

say "Installing headless Chromium and its OS dependencies"
if command -v sudo >/dev/null 2>&1; then
    sudo npx --yes playwright install --with-deps chromium
else
    # No sudo (e.g. already root): install OS deps, then the browser.
    npx --yes playwright install-deps chromium || true
    npx --yes playwright install chromium
fi

# 3. Python dependencies (editable install with dev extras).
say "Installing Python dependencies"
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

say "Bootstrap complete. Try:  make check   or   make run FEATURE=features/refund.feature"
