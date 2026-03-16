from app.bot.service import BotService
from app.bot.wizard import ProjectWizardState


def test_wizard_has_linear_project_setup_steps():
    service = BotService()
    assert service.wizard_name_screen().step == 'name'
    assert service.wizard_niche_screen().step == 'niche'
    assert service.wizard_language_screen().step == 'language'
    assert service.wizard_goal_screen().step == 'goal'
    assert service.wizard_description_screen().step == 'description'
    assert service.wizard_content_format_screen().step == 'content_format'
    assert service.wizard_posting_frequency_screen().step == 'posting_frequency'


def test_wizard_summary_screen_renders_collected_state():
    service = BotService()
    state = ProjectWizardState(
        name='Alpha Channel',
        niche='AI',
        language='Русский',
        goal='Личный бренд',
        description='Канал про ИИ-агентов для предпринимателей',
        content_format='Аналитика',
        posting_frequency='Ежедневно',
    )
    screen = service.wizard_summary_screen(state)
    assert 'Alpha Channel' in screen.text
    assert 'AI' in screen.text
    assert 'Канал про ИИ-агентов для предпринимателей' in screen.text
    assert 'Ежедневно' in screen.text


def test_wizard_summary_screen_truncates_very_long_description_preview():
    service = BotService()
    long_description = 'Очень длинный контекст. ' * 500
    state = ProjectWizardState(
        name='Alpha Channel',
        niche='AI',
        language='Русский',
        goal='Личный бренд',
        description=long_description,
        content_format='Аналитика',
        posting_frequency='Ежедневно',
    )
    screen = service.wizard_summary_screen(state)
    assert 'Проверь настройки проекта' in screen.text
    assert len(screen.text) < 2000
    assert '…' in screen.text
    assert long_description not in screen.text



def test_wizard_has_preset_connection_and_ready_steps():
    service = BotService()
    assert service.wizard_preset_screen().step == 'preset'
    assert service.wizard_channel_connect_screen().step == 'channel_connect'
    assert service.wizard_project_ready_screen().step == 'project_ready'
    assert 'Проект готов' in service.wizard_project_ready_screen().text



def test_project_create_payload_is_built_from_wizard_state():
    service = BotService()
    state = ProjectWizardState(
        name='Alpha Channel',
        niche='AI',
        language='Русский',
        goal='Личный бренд',
        description='Полный контекст проекта',
        content_format='Аналитика',
        posting_frequency='Ежедневно',
    )

    payload = service.project_create_payload_from_wizard_state(state)

    assert payload.name == 'Alpha Channel'
    assert payload.description == 'Полный контекст проекта'
    assert payload.niche == 'AI'
    assert payload.language == 'ru'
    assert payload.goal == 'Личный бренд'
    assert payload.content_format == 'Аналитика'
    assert payload.posting_frequency == 'Ежедневно'
