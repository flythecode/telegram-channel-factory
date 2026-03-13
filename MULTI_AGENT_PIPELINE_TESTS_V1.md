# Telegram Channel Factory — Multi-Agent Pipeline Tests v1

## 1. Purpose

Этот документ фиксирует требования к тестам multi-agent pipeline в MVP v1.

## 2. Goal

Нужно подтверждать, что команда из 3–7 агентов обрабатывает задачу предсказуемо и выдаёт корректный draft/result.

## 3. Priority scenarios to test

- pipeline с preset `starter_3`
- pipeline с preset `balanced_5`
- pipeline с preset `editorial_7`
- pipeline с отключённым агентом
- pipeline с изменённым порядком агентов
- failure на одном из этапов

## 4. MVP rule

Тесты должны подтверждать логику оркестрации, а не качество текста как такового.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- orchestration logic требует отдельного слоя тестирования
- нужно проверять состав команды, порядок и статусные переходы
- multi-agent pipeline должен быть воспроизводимым в тестовом режиме
