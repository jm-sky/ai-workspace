#!/bin/bash

# Docker Compose Exec Wrapper
# This script executes commands in the Docker Compose container
#
# Usage: ./exec.sh [command] [arguments...]
# Example: ./exec.sh                    # Runs: python -m cli (interactive menu)
# Example: ./exec.sh python -m cli users list
# Example: ./exec.sh python -m cli db migrate

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
APP_CONTAINER_NAME="ai-workspace-app"

# shellcheck source=scripts/lib/detect_compose.sh
source "$PROJECT_DIR/scripts/lib/detect_compose.sh"

# Determine which docker-compose file to use
COMPOSE_CONTEXT=$(detect_compose_context)
COMPOSE_DIR="${COMPOSE_CONTEXT%%|*}"
COMPOSE_FILE="${COMPOSE_CONTEXT##*|}"

if [ -z "$COMPOSE_FILE" ] || [ -z "$COMPOSE_DIR" ]; then
  echo -e "${RED}Error: Could not detect docker-compose file${NC}"
  echo -e "${YELLOW}Make sure at least one container is running or a compose file exists in ${PROJECT_DIR} or ${BACKEND_DIR}${NC}"
  exit 1
fi

# Check if compose directory exists
if [ ! -d "$COMPOSE_DIR" ]; then
  echo -e "${RED}Error: Compose directory not found: $COMPOSE_DIR${NC}"
  exit 1
fi

# Check if docker-compose file exists
if [ ! -f "$COMPOSE_DIR/$COMPOSE_FILE" ]; then
  echo -e "${RED}Error: Docker Compose file not found: $COMPOSE_DIR/$COMPOSE_FILE${NC}"
  exit 1
fi

cd "$COMPOSE_DIR"

# shellcheck disable=SC2207
COMPOSE_ENV_ARGS=($(compose_env_file_args))
compose() {
  docker compose "${COMPOSE_ENV_ARGS[@]}" -f "$COMPOSE_FILE" "$@"
}

# Check if container is running
if ! compose ps --services --filter status=running | grep -q '^app$'; then
  echo -e "${YELLOW}Warning: Service 'app' is not running. Starting it...${NC}"
  compose up -d app

  # Wait a bit for container to be ready
  echo -e "${YELLOW}Waiting for container to be ready...${NC}"
  sleep 3
fi

# If no arguments provided, default to 'python -m cli'
if [ $# -eq 0 ]; then
  CMD_ARGS=("python" "-m" "cli")
else
  CMD_ARGS=("python" "-m" "cli" "$@")
fi

# Execute command in container
echo -e "${GREEN}Executing in container (${COMPOSE_FILE}):${NC} ${CMD_ARGS[*]}"
compose exec app "${CMD_ARGS[@]}"
