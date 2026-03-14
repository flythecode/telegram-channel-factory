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
- сам Telegram token хранится в отдельном secret file (например `/etc/telegram-channel-factory/secrets/telegram_bot_token`)
- приложение читает токен через `TELEGRAM_BOT_TOKEN_FILE`
- `TELEGRAM_BOT_TOKEN` остаётся только как fallback для локальных и аварийных случаев, не как основной production способ

Пример:

```env
RUNTIME_MODE=live
PUBLISHER_BACKEND=telegram
TELEGRAM_BOT_TOKEN_FILE=/etc/telegram-channel-factory/secrets/telegram_bot_token
```

## 7. Rotation rule

Если токен использовался в тестовом live run, был показан в shell history, попал в лог, demo-файл, скриншот или в чужой доступ, он считается скомпрометированным.

Минимальный порядок действий:
1. перевыпустить bot token у BotFather
2. обновить secret file новым токеном
3. перезапустить stack с тем же env-файлом
4. убедиться, что старый токен больше не используется

## 8. Repo hygiene

- реальные токены не коммитятся
- директория `secrets/` игнорируется git
- для примеров используется отдельная tracked-директория `secrets.example/`
- tracked env-файлы содержат только пустые значения, заглушки или ссылки на secret file path
