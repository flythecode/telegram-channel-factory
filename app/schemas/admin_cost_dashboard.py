from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AdminCostDashboardRowRead(BaseModel):
    key: str
    label: str
    events_count: int
    successful_events_count: int
    failed_events_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal


class AdminCostDashboardPeriodRead(BaseModel):
    period_key: str
    period_start: datetime
    period_end: datetime | None
    events_count: int
    successful_events_count: int
    failed_events_count: int
    total_tokens: int
    total_cost_usd: Decimal


class AdminCostDashboardRead(BaseModel):
    generated_at: datetime
    totals: AdminCostDashboardRowRead
    by_client: list[AdminCostDashboardRowRead]
    by_project: list[AdminCostDashboardRowRead]
    by_channel: list[AdminCostDashboardRowRead]
    by_operation: list[AdminCostDashboardRowRead]
    by_model: list[AdminCostDashboardRowRead]
    by_period: list[AdminCostDashboardPeriodRead]
