#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/srv/telegram-channel-factory"
ENV_FILE_PATH="/etc/telegram-channel-factory/.env.live"
SECRETS_DIR="/etc/telegram-channel-factory/secrets"

cd "$ROOT_DIR"
export ENV_FILE="$ENV_FILE_PATH"
export SECRET_FILES_DIR="$SECRETS_DIR"

docker compose up -d --build "$@"
docker compose ps
