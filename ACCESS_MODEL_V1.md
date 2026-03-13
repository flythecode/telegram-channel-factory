# Telegram Channel Factory — Access Model v1

## 1. Purpose

Этот документ фиксирует минимальную модель пользователей, владения и доступа для MVP v1.

Цель: у каждого проекта и канала должен быть понятный владелец, а система должна различать пользователя Telegram и объекты продукта.

---

## 2. MVP principle

В MVP v1 модель доступа должна быть **простой**:
- один Telegram user может иметь несколько проектов
- каждый проект принадлежит одному владельцу
- каждый канал принадлежит одному проекту
- сложные multi-user permissions в MVP не входят

---

## 3. Core entities

### User
Представляет пользователя продукта, пришедшего из Telegram.

Поля v1:
- `id`
- `telegram_user_id` (unique)
- `telegram_username` (nullable)
- `first_name` (nullable)
- `last_name` (nullable)
- `is_active`
- `created_at`
- `updated_at`

### Workspace
Логическая оболочка над проектами пользователя.

В MVP можно держать правило: **1 user = 1 personal workspace**.

Поля v1:
- `id`
- `owner_user_id`
- `name`
- `created_at`
- `updated_at`

### Project ownership
Каждый проект обязательно связан с workspace и user-владельцем.

Поля в `Project`:
- `workspace_id`
- `owner_user_id`

### Channel ownership
Каждый Telegram channel принадлежит проекту, а значит и пользователю-владельцу проекта.

---

## 4. Ownership rules

1. Пользователь создаёт проект от своего имени.
2. Проект принадлежит одному `owner_user_id`.
3. Все каналы, агенты, планы, задачи, черновики и публикации наследуют владение через проект.
4. Пользователь видит и редактирует только свои проекты.
5. В MVP нет shared workspaces и со-владельцев.

---

## 5. Minimal access rules for MVP

### User can:
- создавать свои проекты
- читать свои проекты
- редактировать свои проекты
- подключать свои каналы
- управлять своими агентами
- запускать свои генерации
- управлять своими черновиками и публикациями

### User cannot:
- видеть проекты других пользователей
- редактировать объекты чужих проектов
- публиковать в чужие каналы через UI продукта

---

## 6. Object ownership inheritance

Владение объектами наследуется так:

`User -> Workspace -> Project -> TelegramChannel / AgentProfile / ContentPlan / Task / Draft / Publication`

Практический смысл:
- проверка доступа чаще всего делается на уровне `project.owner_user_id`
- остальные сущности валидируются через принадлежность проекту

---

## 7. Recommended data relationships

### User
- has one personal workspace
- has many projects

### Workspace
- belongs to user
- has many projects

### Project
- belongs to workspace
- belongs to owner user
- has many channels
- has many agent profiles
- has many content plans
- has many tasks

### TelegramChannel
- belongs to project

### AgentProfile
- belongs to project
- optionally belongs to channel if later needed

### ContentPlan
- belongs to project

### Task
- belongs to project
- optionally belongs to content plan

### Draft
- belongs to task

### Publication
- belongs to draft
- belongs to channel

---

## 8. MVP auth model

В Telegram-first MVP основной источник identity — это Telegram inbound context.

MVP flow:
1. user пишет боту
2. система получает `telegram_user_id`
3. находит или создаёт `User`
4. находит или создаёт personal `Workspace`
5. все действия маршрутизируются в контексте этого пользователя

---

## 9. API-level rule

Каждый endpoint, который работает с project-bound объектами, должен:
1. определить текущего пользователя
2. проверить принадлежность проекта пользователю
3. только потом выполнять действие

---

## 10. Out of scope for v1

Не входит в MVP v1:
- shared workspace
- team roles
- granular permissions matrix
- invited collaborators
- per-object ACL
- RBAC enterprise-level

---

## 11. Decisions fixed by this doc

Этим документом фиксируется:
- в системе появляется сущность `User`
- в системе появляется сущность `Workspace`
- MVP идёт по модели `1 user -> 1 personal workspace`
- каждый проект должен иметь владельца
- доступ в MVP ограничен объектами владельца
- сложные права откладываются на post-MVP
