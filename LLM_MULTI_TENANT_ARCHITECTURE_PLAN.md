# Telegram Channel Factory — Multi-tenant LLM Architecture Plan

## Goal

Перевести продукт с текущей text-orchestration заглушки на реальный multi-tenant LLM runtime:
- один platform-owned provider key
- отдельный tenant-scoped execution context на клиента/канал
- прозрачный cost accounting
- generation queue + worker pool

## Core architecture

### 1. Tenant boundary
- `ClientAccount` / subscription context
- `Project`
- `TelegramChannel`
- `AgentProfile[]`
- `AgentTeamRuntime`
- `GenerationJob`
- `LlmGenerationEvent`

Изоляция проходит по `client_account_id` + `project_id` + `channel_id`.

### 2. Runtime flow
1. Bot/API создаёт operation request (`generate_ideas`, `generate_plan`, `generate_draft`, `rewrite_draft`).
2. Request превращается в `GenerationJob`.
3. Worker забирает job.
4. Worker поднимает tenant context: client/project/channel/agents/prompts/budget.
5. `GenerationService` строит effective prompt chain.
6. `LlmProviderAdapter` вызывает provider через platform key.
7. Usage/cost пишутся в `LlmGenerationEvent`.
8. Result сохраняется в `Task` / `Draft` / `Publication` metadata.

### 3. New services
- `app/services/llm_provider.py`
- `app/services/generation_service.py`
- `app/services/generation_jobs.py`
- `app/services/cost_accounting.py`
- `app/services/tenant_runtime.py`

### 4. New entities
- `client_accounts`
- `agent_team_runtimes`
- `generation_jobs`
- `llm_generation_events`
- optional `subscription_plans`

### 5. Config layer
Required env:
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_MODEL_DEFAULT`
- `LLM_BASE_URL` (optional)
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`
- `LLM_SOFT_BUDGET_USD_DEFAULT`

### 6. Cost accounting
For every generation call store:
- provider
- model
- prompt/completion/total tokens
- estimated_cost_usd
- latency_ms
- status
- request_id
- client/project/channel/task/draft linkage

### 7. Execution modes
- cheap tier: single-pass generation
- premium tier: staged multi-agent generation

### 8. First implementation slice
1. add config + provider adapter
2. add `llm_generation_events`
3. add real generation for ideas
4. add real generation for drafts
5. log cost/usage
6. move generation into queue

## Current repo impact

### Replace/extend
- `app/services/orchestration.py`
- `app/bot/backend_bridge.py`
- current sample generation paths for ideas/drafts

### Keep
- `AgentProfile` model as tenant-scoped team member config
- current bot UX shell
- worker runtime as base for generation queue expansion

## Non-goals for first slice
- no enterprise billing yet
- no client-provided LLM keys
- no advanced multi-provider routing before baseline accounting works
