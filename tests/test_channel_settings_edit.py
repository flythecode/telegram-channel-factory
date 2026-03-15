from app.bot.app import resolve_screen_for_text, session_store
from app.services.identity import TelegramIdentity


def test_channel_settings_can_edit_project_description(client, fake_db):
    identity = TelegramIdentity(telegram_user_id='settings-edit-user', telegram_username='settings_edit_user')
    headers = {
        'x-telegram-user-id': identity.telegram_user_id,
        'x-telegram-username': identity.telegram_username,
    }
    project = client.post('/api/v1/projects', json={'name': 'Settings Project', 'language': 'ru'}, headers=headers).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={'channel_title': 'Settings Channel', 'channel_username': 'settings_channel', 'publish_mode': 'manual', 'is_active': True},
        headers=headers,
    ).json()

    chat_id = 777001
    session_store.clear(chat_id)
    session_store.set_meta(chat_id, 'project_id', project['id'])
    session_store.set_meta(chat_id, 'channel_id', channel['id'])

    edit_screen = resolve_screen_for_text('✏️ Редактировать проект', chat_id=chat_id, identity=identity)
    assert 'Следующий рабочий шаг один: выбери конкретный пункт для редактирования.' in edit_screen.text

    value_prompt = resolve_screen_for_text('✏️ Описание', chat_id=chat_id, identity=identity)
    assert 'Введи новое описание проекта / контекст.' in value_prompt.text

    updated = resolve_screen_for_text('Новый контекст проекта для генерации.', chat_id=chat_id, identity=identity)
    assert 'Описание: Новый контекст проекта для генерации.' in updated.text
