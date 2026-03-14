#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/telegram-channel-factory}"
ENV_FILE="${ENV_FILE:-/etc/telegram-channel-factory/.env.live}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

if [[ "$(id -un)" == "root" ]]; then
  echo "Run this script as the runtime user (for example: sudo -u tcf ...), not as root." >&2
  exit 1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  echo "App dir not found: ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Env file not found: ${ENV_FILE}" >&2
  exit 1
fi

if grep -Eq '^TELEGRAM_BOT_TOKEN_FILE=' "${ENV_FILE}"; then
  TOKEN_FILE="$(grep -E '^TELEGRAM_BOT_TOKEN_FILE=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
  if [[ -n "${TOKEN_FILE}" ]]; then
    if [[ "${TOKEN_FILE}" != /* ]]; then
      TOKEN_FILE="${APP_DIR}/${TOKEN_FILE}"
    fi
    if [[ ! -f "${TOKEN_FILE}" ]]; then
      echo "Telegram token file not found: ${TOKEN_FILE}" >&2
      exit 1
    fi
  fi
fi

cd "${APP_DIR}"

if [[ -d .git ]]; then
  git fetch --all --prune
  git pull --ff-only
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not reachable for user $(id -un). Ensure this runtime user is allowed to use Docker." >&2
  exit 1
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up --build -d

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
