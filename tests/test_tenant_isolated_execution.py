from app.models.agent_profile import AgentProfile
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from decimal import Decimal

from app.models.llm_generation_event import LLMGenerationEvent
from app.services.execution_context import resolve_project_execution_context
from app.services.generation_events import create_generation_event, summarize_generation_usage
from app.services.generation_service import build_generation_service
from app.utils.enums import AgentRole, SubscriptionStatus


def test_execution_context_is_frozen_per_project_and_client(fake_db):
    user = User(email='tenant@example.com', full_name='Tenant Owner', telegram_user_id='tenant-1')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Tenant WS', slug='tenant-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    client_account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Tenant Account',
        subscription_plan_code='pro',
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    fake_db.add(client_account)
    fake_db.refresh(client_account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=client_account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Tenant Project',
        language='ru',
        tone_of_voice='calm expert',
    )
    fake_db.add(project)
    fake_db.refresh(project)

    channel = TelegramChannel(project_id=project.id, channel_title='Tenant Channel', is_active=True)
    fake_db.add(channel)
    fake_db.refresh(channel)

    strategist = AgentProfile(
        project_id=project.id,
        channel_id=channel.id,
        role=AgentRole.STRATEGIST,
        name='tenant-strategist',
        display_name='Tenant Strategist',
        model='stub',
        custom_prompt='Use tenant prompt',
    )
    writer = AgentProfile(
        project_id=project.id,
        role=AgentRole.WRITER,
        name='tenant-writer',
        display_name='Tenant Writer',
        model='stub',
        custom_prompt='Write for this tenant only',
    )
    fake_db.add(strategist)
    fake_db.add(writer)
    fake_db.refresh(strategist)
    fake_db.refresh(writer)

    task = ContentTask(project_id=project.id, title='Tenant task', brief='Need isolated execution')
    fake_db.add(task)
    fake_db.refresh(task)

    context = resolve_project_execution_context(fake_db, task=task)

    assert context.project_id == str(project.id)
    assert context.client_account_id == str(client_account.id)
    assert context.channel_id == str(channel.id)
    assert context.agent_team_runtime.project_id == str(project.id)
    assert context.agent_team_runtime.channel_id == str(channel.id)
    assert context.agent_team_runtime.runtime_scope == 'project_channel'
    assert [agent.role for agent in context.agents] == ['strategist', 'writer']
    assert all(agent.prompt_fingerprint for agent in context.agents)
    assert context.settings_fingerprint


def test_generation_metadata_contains_isolated_execution_context(client):
    project = client.post(
        '/api/v1/projects',
        json={'name': 'Isolation Project', 'language': 'ru', 'tone_of_voice': 'sharp analyst'},
    ).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200

    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Isolation task'}).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'seed', 'version': 1}).json()

    metadata = draft['generation_metadata']
    execution_context = metadata['execution_context']

    assert metadata['operation_type'] == 'draft'
    assert execution_context['project_id'] == project['id']
    assert execution_context['client_account_id'] == project['client_account_id']
    assert execution_context['runtime_scope'] == 'project'
    assert execution_context['tenant_isolation_mode'] == 'isolated_agent_profiles_and_execution_context'
    assert execution_context['agent_team_runtime']['project_id'] == project['id']
    assert execution_context['agent_team_runtime']['runtime_scope'] in {'project', 'project_channel'}
    assert execution_context['agent_team_runtime']['runtime_fingerprint']
    assert execution_context['provider_key_scope'] == 'application'
    assert execution_context['provider_key_per_client'] is False
    assert execution_context['settings_fingerprint']
    assert execution_context['agent_runtime']
    assert all(agent['prompt_fingerprint'] for agent in execution_context['agent_runtime'])


def test_generation_service_uses_only_current_project_agents(fake_db):
    project_alpha = Project(name='Alpha', language='ru')
    project_beta = Project(name='Beta', language='ru')
    fake_db.add(project_alpha)
    fake_db.add(project_beta)
    fake_db.refresh(project_alpha)
    fake_db.refresh(project_beta)

    alpha_writer = AgentProfile(
        project_id=project_alpha.id,
        role=AgentRole.WRITER,
        name='alpha-writer',
        display_name='Alpha Writer',
        model='stub',
    )
    beta_writer = AgentProfile(
        project_id=project_beta.id,
        role=AgentRole.WRITER,
        name='beta-writer',
        display_name='Beta Writer',
        model='stub',
    )
    fake_db.add(alpha_writer)
    fake_db.add(beta_writer)
    fake_db.refresh(alpha_writer)
    fake_db.refresh(beta_writer)

    task = ContentTask(project_id=project_alpha.id, title='Alpha task')
    fake_db.add(task)
    fake_db.refresh(task)

    result = build_generation_service(fake_db).generate_draft(task, source_text='seed')
    execution_context = result.metadata()['execution_context']

    assert result.created_by_agent == 'Alpha Writer'
    assert execution_context['project_id'] == str(project_alpha.id)
    assert execution_context['agent_runtime'][0]['name'] == 'Alpha Writer'
    assert all(agent['name'] != 'Beta Writer' for agent in execution_context['agent_runtime'])



def test_generation_runs_keep_prompts_runtime_and_usage_isolated_between_clients(fake_db):
    owner_a = User(email='tenant-a@example.com', full_name='Tenant A', telegram_user_id='tenant-a')
    owner_b = User(email='tenant-b@example.com', full_name='Tenant B', telegram_user_id='tenant-b')
    fake_db.add(owner_a)
    fake_db.add(owner_b)
    fake_db.refresh(owner_a)
    fake_db.refresh(owner_b)

    workspace_a = Workspace(owner_user_id=owner_a.id, created_by_user_id=owner_a.id, name='WS A', slug='ws-a')
    workspace_b = Workspace(owner_user_id=owner_b.id, created_by_user_id=owner_b.id, name='WS B', slug='ws-b')
    fake_db.add(workspace_a)
    fake_db.add(workspace_b)
    fake_db.refresh(workspace_a)
    fake_db.refresh(workspace_b)

    account_a = ClientAccount(
        owner_user_id=owner_a.id,
        workspace_id=workspace_a.id,
        name='Account A',
        subscription_plan_code='pro',
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    account_b = ClientAccount(
        owner_user_id=owner_b.id,
        workspace_id=workspace_b.id,
        name='Account B',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    fake_db.add(account_a)
    fake_db.add(account_b)
    fake_db.refresh(account_a)
    fake_db.refresh(account_b)

    project_a = Project(
        workspace_id=workspace_a.id,
        client_account_id=account_a.id,
        owner_user_id=owner_a.id,
        created_by_user_id=owner_a.id,
        name='Project A',
        language='ru',
        tone_of_voice='calm expert',
    )
    project_b = Project(
        workspace_id=workspace_b.id,
        client_account_id=account_b.id,
        owner_user_id=owner_b.id,
        created_by_user_id=owner_b.id,
        name='Project B',
        language='ru',
        tone_of_voice='bold trader',
    )
    fake_db.add(project_a)
    fake_db.add(project_b)
    fake_db.refresh(project_a)
    fake_db.refresh(project_b)

    channel_a = TelegramChannel(project_id=project_a.id, channel_title='Channel A', is_active=True)
    channel_b = TelegramChannel(project_id=project_b.id, channel_title='Channel B', is_active=True)
    fake_db.add(channel_a)
    fake_db.add(channel_b)
    fake_db.refresh(channel_a)
    fake_db.refresh(channel_b)
    project_a.telegram_channels = [channel_a]
    project_b.telegram_channels = [channel_b]

    writer_a = AgentProfile(
        project_id=project_a.id,
        channel_id=channel_a.id,
        role=AgentRole.WRITER,
        name='writer-a',
        display_name='Writer A',
        model='stub',
        custom_prompt='Use tenant A vocabulary only',
        sort_order=1,
        priority=10,
    )
    writer_b = AgentProfile(
        project_id=project_b.id,
        channel_id=channel_b.id,
        role=AgentRole.WRITER,
        name='writer-b',
        display_name='Writer B',
        model='stub',
        custom_prompt='Use tenant B vocabulary only',
        sort_order=1,
        priority=10,
    )
    fake_db.add(writer_a)
    fake_db.add(writer_b)
    fake_db.refresh(writer_a)
    fake_db.refresh(writer_b)

    task_a = ContentTask(project_id=project_a.id, title='Task A', brief='Need A-specific post')
    task_b = ContentTask(project_id=project_b.id, title='Task B', brief='Need B-specific post')
    fake_db.add(task_a)
    fake_db.add(task_b)
    fake_db.refresh(task_a)
    fake_db.refresh(task_b)
    task_a.project = project_a
    task_b.project = project_b

    generation_service = build_generation_service(fake_db)
    result_a = generation_service.generate_draft(task_a, source_text='seed A')
    result_b = generation_service.generate_draft(task_b, source_text='seed B')

    metadata_a = result_a.metadata()
    metadata_b = result_b.metadata()
    context_a = metadata_a['execution_context']
    context_b = metadata_b['execution_context']

    assert context_a['client_account_id'] == str(account_a.id)
    assert context_b['client_account_id'] == str(account_b.id)
    assert context_a['project_id'] == str(project_a.id)
    assert context_b['project_id'] == str(project_b.id)
    assert context_a['channel_id'] == str(channel_a.id)
    assert context_b['channel_id'] == str(channel_b.id)
    assert context_a['agent_runtime'][0]['name'] == 'Writer A'
    assert context_b['agent_runtime'][0]['name'] == 'Writer B'
    assert context_a['agent_runtime'][0]['prompt_fingerprint'] != context_b['agent_runtime'][0]['prompt_fingerprint']
    assert context_a['agent_team_runtime']['runtime_fingerprint'] != context_b['agent_team_runtime']['runtime_fingerprint']
    assert context_a['settings_fingerprint'] != context_b['settings_fingerprint']

    event_a = create_generation_event(fake_db, result_a, task=task_a, channel=channel_a, project=project_a)
    event_b = create_generation_event(fake_db, result_b, task=task_b, channel=channel_b, project=project_b)
    fake_db.refresh(event_a)
    fake_db.refresh(event_b)

    assert isinstance(event_a, LLMGenerationEvent)
    assert isinstance(event_b, LLMGenerationEvent)
    assert event_a.client_id == account_a.id
    assert event_b.client_id == account_b.id
    assert event_a.project_id == project_a.id
    assert event_b.project_id == project_b.id
    assert event_a.telegram_channel_id == channel_a.id
    assert event_b.telegram_channel_id == channel_b.id
    assert event_a.request_id == result_a.generation.request_id
    assert event_b.request_id == result_b.generation.request_id

    summaries = summarize_generation_usage(fake_db, billable_rates_usd={'draft': Decimal('0.050000')})

    assert len(summaries) == 2
    summary_by_client = {str(item.client_id): item for item in summaries}
    summary_a = summary_by_client[str(account_a.id)]
    summary_b = summary_by_client[str(account_b.id)]
    assert summary_a.project_id == project_a.id
    assert summary_b.project_id == project_b.id
    assert summary_a.channel_id == channel_a.id
    assert summary_b.channel_id == channel_b.id
    assert summary_a.events_count == 1
    assert summary_b.events_count == 1
    assert summary_a.successful_events_count == 1
    assert summary_b.successful_events_count == 1
    assert summary_a.billed_revenue_usd == Decimal('0.050000')
    assert summary_b.billed_revenue_usd == Decimal('0.050000')
