# Telegram Channel Factory — Channel Connection Flow

Этот документ фиксирует **воспроизводимый flow подключения Telegram-канала** к проекту.

Цель простая: чтобы оператор, разработчик или QA не угадывали, что значит “канал подключён”, какие права нужны и как проверить, что всё действительно готово к публикации.

---

## 1. Что значит “канал подключён” в MVP

В текущем MVP канал считается корректно подключённым, если выполнены три условия:

- `is_connected = true`
- `bot_is_admin = true`
- `can_post_messages = true`

Если хотя бы одно из этих условий не выполнено, статус канала считается:

- `needs_attention`

Если все три выполнены:

- `connected`

---

## 2. Product meaning of the flow

Channel connection flow нужен, чтобы перевести проект из состояния:
- “канал в системе заведен формально”

в состояние:
- “бот реально может публиковать в этот канал”

То есть это не просто заполнение карточки канала, а **операционный readiness check** перед публикациями.

---

## 3. Минимальные данные канала

При создании/обновлении канала в MVP используются поля:
- `channel_title`
- `channel_username` (опционально)
- `channel_id` (опционально)
- `is_connected`
- `bot_is_admin`
- `can_post_messages`
- `connection_notes`
- `publish_mode`

Практически для реальной публикации важно, чтобы у канала был хотя бы один target:
- `channel_id`
- или `channel_username`

Если их нет, Telegram publisher не сможет отправить сообщение.

---

## 4. User flow

Ожидаемый пользовательский сценарий:

1. пользователь создаёт проект
2. пользователь добавляет канал в проект
3. бот/система объясняет, что нужно:
   - добавить бота в админы канала
   - выдать право на публикацию
4. пользователь возвращается после настройки канала в Telegram
5. система отмечает/обновляет connection flags
6. выполняется connection check
7. пользователь получает понятный результат:
   - `connected`
   - или `needs_attention`

---

## 5. API flow

### Step 1 — создать канал

```http
POST /api/v1/projects/{project_id}/channels
```

Пример:

```json
{
  "channel_title": "My Channel",
  "channel_username": "my_channel",
  "publish_mode": "manual"
}
```

На этом этапе канал обычно ещё **не fully connected**.

---

### Step 2 — сохранить результат подключения

```http
POST /api/v1/channels/{channel_id}/connect
```

Пример успешной готовности:

```json
{
  "is_connected": true,
  "bot_is_admin": true,
  "can_post_messages": true
}
```

Пример частично готового канала:

```json
{
  "is_connected": true,
  "bot_is_admin": true,
  "can_post_messages": false
}
```

---

### Step 3 — проверить статус подключения

```http
GET /api/v1/channels/{channel_id}/connection-check
```

Ответ:

```json
{
  "is_connected": true,
  "bot_is_admin": true,
  "can_post_messages": true,
  "status": "connected"
}
```

Или:

```json
{
  "is_connected": true,
  "bot_is_admin": true,
  "can_post_messages": false,
  "status": "needs_attention"
}
```

---

## 6. Status interpretation

### `connected`
Означает:
- канал помечен как подключённый
- бот админ
- бот может публиковать сообщения

Это минимально достаточное состояние для publication flow.

### `needs_attention`
Означает, что подключение ещё не доведено до рабочего состояния.

Причины могут быть такие:
- канал не подтверждён как подключённый
- бот не админ
- у бота нет права `can_post_messages`

---

## 7. Decision table

### Case A — всё готово
- `is_connected = true`
- `bot_is_admin = true`
- `can_post_messages = true`
- результат: `connected`

### Case B — бот не добавлен
- `is_connected = false`
- результат: `needs_attention`

### Case C — бот добавлен, но не админ
- `is_connected = true`
- `bot_is_admin = false`
- результат: `needs_attention`

### Case D — бот админ, но без права писать
- `is_connected = true`
- `bot_is_admin = true`
- `can_post_messages = false`
- результат: `needs_attention`

---

## 8. Live operator checklist

Перед тем как считать канал готовым к публикации, проверь:

1. бот реально добавлен в нужный канал
2. бот выдан в админы
3. боту разрешено публиковать сообщения
4. в системе у канала сохранён:
   - `channel_id`
   - или `channel_username`
5. `connection-check` возвращает `connected`

Если хотя бы один пункт не проходит — публикация ещё не считается надёжно готовой.

---

## 9. Recommended UX messaging

Если connection check не проходит, пользователь должен получать не абстрактное “ошибка”, а конкретное объяснение.

Рекомендуемые сообщения по веткам:

### Missing connection
> Канал ещё не отмечен как подключённый. Добавь бота в канал и повтори проверку.

### Bot is not admin
> Бот найден, но не является администратором канала. Выдай права администратора и повтори проверку.

### Missing post permission
> Бот добавлен, но не может публиковать сообщения. Включи право на отправку сообщений и повтори проверку.

---

## 10. QA scenarios

Минимум что нужно прогонять в QA:

### Scenario 1 — happy path
1. создать проект
2. создать канал
3. выполнить connect с:
   - `is_connected=true`
   - `bot_is_admin=true`
   - `can_post_messages=true`
4. проверить, что `connection-check` даёт `connected`

### Scenario 2 — missing permission
1. создать проект
2. создать канал
3. выполнить connect с:
   - `is_connected=true`
   - `bot_is_admin=true`
   - `can_post_messages=false`
4. проверить, что `connection-check` даёт `needs_attention`

### Scenario 3 — not connected yet
1. создать канал
2. сразу вызвать `connection-check`
3. проверить, что статус = `needs_attention`

---

## 11. How this relates to publication flow

Channel connection flow и publication flow связаны, но это не одно и то же.

Connection flow отвечает на вопрос:
- “готов ли канал в принципе?”

Publication flow отвечает на вопрос:
- “можем ли мы сейчас отправить конкретный post/draft?”

Даже если connection flags в порядке, publication всё равно может упасть, если:
- неправильный `channel_id`
- неправильный `channel_username`
- токен бота неверный
- Telegram API вернул ошибку

Поэтому channel connection flow — это **не полная гарантия**, а минимальный readiness layer.

---

## 12. Current MVP limitation

В текущем MVP connection check основан на сохранённых флагах и не делает live Telegram introspection.

То есть:
- система не идёт в Telegram и не валидирует права напрямую в момент check
- она опирается на сохранённое состояние канала

Это нормально для MVP, но важно понимать ограничение.

---

## 13. Definition of done for channel connection flow

Flow считается собранным, если:
- канал можно создать в проекте
- можно сохранить connection state
- можно повторно проверить состояние
- happy path даёт `connected`
- проблемные ветки дают `needs_attention`
- оператор понимает, что именно нужно исправить
