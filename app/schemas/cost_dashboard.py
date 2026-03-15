from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CostDashboardRowRead(BaseModel):
    key: str
    label: str
    events_count: int
    successful_events_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal


class CostDashboardPeriodRead(BaseModel):
    period_key: str
    period_start: datetime
    period_end: datetime | None
    events_count: int
    successful_events_count: int
    total_tokens: int
    total_cost_usd: Decimal


class CostDashboardRead(BaseModel):
    client_id: UUID
    generated_at: datetime
    billing_period_start: datetime | None
    billing_period_end: datetime | None
    totals: CostDashboardRowRead
    by_channel: list[CostDashboardRowRead]
    by_operation: list[CostDashboardRowRead]
    by_model: list[CostDashboardRowRead]
    by_period: list[CostDashboardPeriodRead]
