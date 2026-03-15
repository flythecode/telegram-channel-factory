from fastapi import APIRouter, Depends, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.client_account import ClientAccountRead
from app.schemas.cost_dashboard import CostDashboardRead
from app.schemas.pricing import ClientPricingSummaryRead
from app.schemas.user import UserRead
from app.schemas.workspace import WorkspaceRead
from app.services.cost_dashboard import build_cost_dashboard
from app.services.pricing import build_client_pricing_summary
from app.services.report_exports import render_csv
from app.services.identity import (
    TelegramIdentity,
    get_or_create_client_account_for_user,
    get_or_create_current_user,
    get_or_create_workspace_for_user,
    get_telegram_identity,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_current_user(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    return get_or_create_current_user(db, identity)


@router.get("/me/workspace", response_model=WorkspaceRead)
def get_my_workspace(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    return get_or_create_workspace_for_user(db, user, identity)


@router.get("/me/client-account", response_model=ClientAccountRead)
def get_my_client_account(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    workspace = get_or_create_workspace_for_user(db, user, identity)
    return get_or_create_client_account_for_user(db, user, workspace, identity)


@router.get("/me/client-account/cost-dashboard", response_model=CostDashboardRead)
def get_my_client_account_cost_dashboard(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    workspace = get_or_create_workspace_for_user(db, user, identity)
    client_account = get_or_create_client_account_for_user(db, user, workspace, identity)
    return build_cost_dashboard(db, client_account)


@router.get("/me/client-account/pricing", response_model=ClientPricingSummaryRead)
def get_my_client_account_pricing_summary(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    workspace = get_or_create_workspace_for_user(db, user, identity)
    client_account = get_or_create_client_account_for_user(db, user, workspace, identity)
    return build_client_pricing_summary(db, client_account)


@router.get("/me/client-account/cost-dashboard/export", response_class=PlainTextResponse)
def export_my_client_account_cost_dashboard(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    workspace = get_or_create_workspace_for_user(db, user, identity)
    client_account = get_or_create_client_account_for_user(db, user, workspace, identity)
    dashboard = build_cost_dashboard(db, client_account)
    rows = [
        {
            "section": "totals",
            "key": dashboard.totals.key,
            "label": dashboard.totals.label,
            "events_count": dashboard.totals.events_count,
            "successful_events_count": dashboard.totals.successful_events_count,
            "total_prompt_tokens": dashboard.totals.total_prompt_tokens,
            "total_completion_tokens": dashboard.totals.total_completion_tokens,
            "total_tokens": dashboard.totals.total_tokens,
            "total_cost_usd": dashboard.totals.total_cost_usd,
            "period_key": "",
            "period_start": dashboard.billing_period_start,
            "period_end": dashboard.billing_period_end,
        }
    ]
    rows.extend(
        {
            "section": "by_channel",
            "key": row.key,
            "label": row.label,
            "events_count": row.events_count,
            "successful_events_count": row.successful_events_count,
            "total_prompt_tokens": row.total_prompt_tokens,
            "total_completion_tokens": row.total_completion_tokens,
            "total_tokens": row.total_tokens,
            "total_cost_usd": row.total_cost_usd,
            "period_key": "",
            "period_start": "",
            "period_end": "",
        }
        for row in dashboard.by_channel
    )
    rows.extend(
        {
            "section": "by_operation",
            "key": row.key,
            "label": row.label,
            "events_count": row.events_count,
            "successful_events_count": row.successful_events_count,
            "total_prompt_tokens": row.total_prompt_tokens,
            "total_completion_tokens": row.total_completion_tokens,
            "total_tokens": row.total_tokens,
            "total_cost_usd": row.total_cost_usd,
            "period_key": "",
            "period_start": "",
            "period_end": "",
        }
        for row in dashboard.by_operation
    )
    rows.extend(
        {
            "section": "by_model",
            "key": row.key,
            "label": row.label,
            "events_count": row.events_count,
            "successful_events_count": row.successful_events_count,
            "total_prompt_tokens": row.total_prompt_tokens,
            "total_completion_tokens": row.total_completion_tokens,
            "total_tokens": row.total_tokens,
            "total_cost_usd": row.total_cost_usd,
            "period_key": "",
            "period_start": "",
            "period_end": "",
        }
        for row in dashboard.by_model
    )
    rows.extend(
        {
            "section": "by_period",
            "key": row.period_key,
            "label": row.period_key,
            "events_count": row.events_count,
            "successful_events_count": row.successful_events_count,
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
        headers={"Content-Disposition": 'attachment; filename="client-cost-dashboard-report.csv"'},
    )
