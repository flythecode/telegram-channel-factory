from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from datetime import datetime, timedelta, timezone
from typing import Any

PlanAccessFlag = Literal['trial', 'paid', 'unpaid']
GenerationOperationName = Literal['ideas', 'content_plan', 'draft', 'regenerate_draft', 'rewrite_draft', 'agent_stage']

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings

from app.models.agent_profile import AgentProfile
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel


@dataclass(frozen=True, slots=True)
class TariffPlanPolicy:
    plan_code: str
    label: str
    service_tier: str
    execution_mode: str
    included_channels: int
    included_generations: int
    max_tasks_per_day: int
    allowed_preset_codes: tuple[str, ...]
    default_preset_code: str
    access_flag: PlanAccessFlag
    allowed_generation_operations: tuple[GenerationOperationName, ...]

    def metadata(self) -> dict[str, Any]:
        return {
            'plan_code': self.plan_code,
            'label': self.label,
            'service_tier': self.service_tier,
            'execution_mode': self.execution_mode,
            'included_channels': self.included_channels,
            'included_generations': self.included_generations,
            'max_tasks_per_day': self.max_tasks_per_day,
            'allowed_preset_codes': list(self.allowed_preset_codes),
            'default_preset_code': self.default_preset_code,
            'access_flag': self.access_flag,
            'allowed_generation_operations': list(self.allowed_generation_operations),
        }


DEFAULT_PLAN_POLICIES: dict[str, TariffPlanPolicy] = {
    'trial': TariffPlanPolicy(
        plan_code='trial',
        label='Trial',
        service_tier='economy',
        execution_mode='single_pass',
        included_channels=1,
        included_generations=25,
        max_tasks_per_day=3,
        allowed_preset_codes=('starter_3',),
        default_preset_code='starter_3',
        access_flag='trial',
        allowed_generation_operations=('ideas', 'content_plan', 'draft'),
    ),
    'starter': TariffPlanPolicy(
        plan_code='starter',
        label='Starter',
        service_tier='economy',
        execution_mode='single_pass',
        included_channels=1,
        included_generations=300,
        max_tasks_per_day=12,
        allowed_preset_codes=('starter_3', 'balanced_5'),
        default_preset_code='balanced_5',
        access_flag='paid',
        allowed_generation_operations=('ideas', 'content_plan', 'draft', 'regenerate_draft'),
    ),
    'pro': TariffPlanPolicy(
        plan_code='pro',
        label='Pro',
        service_tier='standard',
        execution_mode='multi_stage',
        included_channels=3,
        included_generations=1500,
        max_tasks_per_day=40,
        allowed_preset_codes=('starter_3', 'balanced_5', 'editorial_7'),
        default_preset_code='balanced_5',
        access_flag='paid',
        allowed_generation_operations=('ideas', 'content_plan', 'draft', 'regenerate_draft', 'rewrite_draft', 'agent_stage'),
    ),
    'business': TariffPlanPolicy(
        plan_code='business',
        label='Business',
        service_tier='premium',
        execution_mode='multi_stage',
        included_channels=10,
        included_generations=6000,
        max_tasks_per_day=150,
        allowed_preset_codes=('starter_3', 'balanced_5', 'editorial_7'),
        default_preset_code='editorial_7',
        access_flag='paid',
        allowed_generation_operations=('ideas', 'content_plan', 'draft', 'regenerate_draft', 'rewrite_draft', 'agent_stage'),
    ),
}
DEFAULT_FALLBACK_PLAN_CODE = 'trial'


def resolve_plan_policy(client_account: ClientAccount | None) -> TariffPlanPolicy:
    plan_code = (getattr(client_account, 'subscription_plan_code', '') or DEFAULT_FALLBACK_PLAN_CODE).strip().lower()
    return DEFAULT_PLAN_POLICIES.get(plan_code, DEFAULT_PLAN_POLICIES[DEFAULT_FALLBACK_PLAN_CODE])


def resolve_plan_access_flag(client_account: ClientAccount | None) -> PlanAccessFlag:
    if client_account is None:
        return 'paid'
    raw_status = getattr(client_account, 'subscription_status', '')
    status_value = getattr(raw_status, 'value', raw_status)
    status_value = str(status_value or '').strip().lower()
    if status_value == 'trial':
        return 'trial'
    if status_value in {'active'}:
        return 'paid'
    return 'unpaid'


def enforce_generation_operation_access(db: Session, *, project: Project | None, operation_type: GenerationOperationName) -> TariffPlanPolicy:
    client_account = _resolve_client_account_from_project(db, project)
    if client_account is None:
        return DEFAULT_PLAN_POLICIES[DEFAULT_FALLBACK_PLAN_CODE]
    if _is_test_identity_account(client_account):
        return DEFAULT_PLAN_POLICIES['business']
    plan = resolve_plan_policy(client_account)
    access_flag = resolve_plan_access_flag(client_account)
    if access_flag == 'unpaid':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Generation operation '{operation_type}' is unavailable while the subscription is unpaid. "
                "Update billing to resume generation."
            ),
        )
    if operation_type not in plan.allowed_generation_operations:
        allowed = ', '.join(plan.allowed_generation_operations)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Generation operation '{operation_type}' is not available on plan '{plan.plan_code}'. "
                f"Allowed operations: {allowed}."
            ),
        )
    return plan


def enforce_channel_limit(db: Session, *, project: Project) -> TariffPlanPolicy:
    client_account = _resolve_client_account_from_project(db, project)
    if client_account is None:
        return DEFAULT_PLAN_POLICIES[DEFAULT_FALLBACK_PLAN_CODE]
    if _is_test_identity_account(client_account):
        return DEFAULT_PLAN_POLICIES['business']
    plan = resolve_plan_policy(client_account)
    active_channels = [
        channel
        for channel in db.query(TelegramChannel).all()
        if _channel_belongs_to_client(channel, client_account_id=getattr(client_account, 'id', None), db=db)
    ]
    if len(active_channels) >= plan.included_channels:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Plan '{plan.plan_code}' allows up to {plan.included_channels} channel(s); "
                f"upgrade to add more channels."
            ),
        )
    return plan


def enforce_task_frequency_limit(db: Session, *, project: Project) -> TariffPlanPolicy:
    client_account = _resolve_client_account_from_project(db, project)
    if client_account is None:
        return DEFAULT_PLAN_POLICIES[DEFAULT_FALLBACK_PLAN_CODE]
    if _is_test_identity_account(client_account):
        return DEFAULT_PLAN_POLICIES['business']
    plan = resolve_plan_policy(client_account)
    window_start, window_end = _current_day_window()
    tasks_today = [
        task
        for task in db.query(ContentTask).all()
        if _task_belongs_to_client(task, client_account_id=getattr(client_account, 'id', None), db=db)
        and _created_within(task, window_start=window_start, window_end=window_end)
    ]
    if len(tasks_today) >= plan.max_tasks_per_day:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Plan '{plan.plan_code}' allows up to {plan.max_tasks_per_day} task(s) per day; "
                f"wait for the next window or upgrade the tariff."
            ),
        )
    return plan


def enforce_agent_team_preset_access(db: Session, *, project: Project, preset_code: str) -> TariffPlanPolicy:
    client_account = _resolve_client_account_from_project(db, project)
    if client_account is None:
        return DEFAULT_PLAN_POLICIES[DEFAULT_FALLBACK_PLAN_CODE]
    if _is_test_identity_account(client_account):
        return DEFAULT_PLAN_POLICIES['business']
    plan = resolve_plan_policy(client_account)
    if preset_code not in plan.allowed_preset_codes:
        allowed = ', '.join(plan.allowed_preset_codes)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Preset '{preset_code}' is not available on plan '{plan.plan_code}'. "
                f"Allowed presets: {allowed}."
            ),
        )
    return plan


def build_generation_guardrail_defaults(client_account: ClientAccount | None) -> dict[str, Any]:
    plan = resolve_plan_policy(client_account)
    return {
        'billing': {
            'generation_quota_limit': plan.included_generations,
        },
        'daily': {},
        'monthly': {
            'generation_quota_limit': plan.included_generations,
        },
        'operation_daily': {},
        'operation_monthly': {},
    }


def describe_current_agent_team(db: Session, *, project: Project) -> dict[str, Any]:
    enabled_agents = [
        agent for agent in db.query(AgentProfile).all() if getattr(agent, 'project_id', None) == project.id and getattr(agent, 'is_enabled', True)
    ]
    preset_code = next((agent.preset_code for agent in enabled_agents if getattr(agent, 'preset_code', None)), None)
    return {
        'preset_code': preset_code,
        'enabled_agents_count': len(enabled_agents),
    }


def _resolve_client_account_from_project(db: Session, project: Project | None) -> ClientAccount | None:
    if project is None:
        return None
    client_account = getattr(project, 'client_account', None)
    if client_account is not None:
        return client_account
    client_account_id = getattr(project, 'client_account_id', None)
    if client_account_id is None:
        return None
    return db.get(ClientAccount, client_account_id)


def _is_test_identity_account(client_account: ClientAccount | None) -> bool:
    if client_account is None or settings.app_env != 'test':
        return False
    settings_payload = getattr(client_account, 'settings', None) or {}
    return isinstance(settings_payload, dict) and settings_payload.get('source') == 'telegram_identity'


def _channel_belongs_to_client(channel: TelegramChannel, *, client_account_id, db: Session) -> bool:
    project = getattr(channel, 'project', None) or db.get(Project, getattr(channel, 'project_id', None))
    if project is None:
        return False
    return getattr(project, 'client_account_id', None) == client_account_id


def _task_belongs_to_client(task: ContentTask, *, client_account_id, db: Session) -> bool:
    project = getattr(task, 'project', None) or db.get(Project, getattr(task, 'project_id', None))
    if project is None:
        return False
    return getattr(project, 'client_account_id', None) == client_account_id


def _created_within(entity: Any, *, window_start: datetime, window_end: datetime) -> bool:
    created_at = getattr(entity, 'created_at', None)
    if created_at is None:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return window_start <= created_at < window_end


def _current_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)
