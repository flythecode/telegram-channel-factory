from dataclasses import dataclass

from app.bot.keyboards import back_menu_keyboard, main_menu_keyboard, project_ready_keyboard
from app.bot.screens import (
    AgentSummary,
    ChannelSummary,
    ContentPlanSummary,
    DraftSummary,
    PublicationSummary,
    channel_agents_screen,
    channel_content_plan_screen,
    channel_dashboard_screen,
    channel_drafts_screen,
    channel_settings_screen,
    channel_project_edit_screen,
    channels_list_screen,
    draft_detail_screen,
    mode_screen,
    publication_detail_screen,
    publications_screen,
    section_screen,
)
from app.bot.texts import (
    HELP_TEXT,
    HOW_IT_WORKS_TEXT,
    MY_CHANNELS_EMPTY_TEXT,
    PROJECT_READY_TEXT,
    START_TEXT,
)
from app.bot.ux import human_action_label
from app.bot.wizard import CHANNEL_CREATION_GUIDE_TEXT, ProjectWizardService, ProjectWizardState, WizardScreen
from app.schemas.project import ProjectCreate, ProjectUpdate


@dataclass(slots=True)
class BotScreen:
    text: str
    buttons: list[list[str]]


class BotService:
    """Telegram UI screen factory for bot control layer."""

    def __init__(self):
        self.wizard = ProjectWizardService()

    def start_screen(self) -> BotScreen:
        return BotScreen(text=START_TEXT, buttons=main_menu_keyboard())

    def main_menu_screen(self) -> BotScreen:
        return BotScreen(text=START_TEXT, buttons=main_menu_keyboard())

    def how_it_works_screen(self) -> BotScreen:
        return BotScreen(text=HOW_IT_WORKS_TEXT, buttons=back_menu_keyboard())

    def help_screen(self) -> BotScreen:
        return BotScreen(text=HELP_TEXT, buttons=back_menu_keyboard())

    def my_channels_empty_screen(self) -> BotScreen:
        return BotScreen(text=MY_CHANNELS_EMPTY_TEXT, buttons=[["Создать канал"], ["Главное меню"]])

    def my_channels_screen(self, channels: list[ChannelSummary] | None = None) -> BotScreen:
        data = channels_list_screen(channels or [])
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_dashboard_screen(
        self,
        title: str,
        mode: str,
        agents_count: int,
        content_plans_count: int = 0,
        drafts_count: int = 0,
        generation_summary: dict | None = None,
    ) -> BotScreen:
        data = channel_dashboard_screen(title, mode, agents_count, content_plans_count, drafts_count, generation_summary)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_settings_screen(
        self,
        project_name: str,
        topic: str | None,
        language: str,
        content_format: str | None,
        posting_frequency: str | None,
        operation_mode: str,
    ) -> BotScreen:
        data = channel_settings_screen(project_name, topic, language, content_format, posting_frequency, operation_mode)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_project_edit_screen(
        self,
        project_name: str,
        topic: str | None,
        language: str,
        goal: str | None,
        content_format: str | None,
        posting_frequency: str | None,
        description: str | None,
    ) -> BotScreen:
        data = channel_project_edit_screen(project_name, topic, language, goal, content_format, posting_frequency, description)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_agents_screen(self, agents: list[AgentSummary] | None = None) -> BotScreen:
        data = channel_agents_screen(agents or [])
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_content_plan_screen(self, plans: list[ContentPlanSummary] | None = None, tasks_total: int = 0, generation_summary: dict | None = None) -> BotScreen:
        data = channel_content_plan_screen(plans or [], tasks_total, generation_summary)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_drafts_screen(self, drafts: list[DraftSummary] | None = None) -> BotScreen:
        data = channel_drafts_screen(drafts or [])
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def draft_detail_screen(self, title: str, status: str, version: int, text: str, created_by_agent: str | None = None, generation_summary: dict | None = None) -> BotScreen:
        data = draft_detail_screen(title, status, version, text, created_by_agent, generation_summary)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def draft_action_result_screen(self, action: str, title: str, status: str, version: int, text: str, created_by_agent: str | None = None, generation_summary: dict | None = None) -> BotScreen:
        data = draft_detail_screen(title, status, version, text, created_by_agent, generation_summary)
        return BotScreen(text=f'{human_action_label(action)}.\n\n{data["text"]}', buttons=data['buttons'])

    def publications_screen(self, publications: list[PublicationSummary] | None = None) -> BotScreen:
        data = publications_screen(publications or [])
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def publication_detail_screen(self, title: str, status: str, scheduled_for: str | None, error_message: str | None = None) -> BotScreen:
        data = publication_detail_screen(title, status, scheduled_for, error_message)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def publication_action_result_screen(self, action: str, title: str, status: str, scheduled_for: str | None, error_message: str | None = None) -> BotScreen:
        data = publication_detail_screen(title, status, scheduled_for, error_message)
        return BotScreen(text=f'{human_action_label(action)}.\n\n{data["text"]}', buttons=data['buttons'])

    def channel_publications_screen(self) -> BotScreen:
        data = section_screen('Публикации', 'Управляй очередью, запланированными и готовыми к отправке публикациями.')
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def channel_mode_screen(self, current_mode: str = 'manual') -> BotScreen:
        data = mode_screen(current_mode)
        return BotScreen(text=data['text'], buttons=data['buttons'])

    def mode_action_result_screen(self, current_mode: str) -> BotScreen:
        data = mode_screen(current_mode)
        return BotScreen(text=f'Режим обновлён.\n\n{data["text"]}', buttons=data['buttons'])

    def loading_screen(self, title: str = 'Обработка', detail: str | None = None) -> BotScreen:
        text = title if detail is None else f'{title}\n{detail}'
        return BotScreen(text=text, buttons=[["Главное меню"]])

    def error_screen(self, message: str, next_steps: list[list[str]] | None = None) -> BotScreen:
        return BotScreen(text=f'Не получилось выполнить действие.\n\n{message}', buttons=next_steps or back_menu_keyboard())

    def project_ready_screen(self) -> BotScreen:
        return BotScreen(text=PROJECT_READY_TEXT, buttons=project_ready_keyboard())

    def channel_creation_guide_screen(self) -> BotScreen:
        return BotScreen(
            text=CHANNEL_CREATION_GUIDE_TEXT,
            buttons=[["У меня уже есть канал"], ["Проверить подключение"], ["Назад"], ["Главное меню"]],
        )

    def wizard_start_screen(self) -> WizardScreen:
        return self.wizard.start()

    def wizard_name_screen(self) -> WizardScreen:
        return self.wizard.step_name()

    def wizard_niche_screen(self) -> WizardScreen:
        return self.wizard.step_niche()

    def wizard_language_screen(self) -> WizardScreen:
        return self.wizard.step_language()

    def wizard_goal_screen(self) -> WizardScreen:
        return self.wizard.step_goal()

    def wizard_description_screen(self) -> WizardScreen:
        return self.wizard.step_description()

    def wizard_content_format_screen(self) -> WizardScreen:
        return self.wizard.step_content_format()

    def wizard_posting_frequency_screen(self) -> WizardScreen:
        return self.wizard.step_posting_frequency()

    def wizard_summary_screen(self, state: ProjectWizardState) -> WizardScreen:
        return self.wizard.summary(state)

    def wizard_preset_screen(self) -> WizardScreen:
        return self.wizard.preset_step()

    def wizard_channel_connect_screen(self) -> WizardScreen:
        return self.wizard.channel_connect_step()

    def wizard_project_ready_screen(self) -> WizardScreen:
        return self.wizard.project_ready()

    def channel_connection_result_screen(self, status: str, channel_ref: str | None = None) -> BotScreen:
        if status == 'connected':
            text = (
                'Канал подключён и готов к публикациям.\n'
                f'Канал: {channel_ref or "—"}\n'
                'Бот добавлен, права на публикацию подтверждены.'
            )
            buttons = project_ready_keyboard()
        elif status == 'bot_not_admin':
            text = (
                'Бот найден, но не является администратором канала.\n'
                f'Канал: {channel_ref or "—"}\n'
                'Следующий шаг один: открой канал → Управление каналом → Администраторы, добавь бота и потом повтори проверку.'
            )
            buttons = [["Повторить инструкцию"], ["Проверить подключение"], ["Главное меню"]]
        elif status == 'missing_post_permission':
            text = (
                'Бот добавлен, но не может публиковать сообщения.\n'
                f'Канал: {channel_ref or "—"}\n'
                'Следующий шаг один: в правах администратора включи публикацию сообщений и повтори проверку.'
            )
            buttons = [["Повторить инструкцию"], ["Проверить подключение"], ["Главное меню"]]
        elif status == 'channel_not_found':
            text = (
                'Канал не найден или username указан неверно.\n'
                f'Канал: {channel_ref or "—"}\n'
                'Следующий шаг один: проверь публичный @username канала, пришли его заново в формате @my_channel и потом повтори проверку.'
            )
            buttons = [["Повторить инструкцию"], ["Главное меню"]]
        else:
            text = (
                'Подключение ещё требует внимания.\n'
                f'Канал: {channel_ref or "—"}\n'
                'Проверь, что бот добавлен в админы и ему выдано право на публикацию сообщений.'
            )
            buttons = [["Повторить инструкцию"], ["Проверить подключение"], ["Главное меню"]]
        return BotScreen(text=text, buttons=buttons)

    def project_create_payload_from_wizard_state(self, state: ProjectWizardState) -> ProjectCreate:
        return ProjectCreate(
            name=state.name or 'Новый канал',
            description=state.description,
            niche=state.niche,
            language='ru' if state.language == 'Русский' else ('en' if state.language == 'English' else 'ru'),
            goal=state.goal,
            content_format=state.content_format,
            posting_frequency=state.posting_frequency,
        )

    def build_project_update_payload(self, values: dict) -> ProjectUpdate:
        return ProjectUpdate(**values)
