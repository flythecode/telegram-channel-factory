# Telegram Channel Factory — Manual Telegram UI e2e run

- Date: 2026-03-13 22:49 UTC
- Environment: local UI-only bot flow with in-memory fake session store
- Mode: stub / test-safe
- QA runner: Муха
- Goal: пройти основной Telegram flow только через bot UI, без API-bypass

## Scope actually executed

Прогон шёл только через `resolve_screen_for_text(...)` и bot UI state machine:
- `/start`
- wizard создания проекта
- выбор agent preset
- channel connection flow
- вход в dashboard
- просмотр sections `Контент-план`, `Черновики`, `Публикации`, `Режим работы`
- смена publish mode
- попытка вернуться позже и снова открыть проект

## Result by checkpoint

- `/start` OK: **yes**
- Main menu OK: **yes**
- Setup flow OK: **yes**
- Agent preset OK: **yes**
- Channel connection OK: **yes**
- Content plan via UI OK: **no**
- Draft flow via UI OK: **no**
- Publication queue via UI OK: **no**
- Return later / reopen existing channel OK: **no**

## What passed

### 1. Entry and wizard
UI path `/start -> Создать канал -> Начать` работает.
Wizard проходит до создания проекта.

### 2. Preset selection
Кнопка `3 агента — Быстрый старт` применяет preset и переводит в channel connection flow.

### 3. Channel connection
Передача `@username` и кнопка `Проверить подключение` дают happy-path экран `Канал подключён и готов к публикациям`.

### 4. Project dashboard
`Открыть проект` открывает dashboard канала.
Экран показывает режим, число агентов, число контент-планов и черновиков.

### 5. Mode change
Экран `Режим работы` открывается.
Кнопка `Mode: semi_auto` реально меняет состояние канала.

## Blocking gaps found in real UI-only e2e

### Blocker 1 — content plan path is view-only
После кнопки `Создать контент-план` UI не создаёт план и не запускает flow генерации.
Вместо этого открывается пустой экран раздела:
`Контент-планов пока нет.`

Итог: из UI нельзя пройти checkpoint `content plan creation`.

### Blocker 2 — no UI path from content plan to task/draft
После подключения канала и входа в dashboard нет рабочего UI-действия, которое реально создаёт:
- content plan
- task
- draft

Кнопки `Создать контент-план`, `Сгенерировать 10 идей`, `Создать 3 черновика` сейчас не доводят пользователя до объектов pipeline.

Итог: невозможно пройти `plan -> task -> draft` только через UI.

### Blocker 3 — draft actions are unreachable in a pure UI run
Экран detail с кнопками `Approve`, `Reject`, `Edit draft`, `Regenerate`, `Create publication` существует,
но до него нельзя дойти честным UI-only путём, потому что UI не умеет создать/показать draft в этом сценарии.

Итог: checkpoint `edit + approve draft` заблокирован выше по цепочке.

### Blocker 4 — publication flow unreachable in UI-only run
Экран публикаций существует, но остаётся пустым.
До `Create publication / Schedule publication / Publish now` нельзя дойти из-за отсутствия создаваемого draft.

Итог: checkpoint `queue/publication flow` не проходит.

### Blocker 5 — return later / reopen flow broken
После успешного setup экран `Мои каналы` всё ещё показывает пустое состояние:
`У тебя пока нет каналов или подключённых проектов.`

Также попытка позже открыть проект по названию `Alpha Factory` не срабатывает и возвращает в главное меню.

Итог: post-setup reopen/edit path в текущем UI-only сценарии сломан.

## Final decision

**FAIL** for full manual Telegram UI e2e.

Причина: entry/setup/preset/channel connection работают, но основной MVP path блокируется на переходе к content plan / draft / publication / reopen flow.

## Next task implied by this run

Следующий backlog item должен закрыть найденные дыры UI-only сценария:
- дать реальное UI-действие для создания content plan
- дать UI-путь до task/draft
- довести draft actions до достижимого состояния
- довести publication queue до достижимого состояния
- починить `Мои каналы` / reopen existing project flow
