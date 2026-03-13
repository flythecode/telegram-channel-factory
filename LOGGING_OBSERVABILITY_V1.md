# Telegram Channel Factory — Logging & Observability v1

## 1. Purpose

Этот документ фиксирует минимальные требования к logging/observability для MVP v1.

## 2. Goal

Нужно иметь возможность понять, что произошло с проектом, генерацией, черновиком или публикацией, не угадывая по косвенным признакам.

## 3. MVP needs

- логи ключевых действий
- логи ошибок
- статусы пайплайна
- базовые operational signals для API/worker/publication flow

## 4. MVP rule

Даже без enterprise monitoring у команды должен быть способ быстро диагностировать проблему.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- observability нужна уже в MVP
- logging должен покрывать ключевые product flows
- диагностируемость — часть качества продукта
