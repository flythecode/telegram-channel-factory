# Telegram Channel Factory — Prompt Template Management v1

## 1. Purpose

Этот документ фиксирует систему prompt/template management для MVP v1.

---

## 2. Goal

Нужна модель, в которой поведение агентов можно:
- задавать шаблонами
- переиспользовать
- адаптировать под проект
- менять без переписывания кода

---

## 3. Template layers

В MVP рекомендуется 4 слоя:
1. `global default`
2. `preset template`
3. `project override`
4. `agent custom override`

Итоговое поведение агента собирается сверху вниз.

---

## 4. Template content

Каждый template может содержать:
- `title`
- `role_code`
- `system_prompt`
- `style_prompt`
- `notes`
- `is_active`

---

## 5. MVP use cases

Нужно поддержать:
- базовые prompts по ролям
- prompts для preset-команд
- project-level overrides
- ручную донастройку конкретного агента

---

## 6. UX rule

В UI не надо показывать prompt engineering как сложный техрежим.

Лучше давать пользователю понятные действия:
- `Изменить стиль агента`
- `Добавить инструкцию`
- `Вернуть стандартное поведение`

---

## 7. Safety rule

Изменение template'а:
- влияет на будущие генерации
- не должно ломать историю старых результатов
- должно быть версионируемо хотя бы на уровне audit/config snapshots

---

## 8. Decisions fixed by this doc

Этим документом фиксируется:
- поведение агентов строится на layers шаблонов
- prompts не хардкодятся только в коде
- в MVP пользователь может менять поведение агентов через project/agent overrides
- template management — часть продукта, а не внутренняя инженерная деталь
