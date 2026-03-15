from app.bot.service import BotService
from app.bot.screens import ChannelSummary
from app.bot.state_machine import CALLBACKS, BotStates


def test_my_channels_screen_supports_empty_and_non_empty_states():
    service = BotService()
    empty = service.my_channels_screen([])
    assert 'нет каналов' in empty.text.lower() or 'создай первый проект' in empty.text.lower()

    filled = service.my_channels_screen([
        ChannelSummary(id='1', title='Alpha', mode='manual', status='active'),
        ChannelSummary(id='2', title='Beta', mode='semi_auto', status='paused'),
    ])
    assert 'Мои каналы' in filled.text
    flat = [item for row in filled.buttons for item in row]
    assert 'Alpha' in flat and 'Beta' in flat


def test_channel_dashboard_and_sections_exist():
    service = BotService()
    dashboard = service.channel_dashboard_screen('Alpha Channel', 'manual', 5, 2, 4)
    assert 'Alpha Channel' in dashboard.text
    assert 'Ручной — каждое важное действие подтверждаешь ты' in dashboard.text
    assert 'Контент-планов: 2' in dashboard.text
    assert 'Черновиков: 4' in dashboard.text
    flat = [item for row in dashboard.buttons for item in row]
    assert '⚙️ Настройки' in flat
    assert '🤖 Агенты' in flat
    assert '🗂 План' in flat
    assert '📝 Черновики' in flat
    assert '📢 Посты' in flat
    assert '🎛 Режим' in flat

    assert 'Настройки канала' in service.channel_settings_screen('Alpha', 'AI', 'ru', 'Аналитика', 'Ежедневно', 'manual').text
    assert 'Агенты' in service.channel_agents_screen().text
    assert 'Контент-план' in service.channel_content_plan_screen().text
    drafts = service.channel_drafts_screen()
    assert 'Черновики' in drafts.text
    detail = service.draft_detail_screen('Task A', 'created', 1, 'Body text', 'writer')
    assert 'Task A' in detail.text
    assert '✅ Подтвердить' in [item for row in detail.buttons for item in row]
    publications = service.publications_screen()
    assert 'Публикации' in publications.text
    publication_detail = service.publication_detail_screen('Task A', 'queued', '2026-03-20T10:00:00+00:00')
    assert 'В очереди' in publication_detail.text
    assert '🚀 Опубликовать' in [item for row in publication_detail.buttons for item in row]
    assert 'Режим работы' in service.channel_mode_screen('manual').text


def test_callback_scheme_and_states_are_defined():
    assert CALLBACKS['main_create_channel'].value == 'main:create_channel'
    assert CALLBACKS['wizard_summary'].value == 'wizard:summary'
    assert BotStates.MY_CHANNELS == 'my_channels'
    assert BotStates.CHANNEL_DASHBOARD == 'channel_dashboard'
