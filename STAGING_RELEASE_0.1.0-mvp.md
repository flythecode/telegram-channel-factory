# Telegram Channel Factory — Staging Release 0.1.0-mvp

Это документ первого **staging release** для MVP.

Он фиксирует:
- что именно считается staging release
- как его поднимать
- какой сценарий обязательно прогонять
- по каким критериям считать релиз успешным
- когда после этого можно говорить о готовности к live decision

---

## 1. Release identity

- Release name: `0.1.0-mvp`
- Release type: `staging`
- Environment intent: `safe staging / demo-like validation`
- Runtime mode: `demo`
- Publisher backend: `stub`

Почему так:
- staging release должен подтвердить продуктовый путь
- но не должен случайно стрелять в live Telegram

---

## 2. Purpose of this staging release

Этот staging release нужен не для “красивого статуса”, а для финальной проверки главного вопроса:

> можно ли пройти основной MVP path без разработческой магии и без скрытых ручных фиксов?

Если да — продукт можно считать **готовым к следующему шагу решения по live запуску**.

---

## 3. Required environment for staging release

Использовать safe env:

```bash
cp .env.demo .env
```

Ключевые ожидаемые значения:

```env
APP_ENV=staging
RUNTIME_MODE=demo
PUBLISHER_BACKEND=stub
```

Нельзя проводить staging release, если:
- случайно включён `live`
- подмешан реальный production token
- send path может уйти в реальный канал

---

## 4. Recommended startup path

## Option A — local staging-like run

```bash
cp .env.demo .env
python3 -m compileall app scripts
pytest -q tests/test_e2e_mvp_flow.py tests/test_channel_connection_flow.py tests/test_bot_navigation.py tests/test_worker.py tests/test_runtime_hardening.py tests/test_telegram_publisher.py
alembic upgrade head
```

Запуск API:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Запуск worker:

```bash
python3 scripts/run_worker.py
```

Bot runtime smoke:

```bash
python3 scripts/run_bot.py
```

## Option B — compose-based staging run

```bash
cp .env.demo .env
make deploy-smoke
```

---

## 5. Mandatory pre-release checks

Перед основным сценарием должны пройти:

### Version check
```bash
cat VERSION
```
Ожидаемо:
- `0.1.0-mvp`

### Release smoke
Смотри:
- `RELEASE_SMOKE.md`

### Docs readiness
На месте должны быть:
- `README.md`
- `BOT_SETUP.md`
- `CHANNEL_CONNECTION_FLOW.md`
- `ENV_MODES.md`
- `STAGING_DEMO_RUNBOOK.md`
- `FINAL_QA_RUNBOOK.md`
- `RELEASE_MANIFEST.md`
- `GO_NO_GO_CHECK.md`

---

## 6. Mandatory MVP scenario to validate

В staging release обязательно пройти основной пользовательский сценарий.

### Scenario A — happy path
1. открыть продукт / bot shell
2. `/start`
3. создать проект
4. применить `starter_3`
5. подключить канал
6. проверить `connection-check = connected`
7. создать content plan
8. создать task
9. создать draft
10. отредактировать draft
11. approve draft
12. поставить publication в queue

### Scenario B — post-setup editing path
1. вернуться к уже созданному каналу
2. открыть канал позже
3. изменить `channel_title`
4. изменить `publish_mode`
5. выполнить regenerate content plan

---

## 7. Expected results

Staging release считается успешным, если:

### Product shell
- `/start` работает
- главное меню понятно
- bot runtime не падает

### Setup path
- проект создаётся
- preset применяется
- channel connection flow читаем и работоспособен

### Content path
- content plan создаётся
- task/draft flow работает
- draft edit/approve работает
- publication queue даёт понятный статус

### Post-setup management
- канал можно открыть позже
- настройки меняются
- regenerate path работает

### Runtime / ops
- API health = `200`
- worker не уходит в crash-loop
- demo mode остаётся безопасным
- release path не требует скрытых ручных фиксов

---

## 8. What counts as failure

Staging release считается проваленным, если происходит хотя бы одно:
- `/start` не даёт внятного входа
- setup flow ломается
- preset не применяется
- connection flow непонятен или сломан
- нельзя дойти до draft
- edit/approve ломается
- queue/publication flow непрозрачен
- return-later/edit flow ломается
- worker/api/bot unstable
- запуск требует скрытой ручной магии

---

## 9. Evidence sources for the staging decision

Решение по staging release должно опираться на:
- `GO_NO_GO_CHECK.md`
- `FINAL_QA_RUNBOOK.md`
- `RELEASE_SMOKE.md`
- `STAGING_DEMO_RUNBOOK.md`
- фактический результат прогона текущего staging сценария

---

## 10. Recommended result template

После staging run заполнить:

- Date:
- Release:
- Runner:
- Environment:
- Mode:
- `/start` OK: yes/no
- Setup flow OK: yes/no
- Agent preset OK: yes/no
- Channel connection OK: yes/no
- Draft flow OK: yes/no
- Publication queue OK: yes/no
- Return-later/edit OK: yes/no
- API/worker/bot stable: yes/no
- Hidden manual fixes needed: yes/no
- Final staging result: pass / fail
- Notes:

---

## 11. Current staging decision

На основании текущего состояния репозитория и собранных артефактов:

### Current decision
- **Proceed with staging release 0.1.0-mvp**

### Meaning
Это означает:
- staging release можно и нужно поднимать
- основной MVP path уже достаточно собран, чтобы проверить его как единое целое

### Not the same as
Это **не означает автоматически**, что live launch уже подтверждён без дополнительного фактического staging pass

---

## 12. Exit criteria after staging release

После staging release возможны два исхода:

### PASS
Если staging сценарий прошёл:
- MVP можно считать **готовым к live go decision**
- уверенность в продукте повышается с “go for staging release” до более сильного “go, subject to controlled live launch”

### FAIL
Если staging сценарий не прошёл:
- статус возвращается в `NO-GO`
- фиксируются blocking issues
- после исправлений staging run повторяется
