from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import ContentPlanPeriod


class ContentPlanBase(BaseModel):
    period_type: ContentPlanPeriod
    start_date: date
    end_date: date
    status: str = "generated"
    generated_by: str | None = Field(default=None, max_length=255)
    summary: str | None = None


class ContentPlanCreate(ContentPlanBase):
    pass


class ContentPlanUpdate(BaseModel):
    period_type: ContentPlanPeriod | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    generated_by: str | None = Field(default=None, max_length=255)
    summary: str | None = None


class ContentPlanRead(TimestampedSchema):
    project_id: UUID
    period_type: ContentPlanPeriod
    start_date: date
    end_date: date
    status: str
    generated_by: str | None
    summary: str | None
