# Telegram Channel Factory — LLM Cost Operator Runbook

Этот runbook нужен оператору, который поддерживает generation pipeline в production/staging и должен быстро понять:
- почему выросли LLM-расходы;
- какой клиент/канал/операция сожгли бюджет;
- сработали ли quota / budget guardrails;
- это проблема одного provider'а, конкретного tenant'а или всей очереди;
- когда достаточно локальной стабилизации, а когда нужна эскалация разработчику.

---

## 1. Что считается нормой

В нормальном состоянии generation pipeline должен вести себя так:
- generation events пишутся в `llm_generation_events`;
- usage/cost attribution привязаны к `client_id`, `project_id`, `channel_id`, `operation_type`, `provider`, `model`;
- cost dashboard и admin endpoints дают согласованные цифры;
- soft-limit guardrails предупреждают о приближении к лимитам;
- hard-stop guardrails блокируют новые generation calls после превышения бюджета/квоты;
- provider retries/failover/graceful degradation видны в structured logs и observability snapshot;
- tenant isolation сохраняется: один клиент не влияет на attribution/prompts/state другого.

Если что-то из этого не подтверждается фактами — это уже инцидент, а не «странное поведение».

---

## 2. Где смотреть правду по LLM economics

Главные источники истины:
- `README.md` — общая архитектура generation pipeline, guardrails, pricing, observability;
- `MODEL_ROUTING_STRATEGY_V1.md` — какие модели ожидаются для ideas / content plan / drafts / rewrite;
- `LLM_FAILOVER_POLICY_V1.md` — что считается нормальной деградацией/failover;
- `/api/v1/users/me/client-account/cost-dashboard` — клиентский cost/usage dashboard;
- `/api/v1/admin/generation/history` — сырая история generation events;
- `/api/v1/admin/generation/usage` — агрегаты usage по client/channel/operation;
- `/api/v1/admin/generation/cost-breakdown` — агрегаты cost по client/channel/operation/model;
- CSV export endpoints — когда нужно сверить цифры вне продукта;
- structured logs generation pipeline (`generation_observability.py`) — retries, provider failures, failover, queue snapshots, hard-stop/block reasons.

Если dashboard и raw history расходятся, источником истины считается raw history + logs.

---

## 3. Быстрый triage: 5 вопросов до любых действий

Перед любым restart или ручным вмешательством ответь на 5 вопросов:

1. **Что именно сломалось?**
   - рост cost;
   - generation stopped;
   - массовые provider errors;
   - один клиент жалуется на block/лимит;
   - usage attribution выглядит неверным.

2. **Это scope одного tenant'а или всей системы?**
   - один `client_id` / `project_id` / `channel_id`;
   - один `operation_type`;
   - один provider/model;
   - или глобально весь pipeline.

3. **Что изменилось перед инцидентом?**
   - новый deploy;
   - смена routing profile/model;
   - новые pricing/guardrails settings;
   - provider outage/429 spike;
   - всплеск generation jobs у конкретного клиента.

4. **Это нормальная защитная реакция или реальная поломка?**
   - soft-limit warning — не авария;
   - hard-stop после exceeded budget — тоже не авария, если лимиты настроены корректно;
   - failover/graceful degradation — не авария, если system продолжает работать в policy;
   - а вот неверный cost attribution, бесконечные retries или отсутствие hard-stop при exceeded budget — уже инцидент.

5. **Есть ли риск продолжения ущерба?**
   - расходы продолжают расти;
   - очередь не останавливается;
   - provider 429/5xx множатся;
   - один tenant генерирует бесконтрольный поток задач.

Если риск продолжается — сначала локализуй blast radius, потом разбирайся глубже.

---

## 4. Ежедневный операторский чек по LLM pipeline

Раз в день и после каждого релиза:

1. Проверить `/health` и состояние `api` / `worker` / `bot`.
2. Посмотреть, нет ли резкого скачка generation failures / retries / failover events.
3. Сверить top clients/channels по cost и usage за текущий период.
4. Проверить, что hard-stop guardrails реально срабатывают по exceeded limits, а не игнорируются.
5. Проверить, что нет аномального роста у одного `operation_type` (`rewrite`, `regenerate`, `generate_content_plan`, `create_draft`).
6. Если был deploy в generation layer — прогнать smoke не только по UX, но и по economics/guardrails.

Минимальный runtime check:

```bash
curl http://127.0.0.1:8000/health
docker compose ps
docker compose logs --tail=200 api worker
```

---

## 5. Базовая карта симптом → куда смотреть

### Симптом A — расходы резко выросли
Смотри:
- `/api/v1/admin/generation/cost-breakdown`
- `/api/v1/admin/generation/usage`
- logs на retries/failover/repeated generation

Проверь:
- какой `client_id` / `channel_id` / `operation_type` дал рост;
- нет ли аномального числа `regenerate` / `rewrite`;
- не переключился ли routing на более дорогую model profile;
- не было ли provider failover на более дорогой запасной провайдер;
- не пошёл ли worker в повторный цикл из-за retryable ошибки.

### Симптом B — клиент жалуется, что generation заблокирован
Смотри:
- generation metadata `guardrails`;
- API response с blocking reason;
- `/api/v1/admin/generation/usage` и `/cost-breakdown` по этому клиенту.

Проверь:
- soft-limit это или hard-stop;
- какой именно лимит exceeded: budget, generations, tokens, daily/monthly, operation-specific;
- не устарели ли pricing/guardrails settings;
- не бьётся ли клиент об лимит из-за runaway loop на своей стороне.

### Симптом C — массовые provider errors / деградация качества
Смотри:
- structured logs по provider retries/failover/graceful degradation;
- `LLM_FAILOVER_POLICY_V1.md`;
- history/cost breakdown по affected provider/model.

Проверь:
- это 429 / timeout / 5xx или non-retryable 4xx;
- переключился ли pipeline на fallback provider;
- не выросла ли стоимость после failover;
- не появились ли длинные latency spikes.

### Симптом D — usage/cost attribution выглядит неверным
Смотри:
- `/api/v1/admin/generation/history`
- `/api/v1/admin/generation/usage`
- `llm_generation_events`

Проверь:
- заполнены ли `client_id`, `project_id`, `channel_id`, `operation_type`;
- нет ли событий без нужного attribution context;
- не сработал ли channel attribution fallback неожиданным образом;
- относится ли проблема к одному tenant'у или к нескольким.

Если есть намёк на cross-tenant contamination — это немедленная эскалация.

---

## 6. Ручной разбор cost anomaly

Используй такой порядок, чтобы не прыгать между гипотезами:

### Шаг 1 — локализуй всплеск
Определи:
- период начала;
- affected client/channel/project;
- affected operation types;
- affected provider/model;
- выросли tokens, количество вызовов или оба показателя.

### Шаг 2 — отдели объём от цены
Сценарии:
- **выросло число вызовов** → ищи runaway retries, user loops, queue burst, массовые regenerate/rewrite;
- **выросла цена за вызов** → ищи routing change, failover на дорогую model, смену тарифного execution mode;
- **выросло и то и другое** → вероятен составной инцидент (burst + дорогой fallback).

### Шаг 3 — проверь защиту
Проверь, должны ли были сработать:
- soft-limit warnings;
- hard-stop;
- provider retry cap;
- circuit breaker;
- queue concurrency controls.

Если защита должна была остановить ущерб и не остановила — фиксируй это как policy breach.

### Шаг 4 — проверь user/business причину
Иногда это не баг, а реальное использование:
- новый клиент активно генерирует контент;
- агентная команда переключилась в multi-stage на premium plan;
- был ручной массовый прогон draft/rewrite;
- оператор/пользователь сознательно тестировал staging/live flow.

### Шаг 5 — зафиксируй вывод
Итог anomaly review должен ответить на 4 вещи:
- root cause;
- blast radius;
- продолжает ли проблема наносить cost damage сейчас;
- что нужно: restart, config rollback, временный stop, или dev escalation.

---

## 7. Что делать при provider degradation

### Нормальная деградация
Считается нормальной, если:
- primary provider временно отдаёт 429/5xx/timeout;
- retry policy с bounded backoff отрабатывает штатно;
- circuit breaker открывается после серии transient failures;
- pipeline уходит в failover/graceful degradation по policy;
- user-facing flow остаётся доступным, пусть и с худшим качеством/дороже.

### Ненормальная деградация
Это уже инцидент, если:
- retries бесконечно повторяются;
- failover резко увеличил cost без контроля;
- fallback provider тоже падает, а queue продолжает бесконтрольно расти;
- non-retryable 4xx трактуются как retryable;
- circuit breaker не открывается, хотя provider явно мёртв.

### Операторское действие
1. Подтверди тип ошибки по логам.
2. Подтверди, сработал ли failover/graceful degradation.
3. Сверь рост стоимости после failover.
4. Если fallback рабочий и ущерб приемлем — мониторь.
5. Если стоимость/ошибки продолжают расти — локализуй affected traffic и эскалируй.

---

## 8. Что делать при exceeded limits / hard-stop

Hard-stop — это защитный механизм, а не баг сам по себе.

Оператор должен определить:
- какой именно scope заблокирован: client или channel;
- какой window exceeded: billing period, daily, monthly;
- какая метрика exceeded: USD, generation count, tokens, operation-specific cap;
- есть ли у клиента основания для лимита (тариф, тестовый аккаунт, ручное ограничение).

### Если hard-stop ожидаемый
Действие:
- подтвердить blocking reason;
- сообщить фактологию (какой лимит достигнут);
- не «лечить» это restart'ом.

### Если hard-stop выглядит ложным
Проверь:
- корректность pricing/guardrails settings;
- дублированные generation events;
- ошибочное attribution на другой channel/client;
- временное окно подсчёта (daily/monthly/billing period).

Если есть подозрение на неверный подсчёт — эскалируй как cost-accounting incident.

---

## 9. Когда можно делать restart, а когда нельзя

### Можно
- worker завис после transient provider outage;
- после fix/rollback нужно безопасно восстановить обработку;
- queue перестала двигаться при уже локализованной причине.

### Нельзя считать restart решением
- при неверном usage attribution;
- при runaway cost anomaly без понимания источника;
- при hard-stop/blocking policy mismatch;
- при cross-tenant подозрении;
- при скачке cost после routing/failover change.

Базовый безопасный порядок:

```bash
docker compose ps
docker compose logs --tail=200 api worker
docker compose restart api worker
curl http://127.0.0.1:8000/health
```

После restart обязательно перепроверь, исчезла ли первопричина, а не только симптом.

---

## 10. Немедленная эскалация разработчику

Эскалируй сразу, если есть хоть одно из условий:
- признаки cross-tenant prompt/state/usage contamination;
- cost attribution нельзя объяснить raw events;
- hard-stop не сработал при exceeded budget/quota;
- failover policy ведёт к неконтролируемому росту стоимости;
- provider 4xx ошибочно ретраятся как transient;
- queue продолжает генерировать расходы после supposed stop;
- расход и usage нельзя сверить между dashboard, admin API и raw history.

В эскалации должны быть:
- время начала инцидента;
- environment;
- affected client/project/channel;
- affected provider/model/operation;
- request ids / entity ids;
- выдержка из logs;
- что уже проверили;
- продолжается ли cost damage прямо сейчас.

---

## 11. Минимальный шаблон LLM cost incident report

```md
# LLM Cost Incident
- Time detected:
- Environment:
- Detected by:
- Affected client/project/channel:
- Affected operation/model/provider:
- Symptom:
- Is spend still increasing right now:
- Expected guardrail/policy:
- Actual observed behavior:
- Evidence from history/usage/cost-breakdown/logs:
- Immediate containment action:
- Escalation needed: yes/no
- Proposed next step:
```

---

## 12. Definition of done для оператора

Инцидент по LLM economics считается закрытым, если:
- локализован scope проблемы;
- понятно, это bug, expected guardrail, provider issue или user-driven spike;
- подтверждено, продолжает ли система нести лишние расходы;
- если нужен restart/rollback — он уже подтверждён фактами;
- есть короткий письменный отчёт с evidence, а не догадки.
