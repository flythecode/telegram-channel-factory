# Telegram Channel Factory — Release Smoke Checks

Этот документ фиксирует короткий smoke path перед packaging/sign-off релиза.

## 1. Version marker
Проверить:
```bash
cat VERSION
```

Ожидаемо:
- версия существует
- соответствует текущему релизному состоянию

## 2. Syntax / import confidence
```bash
python3 -m compileall app scripts
```

## 3. Test confidence
Минимальный релизный прогон:
```bash
pytest -q tests/test_e2e_mvp_flow.py tests/test_channel_connection_flow.py tests/test_bot_navigation.py tests/test_worker.py tests/test_runtime_hardening.py tests/test_telegram_publisher.py
```

Полный прогон:
```bash
pytest -q
```

## 4. Migration confidence
```bash
alembic upgrade head
```

## 5. API health confidence
Локально:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Проверка:
```bash
curl http://127.0.0.1:8000/health
```

Ожидаемо:
- `200`
- `{"status":"ok",...}`

## 6. Worker confidence
```bash
python3 scripts/run_worker.py
```

Ожидаемо:
- worker стартует без crash-loop

## 7. Bot runtime confidence
Demo/stub path:
```bash
cp .env.demo .env
python3 scripts/run_bot.py
```

Ожидаемо:
- bot runtime собирается
- в non-live режиме не падает

## 8. Compose confidence
```bash
make deploy-smoke
```

Ожидаемо:
- compose stack поднимается
- `/health` отвечает изнутри контейнера

## 9. Docs confidence
Проверить наличие:
- `README.md`
- `BOT_SETUP.md`
- `CHANNEL_CONNECTION_FLOW.md`
- `ENV_MODES.md`
- `STAGING_DEMO_RUNBOOK.md`
- `FINAL_QA_RUNBOOK.md`
- `RELEASE_MANIFEST.md`

## 10. Release decision
Release smoke считается пройденным, если:
- версия зафиксирована
- compile/test/migration path зелёные
- API/worker/bot стартуют предсказуемо
- compose smoke path живой
- релизные документы на месте
