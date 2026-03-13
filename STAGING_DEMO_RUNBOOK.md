# Telegram Channel Factory — Staging / Demo Runbook

Этот документ нужен для **стабильного показа продукта** и для предрелизного demo/staging прогона без импровизации.

Главная цель:
- поднять продукт в безопасном режиме
- пройти ключевой сценарий от setup до post-setup editing
- не зависеть от скрытых ручных шагов
- не отправлять реальные посты в Telegram

---

## 1. Demo mode principles

Для demo используем безопасную конфигурацию:
- `APP_ENV=staging`
- `RUNTIME_MODE=demo`
- `PUBLISHER_BACKEND=stub`

Это значит:
- продукт ведёт себя как staging/demo
- API/worker/bot path можно показывать
- реальные Telegram публикации не уходят
- ошибкой demo считается любой скрытый live side effect

---

## 2. What the demo must prove

Хороший demo run должен доказать 5 вещей:

1. продукт понятен с первого входа
2. setup flow собирается без ручной магии
3. content pipeline проходит основной путь
4. post-setup editing работает
5. publication queue живёт как управляемый flow

---

## 3. Recommended environment

### Option A — local demo
Подходит для быстрого controlled показа на одной машине.

### Option B — compose-based demo
Подходит для staging-like запуска перед релизом.

Для обоих вариантов безопасная основа одна:

```bash
cp .env.demo .env
```

---

## 4. Pre-demo preparation

Перед демонстрацией нужно проверить:

### Code / repo
```bash
make test
```

Минимум — должны быть зелёные ключевые сценарии.

### Database
- база доступна
- миграции применяются
- нет случайного подключения к live-окружению

### Runtime mode
Проверь `.env`:

```env
APP_ENV=staging
RUNTIME_MODE=demo
PUBLISHER_BACKEND=stub
```

### Safety check
Убедись, что:
- `TELEGRAM_BOT_TOKEN` пустой или demo-safe
- реальные live-каналы не используются для send path
- публикации идут только через `stub`

---

## 5. Startup paths

## Option A — local Python demo

```bash
cp .env.demo .env
python3 -m pip install --user --break-system-packages -e '.[dev]'
alembic upgrade head
```

API:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Worker:

```bash
python3 scripts/run_worker.py
```

Bot runtime smoke:

```bash
python3 scripts/run_bot.py
```

В demo режиме bot runtime не уходит в live polling — это нормально.

---

## Option B — Docker Compose demo

```bash
cp .env.demo .env
docker compose up --build -d
```

Проверка:

```bash
docker compose ps
docker compose logs --tail=100 api worker bot
```

Health smoke:

```bash
make deploy-smoke
```

---

## 6. Demo scenario to show

Это рекомендуемый порядок показа.

### Phase 1 — product entry
Показать:
- что это Telegram Channel Factory
- что пользователь проходит Telegram-first flow
- что есть bot layer + backend + worker

Если показываешь bot shell:
- `/start`
- главное меню
- `Как это работает`
- `Мои каналы`

Checkpoint:
- пользователь понимает, что продукт — это control panel для канала

---

### Phase 2 — create project
Показать создание проекта канала.

Минимум проговорить:
- название проекта
- язык
- что это не одноразовый wizard, а управляемый проект

Checkpoint:
- проект создан

---

### Phase 3 — apply agent team preset
Показать выбор preset команды агентов.

Рекомендуемый preset для demo:
- `starter_3`

Checkpoint:
- у проекта появилась предсказуемая команда агентов

---

### Phase 4 — connect channel
Показать подключение канала и объяснить смысл readiness.

В demo можно показывать safe branch через сохранённые флаги:
- `is_connected=true`
- `bot_is_admin=true`
- `can_post_messages=true`

Checkpoint:
- `connection-check` возвращает `connected`

Если нужно показать ошибочную ветку:
- поставить `can_post_messages=false`
- показать `needs_attention`

---

### Phase 5 — create content plan and task
Показать:
- создание content plan
- появление задачи
- связь между plan → task → draft

Checkpoint:
- контентный цикл запущен

---

### Phase 6 — draft flow
Показать основной путь:
- создать draft
- отредактировать draft
- approve draft

Checkpoint:
- сценарий `draft → edit → approve` выглядит управляемым

---

### Phase 7 — queue publication
Показать постановку публикации в очередь:
- создать publication
- использовать `scheduled_for`
- получить `queued`

Checkpoint:
- публикация не “магически исчезает”, а попадает в управляемый queue flow

---

### Phase 8 — return later / edit after setup
Показать второй важный сценарий:
- открыть уже существующий канал
- поменять настройки
- поменять `publish_mode`
- выполнить regenerate для content plan

Checkpoint:
- продукт полезен не только на старте, но и после setup

---

## 7. Recommended API-backed demo flow

Если демонстрация идёт через API/QA run:

1. создать проект
2. применить `starter_3`
3. создать канал
4. отметить канал как connected
5. сделать `connection-check`
6. создать content plan
7. создать task
8. создать draft
9. отредактировать draft
10. approve draft
11. поставить publication в queue
12. позже открыть канал и изменить настройки
13. regenerate content plan

Это соответствует уже закреплённым e2e-сценариям в репозитории.

---

## 8. Demo checkpoints

В конце демонстрации должны быть подтверждены такие вещи:

- `/start` и базовые экраны понятны
- проект создаётся
- агентный preset применяется
- канал подключается
- content plan создаётся
- draft можно редактировать
- draft можно approve
- publication можно поставить в очередь
- позже можно вернуться и изменить настройки

Если один из пунктов не проходит — demo readiness под вопросом.

---

## 9. Pre-demo smoke checklist

Непосредственно перед показом прогнать:

### Runtime smoke
- `GET /health` отвечает `200`
- worker живой
- bot runtime не падает

### Scenario smoke
- happy path `draft -> edit -> approve -> queue`
- return-later path `open channel -> change settings -> regenerate`

### Environment smoke
- `.env` реально demo-safe
- нет live token leakage
- `PUBLISHER_BACKEND=stub`

---

## 10. Suggested commands before demo

### Fast confidence path

```bash
cp .env.demo .env
python3 -m compileall app scripts
pytest -q tests/test_e2e_mvp_flow.py tests/test_channel_connection_flow.py tests/test_worker.py
```

### Compose confidence path

```bash
cp .env.demo .env
docker compose up --build -d
docker compose ps
make deploy-smoke
```

---

## 11. What not to do in demo

Не стоит:
- показывать live отправку без необходимости
- полагаться на незафиксированные локальные данные
- использовать неясный `.env`, происхождение которого непонятно
- смешивать demo и live каналы
- импровизировать шаги, которые нельзя потом воспроизвести

---

## 12. Definition of done for staging/demo scenario

Staging/demo сценарий считается готовым, если:
- окружение поднимается предсказуемо
- demo идёт в safe mode
- основной пользовательский путь проходится без ручных костылей
- post-setup editing тоже показывается
- перед показом есть короткий smoke path
- другой человек может повторить демонстрацию по этому runbook
