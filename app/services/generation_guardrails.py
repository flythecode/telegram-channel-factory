from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.client_account import ClientAccount
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.services.tariff_policy import build_generation_guardrail_defaults


@dataclass(slots=True)
class GuardrailUsageWindowSnapshot:
    scope: str
    scope_id: str | None
    window: str
    operation_type: str | None
    period_start: str | None
    period_end: str | None
    total_cost_usd: Decimal
    total_generations: int
    total_tokens: int
    budget_limit_usd: Decimal | None
    generation_quota_limit: int | None
    token_quota_limit: int | None
    alert_level: str
    alerts: list[str]

    def metadata(self) -> dict[str, Any]:
        return {
            'scope': self.scope,
            'scope_id': self.scope_id,
            'window': self.window,
            'operation_type': self.operation_type,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'total_cost_usd': f'{self.total_cost_usd:.6f}',
            'total_generations': self.total_generations,
            'total_tokens': self.total_tokens,
            'budget_limit_usd': None if self.budget_limit_usd is None else f'{self.budget_limit_usd:.6f}',
            'generation_quota_limit': self.generation_quota_limit,
            'token_quota_limit': self.token_quota_limit,
            'alert_level': self.alert_level,
            'alerts': self.alerts,
        }


@dataclass(slots=True)
class GuardrailScopeSnapshot:
    scope: str
    scope_id: str | None
    period_start: str | None
    period_end: str | None
    total_cost_usd: Decimal
    total_generations: int
    total_tokens: int
    budget_limit_usd: Decimal | None
    generation_quota_limit: int | None
    token_quota_limit: int | None
    alert_level: str
    alerts: list[str]
    windows: list[GuardrailUsageWindowSnapshot]

    def metadata(self) -> dict[str, Any]:
        return {
            'scope': self.scope,
            'scope_id': self.scope_id,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'total_cost_usd': f'{self.total_cost_usd:.6f}',
            'total_generations': self.total_generations,
            'total_tokens': self.total_tokens,
            'budget_limit_usd': None if self.budget_limit_usd is None else f'{self.budget_limit_usd:.6f}',
            'generation_quota_limit': self.generation_quota_limit,
            'token_quota_limit': self.token_quota_limit,
            'alert_level': self.alert_level,
            'alerts': self.alerts,
            'windows': [item.metadata() for item in self.windows],
        }


@dataclass(slots=True)
class GenerationGuardrailSnapshot:
    period: dict[str, str | None]
    operation_type: str | None
    client: GuardrailScopeSnapshot | None
    channel: GuardrailScopeSnapshot | None
    has_alerts: bool
    soft_limit_reached: bool
    hard_stop_reached: bool
    blocked_scopes: list[str]
    blocking_reasons: list[str]

    def metadata(self) -> dict[str, Any]:
        return {
            'period': self.period,
            'operation_type': self.operation_type,
            'client': self.client.metadata() if self.client else None,
            'channel': self.channel.metadata() if self.channel else None,
            'has_alerts': self.has_alerts,
            'soft_limit_reached': self.soft_limit_reached,
            'hard_stop_reached': self.hard_stop_reached,
            'blocked_scopes': self.blocked_scopes,
            'blocking_reasons': self.blocking_reasons,
        }


class GenerationHardStopError(ValueError):
    def __init__(self, snapshot: GenerationGuardrailSnapshot):
        self.snapshot = snapshot
        scopes = ', '.join(snapshot.blocked_scopes) or 'unknown'
        reasons = '; '.join(snapshot.blocking_reasons) or 'quota exceeded'
        super().__init__(f'Generation hard-stopped for {scopes}: {reasons}')


DEFAULT_SOFT_LIMIT_RATIO = Decimal('0.80')
WINDOW_BILLING = 'billing_period'
WINDOW_DAILY = 'daily'
WINDOW_MONTHLY = 'monthly'


def enforce_generation_hard_stop(
    db: Session,
    *,
    project: Project | None,
    channel: TelegramChannel | None = None,
    operation_type: str | None = None,
) -> GenerationGuardrailSnapshot:
    snapshot = evaluate_generation_guardrails(db, project=project, channel=channel, operation_type=operation_type)
    if snapshot.hard_stop_reached:
        raise GenerationHardStopError(snapshot)
    return snapshot


def evaluate_generation_guardrails(
    db: Session,
    *,
    project: Project | None,
    channel: TelegramChannel | None = None,
    operation_type: str | None = None,
) -> GenerationGuardrailSnapshot:
    client_account = _resolve_client_account(db, project)
    billing_start, billing_end = _resolve_billing_period(client_account)
    period_meta = {
        'start': _iso(billing_start),
        'end': _iso(billing_end),
    }

    client_snapshot = None
    if client_account is not None:
        client_limits = _resolve_client_limits(client_account)
        client_snapshot = _build_scope_snapshot(
            db,
            scope='client',
            scope_id=getattr(client_account, 'id', None),
            scope_events=_filtered_events(
                db,
                client_id=getattr(client_account, 'id', None),
            ),
            billing_start=billing_start,
            billing_end=billing_end,
            limits=client_limits,
            operation_type=operation_type,
        )

    channel_snapshot = None
    resolved_channel = channel or _resolve_default_channel(project)
    if resolved_channel is not None:
        channel_limits = _resolve_channel_limits(client_account, resolved_channel)
        if channel_limits:
            channel_snapshot = _build_scope_snapshot(
                db,
                scope='channel',
                scope_id=getattr(resolved_channel, 'id', None),
                scope_events=_filtered_events(
                    db,
                    client_id=getattr(client_account, 'id', None),
                    channel_id=getattr(resolved_channel, 'id', None),
                ),
                billing_start=billing_start,
                billing_end=billing_end,
                limits=channel_limits,
                operation_type=operation_type,
            )

    snapshots = [item for item in (client_snapshot, channel_snapshot) if item is not None]
    blocked_scopes: list[str] = []
    blocking_reasons: list[str] = []
    for item in snapshots:
        if item.alert_level != 'exceeded':
            continue
        blocked_scopes.append(item.scope)
        blocking_reasons.extend(item.alerts)
    return GenerationGuardrailSnapshot(
        period=period_meta,
        operation_type=operation_type,
        client=client_snapshot,
        channel=channel_snapshot,
        has_alerts=any(item.alerts for item in snapshots),
        soft_limit_reached=any(item.alert_level in {'warning', 'exceeded'} for item in snapshots),
        hard_stop_reached=bool(blocked_scopes),
        blocked_scopes=blocked_scopes,
        blocking_reasons=blocking_reasons,
    )


def _build_scope_snapshot(
    db: Session,
    *,
    scope: str,
    scope_id,
    scope_events: list[LLMGenerationEvent],
    billing_start: datetime | None,
    billing_end: datetime | None,
    limits: dict[str, Any],
    operation_type: str | None,
) -> GuardrailScopeSnapshot:
    del db
    windows: list[GuardrailUsageWindowSnapshot] = []

    billing_window = _build_usage_window(
        scope=scope,
        scope_id=scope_id,
        window=WINDOW_BILLING,
        operation_type=None,
        events=scope_events,
        period_start=billing_start,
        period_end=billing_end,
        limits=limits.get('billing', {}),
    )
    windows.append(billing_window)

    daily_start, daily_end = _current_day_window()
    daily_window = _build_usage_window(
        scope=scope,
        scope_id=scope_id,
        window=WINDOW_DAILY,
        operation_type=None,
        events=scope_events,
        period_start=daily_start,
        period_end=daily_end,
        limits=limits.get('daily', {}),
    )
    if _window_has_limits(daily_window):
        windows.append(daily_window)

    monthly_start, monthly_end = _current_month_window()
    monthly_window = _build_usage_window(
        scope=scope,
        scope_id=scope_id,
        window=WINDOW_MONTHLY,
        operation_type=None,
        events=scope_events,
        period_start=monthly_start,
        period_end=monthly_end,
        limits=limits.get('monthly', {}),
    )
    if _window_has_limits(monthly_window):
        windows.append(monthly_window)

    if operation_type:
        daily_operation_limits = _resolve_operation_limits(limits.get('operation_daily', {}), operation_type)
        if daily_operation_limits:
            windows.append(
                _build_usage_window(
                    scope=scope,
                    scope_id=scope_id,
                    window=WINDOW_DAILY,
                    operation_type=operation_type,
                    events=scope_events,
                    period_start=daily_start,
                    period_end=daily_end,
                    limits=daily_operation_limits,
                )
            )
        monthly_operation_limits = _resolve_operation_limits(limits.get('operation_monthly', {}), operation_type)
        if monthly_operation_limits:
            windows.append(
                _build_usage_window(
                    scope=scope,
                    scope_id=scope_id,
                    window=WINDOW_MONTHLY,
                    operation_type=operation_type,
                    events=scope_events,
                    period_start=monthly_start,
                    period_end=monthly_end,
                    limits=monthly_operation_limits,
                )
            )

    alerts: list[str] = []
    alert_level = 'ok'
    for window in windows:
        if window.alert_level == 'exceeded':
            alert_level = 'exceeded'
        elif window.alert_level == 'warning' and alert_level != 'exceeded':
            alert_level = 'warning'
        alerts.extend(window.alerts)

    return GuardrailScopeSnapshot(
        scope=scope,
        scope_id=None if scope_id is None else str(scope_id),
        period_start=billing_window.period_start,
        period_end=billing_window.period_end,
        total_cost_usd=billing_window.total_cost_usd,
        total_generations=billing_window.total_generations,
        total_tokens=billing_window.total_tokens,
        budget_limit_usd=billing_window.budget_limit_usd,
        generation_quota_limit=billing_window.generation_quota_limit,
        token_quota_limit=billing_window.token_quota_limit,
        alert_level=alert_level,
        alerts=alerts,
        windows=windows,
    )


def _build_usage_window(
    *,
    scope: str,
    scope_id,
    window: str,
    operation_type: str | None,
    events: list[LLMGenerationEvent],
    period_start: datetime | None,
    period_end: datetime | None,
    limits: dict[str, Any],
) -> GuardrailUsageWindowSnapshot:
    filtered_events = _events_in_window(events, period_start=period_start, period_end=period_end, operation_type=operation_type)
    total_cost_usd = Decimal('0')
    total_generations = 0
    total_tokens = 0
    for event in filtered_events:
        if getattr(event, 'status', None) != 'succeeded':
            continue
        total_generations += 1
        total_tokens += int(getattr(event, 'total_tokens', 0) or 0)
        total_cost_usd += Decimal(str(getattr(event, 'estimated_cost_usd', 0) or 0))

    total_cost_usd = total_cost_usd.quantize(Decimal('0.000001'))
    budget_limit = _to_decimal(limits.get('budget_limit_usd'))
    generation_quota_limit = _to_int(limits.get('generation_quota_limit'))
    token_quota_limit = _to_int(limits.get('token_quota_limit'))
    warn_at_ratio = _to_decimal(limits.get('warn_at_ratio')) or DEFAULT_SOFT_LIMIT_RATIO

    alerts: list[str] = []
    alert_level = 'ok'
    for label, current, limit in (
        ('budget', total_cost_usd, budget_limit),
        ('generation_quota', total_generations, generation_quota_limit),
        ('token_quota', total_tokens, token_quota_limit),
    ):
        state = _limit_state(current=current, limit=limit, warn_at_ratio=warn_at_ratio)
        if state == 'exceeded':
            alert_level = 'exceeded'
            alerts.extend(_alert_codes(window=window, label=label, state='exceeded', operation_type=operation_type))
        elif state == 'warning' and alert_level != 'exceeded':
            alert_level = 'warning'
            alerts.extend(_alert_codes(window=window, label=label, state='warning', operation_type=operation_type))

    return GuardrailUsageWindowSnapshot(
        scope=scope,
        scope_id=None if scope_id is None else str(scope_id),
        window=window,
        operation_type=operation_type,
        period_start=_iso(period_start),
        period_end=_iso(period_end),
        total_cost_usd=total_cost_usd,
        total_generations=total_generations,
        total_tokens=total_tokens,
        budget_limit_usd=budget_limit,
        generation_quota_limit=generation_quota_limit,
        token_quota_limit=token_quota_limit,
        alert_level=alert_level,
        alerts=alerts,
    )


def _filtered_events(
    db: Session,
    *,
    client_id=None,
    channel_id=None,
) -> list[LLMGenerationEvent]:
    events: list[LLMGenerationEvent] = []
    for event in db.query(LLMGenerationEvent).all():
        if client_id is not None and getattr(event, 'client_id', None) != client_id:
            continue
        if channel_id is not None and getattr(event, 'telegram_channel_id', None) != channel_id:
            continue
        events.append(event)
    return events


def _events_in_window(
    events: list[LLMGenerationEvent],
    *,
    period_start: datetime | None,
    period_end: datetime | None,
    operation_type: str | None,
) -> list[LLMGenerationEvent]:
    filtered: list[LLMGenerationEvent] = []
    for event in events:
        if operation_type is not None and getattr(event, 'operation_type', None) != operation_type:
            continue
        created_at = getattr(event, 'created_at', None)
        if period_start is not None and created_at is not None and created_at < period_start:
            continue
        if period_end is not None and created_at is not None and created_at >= period_end:
            continue
        filtered.append(event)
    return filtered


def _resolve_client_account(db: Session, project: Project | None) -> ClientAccount | None:
    if project is None:
        return None
    client_account = getattr(project, 'client_account', None)
    if client_account is not None:
        return client_account
    client_account_id = getattr(project, 'client_account_id', None)
    if client_account_id is None:
        return None
    return db.get(ClientAccount, client_account_id)


def _resolve_billing_period(client_account: ClientAccount | None) -> tuple[datetime | None, datetime | None]:
    if client_account is None:
        return None, None
    start = getattr(client_account, 'current_period_start', None)
    end = getattr(client_account, 'current_period_end', None)
    return start, end


def _resolve_client_limits(client_account: ClientAccount) -> dict[str, Any]:
    settings = getattr(client_account, 'settings', None) or {}
    if not isinstance(settings, dict):
        settings = {}
    limits = settings.get('generation_guardrails') or {}
    if not isinstance(limits, dict):
        limits = {}
    defaults = build_generation_guardrail_defaults(client_account)
    return {
        'billing': {
            'budget_limit_usd': limits.get('client_budget_limit_usd', limits.get('budget_limit_usd', defaults.get('billing', {}).get('budget_limit_usd'))),
            'generation_quota_limit': limits.get('client_generation_quota_limit', limits.get('generation_quota_limit', defaults.get('billing', {}).get('generation_quota_limit'))),
            'token_quota_limit': limits.get('client_token_quota_limit', limits.get('token_quota_limit', defaults.get('billing', {}).get('token_quota_limit'))),
            'warn_at_ratio': limits.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO),
        },
        'daily': {
            'budget_limit_usd': limits.get('client_daily_budget_limit_usd', limits.get('daily_budget_limit_usd', defaults.get('daily', {}).get('budget_limit_usd'))),
            'generation_quota_limit': limits.get('client_daily_generation_quota_limit', limits.get('daily_generation_quota_limit', defaults.get('daily', {}).get('generation_quota_limit'))),
            'token_quota_limit': limits.get('client_daily_token_quota_limit', limits.get('daily_token_quota_limit', defaults.get('daily', {}).get('token_quota_limit'))),
            'warn_at_ratio': limits.get('client_daily_warn_at_ratio', limits.get('daily_warn_at_ratio', limits.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO))),
        },
        'monthly': {
            'budget_limit_usd': limits.get('client_monthly_budget_limit_usd', limits.get('monthly_budget_limit_usd', defaults.get('monthly', {}).get('budget_limit_usd'))),
            'generation_quota_limit': limits.get('client_monthly_generation_quota_limit', limits.get('monthly_generation_quota_limit', defaults.get('monthly', {}).get('generation_quota_limit'))),
            'token_quota_limit': limits.get('client_monthly_token_quota_limit', limits.get('monthly_token_quota_limit', defaults.get('monthly', {}).get('token_quota_limit'))),
            'warn_at_ratio': limits.get('client_monthly_warn_at_ratio', limits.get('monthly_warn_at_ratio', limits.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO))),
        },
        'operation_daily': limits.get('client_operation_daily_limits', limits.get('operation_daily_limits', defaults.get('operation_daily', {}))),
        'operation_monthly': limits.get('client_operation_monthly_limits', limits.get('operation_monthly_limits', defaults.get('operation_monthly', {}))),
    }


def _resolve_channel_limits(client_account: ClientAccount | None, channel: TelegramChannel) -> dict[str, Any]:
    if client_account is None:
        return {}
    settings = getattr(client_account, 'settings', None) or {}
    if not isinstance(settings, dict):
        return {}
    limits = settings.get('generation_guardrails') or {}
    if not isinstance(limits, dict):
        return {}
    channel_limits = limits.get('channel_limits') or {}
    if not isinstance(channel_limits, dict):
        return {}
    resolved = channel_limits.get(str(getattr(channel, 'id', ''))) or channel_limits.get(
        str(getattr(channel, 'channel_username', '') or '')
    )
    if not isinstance(resolved, dict):
        return {}
    return {
        'billing': {
            'budget_limit_usd': resolved.get('budget_limit_usd'),
            'generation_quota_limit': resolved.get('generation_quota_limit'),
            'token_quota_limit': resolved.get('token_quota_limit'),
            'warn_at_ratio': resolved.get('warn_at_ratio', limits.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO)),
        },
        'daily': {
            'budget_limit_usd': resolved.get('daily_budget_limit_usd'),
            'generation_quota_limit': resolved.get('daily_generation_quota_limit'),
            'token_quota_limit': resolved.get('daily_token_quota_limit'),
            'warn_at_ratio': resolved.get('daily_warn_at_ratio', resolved.get('warn_at_ratio', limits.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO))),
        },
        'monthly': {
            'budget_limit_usd': resolved.get('monthly_budget_limit_usd'),
            'generation_quota_limit': resolved.get('monthly_generation_quota_limit'),
            'token_quota_limit': resolved.get('monthly_token_quota_limit'),
            'warn_at_ratio': resolved.get('monthly_warn_at_ratio', resolved.get('warn_at_ratio', limits.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO))),
        },
        'operation_daily': resolved.get('operation_daily_limits', {}),
        'operation_monthly': resolved.get('operation_monthly_limits', {}),
    }


def _resolve_operation_limits(operation_limits: Any, operation_type: str) -> dict[str, Any]:
    if not isinstance(operation_limits, dict):
        return {}
    resolved = operation_limits.get(operation_type) or operation_limits.get('*') or {}
    if not isinstance(resolved, dict):
        return {}
    return {
        'budget_limit_usd': resolved.get('budget_limit_usd'),
        'generation_quota_limit': resolved.get('generation_quota_limit'),
        'token_quota_limit': resolved.get('token_quota_limit'),
        'warn_at_ratio': resolved.get('warn_at_ratio', DEFAULT_SOFT_LIMIT_RATIO),
    }


def _resolve_default_channel(project: Project | None) -> TelegramChannel | None:
    channels = list(getattr(project, 'telegram_channels', []) or []) if project is not None else []
    if len(channels) == 1:
        return channels[0]
    active = [item for item in channels if getattr(item, 'is_active', False)]
    if len(active) == 1:
        return active[0]
    return None


def _window_has_limits(window: GuardrailUsageWindowSnapshot) -> bool:
    return any(
        value is not None
        for value in (
            window.budget_limit_usd,
            window.generation_quota_limit,
            window.token_quota_limit,
        )
    )


def _current_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _current_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = now.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _alert_codes(*, window: str, label: str, state: str, operation_type: str | None) -> list[str]:
    codes: list[str] = []
    if operation_type:
        codes.append(f'{window}_{operation_type}_{label}_soft_limit_{state}')
    else:
        codes.append(f'{window}_{label}_soft_limit_{state}')
        if window == WINDOW_BILLING:
            codes.append(f'{label}_soft_limit_{state}')
    return codes


def _limit_state(*, current, limit, warn_at_ratio: Decimal) -> str:
    if limit is None:
        return 'ok'
    limit_decimal = Decimal(str(limit))
    current_decimal = Decimal(str(current))
    if current_decimal >= limit_decimal:
        return 'exceeded'
    if current_decimal >= (limit_decimal * warn_at_ratio):
        return 'warning'
    return 'ok'


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ''):
        return None
    return Decimal(str(value)).quantize(Decimal('0.000001'))


def _to_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    return int(value)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
