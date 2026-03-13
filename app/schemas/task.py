from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import ContentTaskStatus


class ContentTaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    topic: str | None = None
    format: str | None = Field(default=None, max_length=100)
    angle: str | None = None
    brief: str | None = None
    scheduled_for: datetime | None = None


class ContentTaskCreate(ContentTaskBase):
    content_plan_id: UUID | None = None


class ContentTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    topic: str | None = None
    format: str | None = Field(default=None, max_length=100)
    angle: str | None = None
    brief: str | None = None
    scheduled_for: datetime | None = None
    status: ContentTaskStatus | None = None


class ContentTaskRead(TimestampedSchema):
    project_id: UUID
    content_plan_id: UUID | None
    title: str
    topic: str | None
    format: str | None
    angle: str | None
    brief: str | None
    scheduled_for: datetime | None
    status: ContentTaskStatus
