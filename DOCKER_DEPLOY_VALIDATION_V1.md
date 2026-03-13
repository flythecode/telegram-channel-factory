# Telegram Channel Factory — Docker & Deploy Validation v1

## 1. Purpose

Этот документ фиксирует требования к финальной проверке Docker/deploy path.

## 2. Goal

Система должна запускаться не только как локальный Python-проект, но и как воспроизводимый deployable сервис.

## 3. Validation targets

- build Docker image
- run compose stack
- apply migrations
- start API
- start worker
- check health endpoints
- validate publication flow in deployed-like mode

## 4. MVP rule

Если продукт нельзя воспроизводимо поднять, релиз остаётся хрупким.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- Docker/deploy validation нужна до релиза
- deploy path должен быть проверяемым и повторяемым
- staging-like запуск является частью release confidence
