from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class AgentTeamPresetBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    agent_count: int = Field(..., ge=1, le=20)
    roles_json: list[str] | dict
    is_recommended: bool = False
    is_active: bool = True


class AgentTeamPresetRead(TimestampedSchema):
    code: str
    title: str
    description: str | None
    agent_count: int
    roles_json: list[str] | dict
    is_recommended: bool
    is_active: bool
