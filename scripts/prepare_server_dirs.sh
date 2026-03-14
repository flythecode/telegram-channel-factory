#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-tcf}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_DIR="${APP_DIR:-/srv/telegram-channel-factory}"
SECRETS_DIR="${SECRETS_DIR:-/etc/telegram-channel-factory}"
APP_SHELL="${APP_SHELL:-/usr/sbin/nologin}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
  groupadd --system "${APP_GROUP}"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd \
    --system \
    --gid "${APP_GROUP}" \
    --create-home \
    --home-dir "${APP_DIR}" \
    --shell "${APP_SHELL}" \
    "${APP_USER}"
fi

mkdir -p "${APP_DIR}" "${SECRETS_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
chown root:"${APP_GROUP}" "${SECRETS_DIR}"
chmod 750 "${APP_DIR}" "${SECRETS_DIR}"

echo "Prepared ${APP_DIR} and ${SECRETS_DIR} for ${APP_USER}:${APP_GROUP}."
