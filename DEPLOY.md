# Production Deploy — Telegram Channel Factory

## Canonical production paths

- App root: `/srv/telegram-channel-factory`
- Live env file: `/etc/telegram-channel-factory/.env.live`
- Secret dir: `/etc/telegram-channel-factory/secrets`
- Safe wrapper: `/usr/local/bin/tcf-compose`
- Safe deploy script: `/srv/telegram-channel-factory/scripts/deploy-prod.sh`

## Golden rule

**Never deploy production with raw `docker compose` from `/srv/telegram-channel-factory` unless the live env is explicitly exported.**

Use one of these:

```bash
tcf-compose ps
tcf-compose logs -f api
/srv/telegram-channel-factory/scripts/deploy-prod.sh api worker bot
```

## Safe deploy

```bash
/srv/telegram-channel-factory/scripts/deploy-prod.sh api worker bot
```

This script always uses:

- `ENV_FILE=/etc/telegram-channel-factory/.env.live`
- `SECRET_FILES_DIR=/etc/telegram-channel-factory/secrets`

## Forbidden routine action

Do **not** use this as a normal deploy path:

```bash
docker compose down -v
```

`down -v` destroys the Postgres volume and wipes user data. It is only for last-resort disaster recovery with explicit approval.

## Health checks

```bash
tcf-compose ps
tcf-compose logs --tail=100 api
tcf-compose logs --tail=100 bot
tcf-compose logs --tail=100 worker
```

## If database auth ever breaks again

1. Check that the deploy used the canonical live env
2. Verify `/srv/telegram-channel-factory/.env` matches `/etc/telegram-channel-factory/.env.live`
3. Re-run deploy via `deploy-prod.sh`
4. Do not wipe volumes unless explicitly approved
