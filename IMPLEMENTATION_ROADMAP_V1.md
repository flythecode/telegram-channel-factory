# Telegram Channel Factory — Implementation Roadmap v1

## 1. Purpose

Этот документ сводит подготовленные спецификации в **один мастер-план реализации**, чтобы разработка шла по единой дорожной карте, а не по россыпи отдельных `.md` файлов.

Этот roadmap — главный рабочий документ для перехода от spec stage к коду, тестам и запуску.

---

## 2. Source documents consolidated here

Этот roadmap опирается на уже подготовленные артефакты:
- `PRODUCT_SPEC_V1.md`
- `USER_FLOWS_V1.md`
- `TELEGRAM_UI_MAP_V1.md`
- `RELEASE_SCOPE_V1.md`
- `ACCESS_MODEL_V1.md`
- `DATA_MODEL_EXPANSION_V1.md`
- `EDITABLE_CONFIG_LAYER_V1.md`
- `AGENT_TEAM_PRESETS_V1.md`
- `AGENT_ROLES_V1.md`
- `AGENT_SETTINGS_V1.md`
- `ORCHESTRATION_ENGINE_V1.md`
- `PROMPT_TEMPLATE_MANAGEMENT_V1.md`
- `MULTI_TENANT_LLM_ARCHITECTURE_V1.md`
- а также screen / test / deploy / release документы проекта

С этого момента именно **этот файл** задаёт порядок реализации.

---

## 3. Product target for MVP launch

К запуску MVP v1 продукт должен уметь одно главное:

> Пользователь заходит в Telegram-бота, создаёт проект канала, выбирает команду из 3–7 ИИ-агентов, подключает Telegram-канал, запускает контентный pipeline, управляет черновиками и публикациями, а затем может вернуться и менять настройки канала после запуска.

Если это работает стабильно — MVP собран.

---

## 4. Execution principles

1. **Сначала воспроизводимость, потом расширение** — test env, run path и deterministic behavior важнее новых фич.
2. **Сначала foundation, потом UI polish** — ownership/data model/backend support идут раньше красивой обвязки.
3. **Bot-first delivery** — реализация должна обслуживать Telegram UX, а не только backend сам по себе.
4. **Editable product is mandatory** — всё строится с учётом post-setup изменений.
5. **Одна рабочая вертикаль важнее россыпи кусков** — лучше закрыть end-to-end сценарий, чем начать десять подсистем.

---

## 5. Master implementation phases

## Phase 0 — Stabilize current backend base

### Goal
Вернуть проект в полностью предсказуемое состояние перед развитием.

### Includes
- test env isolation
- deterministic pytest behavior
- runtime mode separation (`stub/demo/live`)
- secrets hygiene baseline

### Exit criteria
- `pytest` стабильно зелёный
- тесты не зависят от локального `.env`
- безопасный dev/test режим зафиксирован

### Status
- test env isolation: **done**
- green pytest restored: **done**
- runtime/secrets discipline: partially documented, implementation continues

---

## Phase 1 — Ownership and data model foundation

### Goal
Сделать backend модель продукта пригодной для Telegram-first ownership flow.

### Includes
- `User`
- `Workspace`
- project ownership fields
- migrations
- schemas updates
- ownership tests

### Exit criteria
- у проекта есть владелец
- ownership model реально существует в БД и API
- foundation покрыт тестами

### Status
- `User`: **done**
- `Workspace`: **done**
- project ownership fields: **done**
- migration baseline updated: **done**
- ownership tests: **done**

---

## Phase 2 — Project strategy and editable configuration

### Goal
Сделать проект не только CRUD-сущностью, но и управляемой контентной системой.

### Includes
- strategy fields in `Project`
- operation modes
- editable config support
- config versioning
- audit baseline

### Exit criteria
- настройки канала можно хранить и менять после setup
- новые генерации используют текущую конфигурацию
- есть основа для history/versioning

---

## Phase 3 — Agent team model

### Goal
Перевести агентную часть из общих профилей в реальную продуктовую модель команды.

### Includes
- team presets 3/5/7
- agent roles
- editable agent settings
- prompt template layering
- enable/disable/order support

### Exit criteria
- команда агентов собирается как продуктовая сущность
- пользовательская настройка команды поддерживается backend-ом

---

## Phase 4 — Orchestration and content pipeline

### Goal
Сделать working vertical slice: task → agents → draft → approval → publication.

### Includes
- linear orchestration engine
- task to draft generation
- status transitions
- approval flow
- publication queue support

### Exit criteria
- pipeline работает от задачи до draft/publication
- orchestration воспроизводим и тестируем

---

## Phase 5 — Telegram bot foundation

### Goal
Поднять bot control layer поверх backend.

### Includes
- bot runtime/service
- `/start`
- main menu
- onboarding/help screens
- callback/state foundation

### Exit criteria
- бот поднимается как отдельный рабочий слой
- пользователь может зайти и попасть в главный UX

---

## Phase 6 — Setup wizard and channel connection

### Goal
Реализовать основной входной пользовательский сценарий.

### Includes
- project creation wizard
- agent preset selection in bot
- channel connection flow
- setup summary
- first-run activation screen

### Exit criteria
- пользователь проходит путь от `/start` до готового проекта без ручной помощи разработчика

---

## Phase 7 — Ongoing management UI

### Goal
Сделать продукт не одноразовым setup, а постоянной админкой.

### Includes
- `Мои каналы`
- channel dashboard
- settings screen
- agents screen
- content plan screen
- drafts screen
- publications queue screen
- mode screen

### Exit criteria
- пользователь может вернуться позже и управлять своим каналом полностью через Telegram

---

## Phase 8 — Reliability and release hardening

### Goal
Довести продукт до состояния, пригодного для staging/release.

### Includes
- worker hardening
- retry / error handling
- logging / observability
- e2e tests
- bot UI tests
- deploy validation
- release docs
- final QA

### Exit criteria
- есть воспроизводимый run path
- есть тестовая уверенность
- есть release package и demo path

---

## 6. Immediate next execution order

Следующие практические шаги после текущего состояния:

1. Зафиксировать **жёсткий MVP scope запуска** отдельным master-решением
2. Нормализовать **структуру репозитория** под bot layer + backend core
3. Продолжить **Phase 2**: strategy/config model
4. Затем перейти в **Phase 3**: presets/roles/settings
5. Затем закрыть **Phase 4**: orchestration vertical slice
6. После этого поднимать **bot foundation** и setup wizard

---

## 7. What is already truly done

На момент этого roadmap в коде и проверках уже реально сделано:
- test env isolation from working `.env`
- green `pytest`
- `User` model
- `Workspace` model
- ownership fields in `Project`
- initial migration updated for ownership foundation
- ownership tests added

Это считается уже не планом, а выполненной базой.

---

## 8. What this roadmap replaces

Этот документ не удаляет подробные spec-файлы, но заменяет их как **главную точку принятия решений о порядке реализации**.

Если возникает вопрос **«что делать дальше?»**, ответ берётся отсюда, а не из разрозненных файлов.

---

## 9. Roadmap completion rule

Переход к следующей фазе допускается, когда предыдущая фаза хотя бы доведена до рабочего минимального exit criteria, а не просто описана в документах.

Главное правило:

> не считать пункт выполненным, пока он не подтверждён кодом, миграцией, тестом, run path или работающим UI flow.
