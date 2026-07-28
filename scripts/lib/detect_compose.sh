#!/usr/bin/env bash
# Shared Docker Compose context detection for exec.sh, deploy.sh, etc.
# Requires PROJECT_DIR to be set before sourcing. Sets BACKEND_DIR if unset.
# Optional: APP_CONTAINER_NAME (default: ai-workspace-app).
# Output format from detect_compose_context(): "<compose_dir>|<compose_file>"

: "${PROJECT_DIR:?PROJECT_DIR must be set before sourcing detect_compose.sh}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_DIR/backend}"
APP_CONTAINER_NAME="${APP_CONTAINER_NAME:-ai-workspace-app}"

# Compose ${VAR} interpolation reads the project .env / --env-file, NOT service
# env_file. Prefer backend/.env so POSTGRES_PASSWORD / REDIS_PASSWORD match the app.
compose_env_file_args() {
  if [ -f "$BACKEND_DIR/.env" ]; then
    echo --env-file "$BACKEND_DIR/.env"
  fi
}

# Detect compose working dir and file from running containers.
detect_compose_context() {
  local container_name=""
  local compose_dir=""
  local compose_file=""
  local compose_path=""

  if docker ps --format '{{.Names}}' | grep -q "^${APP_CONTAINER_NAME}$"; then
    container_name="$APP_CONTAINER_NAME"
  elif docker ps --format '{{.Names}}' | grep -q "^backend$"; then
    container_name="backend"
  fi

  # Detect from Docker Compose labels first (most reliable with multiple compose files).
  if [ -n "$container_name" ]; then
    compose_dir=$(docker inspect "$container_name" --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' 2>/dev/null || echo "")
    compose_path=$(docker inspect "$container_name" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>/dev/null || echo "")
    compose_path="${compose_path%%,*}" # Use first file when there are multiple

    if [ -n "$compose_path" ] && [ -f "$compose_path" ]; then
      compose_file=$(basename "$compose_path")
      compose_dir=$(dirname "$compose_path")
      echo "${compose_dir}|${compose_file}"
      return
    fi

    if [ -n "$compose_dir" ] && [ -n "$compose_path" ] && [ -f "${compose_dir}/${compose_path}" ]; then
      compose_file=$(basename "$compose_path")
      echo "${compose_dir}|${compose_file}"
      return
    fi
  fi

  # Fallback priority: root dev stack, then other root files, then legacy backend/.
  if [ -f "$PROJECT_DIR/docker-compose.dev.yml" ]; then
    echo "${PROJECT_DIR}|docker-compose.dev.yml"
  elif [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "${PROJECT_DIR}|docker-compose.yml"
  elif [ -f "$PROJECT_DIR/docker-compose.prod.yml" ]; then
    echo "${PROJECT_DIR}|docker-compose.prod.yml"
  elif [ -f "$BACKEND_DIR/docker-compose.dev.yml" ]; then
    echo "${BACKEND_DIR}|docker-compose.dev.yml"
  elif [ -f "$BACKEND_DIR/docker-compose.yml" ]; then
    echo "${BACKEND_DIR}|docker-compose.yml"
  else
    echo "|"
  fi
}

is_app_container_running() {
  docker ps --format '{{.Names}}' | grep -q "^${APP_CONTAINER_NAME}$"
}
