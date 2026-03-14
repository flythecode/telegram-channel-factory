init-db:
	python3 scripts/init_db.py

migrate:
	alembic upgrade head

seed-demo:
	python3 scripts/seed_demo.py

test:
	pytest -q

worker:
	python3 scripts/run_worker.py

run:
	uvicorn app.main:app --host $${API_HOST:-0.0.0.0} --port $${API_PORT:-8000}

up:
	docker compose up --build

up-detached:
	docker compose up --build -d

deploy-smoke:
	docker compose up --build -d
	docker compose ps
	docker compose exec api python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/health').read().decode())"

release-check:
	python3 -m compileall app scripts
	pytest -q tests/test_e2e_mvp_flow.py tests/test_channel_connection_flow.py tests/test_bot_navigation.py tests/test_worker.py tests/test_runtime_hardening.py tests/test_telegram_publisher.py tests/test_release_process.py

release-update:
	APP_DIR=$${APP_DIR:-/srv/telegram-channel-factory} ENV_FILE=$${ENV_FILE:-/etc/telegram-channel-factory/.env.live} ./scripts/release_update.sh


down:
	docker compose down

logs:
	docker compose logs -f api worker db bot

worker-status:
	python3 scripts/check_worker_status.py

bot-status:
	python3 scripts/check_bot_status.py

api-status:
	python3 scripts/check_api_status.py

runtime-alerts:
	python3 scripts/check_runtime_alerts.py
