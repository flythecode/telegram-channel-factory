# Telegram Channel Factory — Orchestration Engine v1

## 1. Purpose

Этот документ фиксирует, как в MVP v1 должна работать базовая multi-agent orchestration логика.

---

## 2. Goal

Система должна уметь прогонять контентную задачу через команду из 3–7 агентов и получать финальный draft, пригодный для ревью и публикации.

---

## 3. MVP orchestration model

В MVP используется **линейный pipeline**, а не сложный graph workflow.

Базовая модель:
1. берётся задача
2. определяется активная конфигурация проекта
3. формируется список включённых агентов по `sort_order`
4. задача проходит через агентов по очереди
5. каждый агент вносит свой вклад в общий результат
6. финальный результат сохраняется как draft

---

## 4. Input and output

### Input
- project config
- channel strategy
- task brief
- active agent team
- prompts and overrides

### Output
- final draft
- optional intermediate artifacts
- metadata о прохождении пайплайна

---

## 5. Recommended stage model

### Stage 1 — Strategy
Strategist формирует угол подачи и структуру материала.

### Stage 2 — Research
Researcher собирает тезисы, аргументы и контекст.

### Stage 3 — Writing
Writer создаёт первичный текст черновика.

### Stage 4 — Editing
Editor улучшает текст.

### Stage 5 — Verification
Fact-checker проверяет явные риски ошибок.

### Stage 6 — Reach optimization
Reach Optimizer усиливает заход, заголовок и читаемость.

### Stage 7 — Publishing handoff
Publisher подготавливает результат к публикации.

---

## 6. MVP simplification rule

В v1 не нужны:
- branching logic
- recursive agent loops
- dynamic debate systems
- autonomous self-repair graphs

Достаточно понятного и управляемого пайплайна.

---

## 7. Failure handling

Если отдельный агент падает:
- система фиксирует ошибку
- задача не теряется
- пользователь получает понятный статус
- допускается fallback behavior по конфигурации later

В MVP минимально допустимо помечать задачу как failed at stage.

---

## 8. User visibility rule

Пользователь не обязан видеть всю внутреннюю сложность orchestration.

В UI достаточно показывать:
- какая команда используется
- какой статус генерации
- какой финальный draft получен

При желании later можно добавить `Показать этапы`.

---

## 9. Decisions fixed by this doc

Этим документом фиксируется:
- в MVP orchestration linear, not graph-based
- активные агенты запускаются по порядку
- результатом пайплайна является draft
- сложные multi-agent debate patterns не входят в первый релиз
