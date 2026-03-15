from app.bot.app import resolve_screen_for_text, session_store
from app.services.identity import TelegramIdentity


def test_editing_project_description_does_not_fall_back_to_welcome_screen(client):
    identity = TelegramIdentity(telegram_user_id='settings-edit-user-2', telegram_username='settings_edit_user_2')
    headers = {
        'x-telegram-user-id': identity.telegram_user_id,
        'x-telegram-username': identity.telegram_username,
    }
    project = client.post('/api/v1/projects', json={'name': 'Settings Project', 'language': 'ru'}, headers=headers).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={'channel_title': 'Settings Channel', 'channel_username': 'settings_channel_flow', 'publish_mode': 'manual', 'is_active': True},
        headers=headers,
    ).json()

    chat_id = 777003
    session_store.clear(chat_id)
    session_store.set_meta(chat_id, 'project_id', project['id'])
    session_store.set_meta(chat_id, 'channel_id', channel['id'])

    resolve_screen_for_text('✏️ Редактировать проект', chat_id=chat_id, identity=identity)
    resolve_screen_for_text('✏️ Описание', chat_id=chat_id, identity=identity)
    updated = resolve_screen_for_text('Новый контекст проекта для генерации.', chat_id=chat_id, identity=identity)

    assert 'Редактировать проект' in updated.text
    assert 'Создадим проект канала' not in updated.text
    assert 'Помогаю запустить Telegram-канал' not in updated.text
    assert session_store.get_meta(chat_id, 'project_id') == project['id']
    assert session_store.get_meta(chat_id, 'channel_id') == channel['id']
