# Economics reconciliation

| client | plan | events | total_tokens | actual_total_cost_usd | projected_monthly_fee_usd | included_cogs_usd | projected_margin_usd | verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PILOT_CLIENT_01 | trial | 3 | 1100 | 0.001100 | 0.00 | 11.040000 | -11.04 | pass |
| PILOT_CLIENT_02 | business | 4 | 1350 | 0.001350 | 123.90 | 37.170000 | 86.73 | pass |

## Findings

- internal pilot выполнен на двух internal clients: trial и business;
- actual generation costs остались ниже projected included COGS выбранных тарифов;
- usage/cost attribution корректно разделены по client/project/channel/operation;
- generation reliability в рамках pilot: все обязательные сценарии завершились успешно.

## Backlog for item 119

- проверить, нужен ли отдельный operator-facing report с более явным `expected vs actual at current sample size` для monthly scaling;
- решить, хотим ли мы в pilot пакете ещё и automatic margin delta summary по каждому operation.

Overall verdict: pilot_pass
