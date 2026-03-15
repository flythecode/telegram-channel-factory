from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.admin_cost_dashboard import AdminCostDashboardRead
from app.schemas.admin_generation import (
    GenerationCostBreakdownRead,
    GenerationHistoryRead,
    GenerationUsageRead,
)
from app.services.admin_cost_dashboard import build_admin_cost_dashboard
from app.services.generation_admin import (
    build_generation_cost_breakdown,
    list_generation_history,
    summarize_generation_usage_admin,
)
from app.services.report_exports import render_csv

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/generation/dashboard", response_model=AdminCostDashboardRead)
def get_admin_generation_dashboard(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return build_admin_cost_dashboard(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )


@router.get("/generation/history", response_model=GenerationHistoryRead)
def get_generation_history(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return GenerationHistoryRead(
        items=list_generation_history(
            db,
            client_id=client_id,
            project_id=project_id,
            channel_id=channel_id,
            operation_type=operation_type,
            status=status,
            limit=limit,
        )
    )


@router.get("/generation/usage", response_model=GenerationUsageRead)
def get_generation_usage(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return GenerationUsageRead(
        items=summarize_generation_usage_admin(
            db,
            client_id=client_id,
            project_id=project_id,
            channel_id=channel_id,
            operation_type=operation_type,
            status=status,
        )
    )


@router.get("/generation/cost-breakdown", response_model=GenerationCostBreakdownRead)
def get_generation_cost_breakdown(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return GenerationCostBreakdownRead(
        items=build_generation_cost_breakdown(
            db,
            client_id=client_id,
            project_id=project_id,
            channel_id=channel_id,
            operation_type=operation_type,
            status=status,
        )
    )


@router.get("/generation/dashboard/export", response_class=PlainTextResponse)
def export_admin_generation_dashboard(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    dashboard = build_admin_cost_dashboard(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    rows = [
        {
            "section": "totals",
            "key": dashboard.totals.key,
            "label": dashboard.totals.label,
            "events_count": dashboard.totals.events_count,
            "successful_events_count": dashboard.totals.successful_events_count,
            "failed_events_count": dashboard.totals.failed_events_count,
            "total_prompt_tokens": dashboard.totals.total_prompt_tokens,
            "total_completion_tokens": dashboard.totals.total_completion_tokens,
            "total_tokens": dashboard.totals.total_tokens,
            "total_cost_usd": dashboard.totals.total_cost_usd,
            "period_key": "",
            "period_start": "",
            "period_end": "",
        }
    ]
    for section_name, section_rows in (
        ("by_client", dashboard.by_client),
        ("by_project", dashboard.by_project),
        ("by_channel", dashboard.by_channel),
        ("by_operation", dashboard.by_operation),
        ("by_model", dashboard.by_model),
    ):
        rows.extend(
            {
                "section": section_name,
                "key": row.key,
                "label": row.label,
                "events_count": row.events_count,
                "successful_events_count": row.successful_events_count,
                "failed_events_count": row.failed_events_count,
                "total_prompt_tokens": row.total_prompt_tokens,
                "total_completion_tokens": row.total_completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost_usd": row.total_cost_usd,
                "period_key": "",
                "period_start": "",
                "period_end": "",
            }
            for row in section_rows
        )
    rows.extend(
        {
            "section": "by_period",
            "key": row.period_key,
            "label": row.period_key,
            "events_count": row.events_count,
            "successful_events_count": row.successful_events_count,
            "failed_events_count": row.failed_events_count,
            "total_prompt_tokens": "",
            "total_completion_tokens": "",
            "total_tokens": row.total_tokens,
            "total_cost_usd": row.total_cost_usd,
            "period_key": row.period_key,
            "period_start": row.period_start,
            "period_end": row.period_end,
        }
        for row in dashboard.by_period
    )
    csv_text = render_csv(
        rows,
        columns=[
            "section",
            "key",
            "label",
            "events_count",
            "successful_events_count",
            "failed_events_count",
            "total_prompt_tokens",
            "total_completion_tokens",
            "total_tokens",
            "total_cost_usd",
            "period_key",
            "period_start",
            "period_end",
        ],
    )
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="admin-generation-dashboard-report.csv"'},
    )


@router.get("/generation/usage/export", response_class=PlainTextResponse)
def export_generation_usage_report(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    rows = summarize_generation_usage_admin(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    csv_text = render_csv(
        [
            {
                "client_id": row.client_id,
                "project_id": row.project_id,
                "channel_id": row.channel_id,
                "operation_type": row.operation_type,
                "events_count": row.events_count,
                "successful_events_count": row.successful_events_count,
                "failed_events_count": row.failed_events_count,
                "total_prompt_tokens": row.total_prompt_tokens,
                "total_completion_tokens": row.total_completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost_usd": row.total_cost_usd,
                "average_latency_ms": row.average_latency_ms,
            }
            for row in rows
        ],
        columns=[
            "client_id",
            "project_id",
            "channel_id",
            "operation_type",
            "events_count",
            "successful_events_count",
            "failed_events_count",
            "total_prompt_tokens",
            "total_completion_tokens",
            "total_tokens",
            "total_cost_usd",
            "average_latency_ms",
        ],
    )
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="generation-usage-report.csv"'},
    )


@router.get("/generation/cost-breakdown/export", response_class=PlainTextResponse)
def export_generation_cost_breakdown_report(
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    channel_id: UUID | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    rows = build_generation_cost_breakdown(
        db,
        client_id=client_id,
        project_id=project_id,
        channel_id=channel_id,
        operation_type=operation_type,
        status=status,
    )
    csv_text = render_csv(
        [
            {
                "group_by": row.group_by,
                "key": row.key,
                "label": row.label,
                "events_count": row.events_count,
                "successful_events_count": row.successful_events_count,
                "total_tokens": row.total_tokens,
                "total_cost_usd": row.total_cost_usd,
            }
            for row in rows
        ],
        columns=[
            "group_by",
            "key",
            "label",
            "events_count",
            "successful_events_count",
            "total_tokens",
            "total_cost_usd",
        ],
    )
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="generation-cost-breakdown-report.csv"'},
    )
