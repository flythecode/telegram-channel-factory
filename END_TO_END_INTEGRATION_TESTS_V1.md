# Telegram Channel Factory — End-to-End Integration Tests v1

## 1. Purpose

Этот документ фиксирует требования к end-to-end интеграционным тестам продукта.

## 2. Goal

Нужно проверять полный пользовательский путь: от создания проекта до черновика, approve и публикации.

## 3. Priority E2E scenario

`user -> setup -> channel connect -> agent team -> content plan -> task -> draft -> approve -> publication`

## 4. MVP rule

Минимум один сквозной воспроизводимый сценарий должен быть автоматизируемым.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- e2e путь обязателен для release confidence
- тесты должны проверять интеграцию слоёв, а не только отдельные функции
- полный цикл контента является ключевым продуктовым сценарием
