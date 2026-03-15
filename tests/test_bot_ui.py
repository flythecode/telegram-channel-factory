from datetime import date, datetime, timezone
import logging

from app.bot.service import BotService
from app.bot.keyboards import main_menu_keyboard
from app.bot.app import (
    build_dispatcher,
    build_reply_keyboard,
    channel_agents_screen_from_backend,
    channel_content_plan_screen_from_backend,
    channel_drafts_screen_from_backend,
    channel_mode_screen_from_backend,
    channel_settings_screen_from_backend,
    change_channel_mode_from_backend,
    create_publication_from_current_draft,
    my_channels_screen_from_backend,
    open_channel_dashboard_from_backend,
    open_draft_screen_from_backend,
    open_publication_screen_from_backend,
    perform_draft_action_from_backend,
    perform_publication_action_from_backend,
    publications_screen_from_backend,
    resolve_screen_for_text,
    resume_current_project_from_backend,
    session_store,
)
from app.services.identity import TelegramIdentity
from app.models.draft import Draft
from app.models.generation_job import GenerationJob
from app.models.llm_generation_event import LLMGenerationEvent
from app.bot.screens import publication_detail_screen
from app.utils.enums import DraftStatus, GenerationJobOperation, GenerationJobStatus, SubscriptionStatus


def test_start_screen_is_meaningful():
    service = BotService()
    screen = service.start_screen()
    assert 'Telegram' in screen.text
    assert screen.buttons == main_menu_keyboard()



def test_main_menu_contains_core_entries():
    service = BotService()
    screen = service.main_menu_screen()
    flat = [item for row in screen.buttons for item in row]
    assert '➕ Канал' in flat
    assert '📂 Каналы' in flat
    assert '❓ Помощь' in flat
    assert '✨ Как это работает' in flat



def test_how_it_works_and_help_screens_exist():
    service = BotService()
    assert 'Нажми «Создать канал»' in service.how_it_works_screen().text
    assert 'С чем я помогаю' in service.help_screen().text



def test_start_and_project_ready_screens_highlight_single_next_step():
    service = BotService()
    assert 'Я буду подсказывать только следующий нужный шаг' in service.start_screen().text
    assert 'Следующий шаг один' in service.project_ready_screen().text
    assert 'без участия разработчика' in service.my_channels_empty_screen().text



def test_dispatcher_builds_with_router():
    dispatcher = build_dispatcher()
    assert dispatcher is not None



def test_build_reply_keyboard_maps_screen_buttons_to_telegram_markup():
    screen = BotService().start_screen()
    markup = build_reply_keyboard(screen)

    assert markup is not None
    assert [[button.text for button in row] for row in markup.keyboard] == main_menu_keyboard()
    assert markup.resize_keyboard is True



def test_resolve_screen_for_text_routes_main_menu_and_wizard_entry():
    start = resolve_screen_for_text('Создать канал')
    assert 'Создадим проект канала' in start.text
    assert start.buttons[0][0] == 'Начать'

    name_step = resolve_screen_for_text('Начать')
    assert 'Шаг 1/7' in name_step.text

    help_screen = resolve_screen_for_text('Помощь')
    assert 'С чем я помогаю' in help_screen.text

    back = resolve_screen_for_text('Назад')
    assert 'Помогаю запустить Telegram-канал' in back.text



def test_resolve_screen_for_text_walks_through_stateful_wizard_steps():
    chat_id = 42
    session_store.clear(chat_id)

    start = resolve_screen_for_text('Создать канал', chat_id=chat_id)
    assert 'Создадим проект канала' in start.text

    name = resolve_screen_for_text('Начать', chat_id=chat_id)
    assert 'Шаг 1/7' in name.text

    language = resolve_screen_for_text('Alpha Channel', chat_id=chat_id)
    assert 'Шаг 2/7' in language.text
    assert session_store.get_state(chat_id).name == 'Alpha Channel'

    goal = resolve_screen_for_text('AI', chat_id=chat_id)
    assert 'Шаг 3/7' in goal.text
    assert session_store.get_state(chat_id).niche == 'AI'

    description = resolve_screen_for_text('Русский', chat_id=chat_id)
    assert 'Шаг 4/7' in description.text
    assert session_store.get_state(chat_id).language == 'Русский'

    content_format = resolve_screen_for_text('Личный бренд', chat_id=chat_id)
    assert 'Шаг 5/7' in content_format.text
    assert session_store.get_state(chat_id).goal == 'Личный бренд'

    frequency = resolve_screen_for_text('Канал про ИИ-агентов для предпринимателей', chat_id=chat_id)
    assert 'Шаг 6/7' in frequency.text
    assert session_store.get_state(chat_id).description == 'Канал про ИИ-агентов для предпринимателей'

    summary = resolve_screen_for_text('Аналитика', chat_id=chat_id)
    assert 'Шаг 7/7' in summary.text
    assert session_store.get_state(chat_id).content_format == 'Аналитика'

    summary = resolve_screen_for_text('Ежедневно', chat_id=chat_id)
    assert 'Проверь настройки проекта' in summary.text
    assert 'Alpha Channel' in summary.text
    assert 'AI' in summary.text
    assert 'Канал про ИИ-агентов для предпринимателей' in summary.text
    assert session_store.get_state(chat_id).posting_frequency == 'Ежедневно'

    preset = resolve_screen_for_text('Подтвердить проект', chat_id=chat_id)
    assert 'выбери команду ai-агентов' in preset.text.lower()

    connection = resolve_screen_for_text('3 агента — Быстрый старт', chat_id=chat_id)
    assert 'Осталось подключить твой Telegram-канал' in connection.text
    assert connection.buttons[0][0] == 'У меня уже есть канал'

    saved_channel = resolve_screen_for_text('@alpha_channel', chat_id=chat_id)
    assert 'Канал для подключения сохранён: @alpha_channel' in saved_channel.text
    assert 'Следующий шаг один' in saved_channel.text

    ready = resolve_screen_for_text('Проверить подключение', chat_id=chat_id)
    assert 'Канал подключён' in ready.text or 'Сначала пришли @username' in ready.text



def test_confirm_project_creates_real_project_and_stores_project_id(monkeypatch):
    chat_id = 99
    session_store.clear(chat_id)
    session_store.start(chat_id)
    session_store.update_state(
        chat_id,
        name='Bridge Channel',
        niche='AI',
        language='Русский',
        goal='Личный бренд',
        content_format='Аналитика',
        posting_frequency='Ежедневно',
    )

    calls = {}

    def fake_create(chat_id_arg, identity_arg):
        calls['chat_id'] = chat_id_arg
        calls['identity'] = identity_arg.telegram_user_id
        session_store.set_meta(chat_id_arg, 'project_id', 'project-123')
        return 'project-123'

    monkeypatch.setattr('app.bot.app.create_project_from_wizard_state', fake_create)

    screen = resolve_screen_for_text(
        'Подтвердить проект',
        chat_id=chat_id,
        identity=TelegramIdentity(telegram_user_id='tg-1', telegram_username='tester'),
    )

    assert 'Проект создан: `project-123`' in screen.text
    assert calls == {'chat_id': 99, 'identity': 'tg-1'}
    assert session_store.get_meta(chat_id, 'project_id') == 'project-123'



def test_preset_selection_applies_agents_and_stores_preset_meta(monkeypatch):
    chat_id = 100
    session_store.clear(chat_id)
    session_store.start(chat_id)
    session_store.set_meta(chat_id, 'project_id', 'project-999')

    calls = {}

    def fake_apply(chat_id_arg, identity_arg, preset_label_arg):
        calls['chat_id'] = chat_id_arg
        calls['identity'] = identity_arg.telegram_user_id
        calls['preset_label'] = preset_label_arg
        session_store.set_meta(chat_id_arg, 'preset_code', 'starter_3')
        session_store.set_meta(chat_id_arg, 'agents_count', '3')
        return 3

    monkeypatch.setattr('app.bot.app.apply_preset_from_wizard_state', fake_apply)

    screen = resolve_screen_for_text(
        '3 агента — Быстрый старт',
        chat_id=chat_id,
        identity=TelegramIdentity(telegram_user_id='tg-2', telegram_username='tester2'),
    )

    assert 'Команда агентов применена: 3.' in screen.text
    assert 'Осталось подключить твой Telegram-канал' in screen.text
    assert calls == {'chat_id': 100, 'identity': 'tg-2', 'preset_label': '3 агента — Быстрый старт'}
    assert session_store.get_meta(chat_id, 'preset_code') == 'starter_3'
    assert session_store.get_meta(chat_id, 'agents_count') == '3'



def test_channel_connect_flow_accepts_channel_ref_and_checks_connection(monkeypatch):
    chat_id = 101
    session_store.clear(chat_id)
    session_store.start(chat_id)
    session_store.set_step(chat_id, 'channel_connect')
    session_store.set_meta(chat_id, 'project_id', 'project-555')

    existing_channel = resolve_screen_for_text('У меня уже есть канал', chat_id=chat_id)
    assert 'Теперь сделай только три действия' in existing_channel.text

    guide = resolve_screen_for_text('Как создать канал', chat_id=chat_id)
    assert 'Если канала ещё нет' in guide.text

    saved = resolve_screen_for_text('@muhatest777', chat_id=chat_id)
    assert 'Канал для подключения сохранён: @muhatest777' in saved.text
    assert 'Следующий шаг один' in saved.text
    assert session_store.get_state(chat_id).channel_ref == '@muhatest777'

    calls = {}

    def fake_connect(chat_id_arg, identity_arg, channel_ref_arg):
        calls['chat_id'] = chat_id_arg
        calls['identity'] = identity_arg.telegram_user_id
        calls['channel_ref'] = channel_ref_arg
        session_store.set_meta(chat_id_arg, 'channel_id', 'channel-123')
        session_store.update_state(chat_id_arg, connection_confirmed=True)
        return 'channel-123', 'connected'

    monkeypatch.setattr('app.bot.app.connect_channel_from_wizard_state', fake_connect)

    checked = resolve_screen_for_text(
        'Проверить подключение',
        chat_id=chat_id,
        identity=TelegramIdentity(telegram_user_id='tg-3', telegram_username='tester3'),
    )

    assert 'Канал подключён и готов к публикациям' in checked.text
    assert calls == {'chat_id': 101, 'identity': 'tg-3', 'channel_ref': '@muhatest777'}
    assert session_store.get_meta(chat_id, 'channel_id') == 'channel-123'



def test_my_channels_and_open_channel_dashboard_are_backed_by_bridge(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-4', telegram_username='tester4')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Alpha', language='ru'))
    bridge.apply_preset(project.id, 'starter_3')
    bridge.connect_channel(project.id, 'Alpha Channel', 'alpha_channel')
    plan = bridge.create_content_plan(project.id, start_date=date(2026, 3, 16), end_date=date(2026, 3, 22))
    task = bridge.create_task(project.id, 'Weekly AI digest', content_plan_id=plan.id)
    fake_db.add(Draft(content_task_id=task.id, text='Draft text', status=DraftStatus.CREATED, version=1))

    channels_screen = my_channels_screen_from_backend(identity)
    assert 'Мои каналы' in channels_screen.text
    assert 'верну тебя прямо в рабочую точку проекта' in channels_screen.text
    flat = [item for row in channels_screen.buttons for item in row]
    assert 'Alpha Channel' in flat

    dashboard = open_channel_dashboard_from_backend(identity, 'Alpha Channel', chat_id=777)
    assert dashboard is not None
    assert 'Канал: Alpha Channel' in dashboard.text
    assert 'Агентов: 3' in dashboard.text
    assert 'Контент-планов: 1' in dashboard.text
    assert 'Черновиков: 1' in dashboard.text
    assert 'Следующий шаг: открой «Черновики»' in dashboard.text
    assert session_store.get_meta(777, 'channel_title') == 'Alpha Channel'



def test_dashboard_surfaces_generation_status_limits_and_queue(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-gen-1', telegram_username='genstatus')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Gamma Channel', language='ru'))
    bridge.apply_preset(project.id, 'starter_3')
    channel = bridge.connect_channel(project.id, 'Gamma Channel', 'gamma_channel')

    bridge.client_account.subscription_plan_code = 'starter'
    bridge.client_account.subscription_status = SubscriptionStatus.ACTIVE
    bridge.client_account.settings = {
        'generation_guardrails': {
            'client_generation_quota_limit': 1,
        }
    }

    fake_db.add(
        GenerationJob(
            project_id=project.id,
            client_account_id=bridge.client_account.id,
            operation=GenerationJobOperation.CREATE_DRAFT,
            status=GenerationJobStatus.FAILED,
            priority=40,
            payload={},
            error_message='openai request failed with status 429',
            queued_at=datetime.now(),
        )
    )

    fake_db.add(
        LLMGenerationEvent(
            client_id=bridge.client_account.id,
            project_id=project.id,
            telegram_channel_id=channel.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=100,
            estimated_cost_usd='0.001000',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    dashboard = open_channel_dashboard_from_backend(identity, 'Gamma Channel', chat_id=778)
    assert dashboard is not None
    assert 'Generation status:' in dashboard.text
    assert 'Статус плана:' in dashboard.text
    assert 'Очередь: queued 0 / processing 0 / failed 1' in dashboard.text
    assert 'Причина блокировки:' in dashboard.text
    assert 'Лимит generation:' in dashboard.text
    assert 'Остаток generation:' in dashboard.text



def test_draft_detail_surfaces_provider_failover_diagnostics():
    screen = BotService().draft_detail_screen(
        title='AI recap',
        status='created',
        version=3,
        text='Draft body',
        created_by_agent='writer',
        generation_summary={
            'queue': {'queued': 0, 'processing': 0, 'failed': 0, 'latest_status': 'succeeded', 'latest_error': None},
            'plan': {
                'label': 'Pro',
                'code': 'pro',
                'access_flag': 'paid',
                'status': 'active',
                'status_label': 'активен',
                'generation_limit': 1500,
                'generation_used': 200,
                'generation_remaining': 1300,
                'period_end': '2026-03-31T00:00:00+00:00',
                'is_blocked': False,
                'block_reason': None,
            },
            'guardrails': {'hard_stop_reached': False, 'soft_limit_reached': False, 'client': {'windows': []}},
            'generation': {
                'provider': 'openai',
                'model': 'gpt-5-mini',
                'finish_reason': 'provider_unavailable',
                'failover_activated': True,
                'failover_outcome': 'graceful-degradation',
                'fallback_provider': 'openrouter',
                'primary_error_message': 'openai request failed with status 429',
            },
        },
    )

    assert 'Статус плана: активен' in screen.text
    assert 'Остаток generation: 1300' in screen.text
    assert 'Provider/model: openai / gpt-5-mini' in screen.text
    assert 'Provider сейчас деградировал' in screen.text
    assert 'Failover: graceful-degradation → openrouter' in screen.text
    assert 'Ошибка provider’а: openai request failed with status 429' in screen.text



def test_dashboard_sections_are_backed_by_real_data(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-5', telegram_username='tester5')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(
        __import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(
            name='Beta Channel',
            language='ru',
            niche='AI',
            content_format='Аналитика',
            posting_frequency='Ежедневно',
        )
    )
    bridge.apply_preset(project.id, 'starter_3')
    bridge.connect_channel(project.id, 'Beta Channel', 'beta_channel')
    plan = bridge.create_content_plan(project.id, start_date=date(2026, 3, 23), end_date=date(2026, 3, 29))
    task = bridge.create_task(project.id, 'Market recap', content_plan_id=plan.id)
    fake_db.add(Draft(content_task_id=task.id, text='Draft body', status=DraftStatus.APPROVED, version=2))

    session_store.set_meta(555, 'project_id', str(project.id))
    session_store.set_meta(555, 'channel_id', 'channel-id')
    session_store.set_meta(555, 'channel_title', 'Beta Channel')

    settings_screen = channel_settings_screen_from_backend(identity, 555)
    assert settings_screen is not None
    assert 'Проект: Beta Channel' in settings_screen.text
    assert 'Формат: Аналитика' in settings_screen.text
    assert 'следующий рабочий шаг' in settings_screen.text.lower()

    agents_screen = channel_agents_screen_from_backend(identity, 555)
    assert agents_screen is not None
    assert 'Всего агентов: 3' in agents_screen.text
    assert 'strategist' in agents_screen.text
    assert 'Следующий рабочий шаг' in agents_screen.text

    plan_screen = channel_content_plan_screen_from_backend(identity, 555)
    assert plan_screen is not None
    assert 'Планов: 1' in plan_screen.text
    assert 'Всего задач: 1' in plan_screen.text

    drafts_screen = channel_drafts_screen_from_backend(identity, 555)
    assert drafts_screen is not None
    assert 'Черновиков: 1' in drafts_screen.text
    assert 'Market recap' in drafts_screen.text
    assert 'Подтверждён' in drafts_screen.text



def test_draft_detail_publications_and_modes_are_backed_by_real_data(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-55', telegram_username='tester55')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Draft Channel', language='ru'))
    channel = bridge.connect_channel(project.id, 'Draft Channel', 'draft_channel')
    task = bridge.create_task(project.id, 'Open this draft')
    draft = Draft(content_task_id=task.id, text='Initial draft body', status=DraftStatus.CREATED, version=1, created_by_agent='writer')
    fake_db.add(draft)

    session_store.set_meta(556, 'project_id', str(project.id))
    session_store.set_meta(556, 'channel_id', str(channel.id))
    session_store.set_meta(556, 'channel_title', 'Draft Channel')

    detail = open_draft_screen_from_backend(identity, 556, 'Open this draft')
    assert detail is not None
    assert 'Черновик' in detail.text
    assert 'Open this draft' in detail.text
    assert 'Initial draft body' in detail.text
    assert session_store.get_meta(556, 'draft_id') == str(draft.id)

    approved = perform_draft_action_from_backend(identity, 556, 'approve')
    assert approved is not None
    assert 'Черновик подтверждён.' in approved.text
    assert 'Статус: Подтверждён' in approved.text

    created_pub = create_publication_from_current_draft(identity, 556, scheduled=False)
    assert created_pub is not None
    assert 'Публикация создана.' in created_pub.text
    assert 'Статус: Отправляется' in created_pub.text

    pubs = publications_screen_from_backend(identity, 556)
    assert pubs is not None
    assert 'Публикаций: 1' in pubs.text
    assert 'Open this draft' in pubs.text

    pub_detail = open_publication_screen_from_backend(identity, 556, 'Open this draft')
    assert pub_detail is not None
    assert 'Публикация' in pub_detail.text

    canceled = perform_publication_action_from_backend(identity, 556, 'cancel')
    assert canceled is not None
    assert 'Публикация отменена.' in canceled.text
    assert 'Статус: Отменено' in canceled.text

    mode_screen = channel_mode_screen_from_backend(identity, 556)
    assert mode_screen is not None
    assert 'Текущий режим канала' in mode_screen.text

    updated_mode = change_channel_mode_from_backend(identity, 556, 'auto')
    assert updated_mode is not None
    assert 'Режим обновлён.' in updated_mode.text
    assert 'Авто' in updated_mode.text
    assert 'максимум автоматизации' in updated_mode.text



def test_resolve_screen_for_text_opens_backend_backed_dashboard_sections(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-6', telegram_username='tester6')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Gamma Channel', language='ru'))
    channel = bridge.connect_channel(project.id, 'Gamma Channel', 'gamma_channel')
    bridge.apply_preset(project.id, 'starter_3')
    task = bridge.create_task(project.id, 'Gamma Draft')
    fake_db.add(Draft(content_task_id=task.id, text='Gamma body', status=DraftStatus.CREATED, version=1))

    session_store.set_meta(888, 'project_id', str(project.id))
    session_store.set_meta(888, 'channel_id', str(channel.id))
    session_store.set_meta(888, 'channel_title', 'Gamma Channel')

    settings = resolve_screen_for_text('Настройки', chat_id=888, identity=identity)
    assert 'Настройки канала' in settings.text
    assert 'Проект: Gamma Channel' in settings.text

    agents = resolve_screen_for_text('Агенты', chat_id=888, identity=identity)
    assert 'Агенты' in agents.text
    assert 'Всего агентов: 3' in agents.text

    drafts = resolve_screen_for_text('Черновики', chat_id=888, identity=identity)
    assert 'Gamma Draft' in drafts.text

    draft_detail = resolve_screen_for_text('Gamma Draft', chat_id=888, identity=identity)
    assert 'Черновик' in draft_detail.text
    assert 'Gamma body' in draft_detail.text

    approve = resolve_screen_for_text('Подтвердить', chat_id=888, identity=identity)
    assert 'Черновик подтверждён.' in approve.text
    assert 'Статус: Подтверждён' in approve.text

    create_pub = resolve_screen_for_text('Создать публикацию', chat_id=888, identity=identity)
    assert 'Публикация создана.' in create_pub.text

    pubs = resolve_screen_for_text('Публикации', chat_id=888, identity=identity)
    assert 'Публикаций: 1' in pubs.text

    mode = resolve_screen_for_text('Режим работы', chat_id=888, identity=identity)
    assert 'Текущий режим канала' in mode.text

    auto = resolve_screen_for_text('Режим: авто', chat_id=888, identity=identity)
    assert 'Режим обновлён.' in auto.text
    assert 'Авто' in auto.text



def test_channel_connection_result_screen_has_human_error_branches():
    service = BotService()

    bot_not_admin = service.channel_connection_result_screen('bot_not_admin', '@alpha')
    assert 'не является администратором' in bot_not_admin.text

    missing_permission = service.channel_connection_result_screen('missing_post_permission', '@alpha')
    assert 'не может публиковать сообщения' in missing_permission.text

    channel_not_found = service.channel_connection_result_screen('channel_not_found', '@alpha')
    assert 'Канал не найден' in channel_not_found.text



def test_resume_current_project_restores_dashboard_by_channel_id(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-restore-1', telegram_username='restore1')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Resume Channel', language='ru'))
    channel = bridge.connect_channel(project.id, 'Resume Channel', 'resume_channel')
    bridge.apply_preset(project.id, 'starter_3')

    session_store.set_meta(990, 'project_id', str(project.id))
    session_store.set_meta(990, 'channel_id', str(channel.id))

    screen = resume_current_project_from_backend(identity, 990)
    assert screen is not None
    assert 'Канал: Resume Channel' in screen.text
    assert session_store.get_meta(990, 'channel_title') == 'Resume Channel'



def test_open_project_restores_dashboard_even_without_channel_title(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-restore-2', telegram_username='restore2')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Later Return', language='ru'))
    channel = bridge.connect_channel(project.id, 'Later Return', 'later_return')
    bridge.apply_preset(project.id, 'starter_3')

    session_store.set_meta(991, 'project_id', str(project.id))
    session_store.set_meta(991, 'channel_id', str(channel.id))
    session_store.delete_meta(991, 'channel_title')

    screen = resolve_screen_for_text('Открыть проект', chat_id=991, identity=identity)
    assert 'Канал: Later Return' in screen.text
    assert session_store.get_meta(991, 'channel_title') == 'Later Return'



def test_back_flow_returns_to_previous_wizard_step_without_losing_context():
    chat_id = 1200
    session_store.clear(chat_id)

    resolve_screen_for_text('Создать канал', chat_id=chat_id)
    resolve_screen_for_text('Начать', chat_id=chat_id)
    resolve_screen_for_text('Alpha Channel', chat_id=chat_id)
    resolve_screen_for_text('AI', chat_id=chat_id)

    back = resolve_screen_for_text('Назад', chat_id=chat_id)
    assert 'Шаг 2/6' in back.text
    assert session_store.get_state(chat_id).name == 'Alpha Channel'
    assert session_store.get_state(chat_id).niche == 'AI'

    back = resolve_screen_for_text('Назад', chat_id=chat_id)
    assert 'Шаг 1/6' in back.text
    assert session_store.get_state(chat_id).name == 'Alpha Channel'



def test_main_menu_keeps_project_context_for_reopen(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-keep-ctx', telegram_username='keepctx')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Keep Context', language='ru'))
    channel = bridge.connect_channel(project.id, 'Keep Context', 'keep_context')
    bridge.apply_preset(project.id, 'starter_3')

    session_store.set_meta(1201, 'project_id', str(project.id))
    session_store.set_meta(1201, 'channel_id', str(channel.id))
    session_store.set_meta(1201, 'channel_title', 'Keep Context')
    session_store.set_step(1201, 'channel_dashboard')

    menu = resolve_screen_for_text('Главное меню', chat_id=1201, identity=identity)
    assert 'Помогаю запустить Telegram-канал' in menu.text
    assert session_store.get_meta(1201, 'project_id') == str(project.id)

    reopened = resolve_screen_for_text('Открыть проект', chat_id=1201, identity=identity)
    assert 'Канал: Keep Context' in reopened.text



def test_context_restores_for_same_user_on_new_chat_id(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-restore-same-user', telegram_username='restoreuser')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Restored Channel', language='ru'))
    channel = bridge.connect_channel(project.id, 'Restored Channel', 'restored_channel')
    bridge.apply_preset(project.id, 'starter_3')

    old_chat_id = 1300
    new_chat_id = 1301
    session_store.bind_identity(old_chat_id, identity)
    session_store.set_meta(old_chat_id, 'project_id', str(project.id))
    session_store.set_meta(old_chat_id, 'channel_id', str(channel.id))
    session_store.set_meta(old_chat_id, 'channel_title', 'Restored Channel')
    session_store.set_step(old_chat_id, 'channel_dashboard')

    screen = resolve_screen_for_text('Открыть проект', chat_id=new_chat_id, identity=identity)
    assert 'Канал: Restored Channel' in screen.text
    assert session_store.get_meta(new_chat_id, 'channel_title') == 'Restored Channel'



def test_empty_states_are_human_and_actionable():
    service = BotService()

    channels = service.my_channels_screen([])
    assert 'Что можно сделать дальше' in channels.text

    agents = service.channel_agents_screen([])
    assert 'Когда команда агентов будет собрана' in agents.text

    plans = service.channel_content_plan_screen([], tasks_total=0)
    assert 'Сначала сгенерируй идеи' in plans.text

    drafts = service.channel_drafts_screen([])
    assert 'здесь будут лежать все новые' in drafts.text

    publications = service.publications_screen([])
    assert 'здесь появятся очередь' in publications.text



def test_loading_and_error_screens_exist():
    service = BotService()

    loading = service.loading_screen('Обработка', 'Подожди пару секунд.')
    assert 'Подожди пару секунд' in loading.text
    assert loading.buttons == [['Главное меню']]

    error = service.error_screen('Черновик ещё не подтверждён.', next_steps=[['Черновики'], ['Главное меню']])
    assert 'Не получилось выполнить действие' in error.text
    assert 'Черновик ещё не подтверждён' in error.text



def test_create_publication_shows_human_error_for_unapproved_draft(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-error-1', telegram_username='err1')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Error Channel', language='ru'))
    channel = bridge.connect_channel(project.id, 'Error Channel', 'error_channel')
    task = bridge.create_task(project.id, 'Unapproved Draft')
    draft = Draft(content_task_id=task.id, text='Body', status=DraftStatus.CREATED, version=1)
    fake_db.add(draft)

    session_store.set_meta(1400, 'project_id', str(project.id))
    session_store.set_meta(1400, 'channel_id', str(channel.id))
    session_store.set_meta(1400, 'draft_id', str(draft.id))

    screen = resolve_screen_for_text('Создать публикацию', chat_id=1400, identity=identity)
    assert 'Не получилось выполнить действие' in screen.text
    assert 'Сначала открой его и нажми «Подтвердить»' in screen.text



def test_full_manual_ui_only_e2e_flow_is_now_reachable(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-ui-e2e', telegram_username='uie2e')
    chat_id = 1500

    assert 'Помогаю запустить Telegram-канал' in resolve_screen_for_text('/start', chat_id=chat_id, identity=identity).text
    assert 'Создадим проект канала' in resolve_screen_for_text('Создать канал', chat_id=chat_id, identity=identity).text
    assert 'Шаг 1/7' in resolve_screen_for_text('Начать', chat_id=chat_id, identity=identity).text
    assert 'Шаг 2/7' in resolve_screen_for_text('Alpha Factory', chat_id=chat_id, identity=identity).text
    resolve_screen_for_text('AI', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Русский', chat_id=chat_id, identity=identity)
    description = resolve_screen_for_text('Экспертный контент', chat_id=chat_id, identity=identity)
    assert 'Шаг 5/7' in description.text
    resolve_screen_for_text('Канал про ИИ-агентов для предпринимателей', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Аналитика', chat_id=chat_id, identity=identity)
    summary = resolve_screen_for_text('Ежедневно', chat_id=chat_id, identity=identity)
    assert 'Alpha Factory' in summary.text
    assert 'Канал про ИИ-агентов для предпринимателей' in summary.text

    preset = resolve_screen_for_text('Подтвердить проект', chat_id=chat_id, identity=identity)
    assert 'Проект создан' in preset.text
    connected = resolve_screen_for_text('3 агента — Быстрый старт', chat_id=chat_id, identity=identity)
    assert 'Открой настройки канала в Telegram' in connected.text
    resolve_screen_for_text('@alpha_factory', chat_id=chat_id, identity=identity)
    ready = resolve_screen_for_text('Проверить подключение', chat_id=chat_id, identity=identity)
    assert 'Канал подключён' in ready.text

    dashboard = resolve_screen_for_text('Открыть проект', chat_id=chat_id, identity=identity)
    assert 'Канал: @alpha_factory' in dashboard.text

    plan_created = resolve_screen_for_text('Создать контент-план', chat_id=chat_id, identity=identity)
    assert 'Контент-план создан.' in plan_created.text
    assert 'Следующий шаг один: нажми «Сгенерировать 10 идей».' in plan_created.text

    ideas = resolve_screen_for_text('Сгенерировать 10 идей', chat_id=chat_id, identity=identity)
    assert '10 идей готовы.' in ideas.text
    assert 'Следующий шаг один: нажми «Создать 3 черновика».' in ideas.text

    drafts_created = resolve_screen_for_text('Создать 3 черновика', chat_id=chat_id, identity=identity)
    assert '3 черновика готовы.' in drafts_created.text
    assert 'Следующий шаг один: нажми «Черновики»' in drafts_created.text

    drafts = resolve_screen_for_text('Черновики', chat_id=chat_id, identity=identity)
    assert 'Черновиков:' in drafts.text
    first_draft_title = next(button[0] for button in drafts.buttons if button[0] not in {'Назад', 'Главное меню'})

    draft_detail = resolve_screen_for_text(first_draft_title, chat_id=chat_id, identity=identity)
    assert 'Черновик' in draft_detail.text
    edited = resolve_screen_for_text('Редактировать', chat_id=chat_id, identity=identity)
    assert 'Пришли новый текст черновика' in edited.text
    edited_done = resolve_screen_for_text('Обновлённый текст черновика для UI e2e', chat_id=chat_id, identity=identity)
    assert 'Черновик обновлён.' in edited_done.text
    approved = resolve_screen_for_text('Подтвердить', chat_id=chat_id, identity=identity)
    assert 'Черновик подтверждён.' in approved.text

    created_publication = resolve_screen_for_text('Создать публикацию', chat_id=chat_id, identity=identity)
    assert 'Публикация создана.' in created_publication.text
    publications = resolve_screen_for_text('Публикации', chat_id=chat_id, identity=identity)
    assert 'Публикаций: 1' in publications.text

    reopened_from_list = resolve_screen_for_text('Мои каналы', chat_id=chat_id, identity=identity)
    assert '@alpha_factory' in [item for row in reopened_from_list.buttons for item in row]
    reopened_project = resolve_screen_for_text('Alpha Factory', chat_id=chat_id, identity=identity)
    assert 'Канал: @alpha_factory' in reopened_project.text


def test_double_tap_create_publication_does_not_create_duplicate(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-double-publication', telegram_username='doublepub')
    chat_id = 1401

    resolve_screen_for_text('/start', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Создать канал', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Начать', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Double Tap Factory', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('AI', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Русский', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Экспертный контент', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Аналитика', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Ежедневно', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Подтвердить проект', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('3 агента — Быстрый старт', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('@doubletap_factory', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Проверить подключение', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Создать контент-план', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Сгенерировать 10 идей', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Создать 3 черновика', chat_id=chat_id, identity=identity)

    drafts = resolve_screen_for_text('Черновики', chat_id=chat_id, identity=identity)
    first_draft_title = next(button[0] for button in drafts.buttons if button[0] not in {'Назад', 'Главное меню'})
    resolve_screen_for_text(first_draft_title, chat_id=chat_id, identity=identity)
    resolve_screen_for_text('Подтвердить', chat_id=chat_id, identity=identity)

    first = resolve_screen_for_text('Создать публикацию', chat_id=chat_id, identity=identity)
    second = resolve_screen_for_text('Создать публикацию', chat_id=chat_id, identity=identity)

    assert 'Публикация создана.' in first.text
    assert 'Публикация создана.' in second.text

    publications = resolve_screen_for_text('Публикации', chat_id=chat_id, identity=identity)
    assert 'Публикаций: 1' in publications.text



def test_mode_change_shows_human_error_when_channel_missing(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-error-2', telegram_username='err2')
    session_store.set_meta(1401, 'channel_id', 'missing-channel-id')

    screen = resolve_screen_for_text('Режим: авто', chat_id=1401, identity=identity)
    assert 'Не получилось выполнить действие' in screen.text
    assert 'Канал не найден' in screen.text



def test_unmatched_input_logs_diagnostic_and_fallback_to_main_menu(caplog):
    chat_id = 1500
    session_store.clear(chat_id)

    with caplog.at_level(logging.INFO):
        screen = resolve_screen_for_text('какая-то неизвестная команда', chat_id=chat_id)

    assert 'Помогаю запустить Telegram-канал' in screen.text

    diagnostics = [record for record in caplog.records if record.message == 'bot diagnostic']
    assert diagnostics
    assert diagnostics[-1].diagnostic_code == 'unmatched_input'
    assert diagnostics[-1].kind == 'fallback_to_main_menu'

    resolved = [record for record in caplog.records if record.message == 'bot screen resolved']
    assert resolved
    assert resolved[-1].screen == 'main_menu'
    assert resolved[-1].reason == 'fallback_unmatched_input'



def test_open_project_without_restorable_context_logs_diagnostic(fake_db, monkeypatch, caplog):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    chat_id = 1501
    session_store.clear(chat_id)
    identity = TelegramIdentity(telegram_user_id='tg-missing-project', telegram_username='missingproject')

    with caplog.at_level(logging.WARNING):
        screen = resolve_screen_for_text('Открыть проект', chat_id=chat_id, identity=identity)

    assert 'Не удалось восстановить текущий проект из сессии' in screen.text

    diagnostics = [record for record in caplog.records if record.message == 'bot diagnostic']
    assert diagnostics
    assert diagnostics[-1].diagnostic_code == 'project_context_missing'
    assert diagnostics[-1].kind == 'project_context_missing'



def test_temporary_telegram_error_is_humanized_for_user(fake_db, monkeypatch):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-error-3', telegram_username='err3')
    session_store.set_meta(1402, 'channel_id', 'missing-channel-id')

    def _boom(_identity, _chat_id, _mode):
        raise RuntimeError('Too Many Requests: retry later')

    monkeypatch.setattr('app.bot.app.change_channel_mode_from_backend', _boom)

    screen = resolve_screen_for_text('Режим: авто', chat_id=1402, identity=identity)
    assert 'Не получилось выполнить действие' in screen.text
    assert 'Telegram временно ограничил запросы' in screen.text
    assert 'Что делать: повторить попытку позже' in screen.text



def test_publication_detail_screen_humanizes_temporary_error_with_retry_hint():
    screen = publication_detail_screen(
        title='Test publication',
        status='failed',
        scheduled_for=None,
        error_message='Telegram HTTP 429: Too Many Requests: retry later',
    )

    assert 'Временная ошибка Telegram/сети' in screen['text']
    assert 'Следующее действие: подожди и попробуй «Опубликовать сейчас» ещё раз' in screen['text']



def test_publication_detail_screen_humanizes_terminal_error_with_operator_hint():
    screen = publication_detail_screen(
        title='Test publication',
        status='failed',
        scheduled_for=None,
        error_message='bot was blocked by the user',
    )

    assert 'Похоже на постоянную ошибку публикации' in screen['text']
    assert 'проверь права бота, канал и конфиг подключения' in screen['text'].lower()



def test_wizard_flow_emits_flow_observability_events(caplog):
    chat_id = 1600
    session_store.clear(chat_id)

    with caplog.at_level(logging.INFO):
        resolve_screen_for_text('Создать канал', chat_id=chat_id)
        resolve_screen_for_text('Начать', chat_id=chat_id)
        resolve_screen_for_text('Alpha Channel', chat_id=chat_id)

    flow_events = [record for record in caplog.records if record.message == 'bot flow event']
    assert flow_events
    assert any(record.flow == 'wizard' and record.event == 'wizard_started' for record in flow_events)
    assert any(record.flow == 'wizard' and record.event == 'wizard_step_opened' and record.step == 'name' for record in flow_events)
    assert any(record.flow == 'wizard' and record.event == 'wizard_step_completed' and record.step == 'name' for record in flow_events)
    assert any(record.flow == 'wizard' and record.event == 'wizard_step_opened' and record.step == 'niche' for record in flow_events)



def test_project_and_channel_connection_emit_flow_events(monkeypatch, caplog):
    chat_id = 1601
    session_store.clear(chat_id)
    session_store.start(chat_id)
    session_store.update_state(
        chat_id,
        name='Bridge Channel',
        niche='AI',
        language='Русский',
        goal='Личный бренд',
        content_format='Аналитика',
        posting_frequency='Ежедневно',
        channel_ref='@bridge_channel',
    )

    identity = TelegramIdentity(telegram_user_id='tg-flow-1', telegram_username='flow1')

    def _fake_create(_chat_id, _identity):
        session_store.set_meta(_chat_id, 'project_id', 'project-321')
        return 'project-321'

    def _fake_connect(_chat_id, _identity, _ref):
        session_store.set_meta(_chat_id, 'channel_id', 'channel-654')
        return 'channel-654', 'connected'

    monkeypatch.setattr('app.bot.app.create_project_from_wizard_state', _fake_create)
    monkeypatch.setattr('app.bot.app.connect_channel_from_wizard_state', _fake_connect)

    with caplog.at_level(logging.INFO):
        resolve_screen_for_text('Подтвердить проект', chat_id=chat_id, identity=identity)
        resolve_screen_for_text('Проверить подключение', chat_id=chat_id, identity=identity)

    flow_events = [record for record in caplog.records if record.message == 'bot flow event']
    assert any(record.flow == 'wizard' and record.event == 'project_created' and record.project_id == 'project-321' for record in flow_events)
    assert any(record.flow == 'channel' and record.event == 'channel_connection_checked' and record.channel_id == 'channel-654' for record in flow_events)
    assert any(record.flow == 'channel' and record.event == 'channel_connected' and record.channel_id == 'channel-654' for record in flow_events)



def test_publication_flow_emits_flow_events(fake_db, monkeypatch, caplog):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-flow-2', telegram_username='flow2')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Pub Flow', language='ru'))
    channel = bridge.connect_channel(project.id, 'Pub Flow', 'pub_flow')
    task = bridge.create_task(project.id, 'Publication Event Task')
    draft = Draft(content_task_id=task.id, text='Draft body', status=DraftStatus.CREATED, version=1)
    fake_db.add(draft)
    fake_db.commit()
    fake_db.refresh(draft)

    session_store.set_meta(1602, 'project_id', str(project.id))
    session_store.set_meta(1602, 'channel_id', str(channel.id))
    session_store.set_meta(1602, 'draft_id', str(draft.id))
    session_store.set_step(1602, 'draft_detail')

    with caplog.at_level(logging.INFO):
        resolve_screen_for_text('Подтвердить', chat_id=1602, identity=identity)
        resolve_screen_for_text('Создать публикацию', chat_id=1602, identity=identity)
        resolve_screen_for_text('Опубликовать сейчас', chat_id=1602, identity=identity)

    flow_events = [record for record in caplog.records if record.message == 'bot flow event']
    assert any(record.flow == 'draft' and record.event == 'draft_approved' for record in flow_events)
    assert any(record.flow == 'publication' and record.event == 'publication_created' for record in flow_events)
    assert any(record.flow == 'publication' and record.event == 'publication_publish_now_requested' for record in flow_events)



def test_render_state_logs_diagnostic_when_draft_detail_cannot_be_restored(fake_db, monkeypatch, caplog):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-diag-1', telegram_username='diag1')
    project = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity).create_project(
        __import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Diag Draft', language='ru')
    )

    chat_id = 1700
    session_store.clear(chat_id)
    session_store.set_meta(chat_id, 'project_id', str(project.id))
    session_store.set_meta(chat_id, 'draft_id', 'missing-draft-id')
    session_store.set_step(chat_id, 'draft_edit_text')

    with caplog.at_level(logging.WARNING):
        screen = resolve_screen_for_text('Отмена редактирования', chat_id=chat_id, identity=identity)

    diagnostics = [record for record in caplog.records if record.message == 'bot diagnostic']
    assert any(record.diagnostic_code == 'draft_detail_missing' for record in diagnostics)
    assert 'Помогаю запустить Telegram-канал' in screen.text



def test_publications_screen_missing_context_logs_diagnostic(fake_db, monkeypatch, caplog):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-diag-2', telegram_username='diag2')
    chat_id = 1701
    session_store.clear(chat_id)

    with caplog.at_level(logging.WARNING):
        screen = resolve_screen_for_text('Публикации', chat_id=chat_id, identity=identity)

    diagnostics = [record for record in caplog.records if record.message == 'bot diagnostic']
    assert any(record.diagnostic_code == 'publications_project_context_missing' for record in diagnostics)
    assert any(record.diagnostic_code == 'unmatched_input' for record in diagnostics)
    assert 'Помогаю запустить Telegram-канал' in screen.text



def test_open_unknown_draft_logs_selection_diagnostic(fake_db, monkeypatch, caplog):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-diag-3', telegram_username='diag3')
    bridge = __import__('app.bot.backend_bridge', fromlist=['BotBackendBridge']).BotBackendBridge(fake_db, identity)
    project = bridge.create_project(__import__('app.schemas.project', fromlist=['ProjectCreate']).ProjectCreate(name='Diag Project', language='ru'))

    chat_id = 1702
    session_store.clear(chat_id)
    session_store.set_meta(chat_id, 'project_id', str(project.id))

    with caplog.at_level(logging.WARNING):
        screen = resolve_screen_for_text('Unknown draft title', chat_id=chat_id, identity=identity)

    diagnostics = [record for record in caplog.records if record.message == 'bot diagnostic']
    assert any(record.diagnostic_code == 'draft_not_found_for_selection' for record in diagnostics)
    assert 'Помогаю запустить Telegram-канал' in screen.text



def test_create_publication_without_context_logs_diagnostic(fake_db, monkeypatch, caplog):
    monkeypatch.setattr('app.bot.app.SessionLocal', lambda: fake_db)

    identity = TelegramIdentity(telegram_user_id='tg-diag-4', telegram_username='diag4')
    chat_id = 1703
    session_store.clear(chat_id)

    with caplog.at_level(logging.WARNING):
        screen = resolve_screen_for_text('Создать публикацию', chat_id=chat_id, identity=identity)

    diagnostics = [record for record in caplog.records if record.message == 'bot diagnostic']
    assert any(record.diagnostic_code == 'publication_create_missing_context' for record in diagnostics)
    assert 'Помогаю запустить Telegram-канал' in screen.text
