from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from app.bot.backend_bridge import BotBackendBridge
from app.bot.screens import AgentSummary, ContentPlanSummary, DraftSummary, PublicationSummary
from app.bot.ux import MODE_TO_BACKEND, parse_user_schedule
from app.bot.service import BotScreen, BotService
from app.bot.wizard import ProjectWizardState
from app.core.database import SessionLocal
from app.core.config import settings
from app.services.identity import TelegramIdentity

router = Router()
service = BotService()
logger = logging.getLogger(__name__)


USER_ERROR_MAP = {
    'Only approved drafts can be queued for publication': 'Этот черновик ещё не подтверждён. Сначала открой его и нажми «Подтвердить», потом создавай публикацию.',
    'Draft not found': 'Черновик не найден. Возможно, он был удалён, не сохранился или уже недоступен в текущем проекте.',
    'Channel not found': 'Канал не найден. Открой нужный проект заново или переподключи канал.',
    'Publication not found': 'Публикация не найдена. Возможно, она уже была отменена или ещё не создана.',
    'Project not found': 'Проект не найден. Попробуй открыть его из списка «Мои каналы».',
}


TEMPORARY_ERROR_HINTS = {
    'Too Many Requests': 'Telegram временно ограничил запросы. Подожди немного и попробуй снова.',
    'retry later': 'Telegram временно ограничил запросы. Подожди немного и попробуй снова.',
    'timed out': 'Telegram временно не ответил вовремя. Это похоже на временный сбой — попробуй ещё раз чуть позже.',
    'timeout': 'Telegram временно не ответил вовремя. Это похоже на временный сбой — попробуй ещё раз чуть позже.',
    'Temporary failure': 'Похоже на временную ошибку Telegram или сети. Повтори действие чуть позже.',
    'network error': 'Похоже на временную сетевую ошибку. Повтори действие чуть позже.',
    'HTTP 429': 'Telegram временно ограничил отправку. Подожди и повтори публикацию позже.',
    'HTTP 500': 'У Telegram временный серверный сбой. Повтори публикацию чуть позже.',
    'HTTP 502': 'У Telegram временный шлюзовый сбой. Повтори публикацию чуть позже.',
    'HTTP 503': 'Telegram временно недоступен. Повтори публикацию чуть позже.',
    'HTTP 504': 'Telegram не успел ответить вовремя. Повтори публикацию чуть позже.',
}


@dataclass(slots=True)
class TelegramUiSession:
    wizard: ProjectWizardState = field(default_factory=ProjectWizardState)
    current_screen: str = 'main_menu'
    screen_stack: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)
    last_input: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WizardSessionStore:
    def __init__(self):
        self._sessions_by_chat: dict[int, TelegramUiSession] = {}
        self._chat_by_user: dict[str, int] = {}

    def _touch(self, session: TelegramUiSession):
        session.updated_at = datetime.now(timezone.utc)

    def _ensure(self, chat_id: int) -> TelegramUiSession:
        session = self._sessions_by_chat.get(chat_id)
        if session is None:
            session = TelegramUiSession()
            self._sessions_by_chat[chat_id] = session
        self._touch(session)
        return session

    def bind_identity(self, chat_id: int, identity: TelegramIdentity | None):
        if identity is None or not identity.telegram_user_id:
            return
        self._chat_by_user[identity.telegram_user_id] = chat_id
        self._ensure(chat_id)

    def restore_for_identity(self, chat_id: int, identity: TelegramIdentity | None) -> TelegramUiSession:
        session = self._ensure(chat_id)
        if identity is None or not identity.telegram_user_id:
            return session
        bound_chat_id = self._chat_by_user.get(identity.telegram_user_id)
        if bound_chat_id is None:
            self._chat_by_user[identity.telegram_user_id] = chat_id
            return session
        if bound_chat_id == chat_id:
            return session
        old_session = self._sessions_by_chat.get(bound_chat_id)
        if old_session is None:
            self._chat_by_user[identity.telegram_user_id] = chat_id
            return session
        self._sessions_by_chat[chat_id] = old_session
        self._sessions_by_chat.pop(bound_chat_id, None)
        self._chat_by_user[identity.telegram_user_id] = chat_id
        self._touch(old_session)
        return old_session

    def start(self, chat_id: int):
        session = self._ensure(chat_id)
        session.wizard = ProjectWizardState()
        session.current_screen = 'wizard_start'
        session.screen_stack = ['main_menu']
        session.meta = {}
        session.last_input = None
        self._touch(session)

    def clear(self, chat_id: int, keep_context: bool = False):
        session = self._ensure(chat_id)
        session.wizard = ProjectWizardState()
        session.current_screen = 'main_menu'
        session.screen_stack = []
        session.last_input = None
        if not keep_context:
            session.meta = {}
        self._touch(session)

    def get_state(self, chat_id: int) -> ProjectWizardState:
        return self._ensure(chat_id).wizard

    def get_step(self, chat_id: int) -> str | None:
        return self._ensure(chat_id).current_screen

    def set_step(self, chat_id: int, step: str, push_current: bool = False):
        session = self._ensure(chat_id)
        if push_current and session.current_screen and session.current_screen != step:
            if not session.screen_stack or session.screen_stack[-1] != session.current_screen:
                session.screen_stack.append(session.current_screen)
        session.current_screen = step
        self._touch(session)

    def go_back(self, chat_id: int) -> str:
        session = self._ensure(chat_id)
        if session.screen_stack:
            session.current_screen = session.screen_stack.pop()
        else:
            session.current_screen = 'main_menu'
        self._touch(session)
        return session.current_screen

    def update_state(self, chat_id: int, **kwargs) -> ProjectWizardState:
        session = self._ensure(chat_id)
        session.wizard = replace(session.wizard, **kwargs)
        self._touch(session)
        return session.wizard

    def set_meta(self, chat_id: int, key: str, value: str):
        session = self._ensure(chat_id)
        session.meta[key] = value
        self._touch(session)

    def get_meta(self, chat_id: int, key: str) -> str | None:
        return self._ensure(chat_id).meta.get(key)

    def delete_meta(self, chat_id: int, key: str):
        session = self._ensure(chat_id)
        session.meta.pop(key, None)
        self._touch(session)

    def remember_input(self, chat_id: int, text: str | None):
        session = self._ensure(chat_id)
        session.last_input = text
        self._touch(session)

    def snapshot(self, chat_id: int) -> TelegramUiSession:
        return self._ensure(chat_id)


session_store = WizardSessionStore()


def build_reply_keyboard(screen: BotScreen) -> ReplyKeyboardMarkup | None:
    if not screen.buttons:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in screen.buttons],
        resize_keyboard=True,
        is_persistent=True,
    )


def _wizard_screen_to_bot_screen(wizard_screen) -> BotScreen:
    return BotScreen(text=wizard_screen.text, buttons=wizard_screen.buttons)


def _humanize_bot_error(exc: Exception) -> str:
    message = str(exc)
    for raw, human in USER_ERROR_MAP.items():
        if raw == message or raw in message:
            return human
    lowered = message.lower()
    for raw, human in TEMPORARY_ERROR_HINTS.items():
        if raw.lower() in lowered:
            return f'{human} Что делать: повторить попытку позже, не меняя проект и черновик.'
    return f'Техническая причина: {message}'


def _log_bot_screen(screen_name: str, *, chat_id: int | None, identity: TelegramIdentity | None, source_screen: str | None = None, reason: str | None = None, input_text: str | None = None, diagnostic_code: str | None = None):
    logger.info(
        'bot screen resolved',
        extra={
            'chat_id': chat_id,
            'telegram_user_id': getattr(identity, 'telegram_user_id', None),
            'screen': screen_name,
            'source_screen': source_screen,
            'reason': reason,
            'input': input_text,
            'diagnostic_code': diagnostic_code,
        },
    )


def _log_bot_diagnostic(kind: str, *, chat_id: int | None, identity: TelegramIdentity | None, source_screen: str | None = None, input_text: str | None = None, diagnostic_code: str, detail: str | None = None):
    logger.warning(
        'bot diagnostic',
        extra={
            'kind': kind,
            'chat_id': chat_id,
            'telegram_user_id': getattr(identity, 'telegram_user_id', None),
            'source_screen': source_screen,
            'input': input_text,
            'diagnostic_code': diagnostic_code,
            'detail': detail,
        },
    )


def _log_bot_flow_event(
    flow: str,
    event: str,
    *,
    chat_id: int | None,
    identity: TelegramIdentity | None,
    source_screen: str | None = None,
    input_text: str | None = None,
    project_id: str | None = None,
    channel_id: str | None = None,
    draft_id: str | None = None,
    publication_id: str | None = None,
    extra_data: dict | None = None,
):
    payload = {
        'flow': flow,
        'event': event,
        'chat_id': chat_id,
        'telegram_user_id': getattr(identity, 'telegram_user_id', None),
        'source_screen': source_screen,
        'input': input_text,
        'project_id': project_id,
        'channel_id': channel_id,
        'draft_id': draft_id,
        'publication_id': publication_id,
    }
    if extra_data:
        payload.update(extra_data)
    logger.info('bot flow event', extra=payload)


def _error_screen_for_exception(
    exc: Exception,
    buttons: list[list[str]] | None = None,
    *,
    chat_id: int | None = None,
    identity: TelegramIdentity | None = None,
    source_screen: str | None = None,
    input_text: str | None = None,
    diagnostic_code: str = 'action_failed',
) -> BotScreen:
    error_text = str(exc)
    lowered = error_text.lower()
    retryable = any(marker.lower() in lowered for marker in TEMPORARY_ERROR_HINTS)
    logger.warning(
        'bot action failed',
        extra={
            'error': error_text,
            'chat_id': chat_id,
            'telegram_user_id': getattr(identity, 'telegram_user_id', None),
            'source_screen': source_screen,
            'input': input_text,
            'diagnostic_code': diagnostic_code,
            'retryable': retryable,
        },
    )
    return service.error_screen(_humanize_bot_error(exc), next_steps=buttons)


def _render_screen_by_state(step: str, chat_id: int | None, identity: TelegramIdentity | None) -> BotScreen:
    source_screen = step
    if step == 'main_menu':
        return service.main_menu_screen()
    if step == 'wizard_start':
        return _wizard_screen_to_bot_screen(service.wizard_start_screen())
    if step == 'name':
        return _wizard_screen_to_bot_screen(service.wizard_name_screen())
    if step == 'niche':
        return _wizard_screen_to_bot_screen(service.wizard_niche_screen())
    if step == 'language':
        return _wizard_screen_to_bot_screen(service.wizard_language_screen())
    if step == 'goal':
        return _wizard_screen_to_bot_screen(service.wizard_goal_screen())
    if step == 'content_format':
        return _wizard_screen_to_bot_screen(service.wizard_content_format_screen())
    if step == 'posting_frequency':
        return _wizard_screen_to_bot_screen(service.wizard_posting_frequency_screen())
    if step == 'summary' and chat_id is not None:
        return _wizard_screen_to_bot_screen(service.wizard_summary_screen(session_store.get_state(chat_id)))
    if step == 'preset':
        return _wizard_screen_to_bot_screen(service.wizard_preset_screen())
    if step == 'channel_connect':
        return _wizard_screen_to_bot_screen(service.wizard_channel_connect_screen())
    if step == 'project_ready':
        return service.project_ready_screen()
    if step == 'how_it_works':
        return service.how_it_works_screen()
    if step == 'help':
        return service.help_screen()
    if step == 'my_channels' and identity is not None:
        return my_channels_screen_from_backend(identity)
    if step == 'channel_dashboard' and chat_id is not None and identity is not None:
        channel_title = session_store.get_meta(chat_id, 'channel_title')
        if channel_title:
            dashboard = open_channel_dashboard_from_backend(identity, channel_title, chat_id=chat_id)
            if dashboard is not None:
                return dashboard
            _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='channel_dashboard_missing', detail='Channel dashboard could not be opened from stored channel title.')
        resumed = resume_current_project_from_backend(identity, chat_id)
        if resumed is not None:
            return resumed
    if step == 'channel_settings' and chat_id is not None and identity is not None:
        screen = channel_settings_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='channel_settings_missing_context', detail='Channel settings screen could not be opened because project context was missing or unavailable.')
    if step == 'channel_agents' and chat_id is not None and identity is not None:
        screen = channel_agents_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='channel_agents_missing_context', detail='Channel agents screen could not be opened because project context was missing or unavailable.')
    if step == 'channel_content_plan' and chat_id is not None and identity is not None:
        screen = channel_content_plan_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='content_plan_screen_missing_context', detail='Content plan screen could not be opened because project context was missing or unavailable.')
    if step == 'channel_drafts' and chat_id is not None and identity is not None:
        screen = channel_drafts_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='drafts_screen_missing_context', detail='Drafts screen could not be opened because project context was missing or unavailable.')
    if step == 'draft_detail' and chat_id is not None and identity is not None:
        screen = open_draft_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='draft_detail_missing', detail='Draft detail screen could not be opened because the draft id/title was missing or no longer matched an existing draft.')
    if step == 'channel_publications' and chat_id is not None and identity is not None:
        screen = publications_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='publications_screen_missing_context', detail='Publications screen could not be opened because project context was missing or unavailable.')
    if step == 'publication_detail' and chat_id is not None and identity is not None:
        screen = open_publication_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='publication_detail_missing', detail='Publication detail screen could not be opened because the publication id/title was missing or publication no longer existed.')
    if step == 'channel_mode' and chat_id is not None and identity is not None:
        screen = channel_mode_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
        _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='channel_mode_missing_context', detail='Channel mode screen could not be opened because channel context was missing or unavailable.')
    _log_bot_diagnostic('screen_unavailable', chat_id=chat_id, identity=identity, source_screen=source_screen, diagnostic_code='screen_restore_fallback_main_menu', detail='Requested screen could not be restored; falling back to main menu.')
    return service.main_menu_screen()


def create_project_from_wizard_state(chat_id: int, identity: TelegramIdentity) -> str:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        payload = service.project_create_payload_from_wizard_state(session_store.get_state(chat_id))
        project = bridge.create_project(payload)
        session_store.set_meta(chat_id, 'project_id', str(project.id))
        return str(project.id)
    finally:
        db.close()


def apply_preset_from_wizard_state(chat_id: int, identity: TelegramIdentity, preset_label: str) -> int:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        preset_code = {
            '3 агента — Быстрый старт': 'starter_3',
            '5 агентов — Сбалансировано': 'balanced_5',
            '7 агентов — Полная редакция': 'full_7',
        }[preset_label]
        agents = bridge.apply_preset(project_id, preset_code)
        session_store.set_meta(chat_id, 'preset_code', preset_code)
        session_store.set_meta(chat_id, 'agents_count', str(len(agents)))
        return len(agents)
    finally:
        db.close()


def connect_channel_from_wizard_state(chat_id: int, identity: TelegramIdentity, channel_ref: str) -> tuple[str, str]:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        channel = bridge.connect_channel(project_id, channel_title=channel_ref, channel_username=channel_ref.lstrip('@'))
        session_store.set_meta(chat_id, 'channel_id', str(channel.id))
        session_store.set_meta(chat_id, 'channel_title', channel.channel_title)
        session_store.update_state(chat_id, channel_ref=channel_ref, connection_confirmed=True)
        return str(channel.id), 'connected'
    finally:
        db.close()


def my_channels_screen_from_backend(identity: TelegramIdentity) -> BotScreen:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        channels = bridge.my_channels()
        summaries = [
            __import__('app.bot.screens', fromlist=['ChannelSummary']).ChannelSummary(
                id=str(channel.id),
                title=channel.channel_title,
                mode=channel.publish_mode.value if hasattr(channel.publish_mode, 'value') else str(channel.publish_mode),
                status='connected' if channel.is_connected else 'needs_attention',
            )
            for channel in channels
        ]
        return service.my_channels_screen(summaries)
    finally:
        db.close()


def open_channel_dashboard_from_backend(identity: TelegramIdentity, channel_title: str, chat_id: int | None = None) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        channel = bridge.find_channel_by_title(channel_title)
        if channel is None:
            return None
        if chat_id is not None:
            session_store.set_meta(chat_id, 'project_id', str(channel.project_id))
            session_store.set_meta(chat_id, 'channel_id', str(channel.id))
            session_store.set_meta(chat_id, 'channel_title', channel.channel_title)
        agents_count = bridge.count_agents_for_project(channel.project_id)
        content_plans_count = bridge.count_content_plans_for_project(channel.project_id)
        drafts_count = bridge.count_drafts_for_project(channel.project_id)
        return service.channel_dashboard_screen(
            title=channel.channel_title,
            mode=channel.publish_mode.value if hasattr(channel.publish_mode, 'value') else str(channel.publish_mode),
            agents_count=agents_count,
            content_plans_count=content_plans_count,
            drafts_count=drafts_count,
        )
    finally:
        db.close()


def resume_current_project_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        channel_id = session_store.get_meta(chat_id, 'channel_id')
        if channel_id:
            channel = bridge.get_channel(channel_id)
            session_store.set_meta(chat_id, 'project_id', str(channel.project_id))
            session_store.set_meta(chat_id, 'channel_id', str(channel.id))
            session_store.set_meta(chat_id, 'channel_title', channel.channel_title)
            agents_count = bridge.count_agents_for_project(channel.project_id)
            content_plans_count = bridge.count_content_plans_for_project(channel.project_id)
            drafts_count = bridge.count_drafts_for_project(channel.project_id)
            return service.channel_dashboard_screen(
                title=channel.channel_title,
                mode=channel.publish_mode.value if hasattr(channel.publish_mode, 'value') else str(channel.publish_mode),
                agents_count=agents_count,
                content_plans_count=content_plans_count,
                drafts_count=drafts_count,
            )

        project_id = session_store.get_meta(chat_id, 'project_id')
        if project_id:
            channels = bridge.my_channels()
            for channel in channels:
                if str(channel.project_id) == str(project_id):
                    session_store.set_meta(chat_id, 'channel_id', str(channel.id))
                    session_store.set_meta(chat_id, 'channel_title', channel.channel_title)
                    agents_count = bridge.count_agents_for_project(channel.project_id)
                    content_plans_count = bridge.count_content_plans_for_project(channel.project_id)
                    drafts_count = bridge.count_drafts_for_project(channel.project_id)
                    return service.channel_dashboard_screen(
                        title=channel.channel_title,
                        mode=channel.publish_mode.value if hasattr(channel.publish_mode, 'value') else str(channel.publish_mode),
                        agents_count=agents_count,
                        content_plans_count=content_plans_count,
                        drafts_count=drafts_count,
                    )
        return None
    finally:
        db.close()


def channel_settings_screen_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            return None
        project = bridge.get_project(project_id)
        operation_mode = project.operation_mode.value if hasattr(project.operation_mode, 'value') else str(project.operation_mode)
        return service.channel_settings_screen(
            project_name=project.name,
            topic=project.topic or project.niche,
            language=project.language,
            content_format=project.content_format,
            posting_frequency=project.posting_frequency,
            operation_mode=operation_mode,
        )
    finally:
        db.close()


def channel_agents_screen_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            return None
        agents = [
            AgentSummary(
                id=str(agent.id),
                name=agent.display_name or agent.name,
                role=agent.role.value if hasattr(agent.role, 'value') else str(agent.role),
                model=agent.model,
                enabled=agent.is_enabled,
            )
            for agent in bridge.list_agents_for_project(project_id)
        ]
        return service.channel_agents_screen(agents)
    finally:
        db.close()


def channel_content_plan_screen_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            return None
        tasks = bridge.list_tasks_for_project(project_id)
        tasks_by_plan: dict[str, int] = {}
        for task in tasks:
            plan_id = str(task.content_plan_id) if task.content_plan_id else ''
            tasks_by_plan[plan_id] = tasks_by_plan.get(plan_id, 0) + 1
        plans = [
            ContentPlanSummary(
                id=str(plan.id),
                period=plan.period_type.value if hasattr(plan.period_type, 'value') else str(plan.period_type),
                date_range=f'{plan.start_date} → {plan.end_date}',
                status=plan.status,
                tasks_count=tasks_by_plan.get(str(plan.id), 0),
            )
            for plan in bridge.list_content_plans_for_project(project_id)
        ]
        return service.channel_content_plan_screen(plans, tasks_total=len(tasks))
    finally:
        db.close()


def create_sample_content_plan_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            return None
        plan, tasks, _drafts = bridge.ensure_sample_pipeline(project_id, tasks_count=0, drafts_count=0)
        return BotScreen(
            text=(
                'Контент-план создан.\n\n'
                f'Период: {plan.start_date} → {plan.end_date}\n'
                f'Статус: {plan.status}\n'
                f'Задач пока: {len(tasks)}\n\n'
                'Следующий шаг один: нажми «Сгенерировать 10 идей». '
                'Я подготовлю темы, из которых потом можно собрать первые черновики.'
            ),
            buttons=[['Сгенерировать 10 идей'], ['Контент-план'], ['Главное меню']],
        )
    finally:
        db.close()


def generate_sample_tasks_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            return None
        plan, tasks, _drafts = bridge.ensure_sample_pipeline(project_id, tasks_count=10, drafts_count=0)
        return BotScreen(
            text=(
                '10 идей готовы.\n\n'
                f'План: {plan.start_date} → {plan.end_date}\n'
                f'Всего задач: {len(tasks)}\n'
                f'Первая идея: {tasks[0].title if tasks else "—"}\n\n'
                'Следующий шаг один: нажми «Создать 3 черновика». '
                'После этого можно будет открыть тексты, подтвердить лучший и превратить его в публикацию.'
            ),
            buttons=[['Создать 3 черновика'], ['Контент-план'], ['Главное меню']],
        )
    finally:
        db.close()


def generate_sample_drafts_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            return None
        _plan, _tasks, drafts = bridge.ensure_sample_pipeline(project_id, tasks_count=10, drafts_count=3)
        if drafts:
            first = drafts[0]
            task = first.content_task
            session_store.set_meta(chat_id, 'draft_id', str(first.id))
            session_store.set_meta(chat_id, 'draft_title', task.title if task is not None else 'Без задачи')
        return BotScreen(
            text=(
                '3 черновика готовы.\n\n'
                f'Всего черновиков в проекте: {len(drafts)}\n'
                'Следующий шаг один: нажми «Черновики», открой лучший текст и подтверди его. '
                'Потом я проведу к созданию публикации без помощи разработчика.'
            ),
            buttons=[['Черновики'], ['Публикации'], ['Главное меню']],
        )
    finally:
        db.close()


def channel_drafts_screen_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='channel_drafts', diagnostic_code='drafts_project_context_missing', detail='Drafts list was requested without project context, so no drafts screen could be shown.')
            return None
        drafts = [
            DraftSummary(
                id=str(draft.id),
                title=(task.title if task is not None else 'Без задачи'),
                status=draft.status.value if hasattr(draft.status, 'value') else str(draft.status),
                version=draft.version,
            )
            for draft, task in bridge.list_drafts_for_project(project_id)
        ]
        return service.channel_drafts_screen(drafts)
    finally:
        db.close()


def open_draft_screen_from_backend(identity: TelegramIdentity, chat_id: int, draft_title: str | None = None) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='draft_detail', input_text=draft_title, diagnostic_code='draft_project_context_missing', detail='Draft detail was requested without project context, so no draft could be opened.')
            return None
        pair = None
        if draft_title:
            pair = bridge.find_draft_for_project_by_title(project_id, draft_title)
        elif session_store.get_meta(chat_id, 'draft_id'):
            try:
                draft = bridge.get_draft(session_store.get_meta(chat_id, 'draft_id'))
            except Exception:
                _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='draft_detail', input_text=draft_title, diagnostic_code='draft_not_found_for_selection', detail='Stored draft id no longer resolves to an existing draft.')
                return None
            task = draft.content_task
            pair = (draft, task)
        if pair is None:
            _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='draft_detail', input_text=draft_title, diagnostic_code='draft_not_found_for_selection', detail='Draft detail was requested, but the selected draft title/id did not match any draft in the current project.')
            return None
        draft, task = pair
        session_store.set_meta(chat_id, 'draft_id', str(draft.id))
        session_store.set_meta(chat_id, 'draft_title', task.title if task is not None else 'Без задачи')
        status = draft.status.value if hasattr(draft.status, 'value') else str(draft.status)
        return service.draft_detail_screen(
            title=task.title if task is not None else 'Без задачи',
            status=status,
            version=draft.version,
            text=draft.text,
            created_by_agent=draft.created_by_agent,
        )
    finally:
        db.close()


def perform_draft_action_from_backend(identity: TelegramIdentity, chat_id: int, action: str) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        draft_id = session_store.get_meta(chat_id, 'draft_id')
        if not draft_id:
            return None
        if action == 'approve':
            draft = bridge.approve_draft(draft_id)
            action_label = 'approve'
        elif action == 'reject':
            draft = bridge.reject_draft(draft_id)
            action_label = 'reject'
        elif action == 'regenerate':
            draft = bridge.regenerate_draft(draft_id)
            action_label = 'regenerate'
        else:
            return BotScreen(
                text=(
                    'Пришли новый текст черновика следующим сообщением.\n\n'
                    'Что можно сделать:\n'
                    '• отправить полностью новую версию текста\n'
                    '• или нажать «Отмена редактирования», чтобы ничего не менять'
                ),
                buttons=[['Отмена редактирования'], ['Черновики'], ['Главное меню']],
            )
        task = draft.content_task
        status = draft.status.value if hasattr(draft.status, 'value') else str(draft.status)
        return service.draft_action_result_screen(
            action=action_label,
            title=task.title if task is not None else 'Без задачи',
            status=status,
            version=draft.version,
            text=draft.text,
            created_by_agent=draft.created_by_agent,
        )
    finally:
        db.close()


def publications_screen_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='channel_publications', diagnostic_code='publications_project_context_missing', detail='Publications list was requested without project context, so no publications screen could be shown.')
            return None
        publications = [
            PublicationSummary(
                id=str(publication.id),
                title=task.title if task is not None else 'Без задачи',
                status=publication.status.value if hasattr(publication.status, 'value') else str(publication.status),
                scheduled_for=publication.scheduled_for.isoformat() if publication.scheduled_for else None,
            )
            for publication, draft, task in bridge.list_publications_for_project(project_id)
        ]
        return service.publications_screen(publications)
    finally:
        db.close()


def open_publication_screen_from_backend(identity: TelegramIdentity, chat_id: int, title: str | None = None) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        project_id = session_store.get_meta(chat_id, 'project_id')
        if not project_id:
            _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='publication_detail', input_text=title, diagnostic_code='publication_project_context_missing', detail='Publication detail was requested without project context, so no publication could be opened.')
            return None
        item = None
        if title:
            item = bridge.find_publication_for_project_by_title(project_id, title)
        elif session_store.get_meta(chat_id, 'publication_id'):
            try:
                publication = bridge.get_publication(session_store.get_meta(chat_id, 'publication_id'))
            except Exception:
                _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='publication_detail', input_text=title, diagnostic_code='publication_not_found_for_selection', detail='Stored publication id no longer resolves to an existing publication.')
                return None
            draft = publication.draft
            task = draft.content_task if draft else None
            item = (publication, draft, task)
        if item is None:
            _log_bot_diagnostic('button_or_screen_missing', chat_id=chat_id, identity=identity, source_screen='publication_detail', input_text=title, diagnostic_code='publication_not_found_for_selection', detail='Publication detail was requested, but the selected publication title/id did not match any publication in the current project.')
            return None
        publication, draft, task = item
        session_store.set_meta(chat_id, 'publication_id', str(publication.id))
        session_store.set_meta(chat_id, 'publication_title', task.title if task is not None else 'Без задачи')
        return service.publication_detail_screen(
            title=task.title if task is not None else 'Без задачи',
            status=publication.status.value if hasattr(publication.status, 'value') else str(publication.status),
            scheduled_for=publication.scheduled_for.isoformat() if publication.scheduled_for else None,
            error_message=publication.error_message,
        )
    finally:
        db.close()


def create_publication_from_current_draft(identity: TelegramIdentity, chat_id: int, scheduled: bool = False) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        draft_id = session_store.get_meta(chat_id, 'draft_id')
        channel_id = session_store.get_meta(chat_id, 'channel_id')
        if not draft_id or not channel_id:
            _log_bot_diagnostic('publication_unavailable', chat_id=chat_id, identity=identity, source_screen='publication_create', diagnostic_code='publication_create_missing_context', detail='Publication creation was requested without active draft or channel context.')
            return None
        if scheduled:
            return BotScreen(
                text=(
                    'Пришли время публикации следующим сообщением в формате:\n'
                    'YYYY-MM-DD HH:MM UTC\n\n'
                    'Пример: 2026-03-20 10:00 UTC'
                ),
                buttons=[['Отмена планирования'], ['Главное меню']],
            )
        publication = bridge.create_publication(draft_id, channel_id, scheduled_for=None)
        task = publication.draft.content_task
        session_store.set_meta(chat_id, 'publication_id', str(publication.id))
        session_store.set_meta(chat_id, 'publication_title', task.title if task is not None else 'Без задачи')
        return service.publication_action_result_screen(
            action='create_publication',
            title=task.title if task is not None else 'Без задачи',
            status=publication.status.value if hasattr(publication.status, 'value') else str(publication.status),
            scheduled_for=publication.scheduled_for.isoformat() if publication.scheduled_for else None,
            error_message=publication.error_message,
        )
    finally:
        db.close()


def perform_publication_action_from_backend(identity: TelegramIdentity, chat_id: int, action: str) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        publication_id = session_store.get_meta(chat_id, 'publication_id')
        if not publication_id:
            return None
        if action == 'publish_now':
            publication = bridge.publish_now(publication_id)
            label = 'publish_now'
        elif action == 'cancel':
            publication = bridge.cancel_publication(publication_id)
            label = 'cancel_publication'
        else:
            scheduled_for_raw = session_store.get_meta(chat_id, 'scheduled_for_input')
            scheduled_for = parse_user_schedule(scheduled_for_raw or '') if scheduled_for_raw else None
            if scheduled_for is None:
                return BotScreen(
                    text='Сначала пришли корректное время публикации в формате YYYY-MM-DD HH:MM UTC.',
                    buttons=[['Отмена планирования'], ['Главное меню']],
                )
            publication = bridge.schedule_publication(publication_id, scheduled_for)
            label = 'schedule_publication'
        task = publication.draft.content_task
        return service.publication_action_result_screen(
            action=label,
            title=task.title if task is not None else 'Без задачи',
            status=publication.status.value if hasattr(publication.status, 'value') else str(publication.status),
            scheduled_for=publication.scheduled_for.isoformat() if publication.scheduled_for else None,
            error_message=publication.error_message,
        )
    finally:
        db.close()


def channel_mode_screen_from_backend(identity: TelegramIdentity, chat_id: int) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        channel_id = session_store.get_meta(chat_id, 'channel_id')
        if not channel_id:
            return None
        channel = bridge.get_channel(channel_id)
        mode = channel.publish_mode.value if hasattr(channel.publish_mode, 'value') else str(channel.publish_mode)
        return service.channel_mode_screen(mode)
    finally:
        db.close()


def change_channel_mode_from_backend(identity: TelegramIdentity, chat_id: int, mode: str) -> BotScreen | None:
    db = SessionLocal()
    try:
        bridge = BotBackendBridge(db, identity)
        channel_id = session_store.get_meta(chat_id, 'channel_id')
        if not channel_id:
            return None
        channel = bridge.update_channel_mode(channel_id, mode)
        current_mode = channel.publish_mode.value if hasattr(channel.publish_mode, 'value') else str(channel.publish_mode)
        return service.mode_action_result_screen(current_mode)
    finally:
        db.close()


def resolve_screen_for_text(text: str, chat_id: int | None = None, identity: TelegramIdentity | None = None) -> BotScreen:
    normalized = (text or '').strip()

    if chat_id is not None:
        session_store.restore_for_identity(chat_id, identity)
        session_store.remember_input(chat_id, normalized)
    step = session_store.get_step(chat_id) if chat_id is not None else None
    source_screen = step

    logger.info(
        'bot input received',
        extra={
            'chat_id': chat_id,
            'telegram_user_id': getattr(identity, 'telegram_user_id', None),
            'screen': step,
            'input': normalized,
        },
    )

    if normalized in {'', 'Главное меню', '/start'}:
        if chat_id is not None:
            session_store.clear(chat_id, keep_context=True)
        screen = service.main_menu_screen()
        _log_bot_screen('main_menu', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='main_menu_command', input_text=normalized)
        return screen
    if normalized == 'Отмена редактирования' and chat_id is not None:
        session_store.set_step(chat_id, 'draft_detail')
        session_store.delete_meta(chat_id, 'draft_edit_pending')
        return _render_screen_by_state('draft_detail', chat_id, identity)
    if normalized == 'Отмена планирования' and chat_id is not None:
        session_store.set_step(chat_id, 'publication_detail')
        session_store.delete_meta(chat_id, 'schedule_publication_pending')
        return _render_screen_by_state('publication_detail', chat_id, identity)
    if normalized == 'Назад' and chat_id is not None:
        previous = session_store.go_back(chat_id)
        return _render_screen_by_state(previous, chat_id, identity)
    if normalized == 'Назад к каналам':
        if chat_id is not None:
            session_store.set_step(chat_id, 'my_channels', push_current=True)
        if identity is not None:
            return my_channels_screen_from_backend(identity)
        return service.my_channels_empty_screen()
    if normalized == 'Создать канал':
        if chat_id is not None:
            session_store.start(chat_id)
        _log_bot_flow_event('wizard', 'wizard_started', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized)
        _log_bot_screen('wizard_start', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='wizard_entry', input_text=normalized)
        return _wizard_screen_to_bot_screen(service.wizard_start_screen())
    if normalized == 'Начать':
        if chat_id is not None:
            session_store.set_step(chat_id, 'name')
        _log_bot_flow_event('wizard', 'wizard_step_opened', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, extra_data={'step': 'name'})
        _log_bot_screen('name', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='wizard_step_opened', input_text=normalized)
        return _wizard_screen_to_bot_screen(service.wizard_name_screen())

    if step == 'name' and normalized and normalized not in {'Главное меню', 'Назад'}:
        if chat_id is not None:
            session_store.update_state(chat_id, name=normalized)
            session_store.set_step(chat_id, 'niche', push_current=True)
        _log_bot_flow_event('wizard', 'wizard_step_completed', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, extra_data={'step': 'name'})
        _log_bot_flow_event('wizard', 'wizard_step_opened', chat_id=chat_id, identity=identity, source_screen='name', input_text=normalized, extra_data={'step': 'niche'})
        _log_bot_screen('niche', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='wizard_name_captured', input_text=normalized)
        return _wizard_screen_to_bot_screen(service.wizard_niche_screen())

    if normalized in {'AI', 'Крипта', 'Маркетинг', 'Новости', 'Свой вариант'}:
        if chat_id is not None:
            session_store.update_state(chat_id, niche=normalized)
            session_store.set_step(chat_id, 'language', push_current=True)
        return _wizard_screen_to_bot_screen(service.wizard_language_screen())
    if normalized in {'Русский', 'English'}:
        if chat_id is not None:
            session_store.update_state(chat_id, language=normalized)
            session_store.set_step(chat_id, 'goal', push_current=True)
        return _wizard_screen_to_bot_screen(service.wizard_goal_screen())
    if normalized in {'Личный бренд', 'Трафик / лиды', 'Экспертный контент'}:
        if chat_id is not None:
            session_store.update_state(chat_id, goal=normalized)
            session_store.set_step(chat_id, 'content_format', push_current=True)
        return _wizard_screen_to_bot_screen(service.wizard_content_format_screen())
    if normalized in {'Короткие посты', 'Аналитика', 'Смешанный формат'}:
        if chat_id is not None:
            session_store.update_state(chat_id, content_format=normalized)
            session_store.set_step(chat_id, 'posting_frequency', push_current=True)
        return _wizard_screen_to_bot_screen(service.wizard_posting_frequency_screen())
    if normalized in {'Ежедневно', '2 раза в день', 'Несколько раз в неделю'}:
        state = None
        if chat_id is not None:
            state = session_store.update_state(chat_id, posting_frequency=normalized)
            session_store.set_step(chat_id, 'summary', push_current=True)
        return _wizard_screen_to_bot_screen(service.wizard_summary_screen(state or ProjectWizardState(posting_frequency=normalized)))
    if normalized == 'Подтвердить проект':
        if chat_id is not None:
            session_store.set_step(chat_id, 'preset', push_current=True)
            if identity is not None:
                try:
                    project_id = create_project_from_wizard_state(chat_id, identity)
                except Exception as exc:
                    return _error_screen_for_exception(exc, buttons=[['Назад'], ['Главное меню']], chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='wizard_project_create_failed')
                _log_bot_flow_event('wizard', 'project_created', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=project_id)
                _log_bot_flow_event('wizard', 'wizard_step_opened', chat_id=chat_id, identity=identity, source_screen='summary', input_text=normalized, project_id=project_id, extra_data={'step': 'preset'})
                wizard_screen = service.wizard_preset_screen()
                _log_bot_screen('preset', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='project_created', input_text=normalized)
                return BotScreen(
                    text=f"{wizard_screen.text}\n\nПроект создан: `{project_id}`",
                    buttons=wizard_screen.buttons,
                )
        _log_bot_flow_event('wizard', 'wizard_step_opened', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, extra_data={'step': 'preset'})
        _log_bot_screen('preset', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='wizard_preset_opened', input_text=normalized)
        return _wizard_screen_to_bot_screen(service.wizard_preset_screen())
    if normalized in {'3 агента — Быстрый старт', '5 агентов — Сбалансировано', '7 агентов — Полная редакция'}:
        agents_count = None
        project_id = session_store.get_meta(chat_id, 'project_id') if chat_id is not None else None
        if chat_id is not None:
            session_store.update_state(chat_id, preset_code=normalized)
            session_store.set_step(chat_id, 'channel_connect', push_current=True)
            if identity is not None and project_id:
                try:
                    agents_count = apply_preset_from_wizard_state(chat_id, identity, normalized)
                except Exception as exc:
                    return _error_screen_for_exception(exc, buttons=[['Назад'], ['Главное меню']], chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='wizard_apply_preset_failed')
        _log_bot_flow_event('wizard', 'preset_selected', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=project_id, extra_data={'preset_label': normalized, 'agents_count': agents_count})
        _log_bot_flow_event('channel', 'channel_connect_step_opened', chat_id=chat_id, identity=identity, source_screen='preset', input_text=normalized, project_id=project_id)
        wizard_screen = service.wizard_channel_connect_screen()
        _log_bot_screen('channel_connect', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='preset_selected', input_text=normalized)
        if agents_count is not None:
            return BotScreen(
                text=f"Команда агентов применена: {agents_count}.\n\n{wizard_screen.text}",
                buttons=wizard_screen.buttons,
            )
        return _wizard_screen_to_bot_screen(wizard_screen)

    if step == 'channel_connect' and normalized.startswith('@'):
        if chat_id is not None:
            session_store.update_state(chat_id, channel_ref=normalized)
        return BotScreen(
            text=(
                f'Канал для подключения сохранён: {normalized}.\n'
                'Следующий шаг один: нажми «Проверить подключение», когда бот уже добавлен в админы и имеет право писать сообщения.'
            ),
            buttons=[["Проверить подключение"], ["Как создать канал"], ["Главное меню"]],
        )

    if normalized == 'У меня уже есть канал':
        return BotScreen(
            text=(
                'Отлично. Теперь сделай только три действия:\n'
                '1. Добавь этого бота в администраторы канала.\n'
                '2. Выдай право на публикацию сообщений.\n'
                '3. Пришли сюда @username канала.\n\n'
                'Когда пришлёшь username, я сразу подскажу следующий шаг.'
            ),
            buttons=[["Проверить подключение"], ["Как создать канал"], ["Назад"], ["Главное меню"]],
        )

    if normalized == 'Как создать канал':
        return service.channel_creation_guide_screen()

    if normalized == 'Повторить инструкцию':
        return _wizard_screen_to_bot_screen(service.wizard_channel_connect_screen())

    if normalized == 'Проверить подключение':
        channel_ref = session_store.get_state(chat_id).channel_ref if chat_id is not None else None
        project_id = session_store.get_meta(chat_id, 'project_id') if chat_id is not None else None
        if chat_id is not None and identity is not None and channel_ref and project_id:
            try:
                channel_id, status = connect_channel_from_wizard_state(chat_id, identity, channel_ref)
            except Exception as exc:
                return _error_screen_for_exception(exc, buttons=[['Повторить инструкцию'], ['Главное меню']], chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='channel_connection_check_failed')
            session_store.set_step(chat_id, 'project_ready', push_current=True if status == 'connected' else False)
            _log_bot_flow_event('channel', 'channel_connection_checked', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=project_id, channel_id=channel_id, extra_data={'status': status, 'channel_ref': channel_ref})
            if status == 'connected':
                _log_bot_flow_event('channel', 'channel_connected', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=project_id, channel_id=channel_id, extra_data={'channel_ref': channel_ref})
                _log_bot_screen('project_ready', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='channel_connected', input_text=normalized)
            return service.channel_connection_result_screen(status, channel_ref=channel_ref)
        _log_bot_diagnostic('channel_connection_missing_ref', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='channel_ref_missing', detail='Connection check requested before channel username or project context was provided.')
        return BotScreen(
            text='Сначала пришли @username канала, затем повтори проверку подключения.',
            buttons=[["Повторить инструкцию"], ["Главное меню"]],
        )
    if normalized == 'Как это работает':
        if chat_id is not None:
            session_store.set_step(chat_id, 'how_it_works', push_current=True)
        return service.how_it_works_screen()
    if normalized == 'Помощь':
        if chat_id is not None:
            session_store.set_step(chat_id, 'help', push_current=True)
        return service.help_screen()
    if normalized == 'Мои каналы':
        if chat_id is not None:
            session_store.set_step(chat_id, 'my_channels', push_current=True)
        if identity is not None:
            return my_channels_screen_from_backend(identity)
        return service.my_channels_empty_screen()
    if normalized == 'Открыть проект':
        if chat_id is not None:
            session_store.set_step(chat_id, 'channel_dashboard', push_current=True)
        channel_title = session_store.get_meta(chat_id, 'channel_title') if chat_id is not None else None
        if identity is not None and chat_id is not None:
            if channel_title:
                dashboard = open_channel_dashboard_from_backend(identity, channel_title, chat_id=chat_id)
                if dashboard is not None:
                    return dashboard
            resumed = resume_current_project_from_backend(identity, chat_id)
            if resumed is not None:
                return resumed
        _log_bot_diagnostic(
            'project_context_missing',
            chat_id=chat_id,
            identity=identity,
            source_screen=source_screen,
            input_text=normalized,
            diagnostic_code='project_context_missing',
            detail='User requested project reopen but no active project/channel context could be restored.',
        )
        return BotScreen(
            text=(
                'Не удалось восстановить текущий проект из сессии.\n'
                'Открой канал из списка «Мои каналы» или пройди подключение заново.'
            ),
            buttons=[['Мои каналы'], ['Создать канал'], ['Главное меню']],
        )
    if normalized == 'Настройки' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_settings', push_current=True)
        screen = channel_settings_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Агенты' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_agents', push_current=True)
        screen = channel_agents_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Контент-план' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_content_plan', push_current=True)
        screen = channel_content_plan_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Черновики' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_drafts', push_current=True)
        screen = channel_drafts_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Публикации' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_publications', push_current=True)
        screen = publications_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Режим работы' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_mode', push_current=True)
        screen = channel_mode_screen_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Подтвердить' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'draft_detail')
        try:
            screen = perform_draft_action_from_backend(identity, chat_id, 'approve')
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Черновики'], ['Главное меню']], chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='draft_approve_failed')
        if screen is not None:
            _log_bot_flow_event('draft', 'draft_approved', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=session_store.get_meta(chat_id, 'project_id'), draft_id=session_store.get_meta(chat_id, 'draft_id'))
            _log_bot_screen('draft_detail', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='draft_approved', input_text=normalized)
            return screen
    if normalized == 'Отклонить' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'draft_detail')
        try:
            screen = perform_draft_action_from_backend(identity, chat_id, 'reject')
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Черновики'], ['Главное меню']])
        if screen is not None:
            return screen
    if normalized == 'Редактировать' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'draft_edit_text', push_current=True)
        session_store.set_meta(chat_id, 'draft_edit_pending', '1')
        screen = perform_draft_action_from_backend(identity, chat_id, 'edit')
        if screen is not None:
            return screen
    if normalized == 'Пересобрать' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'draft_detail')
        try:
            screen = perform_draft_action_from_backend(identity, chat_id, 'regenerate')
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Черновики'], ['Главное меню']])
        if screen is not None:
            return screen
    if normalized == 'Создать публикацию' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'publication_detail', push_current=True)
        try:
            screen = create_publication_from_current_draft(identity, chat_id, scheduled=False)
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Черновики'], ['Главное меню']], chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='publication_create_failed')
        if screen is not None:
            _log_bot_flow_event('publication', 'publication_created', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=session_store.get_meta(chat_id, 'project_id'), channel_id=session_store.get_meta(chat_id, 'channel_id'), draft_id=session_store.get_meta(chat_id, 'draft_id'), publication_id=session_store.get_meta(chat_id, 'publication_id'))
            _log_bot_screen('publication_detail', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='publication_created', input_text=normalized)
            return screen
    if normalized == 'Опубликовать сейчас' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'publication_detail')
        try:
            screen = perform_publication_action_from_backend(identity, chat_id, 'publish_now')
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Публикации'], ['Главное меню']], chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='publication_publish_now_failed')
        if screen is not None:
            _log_bot_flow_event('publication', 'publication_publish_now_requested', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=session_store.get_meta(chat_id, 'project_id'), channel_id=session_store.get_meta(chat_id, 'channel_id'), publication_id=session_store.get_meta(chat_id, 'publication_id'))
            _log_bot_screen('publication_detail', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='publication_publish_now_requested', input_text=normalized)
            return screen
    if normalized == 'Отменить публикацию' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'publication_detail')
        try:
            screen = perform_publication_action_from_backend(identity, chat_id, 'cancel')
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Публикации'], ['Главное меню']])
        if screen is not None:
            return screen
    if normalized == 'Запланировать' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'schedule_publication_time', push_current=True)
        screen = service.loading_screen('Подготовка публикации', 'Проверяю черновик и жду время публикации.')
        try:
            screen = create_publication_from_current_draft(identity, chat_id, scheduled=True)
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Черновики'], ['Главное меню']])
        if screen is not None:
            return screen
    if normalized == 'Режим: ручной' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_mode')
        try:
            screen = change_channel_mode_from_backend(identity, chat_id, MODE_TO_BACKEND['manual'])
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Режим работы'], ['Главное меню']])
        if screen is not None:
            return screen
    if normalized == 'Режим: ассистент' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_mode')
        try:
            screen = change_channel_mode_from_backend(identity, chat_id, MODE_TO_BACKEND['semi_auto'])
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Режим работы'], ['Главное меню']])
        if screen is not None:
            return screen
    if normalized == 'Режим: авто' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_mode')
        try:
            screen = change_channel_mode_from_backend(identity, chat_id, MODE_TO_BACKEND['auto'])
        except Exception as exc:
            return _error_screen_for_exception(exc, buttons=[['Режим работы'], ['Главное меню']])
        if screen is not None:
            return screen
    if step == 'draft_edit_text' and chat_id is not None and identity is not None and normalized and normalized not in {'Назад', 'Главное меню'}:
        db = SessionLocal()
        try:
            bridge = BotBackendBridge(db, identity)
            draft_id = session_store.get_meta(chat_id, 'draft_id')
            if not draft_id:
                return BotScreen(text='Черновик не найден.', buttons=[['Черновики'], ['Главное меню']])
            draft = bridge.edit_draft(draft_id, normalized)
            task = draft.content_task
            session_store.set_step(chat_id, 'draft_detail')
            session_store.delete_meta(chat_id, 'draft_edit_pending')
            status = draft.status.value if hasattr(draft.status, 'value') else str(draft.status)
            return service.draft_action_result_screen(
                action='edit',
                title=task.title if task is not None else 'Без задачи',
                status=status,
                version=draft.version,
                text=draft.text,
                created_by_agent=draft.created_by_agent,
            )
        finally:
            db.close()

    if step == 'schedule_publication_time' and chat_id is not None and identity is not None and normalized and normalized not in {'Назад', 'Главное меню'}:
        when = parse_user_schedule(normalized)
        if when is None:
            _log_bot_diagnostic('publication_schedule_parse_failed', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, diagnostic_code='schedule_time_invalid', detail='User provided an invalid schedule format for publication.')
            return BotScreen(
                text='Не понял время. Пришли в формате YYYY-MM-DD HH:MM UTC. Пример: 2026-03-20 10:00 UTC',
                buttons=[['Отмена планирования'], ['Главное меню']],
            )
        publication_id = session_store.get_meta(chat_id, 'publication_id')
        if publication_id:
            session_store.set_meta(chat_id, 'scheduled_for_input', normalized)
            session_store.set_step(chat_id, 'publication_detail')
            session_store.delete_meta(chat_id, 'schedule_publication_pending')
            screen = perform_publication_action_from_backend(identity, chat_id, 'schedule')
            if screen is not None:
                _log_bot_flow_event('publication', 'publication_scheduled', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=session_store.get_meta(chat_id, 'project_id'), channel_id=session_store.get_meta(chat_id, 'channel_id'), publication_id=session_store.get_meta(chat_id, 'publication_id'), extra_data={'scheduled_for': normalized})
                _log_bot_screen('publication_detail', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='publication_scheduled', input_text=normalized)
                session_store.delete_meta(chat_id, 'scheduled_for_input')
                return screen
        db = SessionLocal()
        try:
            bridge = BotBackendBridge(db, identity)
            draft_id = session_store.get_meta(chat_id, 'draft_id')
            channel_id = session_store.get_meta(chat_id, 'channel_id')
            if not draft_id or not channel_id:
                return BotScreen(text='Не удалось создать публикацию.', buttons=[['Черновики'], ['Главное меню']])
            publication = bridge.create_publication(draft_id, channel_id, scheduled_for=when)
            task = publication.draft.content_task
            session_store.set_meta(chat_id, 'publication_id', str(publication.id))
            session_store.set_meta(chat_id, 'publication_title', task.title if task is not None else 'Без задачи')
            session_store.set_step(chat_id, 'publication_detail')
            session_store.delete_meta(chat_id, 'schedule_publication_pending')
            _log_bot_flow_event('publication', 'publication_scheduled', chat_id=chat_id, identity=identity, source_screen=source_screen, input_text=normalized, project_id=session_store.get_meta(chat_id, 'project_id'), channel_id=session_store.get_meta(chat_id, 'channel_id'), draft_id=session_store.get_meta(chat_id, 'draft_id'), publication_id=str(publication.id), extra_data={'scheduled_for': normalized})
            _log_bot_screen('publication_detail', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='scheduled_publication_created', input_text=normalized)
            return service.publication_action_result_screen(
                action='create_publication',
                title=task.title if task is not None else 'Без задачи',
                status=publication.status.value if hasattr(publication.status, 'value') else str(publication.status),
                scheduled_for=publication.scheduled_for.isoformat() if publication.scheduled_for else None,
                error_message=publication.error_message,
            )
        finally:
            db.close()

    if normalized == 'Создать контент-план' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_content_plan')
        screen = create_sample_content_plan_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Создать 3 черновика' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_drafts', push_current=True)
        screen = generate_sample_drafts_from_backend(identity, chat_id)
        if screen is not None:
            return screen
    if normalized == 'Сгенерировать 10 идей' and chat_id is not None and identity is not None:
        session_store.set_step(chat_id, 'channel_content_plan', push_current=True)
        screen = generate_sample_tasks_from_backend(identity, chat_id)
        if screen is not None:
            return screen

    if identity is not None and chat_id is not None:
        draft_screen = open_draft_screen_from_backend(identity, chat_id, normalized)
        if draft_screen is not None:
            session_store.set_step(chat_id, 'draft_detail', push_current=True)
            return draft_screen
        publication_screen = open_publication_screen_from_backend(identity, chat_id, normalized)
        if publication_screen is not None:
            session_store.set_step(chat_id, 'publication_detail', push_current=True)
            return publication_screen

    if identity is not None:
        dashboard = open_channel_dashboard_from_backend(identity, normalized, chat_id=chat_id)
        if dashboard is not None:
            if chat_id is not None:
                session_store.set_step(chat_id, 'channel_dashboard', push_current=True)
            _log_bot_screen('channel_dashboard', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='channel_title_match', input_text=normalized)
            return dashboard

    _log_bot_diagnostic(
        'fallback_to_main_menu',
        chat_id=chat_id,
        identity=identity,
        source_screen=source_screen,
        input_text=normalized,
        diagnostic_code='unmatched_input',
        detail='Input did not match any bot route; returning main menu.',
    )
    screen = service.main_menu_screen()
    _log_bot_screen('main_menu', chat_id=chat_id, identity=identity, source_screen=source_screen, reason='fallback_unmatched_input', input_text=normalized, diagnostic_code='unmatched_input')
    return screen


async def answer_with_screen(message: Message, screen: BotScreen):
    await message.answer(screen.text, reply_markup=build_reply_keyboard(screen))


@router.message(CommandStart())
async def start_handler(message: Message):
    screen = service.start_screen()
    await answer_with_screen(message, screen)


@router.message()
async def fallback_handler(message: Message):
    user = message.from_user
    identity = TelegramIdentity(
        telegram_user_id=str(user.id) if user else str(message.chat.id),
        telegram_username=user.username if user else None,
        first_name=user.first_name if user else None,
        last_name=user.last_name if user else None,
    )
    screen = resolve_screen_for_text(message.text or '', chat_id=message.chat.id, identity=identity)
    await answer_with_screen(message, screen)



def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher



def build_bot() -> Bot:
    token = settings.telegram_bot_token or 'TEST_TOKEN'
    return Bot(token=token)
