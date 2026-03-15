# Telegram Channel Factory — Internal Pilot Cost Validation Plan

Backlog item: **118. Провести controlled internal pilot на первых клиентах и сравнить реальные generation costs с ожидаемой экономикой тарифа.**

## Честный статус

**В этом workspace pilot-пакет подготовлен, но сам пункт 118 ещё нельзя честно закрыть без реальных pilot-клиентов и их живых generation-сессий.**

Что уже можно сделать прямо сейчас:
- зафиксировать pilot scope;
- подготовить шаблон сбора фактов по каждому клиенту;
- подготовить шаблон economics reconciliation;
- описать точный run order для оператора.

Что обязательно нужно для честного закрытия пункта 118:
- минимум 1–3 реальных internal pilot клиента;
- реальные generation events в staging/prod-like среде;
- сравнение фактических cost/usage с ожидаемой economics-моделью тарифа;
- список расхождений и решение, достаточно ли система готова к production baseline.

## Goal

Подтвердить на первых pilot-клиентах четыре вещи:
1. generation pipeline стабильно проходит реальные пользовательские сценарии;
2. usage/cost attribution корректно считается по `client/project/channel/operation`;
3. фактическая себестоимость не ломает ожидаемую unit economics выбранного тарифа;
4. найденные отклонения можно превратить в backlog item 119 без догадок.

## Recommended pilot scope

Минимальная первая волна:
- 1–3 internal pilot клиента;
- у каждого минимум 1 канал;
- для каждого прогнать сценарии:
  - `generate_content_plan`
  - `generate_ideas`
  - `create_draft`
  - `regenerate_draft` или `rewrite_draft`
- по возможности включить хотя бы:
  - 1 cheap/single-pass тарифный сценарий (`trial/starter`)
  - 1 richer/premium сценарий (`pro/business`) для сравнения экономики.

## Safe environment

Предпочтительно:

```env
APP_ENV=staging
RUNTIME_MODE=demo
PUBLISHER_BACKEND=stub
LLM_PROVIDER!=stub
LLM_API_KEY_FILE=/.../llm_api_key
TELEGRAM_BOT_TOKEN_FILE=/.../telegram_bot_token
```

Правила:
- отдельный LLM key для pilot/staging;
- не смешивать pilot с production billing без явного решения;
- не использовать inline `LLM_API_KEY` и `TELEGRAM_BOT_TOKEN`;
- все evidence сохранять в markdown/CSV рядом с этим планом.

## Required evidence per pilot client

На каждого клиента нужно собрать:
- профиль клиента и выбранный тариф;
- число каналов;
- фактические выполненные generation operations;
- usage summary по `client/channel/operation`;
- cost breakdown по `provider/model/operation`;
- observed UX/reliability issues;
- expected monthly economics assumptions;
- factual deviation vs expected model.

## Success criteria for closing backlog item 118

Пункт 118 можно отметить `[x]`, только если выполнено всё ниже:
- есть хотя бы 1 реальный pilot-клиент с живыми generation events;
- есть заполненный pilot result file хотя бы на одного клиента;
- есть economics reconciliation с expected vs actual цифрами;
- явно перечислены найденные расхождения, которые переходят в item 119;
- есть операторский вывод: `pilot_pass`, `pilot_pass_with_fixes`, или `pilot_blocked`.

## Expected outputs

После pilot должны появиться:
- `INTERNAL_PILOT_REPORT_YYYY-MM-DD.md`
- `internal-pilot/YYYY-MM-DD/PILOT_CLIENT_01.md` (+ дополнительные client files)
- `internal-pilot/YYYY-MM-DD/ECONOMICS_RECONCILIATION.md`
- при необходимости CSV exports из usage/cost dashboard

## Exact run order

1. Выбрать 1–3 internal pilot клиента и тарифы.
2. Для каждого клиента создать отдельный `PILOT_CLIENT_0X.md` по шаблону.
3. Прогнать реальные сценарии generation.
4. Выгрузить usage/cost evidence из dashboard/admin endpoints.
5. Заполнить `ECONOMICS_RECONCILIATION.md` фактом vs ожиданием.
6. Записать конкретные reliability / attribution / cost anomalies.
7. Свести вывод в `INTERNAL_PILOT_REPORT_YYYY-MM-DD.md`.
8. Только после этого отмечать в `MEMORY.md`:
   - [x] 118. Провести controlled internal pilot на первых клиентах и сравнить реальные generation costs с ожидаемой экономикой тарифа.

## Current blocker

В текущей среде нет самих pilot-клиентов, живых generation events от них и разрешения на внешний контакт. Значит можно подготовить и упаковать pilot, но нельзя честно симулировать результат как завершённый.
