#!/bin/bash

# Installs frontend deps and builds. Always invoked as the `deploy` OS user
# (directly from GitHub Actions, or via `sudo -u deploy` from a manual deploy)
# so node_modules/.pnpm-store never end up split between `deploy` and the
# main user. pnpm's shared store objects are immutable and owned by whoever
# wrote them first; a different user can read/link them via the shared
# `deploy` group but cannot chmod them, which is what caused the CI EPERM.
#
# Usage: scripts/frontend_pnpm_build.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_toolchain() {
  if command -v pnpm >/dev/null 2>&1; then
    return 0
  fi
  export NVM_DIR="/home/madeyskij/.nvm"
  export PNPM_HOME="/home/madeyskij/.local/share/pnpm"
  # shellcheck source=/dev/null
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  export PATH="$PNPM_HOME:$PATH"
}
setup_toolchain

cd "$PROJECT_DIR"

# Clean up dist directory to avoid permission issues
rm -rf dist

# Cap Node heap below typical free RAM on this VPS (no swap).
# Run type-check and vite sequentially — `pnpm build` uses run-p and doubles peak RSS (OOM / exit 137).
export NODE_OPTIONS="--max-old-space-size=2048"

CI=true pnpm install --frozen-lockfile
pnpm type-check
pnpm build-only
