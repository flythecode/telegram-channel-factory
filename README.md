# Telegram Channel Factory

**Telegram Channel Factory** — это Telegram-first система для запуска и управления Telegram-каналом через бота: от первого setup до постоянной работы с контентом, агентами, черновиками и публикациями.

Это уже не просто backend-заготовка. Текущий репозиторий содержит:
- FastAPI API
- Telegram bot control layer
- модели и workflow для channel/content pipeline
- worker для очереди публикаций
- stub и Telegram publisher backends
- Docker/deploy path
- тестовое покрытие на ключевые пользовательские сценарии

---

## Product summary

Продукт решает задачу **создания и ведения Telegram-канала как системы**, а не как набора ручных действий.

### Tenant model

В целевой SaaS-модели продукт работает так:
- **1 платящий клиент (`client account`)**
- **→ 1+ channel projects** внутри его аккаунта
- **→ 1 project-scoped agent team/runtime на каждый канал/проект**

Для текущего MVP `workspace` — это операционный контейнер клиента, а `project` — отдельный channel project. На практике это значит:
- один клиент может вести несколько каналов;
- каждый канал обслуживается своим `project`;
- у каждого такого `project` своя команда агентов, свои настройки и свой execution context;
- `отдельные агенты на клиента` в этой архитектуре означают изолированные agent profiles и execution context на уровне client/project/channel, а не отдельный provider API key на каждого клиента;
- контекст, prompts, usage и будущий LLM runtime не должны смешиваться между проектами одного клиента.


Пользователь через Telegram-бота может:
- создать проект канала
- подключить существующий Telegram-канал
- выбрать и настроить команду ИИ-агентов
- сгенерировать контент-план
- получить задачи и черновики
- отредактировать draft
- approve / reject draft
- отправить публикацию сразу или поставить в очередь
- вернуться позже и поменять настройки канала, агентов и режима работы

Ключевая идея:
**это Telegram-админка для AI-управления каналом, а не одноразовый wizard и не просто генератор постов.**

---

## What is implemented now

### 1. Backend core
- FastAPI application
- SQLAlchemy models
- Pydantic schemas
- API routers по основным сущностям
- service layer для workflow и reusable logic

### 2. Product entities
- `users`
- `workspaces`
- `projects`
- `channels`
- `agents`
- `content-plans`
- `tasks`
- `drafts`
- `publications`
- `audit-events`
- `project-config-versions` — versioned snapshots of project settings, agent team config, and prompt state for reproducible/audit-friendly changes

### 3. Channel/content workflow
- project creation
- channel creation and reconnect/reopen flow
- agent team presets
- content plan creation
- task creation
- draft creation
- draft edit
- draft approve / reject
- immediate publication
- scheduled publication
- publication queue
- worker-based dispatch flow

### 4. Bot control layer
В репозитории уже есть bot shell и базовая Telegram navigation model:
- `/start`
- main screens
- `Мои каналы`
- channel dashboard
- channel sections
- wizard/service/backend bridge foundation

### 5. Reliability baseline
- worker batch stability hardening
- retry / backoff / error handling baseline
- request-level observability middleware
- audit history for key actions
- support-grade audit timeline: summaries, changed fields, request id, actor context, latest-first filters/limits
- deterministic test env

### 6. Infra / run path
- `.env.example`
- `.env.demo`
- `.env.live.example`
- Alembic migrations
- Dockerfile
- Docker Compose
- Makefile

---

## Current MVP status

Сейчас проект находится в состоянии:

**working Telegram-channel product core with backend + bot control foundation**

То есть уже собрано:
- основной data model
- API-контур
- publication pipeline
- Telegram send adapter
- queue/worker flow
- post-setup edit path
- reproducible dev/deploy scaffolding
- test coverage на ключевые сценарии MVP

Уже отдельно закреплены сценарии:
- `draft → edit → approve → queue`
- `return later → open channel → change settings → regenerate`
- worker batch continues after one runtime failure
- retryable Telegram failures are separated from terminal failures
- request logging + request id for observability
- support-facing audit trail now returns latest-first history with `summary`, `changed_fields`, `request_id`, `actor`, plus `action` / `entity_type` / `limit` filters
- Docker compose path uses container-safe DB config and healthchecks

---

## Core user flow

MVP launch path выглядит так:

1. открыть Telegram-бота
2. нажать `/start`
3. создать проект канала
4. выбрать команду агентов
5. подключить канал
6. создать контент-план
7. получить задачу и draft
8. отредактировать и approve draft
9. отправить в очередь или опубликовать
10. вернуться позже и изменить настройки

### UX simplification rule

На главном пути бот должен в каждом ключевом экране явно показывать **один следующий шаг**:
- `/start` → `Создать канал`
- summary wizard → `Подтвердить проект`
- выбор агентной команды → рекомендовать `3 агента — Быстрый старт`
- подключение канала → сначала выбрать `У меня уже есть канал` или `Как создать канал`, потом прислать `@username`
- после успешного подключения → `Создать контент-план`
- на dashboard → подсказывать ближайшее полезное действие по текущему состоянию проекта

Цель этого правила: новый пользователь должен понимать, что делать дальше, без внешних объяснений и без чтения документации.

---

## Architecture

### API
- `app/api/v1/`
- `app/api_app.py`
- `app/main.py`

### Bot layer
- `app/bot/`
- `scripts/run_bot.py`

### Models
- `app/models/`

### Schemas
- `app/schemas/`

### Services
Ключевая логика находится в:
- `app/services/workflow.py`
- `app/services/orchestration.py`
- `app/services/publications.py`
- `app/services/publish_service.py`
- `app/services/runtime_hardening.py`
- `app/services/worker.py`
- `app/services/telegram_publisher.py`
- `app/services/stub_publisher.py`

### Architecture decisions
- `MULTI_TENANT_LLM_ARCHITECTURE_V1.md` — целевая multi-tenant SaaS-архитектура для LLM generation layer, tenant isolation, usage/cost accounting и queue-first execution
- `LLM_FAILOVER_POLICY_V1.md` — policy для fallback-provider и graceful degradation при outage основного LLM provider
- `MODEL_ROUTING_STRATEGY_V1.md` — стратегия выбора model profiles для ideas, content plan, drafts, rewrite и premium multi-stage workflows
- `TARIFF_AGENT_MODEL_MATRIX_V1.md` — матрица тарифов, client levels, доступных agent presets, execution modes и routing profiles для `trial` / `starter` / `pro` / `business`
- `TARIFF_MODEL_BASELINE_V1.md` — каноническая тарифная модель v1: plan limits, service tier / execution mode и cost-derived pricing baseline на основе реальных generation costs
- `LLM_COST_OPERATOR_RUNBOOK.md` — operator runbook по LLM-расходам, лимитам, provider degradation и ручному разбору cost anomalies
- `PRODUCTION_LLM_BASELINE_V1.md` — каноническая фиксация новой multi-tenant LLM-agent architecture как production baseline, включая обязательные runtime gates и deprecated pre-baseline подходы
- `INTERNAL_PILOT_COST_VALIDATION_PLAN.md` + `internal-pilot/YYYY-MM-DD/*` — пакет controlled internal pilot для проверки реальной экономики тарифа; raw evidence можно собрать через `python3 scripts/collect_internal_pilot_evidence.py`
- draft orchestration now supports real staged multi-agent generation: each active strategist/researcher/writer/editor-style stage executes as a separate LLM call inside the tenant-scoped execution context, while aggregate usage/latency roll up into the final generation result.
- generation mode is now tariff-aware: cheap plans (`trial/free/starter/basic/lite`) are forced into `single-pass`, while premium plans (`pro/business/growth/premium/scale/enterprise`) keep `multi-stage` execution when multiple agents are active; an explicit `client_account.settings.generation_mode` override can pin either mode.
- content plan generation now runs through the shared generation service and persists the generated plan summary on `content_plans.summary`.
- soft-limit guardrails are now computed from `llm_generation_events` for the active billing period and exposed in generation metadata under `guardrails`; configure them via `client_account.settings.generation_guardrails` using client-level limits (`client_budget_limit_usd`, `client_generation_quota_limit`, `client_token_quota_limit`, `warn_at_ratio`) and optional per-channel overrides in `channel_limits[{channel_id}]`.
- guardrails also support UTC-scoped daily and calendar-month caps for client/channel totals plus operation-specific caps (`client_daily_*`, `client_monthly_*`, `client_operation_daily_limits`, `client_operation_monthly_limits`, and per-channel `daily_*`, `monthly_*`, `operation_daily_limits`, `operation_monthly_limits`); runtime metadata now includes per-window snapshots in `guardrails.client.windows[]` / `guardrails.channel.windows[]`.
- hard-stop guardrails now block draft/content-plan/rewrite/regenerate generation when any client/channel budget or quota is exceeded across billing, daily, monthly, or operation-specific caps; the snapshot exposes `hard_stop_reached`, `blocked_scopes`, and `blocking_reasons`, and API endpoints return HTTP 400 with the blocking reason instead of generating new content beyond the limit.
- cost dashboard / admin reporting baseline added: `/api/v1/users/me/client-account/cost-dashboard` now returns aggregated generation spend/usage for the current client broken down by channel, operation, model, and month so operators can review application LLM costs without querying raw `llm_generation_events` manually.
- unified admin economics dashboard added: `/api/v1/admin/generation/dashboard` now returns one operator-facing rollup for all generation spend/usage with totals plus breakdowns by client, project, channel, operation, model, and month; `/api/v1/admin/generation/dashboard/export` emits the same view as CSV for spreadsheet reconciliation.
- CSV export for pricing/economics reconciliation added: `/api/v1/admin/generation/usage/export`, `/api/v1/admin/generation/cost-breakdown/export`, `/api/v1/admin/generation/dashboard/export`, and `/api/v1/users/me/client-account/cost-dashboard/export` now emit spreadsheet-friendly `text/csv` reports for usage summaries, cost breakdowns, unified admin dashboard data, and client dashboard snapshots.
- pricing/billing baseline added: `/api/v1/users/me/client-account/pricing` now builds a rate card from real `llm_generation_events`, applies configurable target margin / contingency / overhead assumptions from `client_account.settings.pricing_model`, and returns recommended per-operation prices plus operator-facing deltas (`delta_vs_average_cost_usd`, `recommended_unit_margin_*`, `observed_share_pct`) and a monthly plan catalog (`trial/starter/pro/business`) with both catalog baseline COGS/margin and sample-based scaling projections (`observed_blended_generation_cost_usd`, `projected_sample_*`).
- tariff model is now explicitly locked: plan catalog rows expose `service_tier` + `execution_mode`, trial is restricted to `starter_3`, and `TARIFF_MODEL_BASELINE_V1.md` defines the canonical mapping between plan limits, preset access, runtime mode, and cost-derived pricing guidance.
- generation pipeline observability baseline added: `app/services/generation_observability.py` now emits structured logs for generation completion, queue snapshots, enqueue/claim/process outcomes, worker-pool batches, provider retries/failover, and graceful degradation; queue metrics expose status/operation/project depth, while in-memory provider health snapshots track success/failure counters, retryable failures, last error/status code, latency, request id, model, and last failover outcome.
- production baseline is now explicitly locked to the new multi-tenant LLM architecture: `PRODUCTION_LLM_BASELINE_V1.md` defines generation-service-first runtime, tenant-isolated execution context, `llm_generation_events` attribution, queue/worker execution, guardrails, pricing/admin visibility, and secret-file-based provider credentials as the canonical live path for Telegram Channel Factory.

---

## Runtime modes

### `stub`
Безопасный локальный режим.
- реальный Telegram send не выполняется
- publisher backend принудительно stub
- подходит для dev и тестового прогона flow

### `demo`
Безопасный demo-режим.
- продукт выглядит как staging/demo
- send path остаётся stub
- подходит для демонстраций без риска реальной отправки

### `live`
Боевой режим.
- требует `PUBLISHER_BACKEND=telegram`
- требует `TELEGRAM_BOT_TOKEN`
- использует Telegram Bot API для реальной публикации

---

## Quick start

## Option A — local Python

1. Создай `.env`
2. Установи зависимости
3. Прогони миграции
4. Подними API
5. При необходимости подними worker и bot runtime

```bash
cp .env.demo .env
python3 -m pip install --user --break-system-packages -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --host ${API_HOST:-127.0.0.1} --port ${API_PORT:-8000}
```

Worker:

```bash
python3 scripts/run_worker.py
```

Bot runtime:

```bash
python3 scripts/run_bot.py
```

---

### Telegram user journey without developer help

После запуска bot runtime целевой пользователь проходит путь так:

1. `Создать канал` → отвечает на 6 коротких вопросов.
2. `Подтвердить проект` → выбирает рекомендуемый пресет `3 агента — Быстрый старт`.
3. Подключает свой Telegram-канал по экрану `Осталось подключить твой Telegram-канал`.
4. `Создать контент-план` → `Сгенерировать 10 идей` → `Создать 3 черновика`.
5. Открывает `Черновики`, подтверждает лучший текст и создаёт публикацию.
6. Открывает `Публикации` и отправляет пост сразу или по расписанию.

Во всех ключевых экранах бот должен показывать один явный next step, чтобы пользователь не искал помощь разработчика между шагами.

## Option B — Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Что поднимается:
- `db` — PostgreSQL
- `api` — FastAPI application
- `worker` — queue/background worker
- `bot` — Telegram bot runtime entrypoint

Важно:
- `.env.example` оставляет `DATABASE_URL` с `localhost` для локального Python run path
- в `docker-compose.yml` этот адрес автоматически переопределяется на контейнерный `db:5432`
- поэтому compose-stack запускается воспроизводимо без ручного патча env-файла

Health checks:
- `db` через `pg_isready`
- `api` через `/health`
- `worker` и `bot` ждут healthy `db` + healthy `api`

Быстрый smoke check:

```bash
make deploy-smoke
```

### Safer production deploy baseline

Для production не использовать root-only path вроде `/root/telegram-channel-factory`.
Базовый безопасный вариант:

- системный пользователь: `tcf`
- директория приложения: `/srv/telegram-channel-factory`
- директория env/secrets: `/etc/telegram-channel-factory`
- рабочая директория для compose/systemd: `/srv/telegram-channel-factory`
- запуск сервисов: от имени `tcf`, не `root`
- production `.env` хранить вне git working tree, например в `/etc/telegram-channel-factory/.env.live`
- реальный Telegram token хранить отдельно, например в `/etc/telegram-channel-factory/secrets/telegram_bot_token`
- реальный LLM provider key хранить отдельно, например в `/etc/telegram-channel-factory/secrets/llm_api_key`
- release script должен передавать env через `docker compose --env-file ...`, без копирования secrets в `.env` внутри repo

Подготовка сервера:

```bash
sudo APP_USER=tcf APP_DIR=/srv/telegram-channel-factory \
  SECRETS_DIR=/etc/telegram-channel-factory \
  bash scripts/prepare_server_dirs.sh
```

Первичный checkout/env:

```bash
sudo -u tcf git clone <repo> /srv/telegram-channel-factory
sudo install -o root -g tcf -m 640 /srv/telegram-channel-factory/.env.live.example \
  /etc/telegram-channel-factory/.env.live
sudo install -d -o root -g tcf -m 750 /etc/telegram-channel-factory/secrets
sudo install -o root -g tcf -m 640 /srv/telegram-channel-factory/secrets.example/telegram_bot_token.example \
  /etc/telegram-channel-factory/secrets/telegram_bot_token
sudo install -o root -g tcf -m 640 /srv/telegram-channel-factory/secrets.example/llm_api_key.example \
  /etc/telegram-channel-factory/secrets/llm_api_key
# then replace placeholder content with the real rotated secrets
```

Обновление/release выполнять только от имени `tcf`.

Быстрый update без фиксации release ref:

```bash
sudo -u tcf APP_DIR=/srv/telegram-channel-factory \
  ENV_FILE=/etc/telegram-channel-factory/.env.live \
  /srv/telegram-channel-factory/scripts/deploy_as_tcf.sh
```

Повторяемый release path с фиксированным ref, миграциями и обязательным smoke-check:

```bash
sudo -u tcf APP_DIR=/srv/telegram-channel-factory \
  ENV_FILE=/etc/telegram-channel-factory/.env.live \
  RELEASE_REF=<git-tag-or-commit> \
  /srv/telegram-channel-factory/scripts/release_update.sh
```

`scripts/release_update.sh` дополнительно:
- отказывается работать от `root`
- валится, если production env использует inline `TELEGRAM_BOT_TOKEN` или inline `LLM_API_KEY` вместо secret file
- требует детерминированный git state: либо `RELEASE_REF`, либо normal branch fast-forward path
- делает `python3 -m compileall app scripts`
- применяет `alembic upgrade head`
- запускает `docker compose --env-file ... up --build -d --remove-orphans`
- считает релиз успешным только после smoke-check `/health`
- сохраняет previous/current git refs в `.release-backups/` для операционного разбора

`scripts/deploy_as_tcf.sh` остаётся как короткий runtime update path, а `scripts/release_update.sh` — как основной безопасный релизный процесс.
Подробности: `PRODUCTION_DEPLOY_BASELINE_V1.md`.

---

## Configuration

### Application
- `APP_NAME`
- `APP_ENV` = `dev | staging | prod | test`
- `DEBUG`
- `API_V1_PREFIX`
- `API_HOST`
- `API_PORT`

### Database
- `DATABASE_URL`

### Runtime / Publisher
- `RUNTIME_MODE` = `stub | demo | live`
- `PUBLISHER_BACKEND` = `stub | telegram`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_TOKEN_FILE`
- `TELEGRAM_REQUEST_TIMEOUT_SECONDS`

### LLM layer
- `LLM_PROVIDER` = `stub | openai | anthropic | openrouter | gemini`
- `LLM_API_KEY`
- `LLM_API_KEY_FILE`
- `LLM_MODEL_DEFAULT`
- optional `LLM_BASE_URL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`
- `LLM_ROUTING_STRATEGY` = `single-model | by-operation | tiered`
- `LLM_FAILOVER_STRATEGY` = `disabled | fallback-provider | graceful-degradation`
- optional `LLM_FALLBACK_PROVIDER` / `LLM_FALLBACK_MODEL`

### Worker
- `WORKER_POLL_INTERVAL_SECONDS`
- `WORKER_BATCH_LIMIT`
- `GENERATION_WORKER_POOL_SIZE`
- `GENERATION_JOB_BATCH_LIMIT`

Generation jobs now drain through a dedicated worker pool that groups queued jobs by `project_id` and keeps each project's execution inside one worker slot for safer tenant-scoped isolation. Load regressions cover large queue ordering, sustained multi-batch backlog draining, and worker-pool saturation against global/client/project rate limits.

Load-oriented regression coverage lives in `tests/test_generation_queue.py` and `tests/test_generation_worker_pool.py`: the suite now exercises large queued backlogs, multi-tenant slot assignment, and paid-vs-trial prioritization under batch pressure.

---

## Useful commands

```bash
make init-db
make migrate
make seed-demo
make test
make run
make worker
make up
make up-detached
make deploy-smoke
make logs
make down
```

---

## Publisher behavior

### Stub publisher
- симулирует успешную/неуспешную публикацию
- подходит для dev/demo flow

### Telegram publisher
- использует Telegram Bot API `sendMessage`
- определяет target через `channel_id` или `channel_username`
- пишет `external_message_id`
- различает terminal и retryable ошибки
- поддерживает retry path для network/429/temporary failures

---

## Worker behavior

Worker:
- собирает dispatchable publications
- обрабатывает `sending`
- обрабатывает `queued`, если `scheduled_for` уже наступил
- отправляет публикации через выбранный publisher backend
- не валит весь batch, если одна публикация падает
- пишет machine-readable runtime state в `runtime/worker_status.json`
- поддерживает healthcheck через `scripts/check_worker_status.py`

Entry point:
- `scripts/run_worker.py`

Operational monitoring:
- проверить локальный runtime status: `make worker-status`
- compose healthcheck для `worker` использует `python3 scripts/check_worker_status.py`
- в `runtime/worker_status.json` пишутся heartbeat, last_success, last_failure, consecutive_failures и summary последнего цикла

Operational alerts baseline:
- проверить API: `make api-status`
- проверить bot: `make bot-status`
- проверить агрегированные alerts: `make runtime-alerts`
- `scripts/check_runtime_alerts.py` пишет сводку в `runtime/alerts_status.json`
- compose healthcheck для `bot` использует `python3 scripts/check_bot_status.py`

---

## Observability and reliability

В MVP уже есть базовый operational слой:
- request lifecycle logging
- `x-request-id` для API запросов
- логирование publication/worker событий
- retry/backoff baseline для retryable publish errors
- audit events для ключевых действий

Это не enterprise monitoring, но уже позволяет быстро понять:
- какой запрос пришёл
- кто его вызвал
- чем он закончился
- где сломался publication flow

---

## Tests

В проекте есть покрытие на:
- smoke API
- pipeline API
- bot UI/navigation
- channel connection flow
- status transitions
- publication flow
- worker behavior
- runtime hardening
- Telegram publisher behavior
- ownership/access control
- e2e MVP flows

Запуск полного набора:

```bash
make test
```

---

## Env files

### `.env.example`
Базовый шаблон для локального запуска.

### `.env.demo`
Безопасный demo/staging-like шаблон.
- `RUNTIME_MODE=demo`
- `PUBLISHER_BACKEND=stub`

### `.env.live.example`
Шаблон для боевого запуска.
- копируй в **неотслеживаемый** файл, например `.env.live`
- не коммить реальные токены
- для production предпочитай `TELEGRAM_BOT_TOKEN_FILE`, а не inline token в env

Recommended live flow:

```bash
cp .env.live.example .env.live
mkdir -p secrets
cp secrets.example/telegram_bot_token.example secrets/telegram_bot_token
# fill the real token in secrets/telegram_bot_token
ENV_FILE=.env.live SECRET_FILES_DIR=./secrets docker compose up --build
```

---

## Product docs in repo

Ключевые документы:
- `PRODUCT_SPEC_V1.md`
- `USER_FLOWS_V1.md`
- `MVP_LAUNCH_SCOPE_V1.md`
- `IMPLEMENTATION_ROADMAP_V1.md`
- `BOT_SETUP.md`
- `CHANNEL_CONNECTION_FLOW.md`
- `ENV_MODES.md`
- `STAGING_DEMO_RUNBOOK.md`
- `FINAL_QA_RUNBOOK.md`
- `OPERATOR_HANDBOOK.md`
- `PRODUCTION_DEPLOY_BASELINE_V1.md`
- `RELEASE_CHECKLIST.md`
- `GO_NO_GO_CHECK.md`
- `RELEASE_MANIFEST.md`
- `RELEASE_SMOKE.md`
- `STAGING_RELEASE_0.1.0-mvp.md`
- `FIRST_USER_LAUNCH_PATH.md`
- `TELEGRAM_UI_MAP_V1.md`
- `TELEGRAM_CHANNEL_CONNECTION_UX_V1.md`
- `MVP_CHECKLIST.md`

---

## Current bottom line

На текущем этапе **Telegram Channel Factory** — это уже рабочий продуктовый контур под MVP launch:
- backend есть
- bot foundation есть
- content/publication pipeline есть
- retry/worker/observability baseline есть
- deploy path есть
- ключевые сценарии закреплены тестами

Следующий слой работ — operator handbook, user-facing launch path и controlled user tests.

Для controlled user tests подготовлены:
- `CONTROLLED_USER_TEST_PLAN.md` — сценарий, критерии done и правила модерации
- `CONTROLLED_USER_TEST_RESULTS_TEMPLATE.md` — шаблон записи результата по каждому участнику

## Release decision practice

Перед staging/live rollout используй связку:
- `RELEASE_CHECKLIST.md` — обязательный операционный чеклист
- `GO_NO_GO_CHECK.md` — policy принятия решения
- `release_records/TEMPLATE.md` — шаблон записи конкретного релиза

Правило: если нет заполненного release record с явным решением `GO`/`NO-GO`, релиз считается не прошедшим операционный gate.
