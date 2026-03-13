# Telegram Channel Factory — Release Packaging v1

## 1. Purpose

Этот документ фиксирует требования к финальной упаковке релиза MVP v1.

## 2. Goal

Перед выпуском должен существовать понятный набор артефактов и шагов, позволяющий поднять и проверить продукт как единое целое.

## 3. Release package should include

- актуальные migration files
- env templates
- docs
- reproducible run flow
- smoke checks
- release version marker

## 4. MVP rule

Релиз — это не просто код в репозитории, а воспроизводимый пакет запуска и проверки.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- release packaging является отдельной задачей
- финальный выпуск требует не только фич, но и упаковки
- reproducibility — обязательное свойство релиза
