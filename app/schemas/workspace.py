from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class WorkspaceBase(BaseModel):
    owner_user_id: UUID
    created_by_user_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    settings: dict[str, Any] | None = None
    is_active: bool = True


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceRead(TimestampedSchema):
    owner_user_id: UUID
    created_by_user_id: UUID | None
    name: str
    slug: str
    description: str | None
    settings: dict[str, Any] | None
    is_active: bool
