#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/telegram-channel-factory}"
ENV_FILE="${ENV_FILE:-/etc/telegram-channel-factory/.env.live}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
RELEASE_REF="${RELEASE_REF:-}"
SMOKE_URL="${SMOKE_URL:-http://127.0.0.1:8000/health}"
BACKUP_DIR="${BACKUP_DIR:-${APP_DIR}/.release-backups}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"

log() {
  printf '[release_update] %s\n' "$*"
}

fail() {
  printf '[release_update] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

if [[ "$(id -un)" == "root" ]]; then
  fail "Run this script as the runtime user (for example: sudo -u tcf ...), not as root."
fi

require_cmd git
require_cmd docker
require_cmd curl
require_cmd python3

[[ -d "${APP_DIR}" ]] || fail "App dir not found: ${APP_DIR}"
[[ -f "${ENV_FILE}" ]] || fail "Env file not found: ${ENV_FILE}"

if [[ -n "${RELEASE_REF}" && ! "${RELEASE_REF}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  fail "RELEASE_REF contains unsupported characters: ${RELEASE_REF}"
fi

if grep -Eq '^TELEGRAM_BOT_TOKEN=' "${ENV_FILE}"; then
  fail "${ENV_FILE} must not contain inline TELEGRAM_BOT_TOKEN; use TELEGRAM_BOT_TOKEN_FILE instead."
fi

if grep -Eq '^TELEGRAM_BOT_TOKEN_FILE=' "${ENV_FILE}"; then
  TOKEN_FILE="$(grep -E '^TELEGRAM_BOT_TOKEN_FILE=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
  [[ -n "${TOKEN_FILE}" ]] || fail "TELEGRAM_BOT_TOKEN_FILE is empty in ${ENV_FILE}"
  if [[ "${TOKEN_FILE}" != /* ]]; then
    TOKEN_FILE="${APP_DIR}/${TOKEN_FILE}"
  fi
  [[ -f "${TOKEN_FILE}" ]] || fail "Telegram token file not found: ${TOKEN_FILE}"
fi

if grep -Eq '^LLM_API_KEY=' "${ENV_FILE}"; then
  fail "${ENV_FILE} must not contain inline LLM_API_KEY; use LLM_API_KEY_FILE instead."
fi

if grep -Eq '^LLM_API_KEY_FILE=' "${ENV_FILE}"; then
  LLM_KEY_FILE="$(grep -E '^LLM_API_KEY_FILE=' "${ENV_FILE}" | tail -n1 | cut -d= -f2-)"
  [[ -n "${LLM_KEY_FILE}" ]] || fail "LLM_API_KEY_FILE is empty in ${ENV_FILE}"
  if [[ "${LLM_KEY_FILE}" != /* ]]; then
    LLM_KEY_FILE="${APP_DIR}/${LLM_KEY_FILE}"
  fi
  [[ -f "${LLM_KEY_FILE}" ]] || fail "LLM key file not found: ${LLM_KEY_FILE}"
fi

cd "${APP_DIR}"
mkdir -p "${BACKUP_DIR}"

if [[ -d .git ]]; then
  log "Fetching latest git state"
  git fetch --all --tags --prune
  PREVIOUS_REF="$(git rev-parse --short HEAD)"

  if [[ -n "${RELEASE_REF}" ]]; then
    log "Checking out requested release ref ${RELEASE_REF}"
    git checkout --detach "${RELEASE_REF}"
  else
    CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
    [[ -n "${CURRENT_BRANCH}" ]] || fail "Detached HEAD detected. Set RELEASE_REF explicitly to make the release deterministic."
    log "Pulling latest fast-forward updates for ${CURRENT_BRANCH}"
    git pull --ff-only origin "${CURRENT_BRANCH}"
  fi

  CURRENT_REF="$(git rev-parse --short HEAD)"
  printf '%s\n' "${PREVIOUS_REF}" > "${BACKUP_DIR}/previous_ref.txt"
  printf '%s\n' "${CURRENT_REF}" > "${BACKUP_DIR}/current_ref.txt"
  git rev-parse HEAD > "${BACKUP_DIR}/current_commit.txt"
  git status --short > "${BACKUP_DIR}/working_tree_status.txt"
fi

if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is not reachable for user $(id -un). Ensure this runtime user is allowed to use Docker."
fi

log "Building release confidence checks"
python3 -m compileall app scripts

if [[ "${RUN_MIGRATIONS}" == "1" ]]; then
  log "Applying database migrations"
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm api alembic upgrade head
fi

log "Updating compose stack"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up --build -d --remove-orphans

log "Waiting for API smoke endpoint ${SMOKE_URL}"
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error "${SMOKE_URL}" >/dev/null; then
    log "Smoke check passed"
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
    exit 0
  fi
  sleep 2
done

fail "Smoke check failed for ${SMOKE_URL} after deploy."
