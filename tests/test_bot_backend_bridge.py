from datetime import date

from app.bot.backend_bridge import BotBackendBridge
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.identity import TelegramIdentity


def test_bot_bridge_can_create_project_apply_preset_connect_channel_and_plan(fake_db):
    bridge = BotBackendBridge(fake_db, TelegramIdentity(telegram_user_id='bridge-user', telegram_username='bridge'))
    project = bridge.create_project(ProjectCreate(name='Bridge Project', language='ru'))
    agents = bridge.apply_preset(project.id, 'starter_3')
    channel = bridge.connect_channel(project.id, 'Bridge Channel', 'bridge_channel')
    plan = bridge.create_content_plan(project.id, start_date=date(2026, 3, 16), end_date=date(2026, 3, 22))

    assert project.owner_user_id is not None
    assert len(agents) == 3
    assert channel.is_connected is True
    assert plan.project_id == project.id
    assert plan.generated_by == 'generation-service'
    assert plan.summary is not None


def test_bot_bridge_supports_reopen_and_update_flow(fake_db):
    bridge = BotBackendBridge(fake_db, TelegramIdentity(telegram_user_id='bridge-user-2', telegram_username='bridge2'))
    project = bridge.create_project(ProjectCreate(name='Reusable Project', language='ru'))
    updated = bridge.update_project(project.id, ProjectUpdate(topic='AI', operation_mode='semi_auto'))
    projects = bridge.my_projects()

    assert updated.topic == 'AI'
    assert any(item.id == project.id for item in projects)
