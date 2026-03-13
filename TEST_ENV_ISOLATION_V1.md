# Telegram Channel Factory — Test Env Isolation v1

## 1. Purpose

Этот документ фиксирует правило изоляции тестов от рабочего `.env` и live Telegram-конфигурации.

## 2. Problem

Если `pytest` зависит от текущего `.env`, тесты становятся недетерминированными и могут уходить в live backend вместо stub/test mode.

## 3. MVP rule

Тесты должны запускаться в изолированном режиме:
- без зависимости от рабочего `.env`
- без live Telegram token requirements
- с предсказуемым `stub` или `test` backend

## 4. Recommended approach

- выделить test settings path
- переопределять env через fixtures/monkeypatch
- не читать production-like `.env` в unit/integration tests

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- test mode должен быть полностью детерминированным
- live Telegram backend не должен включаться обычным `pytest`
- изоляция тестов — обязательная часть release readiness
