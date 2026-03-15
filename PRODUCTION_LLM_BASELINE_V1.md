# Production LLM Baseline v1

## Purpose

Этот документ фиксирует, что новая multi-tenant LLM-agent architecture больше не считается экспериментом или roadmap-only направлением. Для Telegram Channel Factory это **production baseline**: именно через этот слой должны идти generation flows, cost attribution, tenant isolation и operator controls.

## Production baseline statement

С версии `0.1.0-mvp` production baseline проекта определяется так:

- все generation-операции (`ideas`, `content_plan`, `draft`, `rewrite`, `regenerate`) проходят через `app/services/generation_service.py`;
- execution context tenant-isolated: attribution и runtime snapshot привязаны к `client_account_id`, `project_id`, `channel_id`;
- staged multi-agent orchestration является штатным production path для premium-tier сценариев, а single-pass — для дешёвых тарифов и принудительных override;
- usage/cost accounting ведётся через `llm_generation_events`;
- queue-first execution и worker-pool считаются стандартным путём для non-inline generation workloads;
- guardrails, quota, budget и hard-stop policy являются обязательной частью production runtime;
- observability, pricing summary, admin usage/cost endpoints и export flows считаются частью production operator surface, а не вспомогательным экспериментом.

## What is now deprecated as a baseline

Следующие подходы больше не считаются допустимым product baseline:

- text-orchestration stub как основной generation path;
- inline generation без учёта attribution/cost metadata;
- тарифы без жёсткой связи с generation mode и доступными agent presets;
- runtime, в котором provider key смешан с Telegram bot token или хранится в логах / inline env без secret-file path;
- production rollout без проверки generation guardrails, admin cost visibility и release smoke.

## Canonical implementation anchors

### Core runtime
- `app/services/generation_service.py`
- `app/services/orchestration.py`
- `app/services/execution_context.py`
- `app/services/llm_provider.py`
- `app/services/generation_queue.py`
- `app/services/generation_worker_pool.py`
- `app/services/generation_guardrails.py`
- `app/services/generation_observability.py`

### Data and attribution
- `app/models/client_account.py`
- `app/models/agent_team_runtime.py`
- `app/models/llm_generation_event.py`
- `app/models/generation_job.py`

### Operator/admin surface
- `app/api/v1/admin.py`
- `app/services/cost_dashboard.py`
- `app/services/generation_admin.py`
- `app/services/pricing.py`
- `app/services/report_exports.py`

### Docs / runbooks
- `MULTI_TENANT_LLM_ARCHITECTURE_V1.md`
- `MODEL_ROUTING_STRATEGY_V1.md`
- `TARIFF_AGENT_MODEL_MATRIX_V1.md`
- `LLM_FAILOVER_POLICY_V1.md`
- `LLM_COST_OPERATOR_RUNBOOK.md`
- `STAGING_LLM_ARCHITECTURE_VALIDATION_2026-03-14.md`

## Required production gates

Перед тем как считать rollout соответствующим baseline, должны быть истинны все пункты:

1. `python3 -m compileall app scripts` проходит без ошибок.
2. Targeted regression по generation/runtime surface зелёный.
3. `alembic upgrade head` содержит все миграции baseline (`client_accounts`, `agent_team_runtimes`, `llm_generation_events`, `generation_jobs`, metadata summary).
4. Production env использует secret-file flow для `TELEGRAM_BOT_TOKEN_FILE` и `LLM_API_KEY_FILE`.
5. `/health` smoke проходит после release/update.
6. Operator имеет доступ к cost dashboard / usage exports / pricing summary.
7. Hard-stop guardrails могут объяснить причину блокировки generation клиенту и оператору.

## Release note

Backlog item 120 считается закрытым, когда проектовая документация, release artifacts и MEMORY синхронизированы с этим baseline, а targeted verification подтверждает, что кодовая база и operator surface соответствуют новой архитектуре.
