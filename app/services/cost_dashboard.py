from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.client_account import ClientAccount
from app.models.llm_generation_event import LLMGenerationEvent


@dataclass(slots=True)
class CostDashboardRow:
    key: str
    label: str
    events_count: int
    successful_events_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal


@dataclass(slots=True)
class CostDashboardPeriodSummary:
    period_key: str
    period_start: datetime
    period_end: datetime | None
    events_count: int
    successful_events_count: int
    total_tokens: int
    total_cost_usd: Decimal


@dataclass(slots=True)
class CostDashboardSummary:
    client_id: UUID
    generated_at: datetime
    billing_period_start: datetime | None
    billing_period_end: datetime | None
    totals: CostDashboardRow
    by_channel: list[CostDashboardRow]
    by_operation: list[CostDashboardRow]
    by_model: list[CostDashboardRow]
    by_period: list[CostDashboardPeriodSummary]


def build_cost_dashboard(db: Session, client_account: ClientAccount) -> CostDashboardSummary:
    generated_at = datetime.now(UTC)
    events = [
        event
        for event in db.query(LLMGenerationEvent).all()
        if event.client_id == client_account.id or event.client_id == client_account.owner_user_id
    ]

    totals = _build_row("total", "All generation", events)
    by_channel = _group_rows(events, key_fn=lambda event: str(event.telegram_channel_id or "unassigned"), label_fn=lambda event: str(event.telegram_channel_id or "unassigned"))
    by_operation = _group_rows(events, key_fn=lambda event: event.operation_type or "unknown", label_fn=lambda event: event.operation_type or "unknown")
    by_model = _group_rows(events, key_fn=lambda event: f"{event.provider}:{event.model}", label_fn=lambda event: f"{event.provider}:{event.model}")
    by_period = _group_periods(events)
    return CostDashboardSummary(
        client_id=client_account.id,
        generated_at=generated_at,
        billing_period_start=client_account.current_period_start,
        billing_period_end=client_account.current_period_end,
        totals=totals,
        by_channel=by_channel,
        by_operation=by_operation,
        by_model=by_model,
        by_period=by_period,
    )



def _group_rows(events, *, key_fn, label_fn):
    grouped: dict[str, list[LLMGenerationEvent]] = {}
    labels: dict[str, str] = {}
    for event in events:
        key = key_fn(event)
        grouped.setdefault(key, []).append(event)
        labels[key] = label_fn(event)
    rows = [_build_row(key, labels[key], bucket) for key, bucket in grouped.items()]
    return sorted(rows, key=lambda row: (-row.total_cost_usd, row.label))



def _group_periods(events: list[LLMGenerationEvent]) -> list[CostDashboardPeriodSummary]:
    grouped: dict[str, list[LLMGenerationEvent]] = {}
    for event in events:
        created_at = _ensure_utc(event.created_at)
        key = created_at.strftime("%Y-%m")
        grouped.setdefault(key, []).append(event)

    periods: list[CostDashboardPeriodSummary] = []
    for key, bucket in grouped.items():
        starts = sorted(_ensure_utc(event.created_at) for event in bucket)
        total_cost = sum((Decimal(str(event.estimated_cost_usd or 0)) for event in bucket), Decimal("0"))
        periods.append(
            CostDashboardPeriodSummary(
                period_key=key,
                period_start=starts[0],
                period_end=starts[-1],
                events_count=len(bucket),
                successful_events_count=sum(1 for event in bucket if event.status == "succeeded"),
                total_tokens=sum(int(event.total_tokens or 0) for event in bucket),
                total_cost_usd=_quantize_usd(total_cost),
            )
        )
    return sorted(periods, key=lambda period: period.period_key, reverse=True)



def _build_row(key: str, label: str, events: list[LLMGenerationEvent]) -> CostDashboardRow:
    total_cost = sum((Decimal(str(event.estimated_cost_usd or 0)) for event in events), Decimal("0"))
    return CostDashboardRow(
        key=key,
        label=label,
        events_count=len(events),
        successful_events_count=sum(1 for event in events if event.status == "succeeded"),
        total_prompt_tokens=sum(int(event.prompt_tokens or 0) for event in events),
        total_completion_tokens=sum(int(event.completion_tokens or 0) for event in events),
        total_tokens=sum(int(event.total_tokens or 0) for event in events),
        total_cost_usd=_quantize_usd(total_cost),
    )



def _quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))



def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
