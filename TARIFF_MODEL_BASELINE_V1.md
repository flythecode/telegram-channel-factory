# Tariff Model Baseline v1

## Purpose

Этот документ фиксирует каноническую тарифную модель Telegram Channel Factory v1 на базе уже внедрённых лимитов и реальных generation cost signals из `llm_generation_events`.

Baseline должен снять двусмысленность между:
- лимитами продукта (`included_channels`, `included_generations`, `max_tasks_per_day`);
- execution path (`single_pass` vs `multi_stage`);
- доступными agent preset'ами;
- economics model из `app/services/pricing.py`.

## Canonical source of truth

Тарифная модель считается зафиксированной только если согласованы три слоя:

1. `app/services/tariff_policy.py`
   - plan limits;
   - allowed presets;
   - allowed generation operations;
   - `service_tier` и `execution_mode`.
2. `app/services/pricing.py`
   - rate card по операциям на базе real/fallback generation costs;
   - monthly catalog economics;
   - overage baseline.
3. `TARIFF_AGENT_MODEL_MATRIX_V1.md`
   - продуктовый смысл тарифа;
   - routing / preset / execution-mode policy.

## Locked plan matrix

| Plan | Service tier | Execution mode | Included channels | Included generations | Max tasks/day | Allowed presets |
|---|---|---:|---:|---:|---:|---|
| trial | economy | single_pass | 1 | 25 | 3 | `starter_3` |
| starter | economy | single_pass | 1 | 300 | 12 | `starter_3`, `balanced_5` |
| pro | standard | multi_stage | 3 | 1500 | 40 | `starter_3`, `balanced_5`, `editorial_7` |
| business | premium | multi_stage | 10 | 6000 | 150 | `starter_3`, `balanced_5`, `editorial_7` |

## Locked generation access

- `trial`: `ideas`, `content_plan`, `draft`
- `starter`: `ideas`, `content_plan`, `draft`, `regenerate_draft`
- `pro`: все starter-операции + `rewrite_draft`, `agent_stage`
- `business`: тот же functional surface, но premium tier / multi-stage baseline

## Cost-derived pricing baseline

`/api/v1/users/me/client-account/pricing` строит rate card из:
- real `llm_generation_events`, если они уже есть;
- fallback operation baselines, если sample ещё маленький.

Default pricing assumptions в коде сейчас такие:
- target margin: `70%`
- contingency: `15%`
- platform overhead: `$9/mo`
- channel overhead: `$2/mo`

Default blended generation cost baseline:
- ideas: `0.002500`
- content_plan: `0.004500`
- draft: `0.006500`
- regenerate_draft: `0.007000`
- rewrite_draft: `0.003000`
- weighted blended cost: `0.005025 USD / generation`

Из этих допущений следуют ориентиры каталога v1:
- `starter` ≈ `$41.69/mo`
- `pro` ≈ `$75.13/mo`
- `business` ≈ `$197.17/mo`

Это не hardcoded sales price promise, а economics baseline для operator decision-making. Если реальные `llm_generation_events` смещают blended cost, pricing endpoint должен показывать обновлённую рекомендацию поверх этих лимитов.

## What is considered fixed after item 129

После фиксации модели следующие вещи считаются обязательными:
- trial больше не получает `balanced_5`;
- pricing API возвращает не только лимиты, но и `service_tier` + `execution_mode` для каждого плана;
- docs, tests и runtime policy не противоречат друг другу;
- любые изменения лимитов/tiers/presets должны одновременно менять `tariff_policy.py`, pricing schema и этот документ.

## Verification

Минимальная регрессия для этой фиксации:

```bash
pytest -q tests/test_tariff_policy.py tests/test_client_accounts.py
python3 -m compileall app tests
```

Если эти проверки зелёные, тарифная модель v1 считается зафиксированной на уровне runtime + API + docs.
