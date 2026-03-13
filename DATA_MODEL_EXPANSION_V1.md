# Telegram Channel Factory — Data Model Expansion v1

## 1. Purpose

Этот документ фиксирует, какие поля и сущности нужно добавить к текущему backend MVP, чтобы поддержать продуктовую модель Telegram Channel Factory v1.

---

## 2. Existing base

Уже есть базовые сущности:
- Project
- TelegramChannel
- AgentProfile
- ContentPlan
- Task
- Draft
- Publication

Их нужно расширить, чтобы поддержать Telegram-first product UX.

---

## 3. New entities to add

### User
Для привязки Telegram-пользователя к проектам.

### Workspace
Для логической группировки проектов пользователя.

### AgentTeamPreset
Для шаблонов команд 3/5/7 агентов.

### PromptTemplate
Для базовых шаблонов поведения агентов.

### ProjectConfigVersion
Для хранения версии конфигурации проекта после изменений.

### AuditEvent
Для истории изменений ключевых настроек.

---

## 4. Project fields to add

В `Project` нужно добавить продуктовые настройки:
- `owner_user_id`
- `workspace_id`
- `slug` (optional)
- `topic`
- `niche`
- `language`
- `goal`
- `target_audience`
- `tone_of_voice`
- `content_type`
- `content_format`
- `posting_frequency`
- `approval_mode`
- `operation_mode` (`manual|semi_auto|auto`)
- `status` (`draft|active|paused|archived`)
- `current_config_version`
- `created_at`
- `updated_at`

---

## 5. TelegramChannel fields to add

В `TelegramChannel` стоит поддержать:
- `project_id`
- `channel_title`
- `channel_username`
- `channel_id`
- `bot_is_admin`
- `can_post_messages`
- `is_connected`
- `publish_mode`
- `default_schedule_policy`
- `is_active`
- `last_connection_check_at`
- `created_at`
- `updated_at`

---

## 6. AgentProfile fields to add

`AgentProfile` должен перестать быть только абстрактным профилем и стать конфигурируемой ролью в команде.

Добавить:
- `project_id`
- `channel_id` (nullable)
- `role_code`
- `display_name`
- `description`
- `preset_source`
- `system_prompt`
- `style_prompt`
- `custom_prompt`
- `sort_order`
- `is_enabled`
- `model_hint` (nullable)
- `temperature_hint` (nullable)
- `created_at`
- `updated_at`

---

## 7. ContentPlan fields to add

Для `ContentPlan`:
- `project_id`
- `title`
- `strategy_summary`
- `rubrics_json`
- `planning_horizon_days`
- `status`
- `created_by_agent_id` (nullable)
- `created_at`
- `updated_at`

---

## 8. Task fields to add

Для `Task`:
- `project_id`
- `content_plan_id` (nullable)
- `title`
- `brief`
- `task_type`
- `priority`
- `assigned_stage`
- `status`
- `scheduled_for` (nullable)
- `created_at`
- `updated_at`

---

## 9. Draft fields to add

Для `Draft`:
- `task_id`
- `version`
- `title` (nullable)
- `text`
- `status`
- `generated_by_agent_id` (nullable)
- `editor_notes` (nullable)
- `human_edited`
- `created_at`
- `updated_at`

---

## 10. Publication fields to add

Для `Publication`:
- `draft_id`
- `telegram_channel_id`
- `status`
- `scheduled_for` (nullable)
- `sent_at` (nullable)
- `external_message_id` (nullable)
- `failure_reason` (nullable)
- `publish_attempts`
- `created_at`
- `updated_at`

---

## 11. AgentTeamPreset entity

Нужна сущность для шаблонов команды.

Поля:
- `id`
- `code`
- `title`
- `agent_count`
- `description`
- `roles_json`
- `is_active`

Примеры preset:
- `starter_3`
- `balanced_5`
- `editorial_7`

---

## 12. PromptTemplate entity

Для переиспользуемых шаблонов агентного поведения.

Поля:
- `id`
- `scope` (`global|preset|project|channel|agent`)
- `role_code`
- `title`
- `system_prompt`
- `style_prompt`
- `notes`
- `is_active`

---

## 13. ProjectConfigVersion entity

Чтобы фиксировать изменения конфигурации проекта.

Поля:
- `id`
- `project_id`
- `version`
- `snapshot_json`
- `change_summary`
- `created_by_user_id`
- `created_at`

---

## 14. AuditEvent entity

Для истории действий.

Поля:
- `id`
- `project_id`
- `user_id`
- `entity_type`
- `entity_id`
- `action`
- `before_json`
- `after_json`
- `created_at`

---

## 15. MVP design rule

Все новые поля не обязательно включать в UI сразу, но модель должна поддерживать:
- создание проекта через Telegram wizard
- дальнейшее редактирование
- настройку команды агентов
- смену operation mode
- историю изменений

---

## 16. Priority of implementation

### Phase 1
- User
- Workspace
- owner links in Project
- operation_mode in Project
- expanded AgentProfile

### Phase 2
- AgentTeamPreset
- PromptTemplate
- richer TelegramChannel fields
- richer Project strategy fields

### Phase 3
- ProjectConfigVersion
- AuditEvent

---

## 17. Decisions fixed by this doc

Этим документом фиксируется:
- продукту нужны `User` и `Workspace`
- `Project` становится центром стратегии и владения
- `AgentProfile` становится реальной конфигурируемой ролью
- нужны preset-команды и prompt templates
- конфигурация проекта должна быть версионируемой
- история изменений нужна, но может идти второй волной
