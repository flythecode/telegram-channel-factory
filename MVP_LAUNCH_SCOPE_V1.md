# Telegram Channel Factory — MVP Launch Scope v1

## 1. Purpose

Этот документ фиксирует **жёсткий scope первого запуска MVP**, чтобы разработка не расползалась по вторичным фичам и чтобы любое решение можно было проверять вопросом: **это нужно для первого живого запуска или нет?**

---

## 2. Launch definition

MVP launch считается достигнутым, когда пользователь может пройти следующий путь без ручной помощи разработчика:

1. открыть Telegram-бота
2. нажать `/start`
3. создать проект канала через wizard
4. выбрать команду из 3 / 5 / 7 агентов
5. подключить существующий Telegram-канал
6. запустить первый контентный цикл
7. получить контент-план / задачи / черновики
8. одобрить или отклонить черновик
9. поставить пост в очередь или опубликовать
10. вернуться позже и изменить настройки канала / агентов / режима работы

Если этот путь стабильно работает — MVP можно считать готовым к запуску.

---

## 3. Hard in-scope for launch

### A. Telegram-first product shell
В первый запуск обязательно входят:
- Telegram bot runtime
- `/start`
- главное меню
- onboarding/help базового уровня

### B. Setup flow
Обязательно входят:
- project creation wizard
- summary before create
- preset selection 3 / 5 / 7
- channel connection flow
- first-run activation screen

### C. Channel management after setup
Обязательно входят:
- `Мои каналы`
- channel dashboard
- `Настройки канала`
- `Агенты`
- `Контент-план`
- `Черновики`
- `Публикации`
- `Режим работы`

### D. Backend product core
Обязательно входят:
- `User`
- `Workspace`
- ownership in `Project`
- strategy/config fields in project model
- editable config behavior
- agent team settings
- publication pipeline support

### E. Content lifecycle
Обязательно входят:
- content plan creation
- task creation/management
- draft generation
- approve / reject draft
- publication queue
- Telegram publication path

### F. Core operation modes
Обязательно входят:
- manual
- semi-auto
- auto

### G. Minimum reliability baseline
Обязательно входят:
- deterministic test env
- working pytest baseline
- basic error handling
- worker queue stability baseline
- reproducible local/dev run path

---

## 4. Launch blockers

Если любой из пунктов ниже не готов, запуск считается заблокированным:

1. Пользователь не может самостоятельно пройти setup flow.
2. Бот не может стабильно открыть главное меню и основные экраны.
3. Канал нельзя нормально подключить или проверить права бота.
4. Агентная команда не собирается в предсказуемую конфигурацию.
5. Нельзя получить рабочий draft через pipeline.
6. Нельзя approve/reject draft в продуктовой логике.
7. Публикация не проходит через очередь или Telegram send path.
8. Пользователь не может вернуться позже и изменить настройки.
9. Тесты и dev run path нестабильны.
10. Релиз невозможно воспроизводимо поднять.

---

## 5. Explicitly out of launch scope

Следующие вещи **не должны останавливать первый запуск** и не должны раздувать MVP:

### Not required for launch
- multi-user collaboration
- shared workspaces
- enterprise permissions
- billing / subscriptions
- quotas
- deep analytics
- omnichannel delivery
- advanced graph orchestration
- visual prompt studio
- enterprise observability suite
- сложные dashboards
- массовое создание каналов
- полностью автономное создание Telegram-канала без участия пользователя

---

## 6. Launch quality bar

Для первого запуска достаточно следующего качества:
- продукт работает end-to-end по основному сценарию
- UX понятен на уровне Telegram UI
- основные статусы и ошибки читаемы
- редактирование после setup реально работает
- система не зависит от ручной магии разработчика

Для первого запуска **не требуется**:
- идеальная архитектурная чистота всех слоёв
- полный enterprise-grade hardening
- закрытие всех редких edge cases
- идеальный polished UI на всех вторичных экранах

---

## 7. Launch priority order

При конфликте приоритетов делать в таком порядке:

1. setup flow works
2. bot navigation works
3. content pipeline works
4. draft approval works
5. publication works
6. post-setup editing works
7. reliability hardening
8. secondary polish

---

## 8. Decision rule for future work

Если новая задача не помогает пройти основной launch path, то:
- либо переносим её после MVP
- либо явно обосновываем, почему без неё launch невозможен

Правило жёсткое:

> Всё, что не помогает привести пользователя от `/start` к управляемому каналу с публикацией и последующим редактированием, не должно расширять MVP launch scope автоматически.

---

## 9. Current interpretation of readiness

На текущий момент по launch scope уже есть зафиксированная продуктовая база и частично готов backend foundation.

Для выхода к запуску дальше нужно последовательно закрыть:
- repo normalization under bot + backend contour
- strategy/config implementation
- agent team implementation
- orchestration vertical slice
- bot foundation
- setup wizard
- ongoing management screens
- release hardening

---

## 10. Final launch test question

Перед любой релизной оценкой задаём один вопрос:

**Может ли новый пользователь без разработчика создать, подключить, настроить, запустить и потом изменить свой Telegram-канал через бота?**

Если ответ `да` — MVP launch собран.
Если ответ `нет` — запуск ещё не готов.
