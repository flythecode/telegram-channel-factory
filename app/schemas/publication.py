from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import PublicationStatus


class PublicationCreate(BaseModel):
    telegram_channel_id: UUID
    scheduled_for: datetime | None = None


class PublicationUpdate(BaseModel):
    scheduled_for: datetime | None = None
    published_at: datetime | None = None
    external_message_id: str | None = Field(default=None, max_length=255)
    error_message: str | None = None
    status: PublicationStatus | None = None
    generation_metadata: dict | None = None


class PublicationRead(TimestampedSchema):
    draft_id: UUID
    telegram_channel_id: UUID
    scheduled_for: datetime | None
    published_at: datetime | None
    external_message_id: str | None
    error_message: str | None
    status: PublicationStatus
    generation_metadata: dict | None
