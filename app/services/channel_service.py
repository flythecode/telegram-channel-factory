from sqlalchemy.orm import Session

from app.models.telegram_channel import TelegramChannel
from app.services.audit_service import create_audit_event, snapshot_entity
from app.services.crud import get_entity_or_404, update_entity



def connect_channel(db: Session, channel_id, payload):
    channel = get_entity_or_404(db, TelegramChannel, channel_id, 'Channel not found')
    before = snapshot_entity(channel)
    channel = update_entity(db, channel, payload)
    create_audit_event(
        db,
        project_id=channel.project_id,
        entity_type='channel',
        entity_id=channel.id,
        action='connect_channel',
        before_json=before,
        after_json=snapshot_entity(channel),
    )
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
