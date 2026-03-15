from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.llm_generation_event import LLMGenerationEvent


@dataclass(slots=True)
class AdminCostDashboardRow:
    key: str
    label: str
    events_count: int
    successful_events_count: int
    failed_events_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal


@dataclass(slots=True)
class AdminCostDashboardPeriodSummary:
    period_key: str
    period_start: datetime
    period_end: datetime | None
    events_count: int
    successful_events_count: int
    failed_events_count: int
    total_tokens: int
    total_cost_usd: Decimal


@dataclass(slots=True)
class AdminCostDashboardSummary:
    generated_at: datetime
    totals: AdminCostDashboardRow
    by_client: list[AdminCostDashboardRow]
    by_project: list[AdminCostDashboardRow]
    by_channel: list[AdminCostDashboardRow]
    by_operation: list[AdminCostDashboardRow]
    by_model: list[AdminCostDashboardRow]
    by_period: list[AdminCostDashboardPeriodSummary]


def build_admin_cost_dashboard(
    db: Session,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
) -> AdminCostDashboardSummary:
    events = _filter_events(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    return AdminCostDashboardSummary(
        generated_at=datetime.now(UTC),
        totals=_build_row("total", "All generation", events),
        by_client=_group_rows(events, key_fn=lambda event: str(event.client_id or "unassigned")),
        by_project=_group_rows(events, key_fn=lambda event: str(event.project_id or "unassigned")),
        by_channel=_group_rows(events, key_fn=lambda event: str(event.telegram_channel_id or "unassigned")),
        by_operation=_group_rows(events, key_fn=lambda event: event.operation_type or "unknown"),
        by_model=_group_rows(events, key_fn=lambda event: f"{event.provider}:{event.model}"),
        by_period=_group_periods(events),
    )


def _group_rows(events: list[LLMGenerationEvent], *, key_fn):
    grouped: dict[str, list[LLMGenerationEvent]] = {}
    for event in events:
        key = key_fn(event)
        grouped.setdefault(key, []).append(event)
    rows = [_build_row(key, key, bucket) for key, bucket in grouped.items()]
    return sorted(rows, key=lambda row: (-row.total_cost_usd, row.label))


def _group_periods(events: list[LLMGenerationEvent]) -> list[AdminCostDashboardPeriodSummary]:
    grouped: dict[str, list[LLMGenerationEvent]] = {}
    for event in events:
        created_at = _ensure_utc(event.created_at)
        grouped.setdefault(created_at.strftime("%Y-%m"), []).append(event)

    periods: list[AdminCostDashboardPeriodSummary] = []
    for key, bucket in grouped.items():
        starts = sorted(_ensure_utc(event.created_at) for event in bucket)
        total_cost = sum((Decimal(str(event.estimated_cost_usd or 0)) for event in bucket), Decimal("0"))
        periods.append(
            AdminCostDashboardPeriodSummary(
                period_key=key,
                period_start=starts[0],
                period_end=starts[-1],
                events_count=len(bucket),
                successful_events_count=sum(1 for event in bucket if event.status == "succeeded"),
                failed_events_count=sum(1 for event in bucket if event.status != "succeeded"),
                total_tokens=sum(int(event.total_tokens or 0) for event in bucket),
                total_cost_usd=_quantize_usd(total_cost),
            )
        )
    return sorted(periods, key=lambda period: period.period_key, reverse=True)


def _build_row(key: str, label: str, events: list[LLMGenerationEvent]) -> AdminCostDashboardRow:
    total_cost = sum((Decimal(str(event.estimated_cost_usd or 0)) for event in events), Decimal("0"))
    return AdminCostDashboardRow(
        key=key,
        label=label,
        events_count=len(events),
        successful_events_count=sum(1 for event in events if event.status == "succeeded"),
        failed_events_count=sum(1 for event in events if event.status != "succeeded"),
        total_prompt_tokens=sum(int(event.prompt_tokens or 0) for event in events),
        total_completion_tokens=sum(int(event.completion_tokens or 0) for event in events),
        total_tokens=sum(int(event.total_tokens or 0) for event in events),
        total_cost_usd=_quantize_usd(total_cost),
    )


def _filter_events(
    db: Session,
    *,
    client_id: UUID | None,
    project_id: UUID | None,
    channel_id: UUID | None,
    operation_type: str | None,
    status: str | None,
) -> list[LLMGenerationEvent]:
    events = list(db.query(LLMGenerationEvent).all())
    filtered: list[LLMGenerationEvent] = []
    for event in events:
        if client_id is not None and event.client_id != client_id:
            continue
        if project_id is not None and event.project_id != project_id:
            continue
        if channel_id is not None and event.telegram_channel_id != channel_id:
            continue
        if operation_type is not None and event.operation_type != operation_type:
            continue
        if status is not None and event.status != status:
            continue
        filtered.append(event)
    filtered.sort(key=lambda event: (_ensure_utc(event.created_at), str(event.id)), reverse=True)
    return filtered


def _quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
