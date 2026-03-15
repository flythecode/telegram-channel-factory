# Telegram Channel Factory — Multi-tenant LLM Architecture v1

## 1. Purpose

Этот документ фиксирует целевую архитектуру LLM-слоя для Telegram Channel Factory после MVP.

Цель: перейти от текущего stub/text-orchestration path к реальному SaaS-ready generation stack, где один продукт обслуживает много платящих клиентов, но execution context, prompts, usage attribution и runtime state остаются изолированными по клиенту и каналу.

---

## 2. Core product decision

### Что фиксируем

- **Один общий продуктовый provider account / API key** может использоваться приложением для вызовов LLM.
- **Отдельный provider key на каждого клиента не требуется** и не является целевой моделью по умолчанию.
- **Изоляция должна происходить на уровне application tenancy**, а не через раздачу отдельных внешних ключей.

### Что это означает practically

Внутри одного инстанса продукта:
- много клиентов могут пользоваться одной и той же LLM provider integration
- но у каждого клиента должны быть:
  - свой account/subscription context
  - свои проекты
  - свои каналы
  - свой agent execution context
  - свои prompts/config versions
  - свой usage/cost attribution

Иначе говоря:

> shared provider access, isolated tenant runtime.

Формулировка `отдельные агенты на клиента` в этом продукте должна читаться буквально как:
- отдельные agent profiles / prompt snapshots / execution context на уровне client/project/channel;
- отдельный provider API key на каждого клиента **не требуется** и не является tenant boundary.

---

## 3. Tenant hierarchy

Целевая иерархия продукта:

`client account -> 1+ channel projects -> 1 project-scoped agent team/runtime per channel`

В терминах домена:

1. **Client account**
   - платящий клиент SaaS
   - владеет подпиской, лимитами, биллинг-контекстом и usage budget

2. **Project**
   - отдельный channel project внутри client account
   - в MVP является основной tenant boundary для стратегии, agent team и generation context
   - принадлежит одному client account

3. **Channel**
   - подключённый Telegram-канал внутри конкретного проекта
   - operational surface для публикации и контентных операций
   - в целевой модели один клиент может иметь несколько таких project/channel пар

4. **Agent team runtime**
   - изолированный execution context для проекта/канала
   - фактически это `1 project-scoped agent team` на каждый channel project
   - содержит состав команды, prompt versions, routing rules, generation defaults, memory/context boundaries

### Important rule

**Изоляция должна быть не только по user_id, а по client/project/channel scope.**

Если один пользователь-оператор администрирует несколько клиентских каналов, generation context всё равно не должен смешиваться между ними.

---

## 4. Target architecture overview

Целевая схема:

1. Bot/API принимает generation-запрос.
2. Request normalizes scope: `client_id`, `project_id`, `channel_id`, `operation_type`.
3. Запрос ставится в generation queue.
4. Worker поднимает job и загружает **tenant-scoped runtime context**.
5. Generation service собирает:
   - model routing decision
   - provider config
   - prompt set/version
   - operation payload
   - safety/quota guards
6. Provider adapter выполняет реальный LLM call.
7. Usage/cost/log event записывается как отдельный generation event.
8. Результат сохраняется в drafts/tasks/plans с кратким `generation_metadata`.

---

## 5. Mandatory isolation boundaries

## 5.1 Identity and scope isolation

Каждый generation request обязан нести минимум:
- `client_id`
- `project_id`
- `channel_id`
- `operation_type`
- `actor_id` или system actor context
- `agent_team_runtime_id` или эквивалентный runtime fingerprint

Запрос без полного scope не должен доходить до provider adapter.

## 5.2 Prompt isolation

Prompt templates и agent instructions не должны выбираться глобально «по последнему активному проекту».

Они должны резолвиться через:
- tenant scope
- project/channel scope
- versioned prompt config
- конкретную generation operation

## 5.3 Context isolation

Нельзя использовать shared in-memory conversation state между generation jobs разных клиентов.

Каждый job должен собирать context заново из tenant-scoped data sources:
- project settings
- channel settings
- agent preset/config
- task/draft inputs
- approved knowledge/context for this project

## 5.4 Queue isolation

Generation jobs нельзя выполнять inline в Telegram update handler или веб-запросе, если это ведёт к смешиванию контекста и слабому контролю ресурсов.

Нужен queued execution path с project-scoped runtime loading.

## 5.5 Observability isolation

Логи, usage и cost events должны атрибутироваться к tenant scope, чтобы support, billing и аналитика не читали смешанные данные.

---

## 6. LLM layer components

## 6.1 LLM config layer

Нужен отдельный конфигурационный слой, отделённый от Telegram publishing config.

Минимальный набор настроек:
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_API_KEY_FILE` (preferred production path)
- `LLM_MODEL_DEFAULT`
- `LLM_BASE_URL` (optional)
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`
- `LLM_ROUTING_STRATEGY`
- `LLM_FALLBACK_PROVIDER` / `LLM_FALLBACK_MODEL` (optional)

### Rule

LLM secrets не должны смешиваться с `TELEGRAM_BOT_TOKEN` и не должны логироваться тем же путём без маскирования.

## 6.2 Generation service

Нужен единый application service, через который проходят все generation операции:
- ideas generation
- content-plan generation
- draft generation
- rewrite/regenerate
- future staged agent workflows

Он отвечает за:
- validation of scope
- config resolution
- prompt resolution
- routing decision
- provider invocation
- usage/cost logging
- normalized result envelope

## 6.3 Provider adapters

Provider adapters — это тонкий слой интеграции, а не место для продуктовой логики.

Минимально стоит предусмотреть adapters для:
- OpenAI
- Anthropic
- OpenRouter
- Gemini

Каждый adapter должен возвращать единый нормализованный результат:
- `provider`
- `model`
- `output_text`
- `finish_reason`
- `request_id`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `latency_ms`
- `raw_error` / normalized error

## 6.4 Agent runtime resolver

Нужен resolver, который по `client/project/channel` собирает execution profile:
- состав агентной команды
- роли и их prompts
- prompt version ids
- generation mode (`single-pass` / `multi-stage`)
- routing policy
- feature flags
- quotas / budget limits

### MVP status after task 82

В текущем коде baseline tenant isolation уже проведён через `execution_context` layer и persisted runtime entity:
- для каждого task generation сначала собирается `project-scoped execution context`
- в него замораживаются project settings, client/workspace scope, channel scope и snapshot активных agent profiles
- orchestration использует только агентов текущего проекта и, если применимо, текущего канала
- при резолве контекста синхронизируется `agent_team_runtimes` запись для конкретного `project/channel` scope
- в `generation_metadata` сохраняется execution fingerprint, runtime fingerprint и frozen agent runtime snapshot для аудита

---

## 7. Execution model

## 7.1 Baseline mode

Базовый режим для большинства дешёвых операций:
- single generation request
- один provider call
- одна запись generation event
- быстрый возврат результата

Подходит для:
- ideas
- simple rewrite
- cheap draft refresh

## 7.2 Advanced mode

Продвинутый режим для дорогих тарифов:
- staged multi-agent pipeline
- strategist -> researcher -> writer -> editor
- каждая стадия — отдельный generation event
- общий parent execution id для трассировки

### Rule

Даже в multi-stage режиме stage outputs не должны становиться глобальным shared memory для чужих tenant’ов.

---

## 8. Data model implications

Для этой архитектуры понадобятся новые или расширенные сущности.

## 8.1 Required additions

1. **client_accounts / subscriptions**
   - billing owner
   - tariff / plan
   - status
   - limits

2. **agent_team_runtime** (или equivalent)
   - привязка к project/channel
   - current config snapshot
   - active preset
   - runtime mode
   - prompt/config version refs

3. **llm_generation_events**
   - полный журнал generation вызовов
   - основа для cost accounting, debugging и support

## 8.2 Required fields for `llm_generation_events`

Минимум:
- `id`
- `client_id`
- `project_id`
- `channel_id`
- `task_id` / `draft_id` / `content_plan_id` nullable by operation
- `operation_type`
- `execution_id`
- `parent_execution_id` (for multi-stage)
- `stage_name` nullable
- `provider`
- `model`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `latency_ms`
- `status`
- `request_id`
- `error_code` / `error_summary`
- `created_at`

## 8.3 Metadata projection

В `drafts`, `tasks`, `content_plans`, `publications` можно хранить только краткий summary:
- provider
- model
- execution_id
- tokens/cost summary
- generation mode

Полная история должна лежать отдельно, а не размазываться по domain entities.

---

## 9. Routing strategy

Model routing должен определяться application policy, а не быть захардкожен внутри конкретного endpoint.

Пример целевой политики:
- ideas -> cheap/fast model
- content planning -> medium reasoning model
- draft generation -> stronger writing model
- rewrite -> depends on requested quality/latency
- premium channels -> multi-stage pipeline with higher-end models

### Rule

Routing policy должна быть versionable и testable.

---

## 10. Reliability requirements

Новый LLM stack обязан поддерживать:
- request timeouts
- retry/backoff policy
- provider-specific transient error handling
- rate-limit handling
- provider degradation detection
- optional failover to fallback provider/model
- idempotent job handling where possible

Ошибки provider’а должны возвращаться в bot/admin UX как понятные product-level статусы, а не как сырой stack trace.

---

## 11. Security and secrets

## 11.1 Secret separation

Нужно разделить:
- Telegram publishing secrets
- LLM provider secrets
- internal service credentials

Рекомендуемый production path:
- non-secret LLM config stays in env
- secret key comes from `LLM_API_KEY_FILE`
- logs never print raw key
- health/status endpoints never expose raw LLM config

## 11.2 Log hygiene

Запрещено писать в логи:
- raw provider key
- full authorization headers
- full prompts with secrets/customer-sensitive inserts, если они не прошли redaction policy

## 11.3 Access hygiene

Admin/support интерфейсы могут видеть usage/cost history, но не provider key.

---

## 12. Non-goals of this design

Этот документ **не** фиксирует пока:
- self-hosted model serving
- per-client BYOK as default architecture
- long-lived conversational memory per tenant
- autonomous agent swarms outside channel/project scope

Это может быть добавлено позже, но не является обязательным для первой production-ready multi-tenant версии.

---

## 13. Consequences for backlog

Из этого дизайна прямо следуют следующие блоки работ:
- tenant model formalization
- separate LLM config layer
- real provider adapters
- unified generation service
- usage/cost event log
- tenant-isolated agent runtime
- generation queue + worker pool isolation
- quota/budget guardrails
- observability + billing/reporting
- tests for tenant isolation and cost attribution

---

## 14. Final decision summary

Финальная целевая позиция проекта:

> Telegram Channel Factory строится как multi-tenant SaaS с общим продуктовым доступом к LLM provider’ам, но со строгой изоляцией agent runtime, prompts, execution context, usage attribution и cost accounting на уровне client/project/channel.

Коротко:
- **shared LLM provider integration**
- **isolated tenant execution context**
- **queue-first generation path**
- **event-based usage/cost accounting**
- **versioned prompts and agent runtime**
- **separate LLM secret/config layer**
