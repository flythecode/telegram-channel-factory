from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GenerationHistoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    client_id: UUID | None
    project_id: UUID | None
    channel_id: UUID | None
    task_id: UUID | None
    draft_id: UUID | None
    operation_type: str
    provider: str
    model: str
    status: str
    request_id: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: Decimal
    latency_ms: int | None


class GenerationHistoryRead(BaseModel):
    items: list[GenerationHistoryItemRead]


class GenerationUsageRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: UUID | None
    project_id: UUID | None
    channel_id: UUID | None
    operation_type: str
    events_count: int
    successful_events_count: int
    failed_events_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal
    average_latency_ms: Decimal | None


class GenerationUsageRead(BaseModel):
    items: list[GenerationUsageRowRead]


class GenerationCostBreakdownRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_by: str
    key: str
    label: str
    events_count: int
    successful_events_count: int
    total_tokens: int
    total_cost_usd: Decimal


class GenerationCostBreakdownRead(BaseModel):
    items: list[GenerationCostBreakdownRowRead]
