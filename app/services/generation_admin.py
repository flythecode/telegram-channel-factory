from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.llm_generation_event import LLMGenerationEvent


@dataclass(slots=True)
class GenerationHistoryItem:
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


@dataclass(slots=True)
class GenerationUsageRow:
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


@dataclass(slots=True)
class GenerationCostBreakdownRow:
    group_by: str
    key: str
    label: str
    events_count: int
    successful_events_count: int
    total_tokens: int
    total_cost_usd: Decimal


def list_generation_history(
    db: Session,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[GenerationHistoryItem]:
    events = _filter_events(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    rows: list[GenerationHistoryItem] = []
    for event in events[: max(1, min(limit, 500))]:
        rows.append(
            GenerationHistoryItem(
                id=event.id,
                created_at=_ensure_utc(event.created_at),
                client_id=event.client_id,
                project_id=event.project_id,
                channel_id=event.telegram_channel_id,
                task_id=event.content_task_id,
                draft_id=event.draft_id,
                operation_type=event.operation_type,
                provider=event.provider,
                model=event.model,
                status=event.status,
                request_id=event.request_id,
                prompt_tokens=int(event.prompt_tokens or 0),
                completion_tokens=int(event.completion_tokens or 0),
                total_tokens=int(event.total_tokens or 0),
                estimated_cost_usd=_quantize_usd(Decimal(str(event.estimated_cost_usd or 0))),
                latency_ms=event.latency_ms,
            )
        )
    return rows



def summarize_generation_usage_admin(
    db: Session,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
) -> list[GenerationUsageRow]:
    events = _filter_events(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    grouped: dict[tuple[UUID | None, UUID | None, UUID | None, str], dict[str, Decimal | int]] = {}
    for event in events:
        key = (event.client_id, event.project_id, event.telegram_channel_id, event.operation_type)
        bucket = grouped.setdefault(
            key,
            {
                "events_count": 0,
                "successful_events_count": 0,
                "failed_events_count": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": Decimal("0"),
                "latency_sum_ms": Decimal("0"),
                "latency_count": 0,
            },
        )
        bucket["events_count"] += 1
        bucket["successful_events_count"] += int(event.status == "succeeded")
        bucket["failed_events_count"] += int(event.status != "succeeded")
        bucket["total_prompt_tokens"] += int(event.prompt_tokens or 0)
        bucket["total_completion_tokens"] += int(event.completion_tokens or 0)
        bucket["total_tokens"] += int(event.total_tokens or 0)
        bucket["total_cost_usd"] += Decimal(str(event.estimated_cost_usd or 0))
        if event.latency_ms is not None:
            bucket["latency_sum_ms"] += Decimal(str(event.latency_ms))
            bucket["latency_count"] += 1

    rows: list[GenerationUsageRow] = []
    for key, bucket in sorted(grouped.items(), key=lambda item: tuple("" if part is None else str(part) for part in item[0])):
        latency = None
        if bucket["latency_count"]:
            latency = (bucket["latency_sum_ms"] / Decimal(str(bucket["latency_count"]))).quantize(Decimal("0.01"))
        rows.append(
            GenerationUsageRow(
                client_id=key[0],
                project_id=key[1],
                channel_id=key[2],
                operation_type=key[3],
                events_count=int(bucket["events_count"]),
                successful_events_count=int(bucket["successful_events_count"]),
                failed_events_count=int(bucket["failed_events_count"]),
                total_prompt_tokens=int(bucket["total_prompt_tokens"]),
                total_completion_tokens=int(bucket["total_completion_tokens"]),
                total_tokens=int(bucket["total_tokens"]),
                total_cost_usd=_quantize_usd(bucket["total_cost_usd"]),
                average_latency_ms=latency,
            )
        )
    return rows



def build_generation_cost_breakdown(
    db: Session,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
) -> list[GenerationCostBreakdownRow]:
    events = _filter_events(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    rows: list[GenerationCostBreakdownRow] = []
    rows.extend(_group_cost_rows(events, group_by="client", key_fn=lambda event: str(event.client_id or "unassigned")))
    rows.extend(_group_cost_rows(events, group_by="channel", key_fn=lambda event: str(event.telegram_channel_id or "unassigned")))
    rows.extend(_group_cost_rows(events, group_by="operation", key_fn=lambda event: event.operation_type or "unknown"))
    rows.extend(_group_cost_rows(events, group_by="model", key_fn=lambda event: f"{event.provider}:{event.model}"))
    return sorted(rows, key=lambda row: (row.group_by, -row.total_cost_usd, row.label))



def _group_cost_rows(events: list[LLMGenerationEvent], *, group_by: str, key_fn):
    grouped: dict[str, list[LLMGenerationEvent]] = {}
    for event in events:
        key = key_fn(event)
        grouped.setdefault(key, []).append(event)
    rows: list[GenerationCostBreakdownRow] = []
    for key, bucket in grouped.items():
        rows.append(
            GenerationCostBreakdownRow(
                group_by=group_by,
                key=key,
                label=key,
                events_count=len(bucket),
                successful_events_count=sum(1 for event in bucket if event.status == "succeeded"),
                total_tokens=sum(int(event.total_tokens or 0) for event in bucket),
                total_cost_usd=_quantize_usd(sum((Decimal(str(event.estimated_cost_usd or 0)) for event in bucket), Decimal("0"))),
            )
        )
    return rows



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
    filtered = []
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
