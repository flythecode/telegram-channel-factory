from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.models.agent_team_runtime import AgentTeamRuntime
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel


class TenantIsolationError(ValueError):
    """Raised when agent execution leaks outside the active project/client scope."""


@dataclass(slots=True)
class AgentExecutionProfile:
    id: str
    role: str
    name: str
    channel_id: str | None
    preset_code: str | None
    model: str
    priority: int
    sort_order: int
    prompt_fingerprint: str
    config: dict[str, Any] | None


@dataclass(slots=True)
class AgentTeamRuntimeSnapshot:
    id: str
    project_id: str
    channel_id: str | None
    client_account_id: str | None
    runtime_scope: str
    runtime_key: str
    display_name: str
    preset_code: str | None
    generation_mode: str
    agent_count: int
    settings_fingerprint: str
    agent_fingerprint: str
    runtime_fingerprint: str
    config_snapshot: dict[str, Any]

    def metadata(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'channel_id': self.channel_id,
            'client_account_id': self.client_account_id,
            'runtime_scope': self.runtime_scope,
            'runtime_key': self.runtime_key,
            'display_name': self.display_name,
            'preset_code': self.preset_code,
            'generation_mode': self.generation_mode,
            'agent_count': self.agent_count,
            'settings_fingerprint': self.settings_fingerprint,
            'agent_fingerprint': self.agent_fingerprint,
            'runtime_fingerprint': self.runtime_fingerprint,
            'config_snapshot': self.config_snapshot,
        }


@dataclass(slots=True)
class ProjectExecutionContext:
    """Frozen tenant-scoped runtime for one project/channel generation run.

    The isolation boundary is the application execution context: agent profiles,
    prompts, project settings, channel scope, and usage attribution are resolved
    per client/project/channel. LLM provider credentials stay product-scoped and
    are intentionally not part of tenant runtime.
    """

    project_id: str
    workspace_id: str | None
    client_account_id: str | None
    owner_user_id: str | None
    channel_id: str | None
    channel_ids: list[str]
    runtime_scope: str
    settings_fingerprint: str
    project_settings: dict[str, Any]
    agents: list[AgentExecutionProfile]
    agent_team_runtime: AgentTeamRuntimeSnapshot

    def metadata(self) -> dict[str, Any]:
        return {
            'project_id': self.project_id,
            'workspace_id': self.workspace_id,
            'client_account_id': self.client_account_id,
            'owner_user_id': self.owner_user_id,
            'channel_id': self.channel_id,
            'channel_ids': self.channel_ids,
            'runtime_scope': self.runtime_scope,
            'tenant_isolation_mode': 'isolated_agent_profiles_and_execution_context',
            'provider_key_scope': 'application',
            'provider_key_per_client': False,
            'settings_fingerprint': self.settings_fingerprint,
            'project_settings': self.project_settings,
            'agent_team_runtime': self.agent_team_runtime.metadata(),
            'agent_runtime': [
                {
                    'agent_id': agent.id,
                    'role': agent.role,
                    'name': agent.name,
                    'channel_id': agent.channel_id,
                    'preset_code': agent.preset_code,
                    'model': agent.model,
                    'priority': agent.priority,
                    'sort_order': agent.sort_order,
                    'prompt_fingerprint': agent.prompt_fingerprint,
                    'config': agent.config,
                }
                for agent in self.agents
            ],
        }



def resolve_project_execution_context(
    db: Session,
    *,
    task: ContentTask,
    channel: TelegramChannel | None = None,
) -> ProjectExecutionContext:
    project = task.project or db.get(Project, task.project_id)
    if project is None:
        raise TenantIsolationError('Project runtime context is missing for the task')

    project_channels = _list_project_channels(db, project)
    resolved_channel = _resolve_channel(project_channels, channel)
    agents = _list_project_agents(db, project.id)
    scoped_agents = _scope_agents_to_project_channel(agents, project=project, channel=resolved_channel)
    project_settings = _build_project_settings(project)
    agent_snapshots = [_agent_snapshot(agent) for agent in scoped_agents]
    agent_fingerprint = _fingerprint({'agents': agent_snapshots})
    settings_fingerprint = _fingerprint({'project': project_settings, 'agents': agent_snapshots})
    runtime_record = _ensure_agent_team_runtime(
        db,
        project=project,
        channel=resolved_channel,
        project_settings=project_settings,
        agent_snapshots=agent_snapshots,
        settings_fingerprint=settings_fingerprint,
        agent_fingerprint=agent_fingerprint,
    )

    return ProjectExecutionContext(
        project_id=str(project.id),
        workspace_id=_stringify(getattr(project, 'workspace_id', None)),
        client_account_id=_stringify(getattr(project, 'client_account_id', None)),
        owner_user_id=_stringify(getattr(project, 'owner_user_id', None)),
        channel_id=_stringify(getattr(resolved_channel, 'id', None)),
        channel_ids=[str(item.id) for item in project_channels],
        runtime_scope='project',
        settings_fingerprint=settings_fingerprint,
        project_settings=project_settings,
        agents=[_freeze_agent(agent) for agent in scoped_agents],
        agent_team_runtime=_freeze_runtime(runtime_record),
    )



def _ensure_agent_team_runtime(
    db: Session,
    *,
    project: Project,
    channel: TelegramChannel | None,
    project_settings: dict[str, Any],
    agent_snapshots: list[dict[str, Any]],
    settings_fingerprint: str,
    agent_fingerprint: str,
) -> AgentTeamRuntime:
    runtime_scope = 'project_channel' if channel is not None else 'project'
    runtime_key = f"{project.id}:{getattr(channel, 'id', 'project-default')}"
    preset_code = next((item.get('preset_code') for item in agent_snapshots if item.get('preset_code')), None)
    generation_mode = _resolve_generation_mode(
        project=project,
        agent_snapshots=agent_snapshots,
        client_account=_resolve_client_account(db, project),
    )
    runtime_payload = {
        'project': project_settings,
        'agents': agent_snapshots,
        'channel': _channel_snapshot(channel),
        'runtime_scope': runtime_scope,
        'generation_mode': generation_mode,
    }
    runtime_fingerprint = _fingerprint(runtime_payload)
    display_name = _runtime_display_name(project, channel)
    config_snapshot = {
        'project_settings': project_settings,
        'channel': _channel_snapshot(channel),
        'agent_runtime': agent_snapshots,
    }

    runtime_record = _find_existing_runtime(db, project=project, channel=channel)
    if runtime_record is None:
        runtime_record = AgentTeamRuntime(
            project_id=project.id,
            channel_id=getattr(channel, 'id', None),
            client_account_id=getattr(project, 'client_account_id', None),
            runtime_scope=runtime_scope,
            runtime_key=runtime_key,
            display_name=display_name,
            preset_code=preset_code,
            generation_mode=generation_mode,
            agent_count=len(agent_snapshots),
            settings_fingerprint=settings_fingerprint,
            agent_fingerprint=agent_fingerprint,
            runtime_fingerprint=runtime_fingerprint,
            config_snapshot=config_snapshot,
            notes='Auto-synced from tenant execution context resolver.',
            is_active=True,
        )
        db.add(runtime_record)
        _attach_runtime_relationships(project, channel, runtime_record)
        return runtime_record

    runtime_record.client_account_id = getattr(project, 'client_account_id', None)
    runtime_record.runtime_scope = runtime_scope
    runtime_record.runtime_key = runtime_key
    runtime_record.display_name = display_name
    runtime_record.preset_code = preset_code
    runtime_record.generation_mode = generation_mode
    runtime_record.agent_count = len(agent_snapshots)
    runtime_record.settings_fingerprint = settings_fingerprint
    runtime_record.agent_fingerprint = agent_fingerprint
    runtime_record.runtime_fingerprint = runtime_fingerprint
    runtime_record.config_snapshot = config_snapshot
    runtime_record.is_active = True
    _attach_runtime_relationships(project, channel, runtime_record)
    return runtime_record



def _find_existing_runtime(db: Session, *, project: Project, channel: TelegramChannel | None) -> AgentTeamRuntime | None:
    project_runtimes = list(getattr(project, 'agent_team_runtimes', []) or [])
    target_channel_id = getattr(channel, 'id', None)
    for runtime_record in project_runtimes:
        if getattr(runtime_record, 'channel_id', None) == target_channel_id:
            return runtime_record

    for runtime_record in db.query(AgentTeamRuntime).all():
        if runtime_record.project_id != project.id:
            continue
        if getattr(runtime_record, 'channel_id', None) == target_channel_id:
            return runtime_record
    return None



def _resolve_client_account(db: Session, project: Project) -> ClientAccount | None:
    client_account = getattr(project, 'client_account', None)
    if client_account is not None:
        return client_account
    client_account_id = getattr(project, 'client_account_id', None)
    if client_account_id is None:
        return None
    return db.get(ClientAccount, client_account_id)



def _resolve_generation_mode(
    *,
    project: Project,
    agent_snapshots: list[dict[str, Any]],
    client_account: ClientAccount | None,
) -> str:
    if len(agent_snapshots) <= 1:
        return 'single-pass'

    settings = getattr(client_account, 'settings', None) or {}
    explicit_mode = settings.get('generation_mode') if isinstance(settings, dict) else None
    if explicit_mode in {'single-pass', 'multi-stage'}:
        return explicit_mode

    plan_code = str(getattr(client_account, 'subscription_plan_code', '') or '').strip().lower()
    cheap_plans = {'trial', 'free', 'starter', 'basic', 'lite'}
    premium_plans = {'pro', 'business', 'growth', 'premium', 'scale', 'enterprise'}
    if plan_code in cheap_plans:
        return 'single-pass'
    if plan_code in premium_plans:
        return 'multi-stage'
    return 'multi-stage'



def _attach_runtime_relationships(project: Project, channel: TelegramChannel | None, runtime_record: AgentTeamRuntime) -> None:
    project_runtimes = getattr(project, 'agent_team_runtimes', None)
    if isinstance(project_runtimes, list) and runtime_record not in project_runtimes:
        project_runtimes.append(runtime_record)
    runtime_record.project = project

    if channel is None:
        return
    channel_runtimes = getattr(channel, 'agent_team_runtimes', None)
    if isinstance(channel_runtimes, list) and runtime_record not in channel_runtimes:
        channel_runtimes.append(runtime_record)
    runtime_record.telegram_channel = channel



def _freeze_runtime(runtime_record: AgentTeamRuntime) -> AgentTeamRuntimeSnapshot:
    return AgentTeamRuntimeSnapshot(
        id=str(runtime_record.id),
        project_id=str(runtime_record.project_id),
        channel_id=_stringify(runtime_record.channel_id),
        client_account_id=_stringify(runtime_record.client_account_id),
        runtime_scope=runtime_record.runtime_scope,
        runtime_key=runtime_record.runtime_key,
        display_name=runtime_record.display_name,
        preset_code=runtime_record.preset_code,
        generation_mode=runtime_record.generation_mode,
        agent_count=runtime_record.agent_count,
        settings_fingerprint=runtime_record.settings_fingerprint,
        agent_fingerprint=runtime_record.agent_fingerprint,
        runtime_fingerprint=runtime_record.runtime_fingerprint,
        config_snapshot=runtime_record.config_snapshot,
    )



def _list_project_agents(db: Session, project_id: UUID) -> list[AgentProfile]:
    agents = [agent for agent in db.query(AgentProfile).all() if agent.project_id == project_id and agent.is_enabled]
    agents.sort(key=lambda item: (item.sort_order, item.priority, item.created_at))
    return agents



def _list_project_channels(db: Session, project: Project) -> list[TelegramChannel]:
    channels = list(getattr(project, 'telegram_channels', []) or [])
    if channels:
        return channels
    channels = [channel for channel in db.query(TelegramChannel).all() if channel.project_id == project.id]
    channels.sort(key=lambda item: (item.created_at, item.channel_title))
    return channels



def _resolve_channel(project_channels: list[TelegramChannel], explicit_channel: TelegramChannel | None) -> TelegramChannel | None:
    if explicit_channel is not None:
        return explicit_channel
    if len(project_channels) == 1:
        return project_channels[0]
    active_channels = [channel for channel in project_channels if getattr(channel, 'is_active', False)]
    if len(active_channels) == 1:
        return active_channels[0]
    return None



def _scope_agents_to_project_channel(
    agents: list[AgentProfile],
    *,
    project: Project,
    channel: TelegramChannel | None,
) -> list[AgentProfile]:
    scoped_agents: list[AgentProfile] = []
    project_id = getattr(project, 'id', None)
    project_client_id = getattr(project, 'client_account_id', None)

    for agent in agents:
        if agent.project_id != project_id:
            raise TenantIsolationError('Agent execution attempted to cross project boundary')
        agent_project = getattr(agent, 'project', None)
        if agent_project is not None:
            agent_client_id = getattr(agent_project, 'client_account_id', None)
            if project_client_id is not None and agent_client_id not in (None, project_client_id):
                raise TenantIsolationError('Agent execution attempted to cross client account boundary')
        if channel is not None and agent.channel_id not in (None, channel.id):
            continue
        scoped_agents.append(agent)

    return scoped_agents



def _build_project_settings(project: Project) -> dict[str, Any]:
    return {
        'name': project.name,
        'language': project.language,
        'topic': project.topic,
        'niche': project.niche,
        'tone_of_voice': project.tone_of_voice,
        'goal': project.goal,
        'content_format': project.content_format,
        'posting_frequency': project.posting_frequency,
        'operation_mode': project.operation_mode.value if hasattr(project.operation_mode, 'value') else project.operation_mode,
        'content_rules': project.content_rules,
    }



def _freeze_agent(agent: AgentProfile) -> AgentExecutionProfile:
    return AgentExecutionProfile(
        id=str(agent.id),
        role=agent.role.value if hasattr(agent.role, 'value') else str(agent.role),
        name=agent.display_name or agent.name,
        channel_id=_stringify(agent.channel_id),
        preset_code=agent.preset_code,
        model=agent.model,
        priority=agent.priority,
        sort_order=agent.sort_order,
        prompt_fingerprint=_fingerprint(
            {
                'system_prompt': agent.system_prompt,
                'style_prompt': agent.style_prompt,
                'custom_prompt': agent.custom_prompt,
            }
        ),
        config=agent.config,
    )



def _agent_snapshot(agent: AgentProfile) -> dict[str, Any]:
    return {
        'id': str(agent.id),
        'channel_id': _stringify(agent.channel_id),
        'role': agent.role.value if hasattr(agent.role, 'value') else str(agent.role),
        'name': agent.display_name or agent.name,
        'preset_code': agent.preset_code,
        'model': agent.model,
        'priority': agent.priority,
        'sort_order': agent.sort_order,
        'system_prompt': agent.system_prompt,
        'style_prompt': agent.style_prompt,
        'custom_prompt': agent.custom_prompt,
        'config': agent.config,
    }



def _channel_snapshot(channel: TelegramChannel | None) -> dict[str, Any] | None:
    if channel is None:
        return None
    return {
        'id': str(channel.id),
        'title': channel.channel_title,
        'username': channel.channel_username,
        'telegram_channel_id': channel.channel_id,
        'is_active': channel.is_active,
    }



def _runtime_display_name(project: Project, channel: TelegramChannel | None) -> str:
    if channel is None:
        return f'{project.name} runtime'
    return f'{project.name} / {channel.channel_title} runtime'



def _fingerprint(payload: dict[str, Any]) -> str:
    return sha256(repr(payload).encode('utf-8')).hexdigest()[:16]



def _stringify(value: UUID | str | None) -> str | None:
    return str(value) if value is not None else None
