# Telegram Channel Factory — Production Deploy Baseline v1

## Purpose

Зафиксировать минимальный повторяемый production deploy flow без root-only runtime path.

## Baseline decisions

- системный пользователь для runtime: `tcf`
- директория приложения: `/srv/telegram-channel-factory`
- директория env/secrets: `/etc/telegram-channel-factory`
- compose/runtime запускать из `/srv/telegram-channel-factory`
- файлы приложения принадлежат `tcf:tcf`
- root используется только для первичной подготовки сервера

## Server bootstrap

```bash
sudo useradd --system --create-home --home-dir /srv/telegram-channel-factory --shell /usr/sbin/nologin tcf
sudo mkdir -p /srv/telegram-channel-factory /etc/telegram-channel-factory
sudo chown -R tcf:tcf /srv/telegram-channel-factory
sudo chown root:tcf /etc/telegram-channel-factory
sudo chmod 750 /srv/telegram-channel-factory /etc/telegram-channel-factory
```

## Release sync baseline

```bash
sudo -u tcf git clone <repo> /srv/telegram-channel-factory
sudo -u tcf cp /srv/telegram-channel-factory/.env.live.example /etc/telegram-channel-factory/.env.live
sudo chmod 640 /etc/telegram-channel-factory/.env.live
```

## Runtime rule

Приложение, worker и bot не должны требовать запуск от `root` и не должны жить в `/root/telegram-channel-factory`.

## Release/update command baseline

Запускать обновление от имени runtime-пользователя `tcf`:

```bash
sudo -u tcf APP_DIR=/srv/telegram-channel-factory \
  ENV_FILE=/etc/telegram-channel-factory/.env.live \
  /srv/telegram-channel-factory/scripts/deploy_as_tcf.sh
```

Что делает `scripts/deploy_as_tcf.sh`:
- проверяет, что запуск идёт не от `root`
- переходит в `${APP_DIR}`
- подтягивает fast-forward обновления из git
- проверяет, что runtime-пользователь реально может достучаться до Docker daemon
- выполняет `docker compose --env-file "${ENV_FILE}" up --build -d`
- показывает `docker compose --env-file "${ENV_FILE}" ps`
- не копирует production secrets в `.env` внутри git working tree

## systemd baseline (non-root runtime)

Пример unit для запуска compose stack от имени `tcf` без root-only runtime path:

```ini
[Unit]
Description=Telegram Channel Factory stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=tcf
Group=tcf
WorkingDirectory=/srv/telegram-channel-factory
Environment=TCF_ENV_FILE=/etc/telegram-channel-factory/.env.live
ExecStart=/usr/bin/docker compose -f docker-compose.yml up --build -d
ExecStop=/usr/bin/docker compose -f docker-compose.yml down

[Install]
WantedBy=multi-user.target
```

Release/update по-прежнему выполнять через `sudo -u tcf ... scripts/deploy_as_tcf.sh`, а unit использовать для штатного старта/остановки runtime.

## Release/update process baseline

Повторяемый release/update flow теперь должен идти через `scripts/release_update.sh`.

```bash
sudo -u tcf APP_DIR=/srv/telegram-channel-factory \
  ENV_FILE=/etc/telegram-channel-factory/.env.live \
  RELEASE_REF=<git-tag-or-commit> \
  /srv/telegram-channel-factory/scripts/release_update.sh
```

Что добавляет этот flow:
- требует non-root запуск от runtime-пользователя
- валится, если production env хранит inline `TELEGRAM_BOT_TOKEN` вместо `TELEGRAM_BOT_TOKEN_FILE`
- умеет фиксировать релиз на конкретном `RELEASE_REF`, чтобы обновление было детерминированным
- сохраняет предыдущий и текущий git ref в `${APP_DIR}/.release-backups/`
- делает `python3 -m compileall app scripts`
- применяет `alembic upgrade head` через compose runtime
- поднимает stack через `docker compose --env-file ... up --build -d --remove-orphans`
- считает релиз успешным только после smoke-check `curl http://127.0.0.1:8000/health`

Если smoke-check не проходит, релиз считается незавершённым и требует ручного разбора перед следующим обновлением.

## Next hardening steps

- добавить автоматизированный rollback path на случай падения smoke-check
- включить обязательный release checklist/go-no-go gate перед live rollout
- зафиксировать ротацию токенов после тестовых прогонов
