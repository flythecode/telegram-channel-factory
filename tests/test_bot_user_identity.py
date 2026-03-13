from app.bot.backend_bridge import BotBackendBridge
from app.services.identity import TelegramIdentity


def test_bot_bridge_auto_finds_or_creates_current_user_and_workspace(fake_db):
    bridge = BotBackendBridge(fake_db, TelegramIdentity(telegram_user_id='auto-user', telegram_username='autouser'))

    assert bridge.user.telegram_user_id == 'auto-user'
    assert bridge.workspace.owner_user_id == bridge.user.id
