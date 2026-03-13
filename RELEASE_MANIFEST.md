# Telegram Channel Factory — Release Manifest

## Release marker
- Version: `0.1.0-mvp`
- Version file: `VERSION`
- Python package version: `0.1.0`

## What belongs to the release package

### Core app
- `app/`
- `scripts/`
- `alembic/`
- `alembic.ini`
- `pyproject.toml`
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`

### Env templates
- `.env.example`
- `.env.demo`
- `.env.deploy`
- `.env.live.example`

### Migration baseline
- `alembic/versions/20260312_0704_initial_schema.py`

### Run / release docs
- `README.md`
- `BOT_SETUP.md`
- `CHANNEL_CONNECTION_FLOW.md`
- `ENV_MODES.md`
- `STAGING_DEMO_RUNBOOK.md`
- `FINAL_QA_RUNBOOK.md`
- `RELEASE_SMOKE.md`

### Product docs
- `PRODUCT_SPEC_V1.md`
- `MVP_LAUNCH_SCOPE_V1.md`
- `IMPLEMENTATION_ROADMAP_V1.md`
- `MVP_CHECKLIST.md`

## Required checks before release
- migrations apply successfully
- local/demo run path is documented
- compose deploy path is documented
- smoke checks are documented and runnable
- release version marker exists
- env templates are present
- final QA runbook exists

## Recommended release command path

### Local confidence
```bash
python3 -m compileall app scripts
pytest -q
```

### Migration confidence
```bash
alembic upgrade head
```

### Compose confidence
```bash
make deploy-smoke
```

### Release smoke checklist
See:
- `RELEASE_SMOKE.md`

## Notes
- `.env.live` should stay untracked
- real Telegram tokens must not be committed
- `.env.deploy` is a deployment template, not a secret store
