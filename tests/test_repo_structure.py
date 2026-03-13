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
