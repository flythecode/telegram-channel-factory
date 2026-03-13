from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import OperationMode, ProjectStatus


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    topic: str | None = Field(default=None, max_length=255)
    niche: str | None = Field(default=None, max_length=255)
    language: str = Field(default="ru", min_length=2, max_length=32)
    tone_of_voice: str | None = None
    goal: str | None = None
    content_format: str | None = Field(default=None, max_length=100)
    posting_frequency: str | None = Field(default=None, max_length=100)
    operation_mode: OperationMode = OperationMode.MANUAL
    content_rules: dict[str, Any] | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    topic: str | None = Field(default=None, max_length=255)
    niche: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, min_length=2, max_length=32)
    tone_of_voice: str | None = None
    goal: str | None = None
    content_format: str | None = Field(default=None, max_length=100)
    posting_frequency: str | None = Field(default=None, max_length=100)
    operation_mode: OperationMode | None = None
    content_rules: dict[str, Any] | None = None
    status: ProjectStatus | None = None


class ProjectRead(TimestampedSchema):
    workspace_id: UUID | None
    owner_user_id: UUID | None
    created_by_user_id: UUID | None
    name: str
    description: str | None
    topic: str | None
    niche: str | None
    language: str
    tone_of_voice: str | None
    goal: str | None
    content_format: str | None
    posting_frequency: str | None
    operation_mode: OperationMode
    content_rules: dict[str, Any] | None
    status: ProjectStatus
