from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class AuditEventBase(BaseModel):
    project_id: UUID | None = None
    user_id: UUID | None = None
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: UUID | None = None
    action: str = Field(..., min_length=1, max_length=100)
    before_json: dict | None = None
    after_json: dict | None = None
    notes: str | None = None


class AuditEventCreate(AuditEventBase):
    pass


class AuditEventUpdate(BaseModel):
    project_id: UUID | None = None
    user_id: UUID | None = None
    entity_type: str | None = Field(default=None, min_length=1, max_length=100)
    entity_id: UUID | None = None
    action: str | None = Field(default=None, min_length=1, max_length=100)
    before_json: dict | None = None
    after_json: dict | None = None
    notes: str | None = None


class AuditEventRead(TimestampedSchema):
    project_id: UUID | None
    user_id: UUID | None
    entity_type: str
    entity_id: UUID | None
    action: str
    before_json: dict | None
    after_json: dict | None
    notes: str | None
