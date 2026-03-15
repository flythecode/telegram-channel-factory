# Telegram Channel Factory — LLM Failover Policy v1

## Purpose

Этот документ фиксирует, как generation layer ведёт себя при недоступности основного LLM provider.

## Policy

Поддерживаются 3 режима через `LLM_FAILOVER_STRATEGY`:

- `disabled` — ошибка primary provider идёт как есть, без резервного пути
- `fallback-provider` — после исчерпания retry/circuit-breaker система делает один дополнительный вызов через `LLM_FALLBACK_PROVIDER` и optional `LLM_FALLBACK_MODEL`
- `graceful-degradation` — если primary provider недоступен и fallback не включён/не сработал, generation service возвращает безопасный degraded result и доменный слой использует локальный fallback input

## Graceful degradation behaviour

Когда включён degraded path:

- provider outage не валит весь generation flow
- `finish_reason` становится `provider_unavailable`
- в `generation_metadata.failover` пишется причина и outcome
- ideas/content-plan/rewrite/draft flows получают пустой LLM output и откатываются к локальному fallback (`brief`, текущий draft, seed text и т.д.)
- UI/оператор может отличить degraded result от нормальной генерации по `failover.outcome`

## Fallback provider rule

`fallback-provider` — это не бесконечная цепочка. Разрешён только один дополнительный provider hop после primary. Если fallback тоже падает, система переходит в `graceful-degradation`.

## Operational intent

MVP-цель: не допускать немого падения generation pipeline и не блокировать очередь при кратковременном outage основного provider.
