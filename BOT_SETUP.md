# Telegram Channel Factory — Bot Setup

Этот документ объясняет, как поднять **Telegram-бота** для Telegram Channel Factory в локальном, demo и live режимах.

---

## 1. Что делает bot runtime

Bot runtime отвечает за Telegram-вход в продукт:
- принимает `/start`
- показывает базовые экраны
- обрабатывает кнопочный entry flow
- в live-режиме запускает polling через Telegram Bot API

Entry point:

```bash
python3 scripts/run_bot.py
```

---

## 2. Какой файл отвечает за бота

Основные точки:
- `scripts/run_bot.py` — запуск bot runtime
- `app/bot/app.py` — сборка `Bot` и `Dispatcher`
- `app/bot/service.py` — bot screens/service layer
- `app/core/config.py` — env-конфиг и runtime validation

---

## 3. Runtime modes

### `stub`
Безопасный локальный режим.
- polling не запускается
- runtime просто собирается и проверяет, что bot layer не сломан
- реального общения с Telegram нет

### `demo`
Безопасный demo-режим.
- логика похожа на staging/demo
- polling тоже не запускается
- удобен для демонстраций и smoke-check без реального Telegram traffic

### `live`
Боевой режим.
- запускается реальный `dispatcher.start_polling(bot)`
- нужен валидный `TELEGRAM_BOT_TOKEN`
- нужен `PUBLISHER_BACKEND=telegram`

---

## 4. Минимальные env-переменные

Для live bot setup нужны минимум:

```env
RUNTIME_MODE=live
PUBLISHER_BACKEND=telegram
TELEGRAM_BOT_TOKEN=123456:YOUR_REAL_TOKEN
```

Остальные базовые переменные:

```env
APP_ENV=prod
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tcf
```

Важно:
- в tracked-файлы реальные токены не класть
- для live используй отдельный **неотслеживаемый** файл, например `.env.live`

---

## 5. Local setup without real Telegram polling

Если нужно просто проверить, что bot layer собирается:

```bash
cp .env.demo .env
python3 -m pip install --user --break-system-packages -e '.[dev]'
python3 scripts/run_bot.py
```

Ожидаемое поведение:
- процесс не падает
- выводит сообщение:

```text
Bot layer configured in non-live mode; dispatcher assembled successfully.
```

Это означает, что:
- конфиг прочитался
- bot builder живой
- dispatcher/router собираются корректно

---

## 6. Live setup

### Step 1 — создай live env

```bash
cp .env.live.example .env.live
```

Заполни:

```env
APP_ENV=prod
DEBUG=false
RUNTIME_MODE=live
PUBLISHER_BACKEND=telegram
TELEGRAM_BOT_TOKEN=REPLACE_WITH_REAL_TOKEN
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tcf
```

### Step 2 — подставь env

```bash
cp .env.live .env
```

### Step 3 — подними API и БД

Перед живым bot polling должны быть доступны:
- база
- API
- миграции

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 4 — запусти бота

В отдельном процессе:

```bash
python3 scripts/run_bot.py
```

Если всё ок, бот начнёт polling.

---

## 7. Docker Compose path

Если бот запускается через compose:

```bash
cp .env.example .env
docker compose up --build
```

Сервис `bot` поднимется автоматически.

Важно:
- для настоящего live-запуска compose должен получать **реальный** `TELEGRAM_BOT_TOKEN`
- безопаснее всего делать это через локальный `.env`, собранный из `.env.live`
- внутри compose `DATABASE_URL` переопределяется на контейнерный адрес `db:5432`

Проверить логи бота:

```bash
docker compose logs -f bot
```

---

## 8. BotFather checklist

Перед live-запуском в Telegram нужно:

1. создать бота через **@BotFather**
2. получить токен
3. отключить webhook, если раньше использовался webhook-based режим
4. убедиться, что polling не конфликтует с другим инстансом

Если тот же токен уже используется другим polling/webhook процессом, возможны конфликты при старте.

---

## 9. Что проверить после запуска

Минимальный smoke-check:

1. открыть диалог с ботом
2. отправить `/start`
3. убедиться, что бот отвечает
4. проверить, что открываются базовые экраны:
   - главное меню
   - `Как это работает`
   - `Помощь`
   - `Мои каналы`

Если это работает — bot shell поднят корректно.

---

## 10. Частые проблемы

### Problem: `RUNTIME_MODE=live requires TELEGRAM_BOT_TOKEN`
Причина:
- включён `live`, но токен не передан

Что делать:
- проверить `.env`
- проверить, что `TELEGRAM_BOT_TOKEN` реально заполнен

### Problem: `RUNTIME_MODE=live requires PUBLISHER_BACKEND=telegram`
Причина:
- live-режим, но backend всё ещё `stub`

Что делать:
- поставить:

```env
PUBLISHER_BACKEND=telegram
```

### Problem: бот не отвечает на `/start`
Проверь:
- запущен ли `python3 scripts/run_bot.py`
- нет ли конфликта polling с другим процессом
- валиден ли токен
- читается ли правильный `.env`

### Problem: бот стартует локально, но не в compose
Проверь:
- попал ли токен в env контейнера
- смотри логи:

```bash
docker compose logs -f bot
```

### Problem: бот стартует в demo/stub, но не выходит в Telegram
Это нормально.
В `stub` и `demo` polling **не запускается специально**.

---

## 11. Recommended operator flow

### Для локальной разработки
- используй `.env.demo`
- запускай bot runtime как assembly/smoke check
- не подключай real token без необходимости

### Для demo
- используй `RUNTIME_MODE=demo`
- сохраняй безопасный stub behavior
- показывай продуктовый shell без реальных публикаций

### Для live
- используй отдельный неотслеживаемый `.env.live`
- не коммить токен
- сначала подними API/DB/migrations
- потом запускай bot polling

---

## 12. Short command cheatsheet

### Local bot smoke

```bash
cp .env.demo .env
python3 scripts/run_bot.py
```

### Live bot run

```bash
cp .env.live .env
python3 scripts/run_bot.py
```

### Compose logs

```bash
docker compose logs -f bot
```

---

## 13. Definition of done for bot setup

Bot setup считается рабочим, если:
- конфиг проходит validation
- bot runtime стартует без падения
- в live-режиме polling поднимается
- бот отвечает на `/start`
- оператор понимает, где смотреть логи и что проверять при сбое
