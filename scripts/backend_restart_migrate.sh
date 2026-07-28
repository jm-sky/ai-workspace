#!/usr/bin/env bash
# Rebuild and restart the backend, then run migrations.
# Uses auto-detect for the active Docker Compose stack (running container labels,
# else repo-root compose files).
#
# Usage:
#   COMPOSE_DIR=... COMPOSE_FILE=... bash scripts/backend_restart_migrate.sh
#   bash scripts/backend_restart_migrate.sh   # auto-detect compose context
#
# Called by deploy.sh — can also be run standalone from the project root.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
APP_CONTAINER_NAME="ai-workspace-app"

# shellcheck source=scripts/lib/detect_compose.sh
source "$PROJECT_DIR/scripts/lib/detect_compose.sh"

resolve_compose_context() {
  if [ -n "${COMPOSE_DIR:-}" ] && [ -n "${COMPOSE_FILE:-}" ]; then
    return
  fi

  local compose_context
  compose_context=$(detect_compose_context)
  COMPOSE_DIR="${compose_context%%|*}"
  COMPOSE_FILE="${compose_context##*|}"
}

resolve_compose_context

if [ -z "$COMPOSE_FILE" ] || [ -z "$COMPOSE_DIR" ]; then
  echo -e "${RED}Error: Could not detect docker-compose file${NC}" >&2
  echo -e "${YELLOW}Set COMPOSE_DIR and COMPOSE_FILE, or ensure a compose file exists in the project root.${NC}" >&2
  exit 1
fi

if [ ! -d "$COMPOSE_DIR" ]; then
  echo -e "${RED}Error: Compose directory not found: $COMPOSE_DIR${NC}" >&2
  exit 1
fi

if [ ! -f "$COMPOSE_DIR/$COMPOSE_FILE" ]; then
  echo -e "${RED}Error: Docker Compose file not found: $COMPOSE_DIR/$COMPOSE_FILE${NC}" >&2
  exit 1
fi

COMPOSE_DISPLAY="${COMPOSE_DIR#"$PROJECT_DIR"/}"
if [ "$COMPOSE_DISPLAY" = "$COMPOSE_DIR" ]; then
  COMPOSE_DISPLAY="$COMPOSE_DIR/$COMPOSE_FILE"
else
  COMPOSE_DISPLAY="$COMPOSE_DISPLAY/$COMPOSE_FILE"
fi

echo -e "${GREEN}Restarting backend (${COMPOSE_DISPLAY})...${NC}"

cd "$COMPOSE_DIR"

# shellcheck disable=SC2207
COMPOSE_ENV_ARGS=($(compose_env_file_args))
compose() {
  docker compose "${COMPOSE_ENV_ARGS[@]}" -f "$COMPOSE_FILE" "$@"
}

echo -e "${YELLOW}Building app image...${NC}"
compose build app

# Recreate redis so requirepass matches backend/.env (command-line password is
# re-applied on each start; app REDIS_URL comes from the same file).
echo -e "${YELLOW}Recreating redis + app containers...${NC}"
compose up -d --force-recreate redis app

echo -e "${YELLOW}Waiting for app to be healthy...${NC}"
sleep 5

echo -e "${YELLOW}Running migrations...${NC}"
compose exec app python cli.py db migrate

echo -e "${GREEN}Backend restarted and migrations applied (${COMPOSE_DISPLAY})${NC}"
