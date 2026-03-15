from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PricingOperationRead(BaseModel):
    operation_type: str
    label: str
    successful_events_count: int
    total_events_count: int
    average_cost_usd: Decimal
    target_margin_pct: Decimal
    contingency_pct: Decimal
    recommended_unit_price_usd: Decimal
    recommended_unit_margin_usd: Decimal
    recommended_unit_margin_pct: Decimal | None
    delta_vs_average_cost_usd: Decimal
    observed_share_pct: Decimal
    included_share: Decimal


class PricingPlanRead(BaseModel):
    plan_code: str
    label: str
    service_tier: str
    execution_mode: str
    monthly_fee_usd: Decimal
    included_channels: int
    included_generations: int
    max_tasks_per_day: int
    allowed_preset_codes: list[str]
    default_preset_code: str
    access_flag: str
    allowed_generation_operations: list[str]
    blended_generation_cost_usd: Decimal
    observed_blended_generation_cost_usd: Decimal
    included_cogs_usd: Decimal
    projected_sample_generation_cost_usd: Decimal
    projected_sample_total_cogs_usd: Decimal
    target_margin_pct: Decimal
    projected_gross_margin_usd: Decimal
    projected_gross_margin_pct: Decimal | None
    projected_sample_gross_margin_usd: Decimal
    projected_sample_gross_margin_pct: Decimal | None
    overage_unit_price_usd: Decimal


class ClientPricingSummaryRead(BaseModel):
    client_id: UUID
    generated_at: datetime
    target_margin_pct: Decimal
    contingency_pct: Decimal
    platform_overhead_usd: Decimal
    channel_overhead_usd: Decimal
    active_plan_code: str
    currency: str
    operation_rates: list[PricingOperationRead]
    plan_catalog: list[PricingPlanRead]
    assumptions: dict
