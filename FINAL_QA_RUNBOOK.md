# Telegram Channel Factory — Final QA Runbook

Этот документ — финальный ручной QA-прогон перед релизом.

Его задача:
- проверить продукт **глазами реального пользователя**
- подтвердить, что основной launch path работает связно
- не ограничиваться только unit/integration тестами

---

## 1. Goal of final QA

Перед релизом нужно подтвердить один главный тезис:

> новый пользователь может пройти путь от `/start` до управляемого канала с черновиком, публикацией и последующим редактированием

Если этот путь не проходит — релиз ещё не готов.

---

## 2. Recommended QA environment

Для финального ручного QA рекомендуется безопасный staging/demo-like режим:

```env
APP_ENV=staging
RUNTIME_MODE=demo
PUBLISHER_BACKEND=stub
```

Это позволяет:
- пройти продуктовый сценарий
- не стрелять в live Telegram публикациями
- проверить UX и связность flow

Если нужен live-proof запуск, его делать **отдельно** после safe QA.

---

## 3. What this QA must cover

Обязательный путь:
1. `/start`
2. setup / project creation
3. agent preset selection
4. channel connection
5. draft flow
6. publication / queue flow
7. edit-after-launch flow

Это и есть минимальный MVP acceptance path.

---

## 4. Before you start

Перед ручным QA:

### Runtime sanity
- `GET /health` = `200`
- API поднят
- worker поднят
- bot runtime не падает

### Environment sanity
- `.env` соответствует demo-safe режиму
- нет accidental live token leakage
- `PUBLISHER_BACKEND=stub`

### Confidence sanity
Рекомендуемый быстрый прогон:

```bash
python3 -m compileall app scripts
pytest -q tests/test_e2e_mvp_flow.py tests/test_channel_connection_flow.py tests/test_bot_navigation.py tests/test_worker.py
```

---

## 5. Main manual QA path

## Step 1 — open the bot

Действие:
- открыть Telegram-бота
- отправить `/start`

Ожидаемый результат:
- бот отвечает
- стартовый экран осмысленный
- из стартового экрана понятно, что это Telegram Channel Factory

Fail, если:
- бот не отвечает
- экран пустой / бессмысленный
- пользователь не понимает, что делать дальше

---

## Step 2 — inspect main menu

Действие:
- открыть главное меню
- проверить базовые entry points

Ожидаемый результат:
- есть путь к созданию канала
- есть `Мои каналы`
- есть `Помощь`
- есть `Как это работает`

Fail, если:
- не видно главных действий
- пользователь не понимает, куда идти для setup

---

## Step 3 — create project

Действие:
- создать проект канала

Ожидаемый результат:
- проект создаётся без ручного вмешательства разработчика
- проект виден как управляемая сущность

Fail, если:
- setup обрывается
- проект не создаётся
- flow требует скрытого ручного шага

---

## Step 4 — apply agent preset

Действие:
- выбрать preset команды агентов

Рекомендуемый preset:
- `starter_3`

Ожидаемый результат:
- preset применяется
- агентная команда становится предсказуемой

Fail, если:
- preset не применяется
- роли/состав выглядят случайными или сломанными

---

## Step 5 — connect channel

Действие:
- добавить канал к проекту
- выполнить connection flow
- проверить статус подключения

Ожидаемый результат:
- канал сохраняется
- connection check понятен
- happy path даёт `connected`
- неуспешная ветка читаемо объясняется

Fail, если:
- непонятно, как именно подключить канал
- connection state не проверяется
- статус подключения нельзя интерпретировать

---

## Step 6 — create content plan

Действие:
- запустить создание контент-плана

Ожидаемый результат:
- content plan создаётся
- у пользователя возникает ощущение следующего шага, а не тупика

Fail, если:
- plan не создаётся
- после plan user flow теряется

---

## Step 7 — create task and draft

Действие:
- получить задачу
- получить draft

Ожидаемый результат:
- chain `plan -> task -> draft` выглядит связной
- draft доступен для review/edit

Fail, если:
- нельзя дойти до draft
- draft есть технически, но flow его не показывает как рабочий объект

---

## Step 8 — edit and approve draft

Действие:
- отредактировать draft
- approve draft

Ожидаемый результат:
- edit меняет состояние draft
- approve переводит flow дальше к публикации

Fail, если:
- edit не сохраняется
- approve не работает
- draft/status transitions непонятны

---

## Step 9 — publication flow

Действие:
- отправить draft в publication flow
- предпочтительно показать queue branch

Рекомендуемый сценарий:
- поставить через `scheduled_for`
- получить `queued`

Ожидаемый результат:
- публикация создаётся
- у публикации понятный статус
- очередь выглядит управляемо

Fail, если:
- publication исчезает без статуса
- невозможно понять, queued она или нет
- flow кажется случайным/непрозрачным

---

## Step 10 — return later / edit after launch

Действие:
- вернуться к уже созданному каналу
- открыть канал позже
- изменить настройки
- изменить `publish_mode`
- выполнить regenerate content plan

Ожидаемый результат:
- post-setup editing реально работает
- продукт полезен после первичного создания

Fail, если:
- можно только создать, но нельзя нормально управлять позже
- reopen/edit flow выглядит сломанным

---

## 6. Manual QA checkpoints summary

Финальный QA считается успешным, если подтверждено:
- `/start` работает
- main menu понятен
- project setup работает
- agent preset работает
- channel connection работает
- content plan создаётся
- draft создаётся
- draft можно edit + approve
- publication queue работает
- later reopen + edit path работает

---

## 7. API-backed fallback QA path

Если полный ручной Telegram UI path ещё не закрывает весь сценарий, допускается полуручной QA через API-backed flow.

Рекомендуемый fallback path:
1. создать проект
2. применить `starter_3`
3. создать канал
4. отметить канал как connected
5. сделать `connection-check`
6. создать content plan
7. создать task
8. создать draft
9. edit draft
10. approve draft
11. queue publication
12. reopen channel later
13. change settings
14. regenerate content plan

Этот путь уже закреплён в e2e тестах репозитория.

---

## 8. Recommended commands before sign-off

### Code confidence

```bash
python3 -m compileall app scripts
```

### Flow confidence

```bash
pytest -q tests/test_e2e_mvp_flow.py tests/test_channel_connection_flow.py tests/test_bot_navigation.py tests/test_worker.py
```

### Optional broader confidence

```bash
make test
```

---

## 9. Release-blocking failures

Релиз блокируется, если происходит хотя бы одно из этого:

1. `/start` не даёт нормальный вход в продукт
2. setup flow нельзя пройти без разработчика
3. channel connection flow непонятен или нерабочий
4. нельзя дойти до draft
5. нельзя approve draft
6. queue/publication flow непрозрачен или разваливается
7. нельзя вернуться позже и изменить настройки
8. demo/staging run требует скрытой ручной магии

---

## 10. QA sign-off template

Перед переходом к релизу полезно зафиксировать:

- Date:
- Environment:
- Mode:
- QA runner:
- `/start` OK: yes/no
- Setup flow OK: yes/no
- Agent preset OK: yes/no
- Channel connection OK: yes/no
- Draft edit/approve OK: yes/no
- Publication queue OK: yes/no
- Return later / edit OK: yes/no
- Blocking issues:
- Final decision: pass / fail

---

## 11. Definition of done for final QA

Финальный QA считается закрытым, если:
- основной пользовательский путь проверен вручную или полуручно
- все ключевые checkpoints подтверждены
- нет launch-blocking failures
- результат зафиксирован в явном sign-off виде
