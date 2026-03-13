from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import AgentRole


class AgentProfileBase(BaseModel):
    channel_id: UUID | None = None
    preset_code: str | None = Field(default=None, max_length=100)
    role: AgentRole
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    model: str = Field(..., min_length=1, max_length=255)
    system_prompt: str | None = None
    style_prompt: str | None = None
    custom_prompt: str | None = None
    config: dict[str, Any] | None = None
    is_enabled: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    sort_order: int = Field(default=100, ge=0, le=10000)


class AgentProfileCreate(AgentProfileBase):
    pass


class AgentProfileUpdate(BaseModel):
    channel_id: UUID | None = None
    preset_code: str | None = Field(default=None, max_length=100)
    role: AgentRole | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=255)
    system_prompt: str | None = None
    style_prompt: str | None = None
    custom_prompt: str | None = None
    config: dict[str, Any] | None = None
    is_enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class AgentProfileRead(TimestampedSchema):
    project_id: UUID
    channel_id: UUID | None
    preset_code: str | None
    role: AgentRole
    name: str
    display_name: str | None
    description: str | None
    model: str
    system_prompt: str | None
    style_prompt: str | None
    custom_prompt: str | None
    config: dict[str, Any] | None
    is_enabled: bool
    priority: int
    sort_order: int
