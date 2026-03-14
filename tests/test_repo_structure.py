from pathlib import Path

from app.bot.service import BotService
from app.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_main_entrypoint_exposes_api_app():
    assert app is not None


def test_bot_layer_placeholder_service_exists():
    service = BotService()
    screen = service.start_screen()

    assert screen.text
    assert screen.buttons



def test_docker_compose_uses_container_safe_database_url_and_api_healthcheck():
    compose = (ROOT / 'docker-compose.yml').read_text()

    assert 'postgresql+psycopg://postgres:postgres@db:5432/tcf' in compose
    assert 'condition: service_healthy' in compose
    assert "http://127.0.0.1:8000/health" in compose



def test_makefile_exposes_deploy_smoke_command():
    makefile = (ROOT / 'Makefile').read_text()

    assert 'deploy-smoke:' in makefile
    assert "docker compose exec api" in makefile



def test_prepare_server_dirs_script_creates_non_root_runtime_layout():
    script = (ROOT / 'scripts' / 'prepare_server_dirs.sh').read_text()

    assert 'APP_USER="${APP_USER:-tcf}"' in script
    assert 'APP_DIR="${APP_DIR:-/srv/telegram-channel-factory}"' in script
    assert 'SECRETS_DIR="${SECRETS_DIR:-/etc/telegram-channel-factory}"' in script
    assert 'useradd' in script
    assert 'chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"' in script
    assert 'chown root:"${APP_GROUP}" "${SECRETS_DIR}"' in script



def test_deploy_script_uses_runtime_user_and_external_env_file():
    script = (ROOT / 'scripts' / 'deploy_as_tcf.sh').read_text()

    assert 'Run this script as the runtime user' in script
    assert 'if [[ "$(id -un)" == "root" ]]; then' in script
    assert 'docker info >/dev/null 2>&1' in script
    assert 'docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up --build -d' in script
    assert 'cp "${TCF_ENV_FILE}" .env' not in script
