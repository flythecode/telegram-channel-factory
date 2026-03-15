# Telegram Channel Factory — Real LLM staging scenario

Этот сценарий нужен для backlog item 116: проверить **реальную** генерацию идей и черновиков через **отдельный staging provider key**, не смешивая её с production secret path и не включая live Telegram publish.

## Цель

Подтвердить 4 вещи:
- `ideas` реально идут через внешний LLM provider, а не `stub`
- `draft` реально проходит через production-like generation path
- usage/cost attribution сохраняется для staging run
- staging secret path изолирован от Telegram bot token и production LLM key

## Обязательные guardrails

Сценарий считается валидным только если одновременно соблюдены условия:
- `APP_ENV=staging`
- `RUNTIME_MODE=demo`
- `PUBLISHER_BACKEND=stub`
- `LLM_PROVIDER != stub`
- используется `LLM_API_KEY_FILE`, а не inline `LLM_API_KEY`
- `LLM_API_KEY_FILE` указывает на **отдельный staging secret file**
- `LLM_API_KEY_FILE` не совпадает с `TELEGRAM_BOT_TOKEN_FILE`

Рекомендуемый шаблон: `.env.staging-real.example` → локальная копия `.env.staging-real.local`.

## Что именно прогоняем

Сценарий создаёт staging fixtures и делает два настоящих generation вызова:
1. `generate_ideas(...)`
2. `create_draft` через generation job path

После этого проверяются:
- `provider != stub`
- есть `request_id`
- есть `model`
- есть `latency_ms`
- usage summary содержит операции `ideas` и `draft`
- generation events привязаны к staging project/channel

## Как запускать

### 1. Подготовить untracked env

```bash
cp .env.staging-real.example .env.staging-real.local
```

Заполнить локально:
- `DATABASE_URL`
- `LLM_PROVIDER`
- `LLM_API_KEY_FILE`
- при необходимости `LLM_MODEL_DEFAULT`

### 2. Применить env и поднять БД/миграции

```bash
set -a
source ./.env.staging-real.local
set +a
alembic upgrade head
```

### 3. Запустить smoke scenario

```bash
python3 scripts/run_real_llm_staging_scenario.py
```

## Ожидаемый PASS

PASS означает:
- ideas generation прошла через real provider
- draft generation прошла через real provider
- в output есть `provider`, `model`, `request_id`, `latency_ms`
- usage summary показывает хотя бы по одному success event для `ideas` и `draft`
- сценарий не трогал live Telegram publish path

## Ожидаемый FAIL

NO-GO по item 116, если выполняется хотя бы одно:
- `LLM_PROVIDER=stub`
- отсутствует `LLM_API_KEY_FILE`
- staging key path совпадает с Telegram token path
- ideas/draft ушли без request metadata
- generation events не создались
- usage attribution не содержит `ideas` и `draft`

## Evidence

После успешного прогона сохранить:
- stdout JSON из `scripts/run_real_llm_staging_scenario.py`
- используемый env marker (без секретов)
- дату прогона и модель
- short operator note: separate staging provider key confirmed
