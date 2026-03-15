# Telegram Channel Factory — Tariff / Agent Preset / Model Matrix v1

## 1. Purpose

Этот документ фиксирует, какие agent presets, execution modes и model routing profiles используются для разных тарифов и уровней клиентов.

Цель документа:
- убрать двусмысленность между pricing, agent presets и LLM routing;
- зафиксировать продуктовую матрицу для `trial`, `starter`, `pro`, `business`;
- дать единую основу для quota policy, bot UX и billing enforcement;
- связать тариф с реальным execution path, а не только с числом генераций.

---

## 2. Source decisions this matrix builds on

Матрица опирается на уже принятые решения:
- `AGENT_TEAM_PRESETS_V1.md` — есть 3 preset-команды: `starter_3`, `balanced_5`, `editorial_7`;
- `MODEL_ROUTING_STRATEGY_V1.md` — routing идёт через service tier + execution mode + profile ids;
- `app/services/pricing.py` — базовый catalog планов: `trial`, `starter`, `pro`, `business`;
- `app/services/execution_context.py` — дешёвые планы идут в `single-pass`, premium-планы в `multi-stage`.

Этим документом мы собираем эти решения в одну продуктовую policy.

---

## 3. Client levels

Для v1 фиксируются 4 продуктовых уровня клиентов:

1. **Trial**
   - задача: дать безопасный вход и короткий тест продукта;
   - приоритет: низкая себестоимость, простота, быстрый feedback.

2. **Starter**
   - задача: первый платный solo-режим;
   - приоритет: рабочее качество при контролируемой себестоимости.

3. **Pro**
   - задача: серьёзный рабочий режим для 1–3 каналов;
   - приоритет: заметно более сильное качество черновиков и planning.

4. **Business**
   - задача: каналы с более высокой ценностью, командной или агентной нагрузкой;
   - приоритет: качество, устойчивость, premium execution path.

---

## 4. Tariff matrix

| Plan code | Client level | Service tier | Default preset | Allowed presets | Execution mode | Notes |
|---|---|---|---|---|---|---|
| `trial` | Trial | `economy` | `starter_3` | `starter_3` | `single_pass` | тестовый вход, cheapest path |
| `starter` | Starter | `economy` | `balanced_5` | `starter_3`, `balanced_5` | `single_pass` | основной массовый платный режим |
| `pro` | Pro | `standard` | `balanced_5` | `starter_3`, `balanced_5`, `editorial_7` | `multi_stage` | сильнее planning/draft, 7-агентный preset уже доступен |
| `business` | Business | `premium` | `editorial_7` | `starter_3`, `balanced_5`, `editorial_7` | `multi_stage` | full editorial path и premium routing |

---

## 5. Product rules by plan

### 5.1 Trial

- Доступен только preset `starter_3`.
- Генерация идёт только через `single_pass`.
- Trial не получает полноценный multi-stage pipeline.
- Goal: показать value без дорогого execution path.

### 5.2 Starter

- Default preset: `balanced_5`, чтобы пользователь сразу видел продуктовую ценность.
- Разрешены `starter_3` и `balanced_5`.
- `editorial_7` закрыт для этого тарифа.
- Даже если в составе команды несколько агентов, generation mode остаётся `single_pass`.
- Agent team здесь — это mainly product configuration, а не обещание полного premium orchestration.

### 5.3 Pro

- Default preset: `balanced_5`.
- `editorial_7` становится доступным как upgrade в рамках плана.
- Execution mode: `multi_stage`.
- Pro — первый тариф, где staged agents должны реально давать заметную разницу в качестве.

### 5.4 Business

- Default preset: `editorial_7`.
- Все preset'ы доступны.
- Multi-stage обязателен по умолчанию.
- Business получает premium role-specific routing для strategist / researcher / writer / editor и optional premium stages.

---

## 6. Routing profile matrix by service tier

### 6.1 Economy (`trial`, `starter`)

| Operation | Routing profile | Model class |
|---|---|---|
| `ideas` | `fast_ideas` | `cheap_fast` |
| `content_plan` | `planner_balanced` | `balanced_planner` |
| `draft` | `writer_balanced` | `strong_writer` (lower-cost mapping) |
| `rewrite_draft` | `rewrite_fast` | `strong_editor` (economy mapping) |
| `regenerate_draft` | `writer_balanced` | `strong_writer` (economy mapping) |
| `agent_stage` | collapsed to single-pass / internal lightweight mapping | n/a |

### 6.2 Standard (`pro`)

| Operation | Routing profile | Model class |
|---|---|---|
| `ideas` | `ideas_balanced` | `balanced_fast` |
| `content_plan` | `planner_strong` | `strong_reasoner` |
| `draft` | `writer_strong` | `strong_writer` |
| `rewrite_draft` | `rewrite_balanced` | `strong_editor` |
| `regenerate_draft` | `writer_strong` | `strong_writer` |
| `agent_stage.strategist` | `planner_strong` | `strong_reasoner` |
| `agent_stage.researcher` | `research_balanced` | `balanced_planner` |
| `agent_stage.writer` | `writer_strong` | `strong_writer` |
| `agent_stage.editor` | `rewrite_balanced` | `strong_editor` |

### 6.3 Premium (`business`)

| Operation | Routing profile | Model class |
|---|---|---|
| `ideas` | `ideas_premium` | `balanced_fast` / premium-balanced |
| `content_plan` | `planner_premium` | `premium_reasoner` |
| `draft` | `writer_premium` | `premium_writer` |
| `rewrite_draft` | `editor_premium` | `premium_editor` |
| `regenerate_draft` | `writer_premium` | `premium_writer` |
| `agent_stage.strategist` | `premium_reasoning` | `premium_reasoner` |
| `agent_stage.researcher` | `premium_research` | `balanced_planner` or stronger research-capable mapping |
| `agent_stage.writer` | `premium_writing` | `premium_writer` |
| `agent_stage.editor` | `premium_editor` | `premium_editor` |
| `agent_stage.fact_checker` | `premium_research` | balanced verifier / premium research |
| `agent_stage.reach_optimizer` | `premium_editor` | premium editor / optimization |

---

## 7. Preset-to-tier recommendations

Ниже фиксируется не только what is allowed, но и what is recommended.

| Preset | Trial | Starter | Pro | Business |
|---|---|---|---|---|
| `starter_3` | allowed, fallback default | allowed | allowed | allowed |
| `balanced_5` | not allowed | default | default | allowed |
| `editorial_7` | not allowed | not allowed | allowed | default |

### Recommendation logic

- `starter_3` — onboarding / low-cost / simple content channels.
- `balanced_5` — product default почти для всех обычных платящих клиентов.
- `editorial_7` — only for upper-tier clients, где дополнительная агентная сложность экономически оправдана.

---

## 8. UX and sales implications

В bot/admin UX тариф должен объясняться через простой продуктовый смысл:

- **Trial** — попробовать 1 канал и базовую генерацию.
- **Starter** — рабочий solo-режим, 1 канал, default `balanced_5`.
- **Pro** — несколько каналов, multi-stage generation, доступ к `editorial_7`.
- **Business** — full editorial workflow и premium routing.

UI не должен показывать `editorial_7` как доступный choice для `trial` и `starter`.

Если тариф не даёт доступ к preset или premium execution mode, бот должен явно объяснять:
- что именно недоступно;
- на каком плане это открывается;
- почему операция ограничена.

---

## 9. Enforcement rules for implementation

Следующие правила считаются зафиксированными для дальнейшей реализации:

1. `subscription_plan_code` — источник тарифной policy по умолчанию.
2. Plan -> service tier mapping:
   - `trial`, `starter` -> `economy`
   - `pro` -> `standard`
   - `business` -> `premium`
3. Plan -> execution mode mapping by default:
   - `trial`, `starter` -> `single_pass`
   - `pro`, `business` -> `multi_stage`
4. Plan -> preset availability:
   - `trial` -> only `starter_3`
   - `starter` -> `starter_3`, `balanced_5`
   - `pro`, `business` -> all presets
5. Default recommended preset:
   - `trial` -> `starter_3`
   - `starter` -> `balanced_5`
   - `pro` -> `balanced_5`
   - `business` -> `editorial_7`
6. Manual override через `client_account.settings` допустим только как explicit operator override и должен логироваться.
7. Даже при override нельзя silently выдавать premium routing тарифу, который его не оплачивает; это должно быть осознанным operator action.

---

## 10. Why this matrix is the product baseline

Эта матрица — правильный baseline, потому что она:
- связывает цену с реальным execution path;
- не обещает expensive agent behavior дешёвым тарифам;
- даёт заметимый апгрейд между `starter` -> `pro` -> `business`;
- делает `balanced_5` основным массовым preset, а `editorial_7` — осмысленным premium differentiator;
- упрощает дальнейшую реализацию quota enforcement, upgrade UX, billing logic и support explanations.

---

## 11. Final decision summary

Для Telegram Channel Factory v1 фиксируется:

- `trial` -> `starter_3` -> `economy` -> `single_pass`
- `starter` -> default `balanced_5` -> `economy` -> `single_pass`
- `pro` -> default `balanced_5` + доступ к `editorial_7` -> `standard` -> `multi_stage`
- `business` -> default `editorial_7` -> `premium` -> `multi_stage`

Коротко:

> дешёвые тарифы получают дешёвый execution path, платящие mid-tier клиенты — сильный balanced workflow, верхний тариф — полноценную редакционную multi-agent схему.
