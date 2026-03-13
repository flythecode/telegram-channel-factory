from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class ProjectConfigVersionBase(BaseModel):
    project_id: UUID
    created_by_user_id: UUID | None = None
    version: int = Field(..., ge=1)
    snapshot_json: dict
    change_summary: str | None = None


class ProjectConfigVersionCreate(ProjectConfigVersionBase):
    pass


class ProjectConfigVersionUpdate(BaseModel):
    created_by_user_id: UUID | None = None
    version: int | None = Field(default=None, ge=1)
    snapshot_json: dict | None = None
    change_summary: str | None = None


class ProjectConfigVersionRead(TimestampedSchema):
    project_id: UUID
    created_by_user_id: UUID | None
    version: int
    snapshot_json: dict
    change_summary: str | None
