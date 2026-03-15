from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.services.generation_service import GenerationExecutionResult


@dataclass(slots=True)
class GenerationUsageSummary:
    client_id: UUID | None
    project_id: UUID | None
    channel_id: UUID | None
    operation_type: str
    events_count: int
    successful_events_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal
    billed_revenue_usd: Decimal
    margin_usd: Decimal
    margin_pct: Decimal | None



def create_generation_event(
    db: Session,
    result: GenerationExecutionResult,
    *,
    task: ContentTask | None = None,
    draft: Draft | None = None,
    channel: TelegramChannel | None = None,
    project: Project | None = None,
    status: str = "succeeded",
) -> LLMGenerationEvent:
    project = _resolve_project(project=project, task=task, draft=draft, channel=channel)
    resolved_channel = _resolve_channel(project=project, task=task, draft=draft, channel=channel)

    project_id = getattr(project, "id", None)
    client_id = getattr(project, "client_account_id", None) or getattr(project, "owner_user_id", None)

    estimated_cost = _estimate_cost_usd(result)
    event = LLMGenerationEvent(
        client_id=client_id,
        project_id=project_id,
        telegram_channel_id=getattr(resolved_channel, "id", None),
        content_task_id=getattr(task, "id", None),
        draft_id=getattr(draft, "id", None),
        operation_type=result.operation_type,
        provider=result.generation.provider,
        model=result.generation.model,
        status=status,
        request_id=result.generation.request_id,
        prompt_tokens=result.generation.prompt_tokens,
        completion_tokens=result.generation.completion_tokens,
        total_tokens=result.generation.total_tokens,
        estimated_cost_usd=estimated_cost,
        latency_ms=result.generation.latency_ms,
    )
    db.add(event)
    return event



def summarize_generation_usage(
    db: Session,
    *,
    billable_rates_usd: dict[str, Decimal | str | float | int] | None = None,
) -> list[GenerationUsageSummary]:
    events = db.query(LLMGenerationEvent).all()
    normalized_rates = {
        operation_type: Decimal(str(rate))
        for operation_type, rate in (billable_rates_usd or {}).items()
    }

    grouped: dict[tuple[UUID | None, UUID | None, UUID | None, str], dict[str, Decimal | int]] = {}
    for event in events:
        key = (event.client_id, event.project_id, event.telegram_channel_id, event.operation_type)
        bucket = grouped.setdefault(
            key,
            {
                "events_count": 0,
                "successful_events_count": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": Decimal("0"),
            },
        )
        bucket["events_count"] += 1
        if event.status == "succeeded":
            bucket["successful_events_count"] += 1
        bucket["total_prompt_tokens"] += int(event.prompt_tokens or 0)
        bucket["total_completion_tokens"] += int(event.completion_tokens or 0)
        bucket["total_tokens"] += int(event.total_tokens or 0)
        bucket["total_cost_usd"] += Decimal(str(event.estimated_cost_usd or 0))

    summaries: list[GenerationUsageSummary] = []
    for key, bucket in sorted(grouped.items(), key=lambda item: tuple("" if part is None else str(part) for part in item[0])):
        client_id, project_id, channel_id, operation_type = key
        billed_revenue_usd = normalized_rates.get(operation_type, Decimal("0")) * int(bucket["successful_events_count"])
        total_cost_usd = _quantize_usd(bucket["total_cost_usd"])
        billed_revenue_usd = _quantize_usd(billed_revenue_usd)
        margin_usd = _quantize_usd(billed_revenue_usd - total_cost_usd)
        margin_pct = None
        if billed_revenue_usd > 0:
            margin_pct = ((margin_usd / billed_revenue_usd) * Decimal("100")).quantize(Decimal("0.01"))
        summaries.append(
            GenerationUsageSummary(
                client_id=client_id,
                project_id=project_id,
                channel_id=channel_id,
                operation_type=operation_type,
                events_count=int(bucket["events_count"]),
                successful_events_count=int(bucket["successful_events_count"]),
                total_prompt_tokens=int(bucket["total_prompt_tokens"]),
                total_completion_tokens=int(bucket["total_completion_tokens"]),
                total_tokens=int(bucket["total_tokens"]),
                total_cost_usd=total_cost_usd,
                billed_revenue_usd=billed_revenue_usd,
                margin_usd=margin_usd,
                margin_pct=margin_pct,
            )
        )
    return summaries



def _resolve_project(
    *,
    project: Project | None,
    task: ContentTask | None,
    draft: Draft | None,
    channel: TelegramChannel | None,
):
    project = project or (task.project if task is not None else None)
    if project is None and draft is not None and getattr(draft, "content_task", None) is not None:
        project = draft.content_task.project
    if project is None and channel is not None:
        project = channel.project
    return project



def _resolve_channel(
    *,
    project,
    task: ContentTask | None,
    draft: Draft | None,
    channel: TelegramChannel | None,
) -> TelegramChannel | None:
    if channel is not None:
        return channel
    draft_task = getattr(draft, "content_task", None)
    draft_project = getattr(draft_task, "project", None)
    task_project = getattr(task, "project", None)
    resolved_project = project or draft_project or task_project
    channels = list(getattr(resolved_project, "telegram_channels", []) or [])
    if len(channels) == 1:
        return channels[0]
    active_channels = [item for item in channels if getattr(item, "is_active", False)]
    if len(active_channels) == 1:
        return active_channels[0]
    return None



def _estimate_cost_usd(result: GenerationExecutionResult) -> Decimal | None:
    total_tokens = result.generation.total_tokens
    if total_tokens is None:
        return None
    return (Decimal(total_tokens) * Decimal("0.000001")).quantize(Decimal("0.000001"))



def _quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))
