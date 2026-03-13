# Telegram Channel Factory — Retry & Error Handling v1

## 1. Purpose

Этот документ фиксирует базовые требования к retry/backoff и error handling.

## 2. Goal

Система должна обрабатывать сбои Telegram, сети и внутренних пайплайнов без немого падения и потери контроля.

## 3. MVP needs

- понятные error statuses
- retry policy для временных ошибок
- distinction between retryable and terminal errors
- читаемые сообщения пользователю

## 4. Product rule

Автоматизация без нормальной обработки ошибок быстро превращается в недоверие к продукту.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- retry/error handling входит в release readiness
- пользователю нужны понятные статусы и последствия ошибки
- временные и окончательные ошибки должны различаться
