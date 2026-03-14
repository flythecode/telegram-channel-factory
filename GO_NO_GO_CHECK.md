# Telegram Channel Factory — MVP Go / No-Go Check

Этот документ фиксирует **правило принятия решения GO / NO-GO**.

Важно:
- `GO_NO_GO_CHECK.md` задаёт сами правила решения
- `RELEASE_CHECKLIST.md` задаёт обязательный операционный процесс перед rollout
- `release_records/YYYY-MM-DD-<release-marker>.md` — место, где фиксируется решение по конкретному релизу

Цель документа:
- не гадать “ну вроде уже можно”
- а явно ответить, готов ли MVP по своему собственному scope

---

## 1. Decision rule

Главный вопрос из launch scope:

> Может ли новый пользователь без разработчика создать, подключить, настроить, запустить и потом изменить свой Telegram-канал через бота?

Если ответ `да` — это `GO`.
Если ответ `нет` — это `NO-GO`.

Но для честного ответа ниже фиксируется состояние по блокам.

---

## 2. Current release marker

- Release marker: `0.1.0-mvp`
- Version file: `VERSION`
- Package version: `0.1.0`

---

## 3. Scope check by launch areas

## A. Telegram-first product shell

### Required
- Telegram bot runtime
- `/start`
- главное меню
- onboarding/help baseline

### Current status
- **PARTIALLY READY**

### What is confirmed
- bot runtime entrypoint есть
- `/start` handler есть
- main/help/how-it-works shell есть
- bot setup doc есть
- bot navigation tests есть

### Remaining caution
- полный живой пользовательский Telegram UI проход ещё должен быть подтверждён staging/manual run’ом, а не только кодом и тестами

### Decision
- **условно go**, но требует финального staging подтверждения

---

## B. Setup flow

### Required
- project creation wizard
- summary before create
- preset selection 3/5/7
- channel connection flow
- first-run activation behavior

### Current status
- **MOSTLY READY**

### What is confirmed
- project creation path есть
- presets 3/5/7 зафиксированы
- channel connection flow задокументирован и покрыт тестами
- return-later/edit path уже закреплён

### Remaining caution
- full wizard UX нужно подтвердить реальным staging run, особенно как пользователь воспринимает шаги без помощи разработчика

### Decision
- **go for staging validation**, не финальный unconditional go

---

## C. Channel management after setup

### Required
- `Мои каналы`
- channel dashboard
- настройки канала
- агенты
- контент-план
- черновики
- публикации
- режим работы

### Current status
- **FOUNDATION READY / UX VALIDATION STILL NEEDED**

### What is confirmed
- базовые channel screens и dashboard есть
- reopen flow добавлен
- settings update path есть
- mode update path есть

### Remaining caution
- нужно ещё один раз пройти это как человек в staging/demo, а не только как API/tests

### Decision
- **go for staging validation**

---

## D. Backend product core

### Required
- User
- Workspace
- Project ownership
- config/editability
- agent team settings
- publication pipeline

### Current status
- **READY**

### What is confirmed
- сущности и ownership foundation есть
- editable config layer есть
- agent team presets/settings есть
- publication pipeline есть
- audit/config versioning/supporting entities есть
- pytest baseline проходит

### Decision
- **GO**

---

## E. Content lifecycle

### Required
- content plan creation
- task creation/management
- draft generation
- approve/reject draft
- publication queue
- Telegram publication path

### Current status
- **READY FOR MVP**

### What is confirmed
- e2e flow закреплён
- `draft -> edit -> approve -> queue` закреплён
- `return later -> open channel -> change settings -> regenerate` закреплён
- immediate/scheduled publication branch есть
- Telegram publisher path есть
- retry/error handling baseline есть

### Remaining caution
- финальный live Telegram proof лучше прогонять отдельно от safe staging/demo

### Decision
- **GO**

---

## F. Core operation modes

### Required
- manual
- semi-auto
- auto

### Current status
- **READY AT MVP LEVEL**

### What is confirmed
- режимы описаны
- operation mode API есть
- environment/runtime mode docs есть

### Remaining caution
- это MVP-ready, не production-perfect behavior matrix

### Decision
- **GO**

---

## G. Minimum reliability baseline

### Required
- deterministic test env
- working pytest baseline
- basic error handling
- worker queue stability baseline
- reproducible local/dev run path

### Current status
- **READY**

### What is confirmed
- deterministic test env есть
- pytest baseline зелёный
- retry/backoff/error handling baseline есть
- worker batch hardening есть
- observability baseline есть
- reproducible local/compose path есть
- release package и smoke docs есть

### Decision
- **GO**

---

## 4. Launch blockers review

### Blocker 1 — user cannot pass setup flow without developer
- **Not fully disproven yet**
- reason: нужен финальный staging/manual pass

### Blocker 2 — bot cannot stably open main screens
- **Mostly disproven by tests**
- still needs staging/manual pass

### Blocker 3 — channel cannot be connected or checked
- **Disproven for MVP baseline**

### Blocker 4 — agent team is not assembled predictably
- **Disproven for MVP baseline**

### Blocker 5 — cannot get working draft
- **Disproven by pipeline/e2e tests**

### Blocker 6 — cannot approve/reject draft
- **Disproven**

### Blocker 7 — publication queue / Telegram path broken
- **Mostly disproven**
- safe/demo queue path confirmed
- live should still be validated carefully in controlled run

### Blocker 8 — user cannot return later and edit settings
- **Disproven by dedicated scenario/test**

### Blocker 9 — tests and dev path unstable
- **Disproven**

### Blocker 10 — release cannot be raised reproducibly
- **Mostly disproven**
- release package/docs/compose path prepared
- staging release run is the final confirmation

---

## 5. Honest current verdict

### Strict verdict right now
- **GO FOR STAGING RELEASE**

### Not yet the verdict
- не “full unconditional live release without further check”

Почему именно так:
- backend, pipeline, queue, retries, docs, release packaging уже собраны на MVP уровне
- но по-честному финальный ответ на вопрос “новый пользователь без разработчика проходит весь путь?” должен быть подтверждён ещё staging run’ом из пункта 84

То есть:
- **для staging/demo выпуска — GO**
- **для live launch — only after staging confirmation**

---

## 6. What would make this NO-GO

Решение нужно перевести в `NO-GO`, если на staging run выяснится хотя бы одно:
- `/start` не даёт внятный вход в продукт
- setup flow рвётся
- channel connection непонятен
- нельзя пройти до draft/publication
- return-later/edit flow ломается
- demo requires hidden manual fixes
- release/deploy path требует нестабильной магии

---

## 7. How this becomes an operational decision

Перед любым staging/live rollout оператор обязан:
1. создать конкретный `release_records/YYYY-MM-DD-<release-marker>.md`
2. пройти `RELEASE_CHECKLIST.md`
3. приложить evidence из `FINAL_QA_RUNBOOK.md` или staging run
4. письменно зафиксировать итоговый `GO` или `NO-GO`

Без release record решение считается **непринятым**, даже если команда «и так уверена».

## 8. Final recommendation

### Recommendation
- использовать этот документ как policy для решения
- использовать `RELEASE_CHECKLIST.md` как обязательный execution gate
- использовать `release_records/` как журнал реальных решений

### If staging passes
- решение можно повышать до более уверенного **GO**

### If staging fails
- вернуть статус в **NO-GO** до исправлений
