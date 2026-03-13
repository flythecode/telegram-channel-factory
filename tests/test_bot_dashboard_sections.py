from datetime import date

from app.bot.app import (
    channel_agents_screen_from_backend,
    channel_content_plan_screen_from_backend,
    channel_drafts_screen_from_backend,
    channel_settings_screen_from_backend,
    open_channel_dashboard_from_backend,
    session_store,
)
from app.models.draft import Draft
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.identity import TelegramIdentity
from app.utils.enums import DraftStatus



def test_dashboard_sections_are_backed_by_real_project_data(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-sections', telegram_username='sections')
    bridge_module = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge'])
    bridge = bridge_module.BotBackendBridge(fake_db, identity)

    project = bridge.create_project(ProjectCreate(name='Factory Alpha', language='ru', niche='AI'))
    bridge.update_project(
        project.id,
        ProjectUpdate(topic='AI news', content_format='Аналитика', posting_frequency='Ежедневно', operation_mode='semi_auto'),
    )
    bridge.apply_preset(project.id, 'starter_3')
    bridge.connect_channel(project.id, 'Alpha Channel', 'alpha_channel')
    plan = bridge.create_content_plan(project.id, start_date=date(2026, 3, 16), end_date=date(2026, 3, 22))
    task = bridge.create_task(project.id, 'Разбор рынка', content_plan_id=plan.id)
    fake_db.add(Draft(content_task_id=task.id, version=1, text='Черновик поста', status=DraftStatus.CREATED))

    chat_id = 555
    dashboard = open_channel_dashboard_from_backend(identity, 'Alpha Channel', chat_id=chat_id)
    assert dashboard is not None
    assert 'Контент-планов: 1' in dashboard.text
    assert 'Черновиков: 1' in dashboard.text

    settings = channel_settings_screen_from_backend(identity, chat_id)
    assert 'Factory Alpha' in settings.text
    assert 'AI news' in settings.text
    assert 'semi_auto' in settings.text

    agents = channel_agents_screen_from_backend(identity, chat_id)
    assert 'Всего агентов: 3' in agents.text
    assert 'writer' in agents.text

    content_plan = channel_content_plan_screen_from_backend(identity, chat_id)
    assert 'Планов: 1' in content_plan.text
    assert 'Всего задач: 1' in content_plan.text
    assert '2026-03-16 → 2026-03-22' in content_plan.text

    drafts = channel_drafts_screen_from_backend(identity, chat_id)
    assert 'Черновиков: 1' in drafts.text
    assert 'Разбор рынка' in drafts.text
    assert 'created' in drafts.text

    assert session_store.get_meta(chat_id, 'channel_title') == 'Alpha Channel'
