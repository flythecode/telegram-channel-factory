from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import PublishMode


class TelegramChannelBase(BaseModel):
    channel_title: str = Field(..., min_length=1, max_length=255)
    channel_username: str | None = Field(default=None, max_length=255)
    channel_id: str | None = Field(default=None, max_length=255)
    bot_is_admin: bool = False
    can_post_messages: bool = False
    is_connected: bool = False
    connection_notes: dict | None = None
    publish_mode: PublishMode = PublishMode.MANUAL
    is_active: bool = True


class TelegramChannelCreate(TelegramChannelBase):
    pass


class TelegramChannelUpdate(BaseModel):
    channel_title: str | None = Field(default=None, min_length=1, max_length=255)
    channel_username: str | None = Field(default=None, max_length=255)
    channel_id: str | None = Field(default=None, max_length=255)
    bot_is_admin: bool | None = None
    can_post_messages: bool | None = None
    is_connected: bool | None = None
    connection_notes: dict | None = None
    publish_mode: PublishMode | None = None
    is_active: bool | None = None


class TelegramChannelRead(TimestampedSchema):
    project_id: UUID
    channel_title: str
    channel_username: str | None
    channel_id: str | None
    bot_is_admin: bool
    can_post_messages: bool
    is_connected: bool
    connection_notes: dict | None
    publish_mode: PublishMode
    is_active: bool
