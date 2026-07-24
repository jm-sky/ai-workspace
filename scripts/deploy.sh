#!/bin/bash

# AI Workspace Complete Deployment Script
# This script orchestrates the complete deployment by pulling latest changes,
# building and deploying the frontend, and restarting/migrating the backend
#
# Usage: scripts/deploy.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$PROJECT_DIR/scripts"

echo -e "${GREEN}🚀 Starting complete AI Workspace deployment...${NC}"

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

if [ "${CI:-}" = "true" ]; then
  export GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new'
fi

# CI uses passwordless sudoers; manual deploy prompts once
if [ "${CI:-}" != "true" ]; then
  echo -e "${YELLOW}🔐 Requesting sudo access...${NC}"
  sudo -v
  while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
fi

# Step 1: Pull latest changes
echo -e "${YELLOW}📦 Step 1: Pulling latest changes...${NC}"
cd "$PROJECT_DIR"
git pull

# Step 2: Build and deploy frontend
echo -e "${YELLOW}🔨 Step 2: Building and deploying frontend...${NC}"
"$SCRIPTS_DIR/frontend_build_deploy.sh"

# Step 3: Restart backend and migrate
echo -e "${YELLOW}🐳 Step 3: Restarting backend and running migrations...${NC}"
"$SCRIPTS_DIR/backend_restart_migrate.sh"

echo ""
echo -e "${GREEN}✅ Complete deployment finished successfully!${NC}"
