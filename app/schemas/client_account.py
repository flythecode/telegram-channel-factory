from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema
from app.utils.enums import BillingCycle, SubscriptionStatus


class ClientAccountRead(TimestampedSchema):
    owner_user_id: UUID
    workspace_id: UUID | None
    name: str
    billing_email: str | None
    external_billing_customer_id: str | None
    subscription_plan_code: str
    subscription_status: SubscriptionStatus
    access_flag: str
    billing_cycle: BillingCycle | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_ends_at: datetime | None
    seats_included: int = Field(ge=1)
    settings: dict | None
    notes: str | None
    is_active: bool
