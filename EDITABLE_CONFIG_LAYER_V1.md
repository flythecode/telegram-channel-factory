# Telegram Channel Factory — Editable Config Layer v1

## 1. Purpose

Этот документ фиксирует принцип: пользователь может менять канал после запуска, а система обязана поддерживать редактируемую конфигурацию, а не одноразовый setup.

---

## 2. Product rule

Конфигурация проекта должна быть **editable by design**.

Это значит:
- setup wizard создаёт только стартовую конфигурацию
- после запуска пользователь может менять настройки
- изменения должны применяться к будущим задачам и публикациям
- изменения не должны ломать историю уже созданных объектов

---

## 3. What must be editable in MVP

Пользователь должен иметь возможность менять:
- тему / нишу канала
- язык
- tone of voice
- тип контента
- частоту публикаций
- рубрики
- approval mode
- operation mode
- состав команды агентов
- включённость конкретных агентов
- базовые prompts агентов
- расписание публикаций

---

## 4. Editable config domains

### Domain A — Project strategy
- niche
- goal
- target audience
- tone of voice
- content type
- content format

### Domain B — Operating rules
- manual / semi-auto / auto
- approval policy
- posting frequency
- schedule policy

### Domain C — Agent team
- preset
- enabled agents
- roles
- order of agents
- custom prompts

### Domain D — Channel settings
- connected channel target
- publish behavior
- active/inactive status

---

## 5. Config model approach

Для MVP рекомендуемый подход:
- ключевые поля хранятся структурированно в таблицах
- при каждом значимом изменении сохраняется config snapshot
- у проекта есть `current_config_version`
- новые задачи и генерации используют текущую версию конфигурации

---

## 6. Golden rule for changes

Изменения конфигурации действуют **вперёд**, а не переписывают прошлое.

То есть:
- старые публикации остаются в истории как были
- старые черновики можно не мутировать автоматически
- новые задачи и новые генерации берут обновлённую конфигурацию

---

## 7. Edit actions to support in UI

В Telegram UI пользователь должен иметь кнопочные сценарии:
- `Изменить тему`
- `Изменить стиль`
- `Изменить частоту`
- `Изменить режим`
- `Изменить рубрики`
- `Изменить состав агентов`
- `Включить/выключить агента`
- `Настроить prompt`
- `Изменить расписание`

---

## 8. Update flow pattern

Каждое изменение в MVP должно идти по одной схеме:
1. пользователь открывает раздел
2. выбирает параметр
3. видит текущее значение
4. задаёт новое значение
5. подтверждает изменение
6. система сохраняет новую конфигурацию
7. система создаёт audit event / config version при необходимости
8. бот показывает, что изменения будут применены к следующим действиям

---

## 9. What changes should affect immediately

Можно применять сразу:
- operation mode
- posting frequency
- enabled/disabled agent status
- future queue behavior
- prompt changes for future generations

---

## 10. What should not mutate retroactively by default

Не надо автоматически переписывать:
- уже отправленные публикации
- уже завершённые audit events
- историю прошлых настроек
- старые результаты без явной команды пользователя

---

## 11. Suggested backend pattern

### Write path
- update structured fields in main entities
- write config snapshot row
- write audit event row

### Read path
- current screens читают текущую конфигурацию
- historical views при необходимости читают snapshot/audit

---

## 12. MVP acceptance criteria

Editable config layer считается достаточной для MVP, если:
- пользователь может после setup поменять ключевые настройки
- эти изменения сохраняются устойчиво
- новые задачи используют новые настройки
- старые объекты не ломаются
- UI не создаёт ощущение одноразовой анкеты

---

## 13. Decisions fixed by this doc

Этим документом фиксируется:
- setup не является финальной точкой продукта
- проект обязан поддерживать пост-setup редактирование
- конфигурация должна быть версионируемой хотя бы на базовом уровне
- изменения должны быть безопасными и направленными в будущее
- editable UX — это обязательная часть MVP, а не nice-to-have
