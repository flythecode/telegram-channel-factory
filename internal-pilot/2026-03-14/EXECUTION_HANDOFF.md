# Execution handoff — backlog item 118

## Current truth

Backlog item 118 ещё не закрыт: в workspace нет живых pilot-клиентов и нет real-world economics evidence.

## Ready right now

- `../../INTERNAL_PILOT_COST_VALIDATION_PLAN.md`
- `./PILOT_CLIENT_01.md`
- `./ECONOMICS_RECONCILIATION.md`
- существующие cost/usage/admin endpoints и CSV exports
- `../../LLM_COST_OPERATOR_RUNBOOK.md`
- `../../scripts/collect_internal_pilot_evidence.py` — one-shot сборщик raw JSON/CSV evidence в `internal-pilot/YYYY-MM-DD/raw/`

## Exact run order once pilot clients are available

1. Выбрать 1–3 internal pilot клиента и их тарифы.
2. Скопировать `PILOT_CLIENT_01.md` в дополнительные client files по мере необходимости.
3. Прогнать реальные generation сценарии на каждом клиенте.
4. Снять evidence из cost dashboard, admin usage, admin cost breakdown и при необходимости CSV export.
5. Заполнить client files и `ECONOMICS_RECONCILIATION.md`.
6. Свести итог в `INTERNAL_PILOT_REPORT_YYYY-MM-DD.md`.
7. Только после этого отметить в `MEMORY.md` пункт 118 как `[x]`.

## Concrete evidence collection commands

Подставить свои значения в переменные и сохранять raw evidence рядом с markdown-файлами:

```bash
cd /data/.openclaw/workspace/telegram-channel-factory
export API_BASE="https://<host-or-staging-base-url>"
export ADMIN_TOKEN="<admin-bearer-token>"
export CLIENT_TOKEN="<pilot-client-bearer-token>"
export CHANNEL_ID="<pilot-channel-id>"
export PILOT_DATE="$(date -u +%F)"
python3 scripts/collect_internal_pilot_evidence.py
```

Скрипт создаст `internal-pilot/$PILOT_DATE/raw/`, сохранит все JSON/CSV evidence, а также положит `manifest.csv` и `collection-summary.json`.

Если нужен полностью ручной fallback без Python helper, можно использовать те же curl-вызовы напрямую:

```bash
cd /data/.openclaw/workspace/telegram-channel-factory
export API_BASE="https://<host-or-staging-base-url>"
export ADMIN_TOKEN="<admin-bearer-token>"
export CLIENT_TOKEN="<pilot-client-bearer-token>"
export CHANNEL_ID="<pilot-channel-id>"
export TODAY="$(date -u +%F)"
mkdir -p "internal-pilot/$TODAY/raw"

curl -fsS "$API_BASE/api/v1/users/me/client-account/cost-dashboard" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  > "internal-pilot/$TODAY/raw/client-cost-dashboard.json"

curl -fsS "$API_BASE/api/v1/users/me/client-account/pricing" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  > "internal-pilot/$TODAY/raw/client-pricing.json"

curl -fsS "$API_BASE/api/v1/users/me/client-account/cost-dashboard/export" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  > "internal-pilot/$TODAY/raw/client-cost-dashboard-report.csv"

curl -fsS "$API_BASE/api/v1/admin/generation/history?channel_id=$CHANNEL_ID&limit=200" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  > "internal-pilot/$TODAY/raw/admin-generation-history.json"

curl -fsS "$API_BASE/api/v1/admin/generation/usage?channel_id=$CHANNEL_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  > "internal-pilot/$TODAY/raw/admin-generation-usage.json"

curl -fsS "$API_BASE/api/v1/admin/generation/cost-breakdown?channel_id=$CHANNEL_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  > "internal-pilot/$TODAY/raw/admin-generation-cost-breakdown.json"

curl -fsS "$API_BASE/api/v1/admin/generation/usage/export?channel_id=$CHANNEL_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  > "internal-pilot/$TODAY/raw/admin-generation-usage.csv"

curl -fsS "$API_BASE/api/v1/admin/generation/cost-breakdown/export?channel_id=$CHANNEL_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  > "internal-pilot/$TODAY/raw/admin-generation-cost-breakdown.csv"
```

## Operator checklist before calling item 118 done

- есть минимум один живой pilot-клиент с реальными generation events
- заполнен минимум один `PILOT_CLIENT_0X.md`
- заполнен `ECONOMICS_RECONCILIATION.md`
- raw JSON/CSV evidence сохранён в `internal-pilot/YYYY-MM-DD/raw/`
- в `INTERNAL_PILOT_REPORT_YYYY-MM-DD.md` есть честный verdict: `pass`, `pass_with_fixes` или `blocked`
- если есть проблемы — они явно превращены в item 119

## External action required

Нужны реальные internal pilot клиенты или явное разрешение Mr Fly на их выбор/контакт и запуск pilot-сессий.
