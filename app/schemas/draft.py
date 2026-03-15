from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import DraftStatus


class DraftBase(BaseModel):
    text: str = Field(..., min_length=1)
    source_notes: str | None = None
    created_by_agent: str | None = Field(default=None, max_length=255)


class DraftCreate(DraftBase):
    version: int = Field(default=1, ge=1)


class DraftUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    source_notes: str | None = None
    created_by_agent: str | None = Field(default=None, max_length=255)
    generation_metadata: dict | None = None
    status: DraftStatus | None = None


class DraftRewriteRequest(BaseModel):
    rewrite_prompt: str = Field(..., min_length=1, max_length=2000)


class DraftRead(TimestampedSchema):
    content_task_id: UUID
    version: int
    text: str
    source_notes: str | None
    created_by_agent: str | None
    generation_metadata: dict | None
    status: DraftStatus
