from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.agent_profile import AgentProfile
from app.models.client_account import ClientAccount
from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.draft import Draft
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from app.services.generation_guardrails import GenerationHardStopError
from app.services.generation_service import build_generation_service
from app.utils.enums import AgentRole, SubscriptionStatus


def test_generation_service_creates_draft_metadata(fake_db):
    project = Project(name='Generation Service Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    task = ContentTask(project_id=project.id, title='Service Task', brief='Need concise post')
    fake_db.add(task)
    fake_db.refresh(task)

    result = build_generation_service(fake_db).generate_draft(task, source_text='Seed text')

    assert result.operation_type == 'draft'
    assert result.output_text
    metadata = result.metadata()
    assert metadata['operation_type'] == 'draft'
    assert metadata['provider'] == 'stub'
    assert metadata['final_agent_name'] == result.created_by_agent
    assert isinstance(metadata['stage_generations'], list)
    if metadata['stage_generations']:
        assert metadata['stage_generations'][-1]['agent_name'] == result.created_by_agent


def test_generation_service_regenerate_marks_output(fake_db):
    project = Project(name='Generation Service Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    task = ContentTask(project_id=project.id, title='Service Task')
    fake_db.add(task)
    fake_db.refresh(task)

    draft = Draft(content_task_id=task.id, text='Existing draft', version=1, created_by_agent='Writer')
    draft.content_task = task

    result = build_generation_service(fake_db).regenerate_draft(draft)

    assert result.operation_type == 'regenerate_draft'
    assert '[Regenerated]' in result.output_text
    assert result.metadata()['operation_type'] == 'regenerate_draft'


def test_generation_service_rewrite_uses_generation_path(fake_db):
    project = Project(name='Generation Service Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    task = ContentTask(project_id=project.id, title='Service Task')
    fake_db.add(task)
    fake_db.refresh(task)

    draft = Draft(content_task_id=task.id, text='Existing draft', version=1, created_by_agent='Writer')
    draft.content_task = task

    result = build_generation_service(fake_db).rewrite_draft(draft, rewrite_prompt='Сделай текст короче и жёстче')

    assert result.operation_type == 'rewrite_draft'
    assert 'Сделай текст короче и жёстче' in result.output_text
    assert result.metadata()['operation_type'] == 'rewrite_draft'
    assert result.metadata()['provider'] == 'stub'


def test_generation_service_generates_idea_lines(fake_db):
    result = build_generation_service(fake_db).generate_ideas(
        "Ideas Project",
        brief="крипто-аналитика для Telegram",
        count=3,
    )

    lines = [line for line in result.output_text.splitlines() if line.strip()]
    assert result.operation_type == "ideas"
    assert result.created_by_agent == "generation-service"
    assert len(lines) == 3
    assert lines[0].startswith("1. ")
    assert result.metadata()["operation_type"] == "ideas"


def test_generation_service_generates_content_plan(fake_db):
    project = Project(name='Plan Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    plan = ContentPlan(
        project_id=project.id,
        period_type='week',
        start_date=date(2026, 3, 16),
        end_date=date(2026, 3, 22),
        status='generated',
    )
    fake_db.add(plan)
    fake_db.refresh(plan)

    result = build_generation_service(fake_db).generate_content_plan(
        plan,
        planning_brief='AI-аналитика для Telegram-канала',
    )

    assert result.operation_type == 'content_plan'
    assert result.created_by_agent == 'generation-service'
    assert 'Понедельник' in result.output_text
    assert result.metadata()['operation_type'] == 'content_plan'


def test_generation_service_uses_single_pass_for_trial_plan(fake_db):
    user = User(email='trial-plan@example.com', telegram_user_id='trial-plan')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Trial Plan WS', slug='trial-plan-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Trial Plan Account',
        subscription_plan_code='trial',
        subscription_status=SubscriptionStatus.TRIAL,
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Trial Plan Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)

    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.STRATEGIST,
            name='trial-strategist',
            display_name='Trial Strategist',
            model='stub',
            sort_order=1,
            priority=10,
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.WRITER,
            name='trial-writer',
            display_name='Trial Writer',
            model='stub',
            sort_order=2,
            priority=20,
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.PUBLISHER,
            name='trial-publisher',
            display_name='Trial Publisher',
            model='stub',
            sort_order=3,
            priority=30,
        )
    )

    task = ContentTask(project_id=project.id, title='Trial task', brief='Need one cheap pass only')
    fake_db.add(task)
    fake_db.refresh(task)

    result = build_generation_service(fake_db).generate_draft(task, source_text='Seed text')
    metadata = result.metadata()

    assert metadata['execution_context']['agent_team_runtime']['generation_mode'] == 'single-pass'
    assert metadata['stage_roles'] == ['publisher']
    assert len(metadata['stage_generations']) == 1
    assert result.created_by_agent == 'Trial Publisher'


def test_generation_service_adds_soft_limit_guardrails_to_metadata(fake_db):
    user = User(email='soft-limit@example.com', telegram_user_id='soft-limit-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Soft Limit WS', slug='soft-limit-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Soft Limit Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        settings={
            'generation_guardrails': {
                'client_budget_limit_usd': '0.010000',
                'client_generation_quota_limit': 10,
                'client_token_quota_limit': 10000,
                'warn_at_ratio': '0.80',
            }
        },
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Soft Limit Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    task = ContentTask(project_id=project.id, title='Guardrail task', brief='Need guarded generation')
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=8500,
            estimated_cost_usd='0.009000',
            created_at=now,
            updated_at=now,
        )
    )

    result = build_generation_service(fake_db).generate_draft(task, source_text='Seed text')
    guardrails = result.metadata()['guardrails']

    assert guardrails['has_alerts'] is True
    assert guardrails['soft_limit_reached'] is True
    assert guardrails['client']['alert_level'] == 'warning'
    assert 'budget_soft_limit_warning' in guardrails['client']['alerts']
    assert 'token_quota_soft_limit_warning' in guardrails['client']['alerts']


def test_generation_service_adds_channel_soft_limit_guardrails_to_metadata(fake_db):
    user = User(email='channel-soft-limit@example.com', telegram_user_id='channel-soft-limit-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Channel Soft Limit WS', slug='channel-soft-limit-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Channel Soft Limit Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        settings={'generation_guardrails': {'channel_limits': {}}},
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Channel Guardrail Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    channel = TelegramChannel(
        project_id=project.id,
        channel_title='Guarded Channel',
        channel_username='guarded_channel',
        is_active=True,
    )
    fake_db.add(channel)
    fake_db.refresh(channel)
    channel.project = project
    project.telegram_channels = [channel]
    account.settings['generation_guardrails']['channel_limits'][str(channel.id)] = {
        'budget_limit_usd': '0.005000',
        'generation_quota_limit': 3,
        'token_quota_limit': 5000,
        'warn_at_ratio': '0.80',
    }

    task = ContentTask(project_id=project.id, title='Channel guardrail task', brief='Need guarded generation by channel')
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            telegram_channel_id=channel.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=5100,
            estimated_cost_usd='0.005100',
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(GenerationHardStopError) as exc:
        build_generation_service(fake_db).generate_draft(task, source_text='Seed text')

    guardrails = exc.value.snapshot.metadata()
    assert guardrails['hard_stop_reached'] is True
    assert 'channel' in guardrails['blocked_scopes']
    assert guardrails['channel']['alert_level'] == 'exceeded'
    assert 'budget_soft_limit_exceeded' in guardrails['channel']['alerts']
    assert 'token_quota_soft_limit_exceeded' in guardrails['channel']['alerts']


def test_generation_service_hard_stops_when_client_budget_or_quota_exceeded(fake_db):
    user = User(email='hard-stop@example.com', telegram_user_id='hard-stop-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Hard Stop WS', slug='hard-stop-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Hard Stop Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        settings={
            'generation_guardrails': {
                'client_budget_limit_usd': '0.010000',
                'client_generation_quota_limit': 3,
                'client_token_quota_limit': 10000,
            }
        },
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Hard Stop Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    task = ContentTask(project_id=project.id, title='Hard stop task', brief='Need blocked generation')
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=12000,
            estimated_cost_usd='0.011000',
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(GenerationHardStopError) as exc:
        build_generation_service(fake_db).generate_draft(task, source_text='Seed text')

    guardrails = exc.value.snapshot.metadata()
    assert guardrails['hard_stop_reached'] is True
    assert guardrails['soft_limit_reached'] is True
    assert guardrails['client']['alert_level'] == 'exceeded'
    assert 'client' in guardrails['blocked_scopes']
    assert 'budget_soft_limit_exceeded' in guardrails['blocking_reasons']
    assert 'generation_quota_soft_limit_warning' not in guardrails['blocking_reasons']


def test_generation_service_exposes_failover_metadata(fake_db, monkeypatch):
    from app.services.llm_provider import LLMGenerationResult

    monkeypatch.setattr(
        'app.services.generation_service.generate_with_failover',
        lambda payload: LLMGenerationResult(
            provider='openai',
            model='gpt-4.1-mini',
            output_text='',
            finish_reason='provider_unavailable',
            request_id=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=0,
            raw_error='provider down',
            failover={
                'strategy': 'graceful-degradation',
                'activated': True,
                'outcome': 'graceful-degradation',
            },
        ),
    )

    result = build_generation_service(fake_db).generate_ideas(
        'Ideas Project',
        brief='резервный путь генерации идей',
        count=2,
    )

    assert result.output_text == 'резервный путь генерации идей'
    assert result.metadata()['failover']['outcome'] == 'graceful-degradation'
    assert result.summary_metadata()['failover']['activated'] is True


def test_generation_service_enforces_daily_and_monthly_operation_caps(fake_db):
    user = User(email='daily-monthly@example.com', telegram_user_id='daily-monthly-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Daily Monthly WS', slug='daily-monthly-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Daily Monthly Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=14),
        current_period_end=now + timedelta(days=14),
        settings={
            'generation_guardrails': {
                'client_daily_generation_quota_limit': 5,
                'client_monthly_generation_quota_limit': 20,
                'client_operation_daily_limits': {
                    'draft': {'generation_quota_limit': 1},
                },
                'client_operation_monthly_limits': {
                    'draft': {'generation_quota_limit': 2},
                },
            }
        },
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Daily Monthly Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    task = ContentTask(project_id=project.id, title='Cap task', brief='Need blocked generation')
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=1000,
            estimated_cost_usd='0.001000',
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
    )
    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=1000,
            estimated_cost_usd='0.001000',
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        )
    )

    with pytest.raises(GenerationHardStopError) as exc:
        build_generation_service(fake_db).generate_draft(task, source_text='Seed text')

    guardrails = exc.value.snapshot.metadata()
    assert guardrails['operation_type'] == 'draft'
    assert 'client' in guardrails['blocked_scopes']
    client_windows = {(item['window'], item['operation_type']): item for item in guardrails['client']['windows']}
    assert client_windows[('daily', 'draft')]['alert_level'] == 'exceeded'
    assert client_windows[('monthly', 'draft')]['alert_level'] == 'exceeded'
    assert 'daily_draft_generation_quota_soft_limit_exceeded' in guardrails['blocking_reasons']
    assert 'monthly_draft_generation_quota_soft_limit_exceeded' in guardrails['blocking_reasons']


def test_generation_service_exposes_channel_daily_caps_in_guardrail_metadata(fake_db):
    user = User(email='channel-daily@example.com', telegram_user_id='channel-daily-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Channel Daily WS', slug='channel-daily-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Channel Daily Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        settings={'generation_guardrails': {'channel_limits': {}}},
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Channel Daily Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    channel = TelegramChannel(
        project_id=project.id,
        channel_title='Daily Channel',
        channel_username='daily_channel',
        is_active=True,
    )
    fake_db.add(channel)
    fake_db.refresh(channel)
    channel.project = project
    project.telegram_channels = [channel]
    account.settings['generation_guardrails']['channel_limits'][str(channel.id)] = {
        'daily_generation_quota_limit': 2,
        'operation_daily_limits': {
            'draft': {'generation_quota_limit': 3},
        },
    }

    task = ContentTask(project_id=project.id, title='Channel daily task', brief='Need guarded generation by channel')
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            telegram_channel_id=channel.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=1000,
            estimated_cost_usd='0.001000',
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
    )

    result = build_generation_service(fake_db).generate_draft(task, source_text='Seed text')
    guardrails = result.metadata()['guardrails']
    channel_windows = {(item['window'], item['operation_type']): item for item in guardrails['channel']['windows']}
    assert channel_windows[('daily', None)]['generation_quota_limit'] == 2
    assert channel_windows[('daily', 'draft')]['generation_quota_limit'] == 3
    assert channel_windows[('daily', None)]['total_generations'] == 1
    assert guardrails['operation_type'] == 'draft'


def _bootstrap_guardrail_project(fake_db, *, settings: dict) -> tuple[ClientAccount, Project, ContentTask]:
    user = User(email='guardrail-enforcement@example.com', telegram_user_id='guardrail-enforcement-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Guardrail Enforcement WS', slug='guardrail-enforcement-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Guardrail Enforcement Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        settings={'generation_guardrails': settings},
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Guardrail Enforcement Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    task = ContentTask(project_id=project.id, title='Guardrail enforcement task', brief='Need strict limits')
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project
    return account, project, task


def test_generation_service_blocks_next_run_when_client_generation_quota_is_exactly_reached(fake_db):
    now = datetime.now(timezone.utc)
    account, project, task = _bootstrap_guardrail_project(
        fake_db,
        settings={
            'client_generation_quota_limit': 2,
        },
    )

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='failed',
            total_tokens=500,
            estimated_cost_usd='0.001000',
            created_at=now - timedelta(minutes=10),
            updated_at=now - timedelta(minutes=10),
        )
    )
    for minutes_ago in (5, 1):
        fake_db.add(
            LLMGenerationEvent(
                client_id=account.id,
                project_id=project.id,
                operation_type='draft',
                provider='stub',
                model='stub',
                status='succeeded',
                total_tokens=500,
                estimated_cost_usd='0.001000',
                created_at=now - timedelta(minutes=minutes_ago),
                updated_at=now - timedelta(minutes=minutes_ago),
            )
        )

    with pytest.raises(GenerationHardStopError) as exc:
        build_generation_service(fake_db).generate_draft(task, source_text='Seed text')

    guardrails = exc.value.snapshot.metadata()
    assert guardrails['hard_stop_reached'] is True
    assert 'client' in guardrails['blocked_scopes']
    assert 'generation_quota_soft_limit_exceeded' in guardrails['blocking_reasons']
    billing_window = next(item for item in guardrails['client']['windows'] if item['window'] == 'billing_period' and item['operation_type'] is None)
    assert billing_window['generation_quota_limit'] == 2
    assert billing_window['total_generations'] == 2


def test_generation_service_blocks_next_run_when_channel_budget_is_exactly_reached(fake_db):
    now = datetime.now(timezone.utc)
    account, project, task = _bootstrap_guardrail_project(
        fake_db,
        settings={
            'channel_limits': {},
        },
    )

    channel = TelegramChannel(
        project_id=project.id,
        channel_title='Budget Channel',
        channel_username='budget_channel',
        is_active=True,
    )
    fake_db.add(channel)
    fake_db.refresh(channel)
    channel.project = project
    project.telegram_channels = [channel]
    account.settings['generation_guardrails']['channel_limits'][str(channel.id)] = {
        'budget_limit_usd': '0.005000',
    }

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            telegram_channel_id=channel.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='failed',
            total_tokens=100,
            estimated_cost_usd='0.009000',
            created_at=now - timedelta(minutes=3),
            updated_at=now - timedelta(minutes=3),
        )
    )
    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            telegram_channel_id=channel.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=1000,
            estimated_cost_usd='0.005000',
            created_at=now - timedelta(minutes=1),
            updated_at=now - timedelta(minutes=1),
        )
    )

    with pytest.raises(GenerationHardStopError) as exc:
        build_generation_service(fake_db).generate_draft(task, source_text='Seed text')

    guardrails = exc.value.snapshot.metadata()
    assert guardrails['hard_stop_reached'] is True
    assert 'channel' in guardrails['blocked_scopes']
    assert 'budget_soft_limit_exceeded' in guardrails['blocking_reasons']
    billing_window = next(item for item in guardrails['channel']['windows'] if item['window'] == 'billing_period' and item['operation_type'] is None)
    assert billing_window['budget_limit_usd'] == '0.005000'
    assert billing_window['total_cost_usd'] == '0.005000'
