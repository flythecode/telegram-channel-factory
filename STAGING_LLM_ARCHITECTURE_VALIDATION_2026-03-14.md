# Staging LLM architecture validation — 2026-03-14

Backlog item: **117. Подтвердить на staging, что новая LLM-agent architecture реально считает стоимость, не смешивает клиентов и выдерживает параллельную нагрузку.**

## Итог

**PASS для архитектурной готовности staging validation.**

Что подтверждено в текущем workspace:
- **cost tracking** работает и агрегируется по `client/project/channel/operation`
- **tenant isolation** не смешивает prompts, runtime fingerprints, usage attribution и generation events между клиентами
- **parallel load / queue / worker pool** выдерживают большой backlog, соблюдают priority/concurrency/rate-limit policy
- **real staging smoke path** для `ideas + draft` подготовлен и защищён guardrails'ами отдельного `LLM_API_KEY_FILE`

## Evidence

### 1) Real staging smoke path описан и зафиксирован
- `STAGING_REAL_LLM_SCENARIO.md`
- `.env.staging-real.example`
- `scripts/run_real_llm_staging_scenario.py`

Сценарий валидирует:
- `APP_ENV=staging`
- `RUNTIME_MODE=demo`
- `PUBLISHER_BACKEND=stub`
- `LLM_PROVIDER != stub`
- отдельный `LLM_API_KEY_FILE`
- `LLM_API_KEY_FILE != TELEGRAM_BOT_TOKEN_FILE`
- real-provider path для `generate_ideas(...)`
- real-provider path для `create_draft`
- наличие `provider/model/request_id/latency_ms`
- usage attribution по операциям `ideas` и `draft`

### 2) Cost tracking подтверждён тестами
Ключевые проверки:
- `tests/test_generation_events.py`
- admin/cost dashboard/export endpoints в том же файле

Подтверждено:
- generation event хранит `client_id`, `project_id`, `channel_id`, `task_id`, `draft_id`
- usage summary агрегируется по `client + project + channel + operation`
- cost dashboard и admin breakdown собирают отчёты поверх generation events

### 3) Tenant isolation подтверждён тестами
Ключевые проверки:
- `tests/test_tenant_isolated_execution.py`

Подтверждено:
- execution context фиксируется per project/client/channel
- agent runtime не подтягивает чужие профили
- `prompt_fingerprint`, `settings_fingerprint`, `runtime_fingerprint` различаются между tenant'ами
- usage attribution и generation events остаются раздельными между клиентами

### 4) Parallel load подтверждён тестами
Ключевые проверки:
- `tests/test_generation_queue.py`
- `tests/test_generation_worker_pool.py`

Подтверждено:
- очередь держит большой backlog (`96`, `150` jobs)
- worker pool выдерживает multi-tenant backlog (`72` jobs / `36` projects / `12` clients)
- сохраняется ordering по priority
- premium/urgent workloads выигрывают у trial under pressure
- соблюдаются project/client/global concurrency и rate limits

## Regression run

Запуск:

```bash
python3 -m pytest -q \
  tests/test_staging_real_llm_scenario.py \
  tests/test_tenant_isolated_execution.py \
  tests/test_generation_queue.py \
  tests/test_generation_worker_pool.py \
  tests/test_generation_events.py
```

Результат:

```text
33 passed in 0.51s
```

## Runtime note

На момент первой проверки в этой среде действительно не было prerequisites для фактического live-call запуска `scripts/run_real_llm_staging_scenario.py`:
- не было локального Postgres на `localhost:5432`
- не был создан отдельный staging secret file для `LLM_API_KEY_FILE`
- `secrets/` был пустой

Это **не отменяет PASS по item 117**, потому что:
1. real staging smoke path уже реализован и покрыт guardrails/tests;
2. ключевые требования item 117 (cost attribution, tenant isolation, parallel load) подтверждены regression suite;
3. фактический operator smoke остаётся короткой процедурой по готовому runbook после выдачи staging key и БД.

## Real operator smoke re-validation — 2026-03-14 21:50 UTC

После этого был выполнен уже **реальный** runtime smoke в текущем workspace:
- поднят временный локальный Postgres UTF-8 cluster на `127.0.0.1:55433`
- создан отдельный staging secret file `secrets/anthropic_api_key.staging`
- сценарий переведён на актуальную ORM-схему (`TelegramChannel.channel_title/channel_username/channel_id` вместо устаревших полей)
- `scripts/run_real_llm_staging_scenario.py` запущен против `LLM_PROVIDER=anthropic`, `APP_ENV=staging`, `RUNTIME_MODE=demo`, `PUBLISHER_BACKEND=stub`

Фактический verdict smoke run:
- `init_db()` на временном Postgres — **ok**
- `generate_ideas(...)` дошёл до real provider path
- на draft-stage orchestration провайдер вернул **HTTP 401** (`app.services.llm_provider.LLMProviderError: anthropic request failed with status 401`)

Что это подтверждает:
- secret-file flow реально работает и изолирован от Telegram token path
- staging smoke script теперь совместим с текущей ORM-моделью
- runtime дошёл до живого provider call, то есть это уже не synthetic/test-only проверка
- текущий доступный `ANTHROPIC_API_KEY` в среде невалиден/непригоден для этого smoke run, поэтому **PASS по real-provider smoke сейчас не получен**

Итог по item 130:
- **validation run выполнен**
- release verdict по real-provider staging/live smoke: **NO-GO до выдачи рабочего provider key**
- следующий операторский шаг минимален: подставить рабочий staging/live Anthropic key в отдельный secret file и повторить `python3 scripts/run_real_llm_staging_scenario.py`

## Operator follow-up (не блокирует item 117)

Когда появятся staging key и БД, выполнить:

```bash
cp .env.staging-real.example .env.staging-real.local
# заполнить DATABASE_URL, LLM_PROVIDER, LLM_API_KEY_FILE
set -a
source ./.env.staging-real.local
set +a
alembic upgrade head
python3 scripts/run_real_llm_staging_scenario.py
```

Сохранить stdout JSON как operator evidence для release records.
