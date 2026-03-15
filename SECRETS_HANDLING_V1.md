# Telegram Channel Factory — Secrets Handling v1

## 1. Purpose

Этот документ фиксирует базовые правила работы с секретами в MVP v1.

## 2. Goal

Токены и чувствительные данные не должны случайно утекать через рабочие файлы, тесты, демо-конфигурации и документацию.

## 3. MVP rules

- реальные токены не должны храниться в публичных или demo-oriented файлах
- `.env.example` должен быть безопасным шаблоном
- live secrets должны подставляться отдельно
- при утечке токен должен ротироваться

## 4. Practical rule

`stub` и `demo` режимы не должны требовать реальных production-like токенов.

## 5. Decisions fixed by this doc

Этим документом фиксируется:
- secrets handling — это не post-MVP роскошь, а базовая дисциплина
- demo/dev/test конфиги должны быть безопасными
- live токены требуют отдельного и аккуратного обращения

## 6. Secret file baseline

Предпочтительный production-путь:
- обычные non-secret настройки остаются в env-файле (например `/etc/telegram-channel-factory/.env.live`)
- Telegram bot token хранится в отдельном secret file (например `/etc/telegram-channel-factory/secrets/telegram_bot_token`)
- LLM provider key хранится в отдельном secret file (например `/etc/telegram-channel-factory/secrets/llm_api_key`)
- приложение читает их через `TELEGRAM_BOT_TOKEN_FILE` и `LLM_API_KEY_FILE`
- `TELEGRAM_BOT_TOKEN` и `LLM_API_KEY` остаются только как fallback для локальных и аварийных случаев, не как основной production способ
- production deploy flow обязан валиться, если live env содержит inline `TELEGRAM_BOT_TOKEN` или inline `LLM_API_KEY`
- LLM secret не должен смешиваться с Telegram token ни в одном файле, шаблоне или логическом контейнере секретов

Пример:

```env
RUNTIME_MODE=live
PUBLISHER_BACKEND=telegram
TELEGRAM_BOT_TOKEN_FILE=/etc/telegram-channel-factory/secrets/telegram_bot_token
LLM_PROVIDER=openai
LLM_API_KEY_FILE=/etc/telegram-channel-factory/secrets/llm_api_key
```

## 7. Rotation rule

Если секрет использовался в тестовом live run, был показан в shell history, попал в лог, demo-файл, скриншот или в чужой доступ, он считается скомпрометированным.

Минимальный порядок действий:
1. перевыпустить или отозвать скомпрометированный секрет у соответствующего provider'а
2. обновить отдельный secret file новым значением
3. перезапустить stack с тем же env-файлом
4. убедиться, что старое значение больше не используется
5. проверить, что в release/docs/log output не осталось старого секрета

Для Telegram и LLM ключей ротация выполняется независимо: компрометация LLM key не должна требовать перевыпуска bot token, и наоборот.

## 8. Repo hygiene

- реальные токены не коммитятся
- директория `secrets/` игнорируется git
- для примеров используется отдельная tracked-директория `secrets.example/`
- tracked env-файлы содержат только пустые значения, заглушки или ссылки на secret file path
