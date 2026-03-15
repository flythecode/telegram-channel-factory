# Telegram Channel Factory — Multi-tenant LLM Schema Plan

## Goal

Разложить задачу 70 в конкретные schema changes для multi-tenant LLM runtime.

## New / updated entities

### 1. ClientAccount
Purpose: платный tenant / клиентский billing boundary.

Suggested fields:
- id
- workspace_id
- owner_user_id
- name
- slug
- status (`trial|active|paused|blocked|churned`)
- billing_email
- external_billing_id
- default_plan_code
- soft_budget_usd_monthly
- hard_budget_usd_monthly
- metadata

Relations:
- workspace -> client_accounts
- owner_user -> client_accounts
- projects -> client_account
- generation_jobs -> client_account
- llm_generation_events -> client_account

### 2. Project (extend)
Add:
- client_account_id (nullable first, then required after migration)
- plan_code / subscription snapshot (optional)
- budget_override_usd_monthly (optional)

Purpose:
- attach every channel/project to a billable tenant.

### 3. TelegramChannel (extend)
Add:
- client_account_id (optional redundant denormalization for faster reporting)
- monthly_budget_override_usd (optional)
- usage_caps (JSONB optional)

### 4. AgentTeamRuntime
Purpose: execution-time snapshot of active team config for a project/channel.

Suggested fields:
- id
- client_account_id
- project_id
- channel_id
- active_preset_code
- runtime_mode (`single_pass|multi_stage`)
- is_active
- config_snapshot (JSONB)
- prompt_version

### 5. GenerationJob
Purpose: queued generation request.

Suggested fields:
- id
- client_account_id
- project_id
- channel_id
- content_task_id (nullable)
- draft_id (nullable)
- operation_type (`ideas|plan|draft|rewrite|regenerate`)
- priority
- status (`queued|running|done|failed|cancelled|blocked`)
- provider
- requested_model
- effective_model
- input_payload (JSONB)
- result_payload (JSONB)
- failure_reason
- retry_count
- queued_at
- started_at
- finished_at

### 6. LLMGenerationEvent
Purpose: immutable billing + observability record of every provider call.

Suggested fields:
- id
- client_account_id
- project_id
- channel_id
- content_task_id (nullable)
- draft_id (nullable)
- generation_job_id (nullable but preferred)
- operation_type
- provider
- model
- request_id
- prompt_tokens
- completion_tokens
- total_tokens
- estimated_cost_usd
- latency_ms
- status (`success|error|rate_limited|timeout|cancelled`)
- error_code
- error_message_redacted
- metadata

### 7. Draft / ContentTask (extend metadata only first)
Keep existing tables, but standardize `generation_metadata` structure.

Suggested summary fields inside JSON:
- provider
- model
- operation_type
- generation_job_id
- latest_generation_event_id
- total_cost_usd
- total_tokens
- runtime_mode
- stage_count

## Migration order

1. create `client_accounts`
2. add `client_account_id` to `projects`
3. backfill existing projects into a default client account per owner/workspace
4. create `agent_team_runtimes`
5. create `generation_jobs`
6. create `llm_generation_events`
7. add helpful indexes and foreign keys
8. standardize metadata payloads in drafts/tasks

## Minimum indexes

### client_accounts
- unique(slug)
- index(owner_user_id)
- index(workspace_id)

### projects
- index(client_account_id)

### generation_jobs
- index(status, priority, queued_at)
- index(client_account_id, status)
- index(project_id, status)
- index(channel_id, status)
- index(operation_type, status)

### llm_generation_events
- index(client_account_id, created_at)
- index(project_id, created_at)
- index(channel_id, created_at)
- index(operation_type, created_at)
- index(provider, model, created_at)
- index(status, created_at)
- unique(request_id) where feasible

## First-slice rule

For the first implementation slice:
- create `client_accounts`
- attach `projects` to `client_accounts`
- create `llm_generation_events`
- postpone `agent_team_runtimes` if current `AgentProfile[]` is enough for v1 runtime isolation
- create `generation_jobs` when generation leaves inline execution

## Decision note

`AgentProfile` already gives a good base for tenant-isolated team members because it is project-scoped.
So first iteration can avoid overbuilding a separate complex agent graph. The crucial gap is not agent storage, but real LLM runtime + cost attribution + queued execution.
