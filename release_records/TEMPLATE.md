# Release Record — <release-marker>

- Date: <YYYY-MM-DD>
- Environment: <staging|live>
- Release marker / tag / commit: <value>
- Operator: <name>
- Rollback owner: <name>
- Rollout window: <time window>
- Smoke URL: <url>

## 1. Preflight
- Working tree / source state:
- Env file used:
- Secret file path checked:
- Commands run:
  - `python3 -m compileall app scripts`
  - `pytest -q tests/test_release_process.py tests/test_secret_file_config.py tests/test_secret_hygiene.py tests/test_api_smoke.py tests/test_e2e_mvp_flow.py`
- Result:

## 2. Final QA / staging evidence
- Evidence doc/link:
- Key path verified:
- Open issues:
- Why this is still acceptable for rollout:

## 3. Go / No-Go answers
- User can pass core path without developer: <yes|no>
- Known launch blockers exist: <yes|no>
- Hidden manual magic required: <yes|no>
- Rollback path is clear: <yes|no>
- Human explicitly approves GO: <yes|no>

## 4. Decision
- Final decision: <GO|NO-GO>
- Decision owner:
- Decision timestamp:
- Notes:

## 5. Rollout execution
- Command used:
```bash
APP_DIR=/srv/telegram-channel-factory \
ENV_FILE=/etc/telegram-channel-factory/.env.live \
RELEASE_REF=<git-tag-or-commit> \
./scripts/release_update.sh
```
- Start time:
- End time:
- Smoke result:
- Compose status summary:
- Rollback needed: <yes|no>

## 6. Post-deploy outcome
- Final service state:
- Blocking alerts after deploy:
- Follow-up actions:
- Operator sign-off:
