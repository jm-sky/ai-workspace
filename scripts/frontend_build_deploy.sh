#!/bin/bash

# Frontend Build and Deploy Script
# This script installs dependencies, builds the frontend, and deploys to /var/www/ai-workspace
#
# Usage: scripts/frontend_build_deploy.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
DEPLOY_DIR="/var/www/ai-workspace"

echo -e "${GREEN}🔨 Starting frontend build and deploy...${NC}"

# Install dependencies and build.
# Always run as the `deploy` OS user, regardless of who invoked this script,
# so node_modules/.pnpm-store ownership never splits between `deploy` (CI)
# and the main user (manual deploys) — see frontend_pnpm_build.sh.
echo -e "${YELLOW}📦 Installing dependencies and building frontend...${NC}"
if [ "$(whoami)" = "deploy" ]; then
  "$SCRIPTS_DIR/frontend_pnpm_build.sh"
else
  sudo -u deploy "$SCRIPTS_DIR/frontend_pnpm_build.sh"
fi
echo -e "${GREEN}✅ Frontend build completed${NC}"

# Deploy to /var/www/ai-workspace
echo -e "${YELLOW}📋 Deploying to ${DEPLOY_DIR}...${NC}"

deploy_frontend() {
  rm -rf "${DEPLOY_DIR:?}"/*
  cp -r dist/* "$DEPLOY_DIR/"
}

if [ -w "$DEPLOY_DIR" ]; then
  deploy_frontend
else
  sudo rm -rf "${DEPLOY_DIR:?}"/*
  sudo cp -r dist/* "$DEPLOY_DIR/"
fi

# Fix ownership to caddy:deploy
sudo chown -R caddy:deploy "$DEPLOY_DIR"

echo -e "${GREEN}✅ Deployed to ${DEPLOY_DIR}${NC}"
echo -e "${GREEN}✅ Frontend build and deploy completed successfully!${NC}"
