from sqlalchemy.orm import Session

from app.models.telegram_channel import TelegramChannel
from app.services.crud import get_entity_or_404, update_entity



def connect_channel(db: Session, channel_id, payload):
    channel = get_entity_or_404(db, TelegramChannel, channel_id, 'Channel not found')
    channel = update_entity(db, channel, payload)
    return channel



def check_channel_connection(db: Session, channel_id):
    channel = get_entity_or_404(db, TelegramChannel, channel_id, 'Channel not found')
    status = 'connected' if channel.is_connected and channel.bot_is_admin and channel.can_post_messages else 'needs_attention'
    return {
        'is_connected': channel.is_connected,
        'bot_is_admin': channel.bot_is_admin,
        'can_post_messages': channel.can_post_messages,
        'status': status,
    }
