from app.models.agent_profile import AgentProfile
from app.models.agent_team_runtime import AgentTeamRuntime
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from app.services.execution_context import resolve_project_execution_context
from app.utils.enums import AgentRole, SubscriptionStatus


def test_agent_team_runtime_model_exists(fake_db):
    user = User(email='runtime@example.com', telegram_user_id='runtime-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Runtime WS', slug='runtime-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Runtime Account',
        subscription_plan_code='pro',
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Runtime Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)

    channel = TelegramChannel(project_id=project.id, channel_title='Runtime Channel', is_active=True)
    fake_db.add(channel)
    fake_db.refresh(channel)

    runtime = AgentTeamRuntime(
        project_id=project.id,
        channel_id=channel.id,
        client_account_id=account.id,
        runtime_scope='project_channel',
        runtime_key=f'{project.id}:{channel.id}',
        display_name='Runtime Project / Runtime Channel runtime',
        preset_code='starter_3',
        generation_mode='multi-stage',
        agent_count=3,
        settings_fingerprint='settings123',
        agent_fingerprint='agents123',
        runtime_fingerprint='runtime123',
        config_snapshot={'project_settings': {'language': 'ru'}},
    )
    fake_db.add(runtime)
    fake_db.refresh(runtime)

    assert runtime.project_id == project.id
    assert runtime.channel_id == channel.id
    assert runtime.client_account_id == account.id
    assert runtime.runtime_scope == 'project_channel'
    assert runtime.config_snapshot['project_settings']['language'] == 'ru'


def test_execution_context_creates_agent_team_runtime_snapshot(fake_db):
    user = User(email='tenant-runtime@example.com', telegram_user_id='tenant-runtime')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Tenant Runtime WS', slug='tenant-runtime-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Tenant Runtime Account',
        subscription_plan_code='pro',
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Tenant Runtime Project',
        language='ru',
        tone_of_voice='measured analyst',
    )
    fake_db.add(project)
    fake_db.refresh(project)

    channel = TelegramChannel(project_id=project.id, channel_title='Tenant Runtime Channel', is_active=True)
    fake_db.add(channel)
    fake_db.refresh(channel)

    fake_db.add(
        AgentProfile(
            project_id=project.id,
            channel_id=channel.id,
            role=AgentRole.STRATEGIST,
            name='tenant-strategist',
            display_name='Tenant Strategist',
            model='stub',
            preset_code='starter_3',
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.WRITER,
            name='tenant-writer',
            display_name='Tenant Writer',
            model='stub',
            preset_code='starter_3',
        )
    )

    task = ContentTask(project_id=project.id, title='Runtime task', brief='Need isolated runtime entity')
    fake_db.add(task)
    fake_db.refresh(task)

    context = resolve_project_execution_context(fake_db, task=task)
    runtime = context.agent_team_runtime
    metadata = context.metadata()['agent_team_runtime']
    stored_runtimes = fake_db.storage[AgentTeamRuntime]

    assert runtime.project_id == str(project.id)
    assert runtime.channel_id == str(channel.id)
    assert runtime.client_account_id == str(account.id)
    assert runtime.runtime_scope == 'project_channel'
    assert runtime.runtime_key == f'{project.id}:{channel.id}'
    assert runtime.preset_code == 'starter_3'
    assert runtime.generation_mode == 'multi-stage'
    assert runtime.agent_count == 2
    assert runtime.runtime_fingerprint
    assert metadata['runtime_fingerprint'] == runtime.runtime_fingerprint
    assert metadata['config_snapshot']['channel']['title'] == 'Tenant Runtime Channel'
    assert metadata['config_snapshot']['agent_runtime'][0]['name'] == 'Tenant Strategist'
    assert len(stored_runtimes) == 1
    assert stored_runtimes[0].runtime_fingerprint == runtime.runtime_fingerprint


def test_trial_plan_forces_single_pass_runtime_mode(fake_db):
    user = User(email='trial-runtime@example.com', telegram_user_id='trial-runtime')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Trial Runtime WS', slug='trial-runtime-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Trial Runtime Account',
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
        name='Trial Runtime Project',
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
            preset_code='starter_3',
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
            preset_code='starter_3',
            sort_order=2,
            priority=20,
        )
    )

    task = ContentTask(project_id=project.id, title='Trial runtime task', brief='Keep generation cheap')
    fake_db.add(task)
    fake_db.refresh(task)

    context = resolve_project_execution_context(fake_db, task=task)

    assert context.agent_team_runtime.generation_mode == 'single-pass'
    assert context.metadata()['agent_team_runtime']['generation_mode'] == 'single-pass'
