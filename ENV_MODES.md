# Telegram Channel Factory — Environment Modes

Этот документ нужен, чтобы команда не путалась между **dev / test / demo / live** режимами.

Главная идея:
**режим должен быть выбран явно**, а не случайно через забытый `.env`.

---

## 1. Короткая карта режимов

| Mode | Для чего | Реальный Telegram send | Polling bot | Publisher backend | Риск |
|---|---|---:|---:|---|---|
| `dev` | локальная разработка | нет | нет / по ситуации | `stub` | низкий |
| `test` | автоматические тесты | нет | нет | `stub` | минимальный |
| `demo` | показ продукта | нет | нет | `stub` | низкий |
| `live` | реальная работа | да | да | `telegram` | высокий |

Важно:
- `dev/test/demo/live` в этом документе — это **операционные режимы работы команды**
- в коде runtime validation опирается в первую очередь на:
  - `APP_ENV`
  - `RUNTIME_MODE`
  - `PUBLISHER_BACKEND`

---

## 2. Как думать о режимах

### `dev`
Это режим разработчика.

Задача режима:
- писать код
- гонять API локально
- проверять flow без риска реальных публикаций

Типичные настройки:
- `APP_ENV=dev`
- `RUNTIME_MODE=stub`
- `PUBLISHER_BACKEND=stub`
- локальная БД
- токен Telegram не нужен

Ожидания:
- API работает
- worker работает
- bot runtime собирается
- реальный polling и реальные отправки не нужны

---

### `test`
Это режим автотестов.

Задача режима:
- детерминированно проверять логику
- не зависеть от внешнего Telegram
- не трогать live-секреты

Типичные настройки:
- `APP_ENV=test`
- `RUNTIME_MODE=stub`
- `PUBLISHER_BACKEND=stub`
- in-memory / isolated DB
- токен Telegram пустой

Ожидания:
- тесты должны быть предсказуемыми
- никакого реального Telegram I/O
- никакой зависимости от ручного окружения разработчика

---

### `demo`
Это режим демонстрации продукта.

Задача режима:
- показать продуктовый shell
- пройти сценарий без риска реальной публикации
- показать bot/API/worker flow в staging-like конфигурации

Типичные настройки:
- `APP_ENV=staging`
- `RUNTIME_MODE=demo`
- `PUBLISHER_BACKEND=stub`
- `DEBUG=false`
- demo-данные или безопасная staging БД

Ожидания:
- продукт выглядит близко к боевому
- реальные посты не отправляются
- можно безопасно показывать сценарий end-to-end

Важно:
- `demo` не должен случайно превращаться в `live`
- наличие токена само по себе не должно ломать safe-поведение demo

---

### `live`
Это реальный продуктовый режим.

Задача режима:
- реальная работа с Telegram
- реальный bot polling
- реальные публикации

Типичные настройки:
- `APP_ENV=prod`
- `RUNTIME_MODE=live`
- `PUBLISHER_BACKEND=telegram`
- реальный `TELEGRAM_BOT_TOKEN`
- production/staging DB

Ожидания:
- бот отвечает пользователю в Telegram
- worker реально отправляет публикации
- ошибки Telegram считаются operational events, а не dev-шумом

Важно:
- live нельзя запускать случайно
- live требует явной конфигурации и осознанного operator action

---

## 3. Как эти режимы выражаются в env

### Local dev
Обычный локальный path:

```env
APP_ENV=dev
RUNTIME_MODE=stub
PUBLISHER_BACKEND=stub
```

### Automated test
В тестах:

```env
APP_ENV=test
RUNTIME_MODE=stub
PUBLISHER_BACKEND=stub
```

### Demo
Для демонстрации:

```env
APP_ENV=staging
RUNTIME_MODE=demo
PUBLISHER_BACKEND=stub
```

### Live
Для реальной работы:

```env
APP_ENV=prod
RUNTIME_MODE=live
PUBLISHER_BACKEND=telegram
TELEGRAM_BOT_TOKEN=...
```

---

## 4. Current repo files and their meaning

### `.env.example`
Базовый шаблон для локальной разработки.

Типовой смысл:
- local dev
- safe default
- no real Telegram send

### `.env.demo`
Шаблон для demo/staging-like запуска.

Типовой смысл:
- показать продукт
- не стрелять в Telegram
- использовать safe publisher behavior

### `.env.live.example`
Шаблон для боевого запуска.

Типовой смысл:
- стартовая форма для `.env.live`
- реальные секреты сюда в git не класть

### `.env.live`
Должен быть:
- локальным
- неотслеживаемым
- с реальными токенами

---

## 5. Safe defaults

В этом проекте safe default такой:
- если ты не уверен, используй `stub`
- если показываешь продукт, используй `demo`
- если нужен реальный Telegram, переходи в `live` только явно

Нельзя считать нормой:
- хранить live токен в tracked `.env`
- локально запускать live случайно
- смешивать demo и live env в одном файле без понимания последствий

---

## 6. What works in each mode

### Dev
Работает:
- API
- DB
- migrations
- worker
- bot assembly
- stub publication flow

Не ожидаем:
- реальный Telegram polling
- реальные sendMessage вызовы

### Test
Работает:
- pytest
- fake/in-memory path
- deterministic flow checks

Не ожидаем:
- внешние интеграции
- ручные env secrets

### Demo
Работает:
- product walkthrough
- setup flow demo
- draft/publication demo
- safe worker run

Не ожидаем:
- реальные публикации в канал
- реальный Telegram blast

### Live
Работает:
- bot polling
- real Telegram publication
- operational queue processing
- production-like monitoring/logging path

Не ожидаем:
- случайная безопасность при кривом env
- бездумный запуск без проверки токенов/прав

---

## 7. Common mistakes

### Mistake 1 — думают, что `demo` публикует реально
Нет.
`demo` должен оставаться безопасным режимом.

### Mistake 2 — запускают `live` с `stub`
Это невалидная конфигурация.

### Mistake 3 — кладут реальный токен в `.env.example`
Так делать нельзя.

### Mistake 4 — ожидают, что bot polling стартует в `stub`/`demo`
В текущем проекте это не так.
Polling запускается только в `live`.

### Mistake 5 — путают `APP_ENV` и `RUNTIME_MODE`
Это разные вещи:
- `APP_ENV` описывает среду (`dev/staging/prod/test`)
- `RUNTIME_MODE` описывает поведение runtime (`stub/demo/live`)

---

## 8. Recommended team rules

### Для разработки
Использовать:
- `.env.example`
- или локальный `.env`, построенный от safe defaults

### Для demo
Использовать:
- `.env.demo`
- отдельную demo БД / controlled data set

### Для live
Использовать:
- `.env.live.example` как шаблон
- `.env.live` как реальный локальный секретный файл

### Для CI / tests
Использовать:
- жёстко заданные test env values
- никакой зависимости от локального `.env`

---

## 9. Operator checklist before run

### Перед dev run
- уверен, что `RUNTIME_MODE=stub`
- понимаешь, какая БД указана

### Перед demo run
- уверен, что `RUNTIME_MODE=demo`
- уверен, что `PUBLISHER_BACKEND=stub`
- проверил, что реальных send path не будет

### Перед live run
- `RUNTIME_MODE=live`
- `PUBLISHER_BACKEND=telegram`
- задан `TELEGRAM_BOT_TOKEN`
- проверен target channel
- понятен deploy/logging path

---

## 10. Minimal truth table

### Safe local dev
```env
APP_ENV=dev
RUNTIME_MODE=stub
PUBLISHER_BACKEND=stub
```

### Safe demo
```env
APP_ENV=staging
RUNTIME_MODE=demo
PUBLISHER_BACKEND=stub
```

### Real live
```env
APP_ENV=prod
RUNTIME_MODE=live
PUBLISHER_BACKEND=telegram
TELEGRAM_BOT_TOKEN=...
```

---

## 11. Definition of done for mode separation

Разделение режимов считается понятным, если любой участник команды может без догадок ответить:
- какой env нужен для локальной разработки
- какой env нужен для demo
- какой env нужен для live
- где возможны реальные Telegram send
- почему polling не стартует в safe режимах
