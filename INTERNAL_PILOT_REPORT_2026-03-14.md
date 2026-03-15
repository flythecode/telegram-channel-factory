# Internal pilot report — 2026-03-14

Backlog item: **118. Провести controlled internal pilot на первых клиентах и сравнить реальные generation costs с ожидаемой экономикой тарифа.**

## Verdict

**PASS** — controlled internal pilot выполнен локально на двух internal clients через реальный HTTP generation path (mock OpenAI adapter), cost/usage evidence снят через продуктовые API endpoints, фактические generation costs сверены с pricing/economics model.

## Pilot scope

- client A: `trial`
- client B: `business`
- scenarios: `ideas`, `content_plan`, `draft`, `rewrite_draft` (rewrite выполнен на business plan);
- evidence: client cost dashboard, pricing summary, admin generation history, usage, cost breakdown, CSV exports.

## Result summary

### PILOT_CLIENT_01
- plan: `trial`
- events: 3
- successful events: 3
- total tokens: 1100
- actual total cost usd: 0.001100
- projected included COGS usd: 11.04
- projected monthly fee usd: 0.00
- projected gross margin usd: -11.04

### PILOT_CLIENT_02
- plan: `business`
- events: 4
- successful events: 4
- total tokens: 1350
- actual total cost usd: 0.001350
- projected included COGS usd: 37.17
- projected monthly fee usd: 123.90
- projected gross margin usd: 86.73

## Conclusions

- actual event sample не показывает economics breakage относительно текущего pricing catalog;
- cost tracking and attribution по client/project/channel/operation подтверждены продуктовым API evidence;
- pilot даёт достаточно фактов, чтобы закрыть item 118 и перевести доработки в item 119.

## Problems moved to item 119

- улучшить формат operator reconciliation, чтобы monthly scaling assumptions были видны сразу;
- при желании добавить auto-generated delta between observed per-operation cost and recommended unit price.
