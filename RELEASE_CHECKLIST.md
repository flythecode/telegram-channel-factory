# Telegram Channel Factory — Release Checklist

Этот файл — не справка, а **рабочий чеклист релиза**, который оператор реально проходит перед каждым staging/live rollout.

Правило простое:
- чеклист заполняется **на конкретный релиз**
- пока хоть один release-blocking пункт не закрыт — rollout не делаем
- итоговое решение фиксируется письменно в release record

---

## 1. Где фиксировать конкретный релиз

Для каждого релиза создать файл по шаблону:

- `release_records/YYYY-MM-DD-<release-marker>.md`

Например:

- `release_records/2026-03-14-0.1.0-mvp.md`

Если файла release record нет — релиз считается **неподготовленным**.

---

## 2. Release gate

Перед rollout должны быть одновременно выполнены все условия:

- есть заполненный release record
- пройден preflight checklist
- пройден final QA / staging validation
- выполнен явный go/no-go review
- назначен operator, который делает rollout
- назначен rollback owner

Если хотя бы один пункт не выполнен — решение автоматически `NO-GO`.

---

## 3. Preflight checklist

### Release identity
- [ ] зафиксирован release marker / tag / commit
- [ ] зафиксирован оператор релиза
- [ ] зафиксирован rollback owner
- [ ] указан target environment: `staging` или `live`
- [ ] указан expected rollout window

### Repo and package state
- [ ] рабочее дерево чистое или сознательно зафиксировано в record
- [ ] `VERSION` соответствует целевому релизу
- [ ] release docs актуальны для этого релиза
- [ ] release record создан до начала rollout

### Secrets and environment
- [ ] используется **неотслеживаемый** env file
- [ ] в env нет inline `TELEGRAM_BOT_TOKEN`
- [ ] используется `TELEGRAM_BOT_TOKEN_FILE`
- [ ] secret file существует в ожидаемом месте
- [ ] staging/live env не перепутаны

### Runtime confidence
- [ ] `python3 -m compileall app scripts`
- [ ] обязательные pytest checks выполнены
- [ ] миграции готовы к применению
- [ ] smoke-check path известен оператору

Рекомендуемый минимальный набор команд:

```bash
python3 -m compileall app scripts
pytest -q tests/test_release_process.py tests/test_secret_file_config.py tests/test_secret_hygiene.py tests/test_api_smoke.py tests/test_e2e_mvp_flow.py
```

---

## 4. Final QA / staging gate

Перед live rollout обязательно должно быть одно из двух:

### Вариант A — свежий staging sign-off
- [ ] есть свежий staging/demo run
- [ ] staging run оформлен письменно
- [ ] нет unresolved launch blockers

### Вариант B — controlled live exception
- [ ] причина, почему staging нельзя повторить, зафиксирована
- [ ] исключение явно одобрено человеком
- [ ] риск описан письменно в release record

Если нет A и нет B — это `NO-GO`.

---

## 5. Go / No-Go decision ritual

Перед rollout оператор обязан ответить письменно на 5 вопросов:

1. Может ли новый пользователь пройти путь `/start -> setup -> channel connection -> draft -> publication -> return later/edit` без разработчика?
2. Есть ли сейчас хоть один известный launch blocker?
3. Есть ли скрытая ручная магия, без которой релиз не взлетит?
4. Есть ли понятный rollback path, если rollout ломается?
5. Подписался ли конкретный человек под решением `GO`?

Правило решения:
- если на любой из вопросов 1, 4, 5 ответ отрицательный — `NO-GO`
- если на вопросы 2 или 3 ответ положительный — `NO-GO`
- только набор ответов без красных флагов даёт `GO`

---

## 6. Rollout checklist

Непосредственно перед rollout:

- [ ] release record обновлён последним статусом
- [ ] оператор знает точную команду rollout
- [ ] rollback команда подготовлена заранее
- [ ] smoke URL известен
- [ ] post-deploy verification назначен тому же оператору или отдельному owner

Рекомендуемый rollout path:

```bash
APP_DIR=/srv/telegram-channel-factory \
ENV_FILE=/etc/telegram-channel-factory/.env.live \
RELEASE_REF=<git-tag-or-commit> \
./scripts/release_update.sh
```

---

## 7. Mandatory post-deploy gate

Rollout не считается завершённым, пока не подтверждено:

- [ ] deploy script завершился без ошибок
- [ ] smoke-check прошёл
- [ ] compose services в expected state
- [ ] нет новых release-blocking alerts
- [ ] итоговое решение записано в release record

Если smoke-check не прошёл — это не «починим потом», а **incident / rollback decision point**.

---

## 8. Definition of operationally used process

Процесс считается реально используемым только если одновременно соблюдается всё ниже:

- чеклист используется на конкретный релиз, а не «вообще для справки»
- есть release record с датой, owner и решением
- `GO` принимается только после checklist + QA + явного sign-off
- после rollout фиксируется post-deploy result
- если чего-то из этого нет, релиз считается проведённым вне процесса
