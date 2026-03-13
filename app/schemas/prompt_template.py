from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class PromptTemplateBase(BaseModel):
    project_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=255)
    scope: str = Field(default="global", min_length=1, max_length=50)
    role_code: str | None = Field(default=None, max_length=100)
    system_prompt: str | None = None
    style_prompt: str | None = None
    notes: str | None = None
    is_active: bool = True


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplateUpdate(BaseModel):
    project_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    scope: str | None = Field(default=None, min_length=1, max_length=50)
    role_code: str | None = Field(default=None, max_length=100)
    system_prompt: str | None = None
    style_prompt: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class PromptTemplateRead(TimestampedSchema):
    project_id: UUID | None
    title: str
    scope: str
    role_code: str | None
    system_prompt: str | None
    style_prompt: str | None
    notes: str | None
    is_active: bool
