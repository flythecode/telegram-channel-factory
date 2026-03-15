# Telegram Channel Factory — Model Routing Strategy v1

## 1. Purpose

Этот документ фиксирует целевую стратегию model routing для нового LLM generation layer.

Задача routing policy:
- выбирать модель не «одну на всё», а по типу операции;
- удерживать себестоимость под контролем;
- дать предсказуемое качество для planning/draft workflows;
- отделить базовые тарифы от premium execution path;
- сделать policy versionable, testable и безопасной для multi-tenant SaaS.

---

## 2. Core decision

Routing в Telegram Channel Factory должен определяться **application policy**, а не конкретным endpoint или случайным выбором в коде.

Иначе говоря:

> operation -> routing tier -> provider/model profile

Минимальная единица решения — **generation operation**.

Базовые operation types:
- `ideas`
- `content_plan`
- `draft`
- `rewrite_draft`
- `regenerate_draft`
- `agent_stage`

---

## 3. Routing goals

Стратегия должна одновременно решать 4 задачи:

1. **Cost efficiency**
   - дешёвые операции не должны уходить на дорогие reasoning-модели;
   - массовые сценарии (`ideas`) должны быть максимально дешёвыми и быстрыми.

2. **Quality where it matters**
   - `content_plan` и `draft` требуют лучшего качества, чем простой список идей;
   - premium workflows должны получать заметно лучший output, а не только более дорогой вызов.

3. **Latency control**
   - Telegram UX не должен зависать из-за избыточно тяжёлых моделей там, где это не нужно.

4. **Predictability**
   - одна и та же операция внутри одного routing profile должна давать ожидаемый класс модели;
   - support/operator должны понимать, почему запрос пошёл в конкретную модель.

---

## 4. Routing layers

Routing policy состоит из 4 слоёв.

### 4.1 Operation layer

Сначала определяется тип операции:
- ideas
- planning
- writing
- rewrite
- agent-stage

### 4.2 Service tier layer

Далее выбирается сервисный tier:
- `economy`
- `standard`
- `premium`

По умолчанию:
- MVP/starter клиенты -> `economy`
- обычный платный план -> `standard`
- дорогие тарифы / hand-picked channels -> `premium`

### 4.3 Execution mode layer

После этого выбирается режим выполнения:
- `single_pass`
- `multi_stage`

Правило:
- `economy` и большая часть `standard` работают через `single_pass`
- `premium` может использовать `multi_stage`

### 4.4 Provider/model profile layer

Финальный шаг — выбрать нормализованный profile id, а уже он маппится на реальную provider/model пару.

Это нужно, чтобы в коде не были захардкожены сырые названия моделей.

Примеры profile ids:
- `fast_ideas`
- `planner_balanced`
- `writer_strong`
- `rewrite_fast`
- `premium_reasoning`
- `premium_writing`

---

## 5. Default routing matrix

## 5.1 Economy tier

### `ideas`
- Цель: быстро и дёшево получить 10–30 тем/углов
- Требование: latency и price важнее глубины
- Профиль: `fast_ideas`
- Класс модели: **cheap / fast chat model**

### `content_plan`
- Цель: собрать недельный/месячный план без сильного reasoning overhead
- Профиль: `planner_balanced`
- Класс модели: **mid-tier balanced model**

### `draft`
- Цель: рабочий первый черновик без премиального качества
- Профиль: `writer_balanced`
- Класс модели: **mid-tier writing-capable model**

### `rewrite_draft` / `regenerate_draft`
- Цель: быстрая переработка существующего текста
- Профиль: `rewrite_fast`
- Класс модели: **cheap-to-mid editing model**

### `agent_stage`
- В economy tier по умолчанию не нужен полноценный staged pipeline
- Поведение: сводить к `single_pass` или к урезанному internal stage mapping

---

## 5.2 Standard tier

### `ideas`
- Профиль: `ideas_balanced`
- Класс модели: **fast balanced model**
- Почему: чуть лучше разнообразие и релевантность, чем economy

### `content_plan`
- Профиль: `planner_strong`
- Класс модели: **strong reasoning/writing planning model**
- Почему: план — это уже структурная операция, где дешёвые модели чаще теряют связность

### `draft`
- Профиль: `writer_strong`
- Класс модели: **strong writing model**
- Почему: именно drafts — основной perceived value для клиента

### `rewrite_draft`
- Профиль: `rewrite_balanced`
- Класс модели: **balanced editor model**
- Почему: rewrite должен быть дешевле нового draft, но не деградировать по качеству

### `regenerate_draft`
- Профиль: `writer_strong`
- Класс модели: **тот же writing profile, что и draft**
- Почему: regenerate — это по сути новая генерация, а не поверхностный edit

### `agent_stage`
- Профиль: зависит от stage role:
  - strategist -> `planner_strong`
  - researcher -> `research_balanced`
  - writer -> `writer_strong`
  - editor -> `rewrite_balanced`

---

## 5.3 Premium tier

Premium не должен означать просто «тот же single-pass, но дороже».

Он должен включать:
- более сильные модели;
- optional multi-stage execution;
- более качественный planning;
- более сильный writer/editor path;
- возможность поднять reasoning budget для сложных каналов.

### `ideas`
- Профиль: `ideas_premium`
- Класс модели: **high-quality balanced model**
- Использовать только если канал реально monetized/high-value

### `content_plan`
- Профиль: `planner_premium`
- Класс модели: **high-end planning/reasoning model**

### `draft`
- Профиль: `writer_premium`
- Класс модели: **high-end writing model**

### `rewrite_draft`
- Профиль: `editor_premium`
- Класс модели: **high-end editor model**

### `regenerate_draft`
- Профиль: `writer_premium`

### `agent_stage`
- Полноценный `multi_stage`:
  - strategist -> `premium_reasoning`
  - researcher -> `premium_research`
  - writer -> `premium_writing`
  - editor -> `premium_editor`

---

## 6. Role-based mapping for multi-stage workflows

Если generation mode = `multi_stage`, routing должен смотреть не только на operation, но и на роль stage.

### Recommended mapping

- **Strategist**
  - задача: angle, positioning, rubric logic, sequencing
  - класс модели: reasoning/planning heavy

- **Researcher**
  - задача: собрать тезисы, риски, факты, аргументы
  - класс модели: balanced analysis model

- **Writer**
  - задача: превратить материалы в готовый Telegram post/draft
  - класс модели: strong writing model

- **Editor**
  - задача: сократить, упростить, выровнять tone, усилить CTA
  - класс модели: strong editing/rewrite model

- **Fact-checker / Reach Optimizer**
  - задача: optional premium stages
  - класс модели: balanced verifier / optimization model

### Important rule

Нельзя слать все stage roles в одну и ту же модель только ради упрощения, если premium tier обещает качественную агентную дифференциацию.

---

## 7. Provider-agnostic model classes

Чтобы policy не зависела от бренда модели, фиксируем не конкретные имена, а классы:

- `cheap_fast`
- `balanced_fast`
- `balanced_planner`
- `strong_writer`
- `strong_reasoner`
- `strong_editor`
- `premium_reasoner`
- `premium_writer`
- `premium_editor`

Примеры соответствия:
- OpenAI / Anthropic / Gemini / OpenRouter могут давать разные реальные model ids,
- но routing policy работает через эти классы и profile ids.

Это позволит:
- менять vendor без переписывания продуктовой логики;
- тестировать policy отдельно от provider adapter;
- делать gradual vendor migration.

---

## 8. Initial recommended mapping for first production-ready iteration

Для первой production-ready версии стоит использовать максимально простой набор профилей.

### Baseline profile set

- `fast_ideas`
- `planner_balanced`
- `writer_balanced`
- `writer_strong`
- `rewrite_fast`
- `rewrite_balanced`
- `planner_premium`
- `writer_premium`
- `editor_premium`

### Why this is the right MVP+1 compromise

Потому что он:
- уже даёт routing по операциям;
- не взрывает поддержку десятками моделей;
- позволяет считать юнит-экономику по понятным корзинам;
- оставляет место для future failover/fallback.

---

## 9. Recommended config surface

Конфиг должен задавать не только общий default model, но и operation/routing profiles.

Минимальный следующий слой конфигурации:
- `LLM_ROUTING_STRATEGY=by-operation`
- `LLM_PROFILE_FAST_IDEAS`
- `LLM_PROFILE_PLANNER_BALANCED`
- `LLM_PROFILE_WRITER_BALANCED`
- `LLM_PROFILE_WRITER_STRONG`
- `LLM_PROFILE_REWRITE_FAST`
- `LLM_PROFILE_REWRITE_BALANCED`
- `LLM_PROFILE_PLANNER_PREMIUM`
- `LLM_PROFILE_WRITER_PREMIUM`
- `LLM_PROFILE_EDITOR_PREMIUM`

Опционально потом:
- `LLM_PROFILE_PREMIUM_REASONER`
- `LLM_PROFILE_PREMIUM_RESEARCH`
- `LLM_PROFILE_FALLBACK_FAST`
- `LLM_PROFILE_FALLBACK_STRONG`

### Rule

В проде код должен хранить и логировать **profile id + provider + model**, а не только сырой model id.

---

## 10. Cost policy implications

Routing policy напрямую связана с экономикой.

### Cost rules

1. `ideas` не должны использовать premium class по умолчанию.
2. `rewrite_draft` почти всегда должно быть дешевле, чем новый `draft`.
3. `content_plan` может быть дороже `ideas`, но не должен стоить как premium multi-stage draft.
4. premium multi-stage должен включаться только там, где тариф или LTV это оправдывают.
5. при перегреве бюджета канал должен деградировать по policy:
   - premium -> standard
   - standard -> economy
   - при достижении hard limits generation останавливается.

---

## 11. Observability requirements

Каждый generation event обязан сохранять:
- `routing_strategy`
- `routing_profile`
- `service_tier`
- `execution_mode`
- `provider`
- `model`

Иначе потом невозможно будет:
- анализировать unit economics;
- понять, почему стоимость выросла;
- сравнивать качество между policy versions.

---

## 12. Testing requirements

Routing policy должна тестироваться отдельно от LLM provider.

Нужны тесты минимум на:
- operation -> profile mapping
- tier overrides
- premium multi-stage role mapping
- fallback behavior
- budget degradation rules
- deterministic routing for the same scoped input

---

## 13. Final decision summary

Для Telegram Channel Factory фиксируется следующая стратегия:

- `ideas` -> fast/cheap model class
- `content_plan` -> stronger planning model
- `draft` -> strong writing model
- `rewrite_draft` -> cheaper editor/rewrite model
- `regenerate_draft` -> same or near-same class as draft generation
- `premium workflows` -> multi-stage routing with role-specific stronger models

Коротко:

> cheap where speed matters, strong where output quality matters, premium only where unit economics justify it.
