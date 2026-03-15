from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from app.services.generation_guardrails import evaluate_generation_guardrails


def _bootstrap_client_with_plan(fake_db, *, plan_code: str) -> tuple[ClientAccount, Project]:
    user = User(email=f'{plan_code}@example.com', telegram_user_id=f'{plan_code}-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name=f'{plan_code}-ws', slug=f'{plan_code}-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name=f'{plan_code.title()} Account',
        subscription_plan_code=plan_code,
        subscription_status='active' if plan_code != 'trial' else 'trial',
        current_period_start=datetime(2026, 3, 1, tzinfo=UTC),
        current_period_end=datetime(2026, 4, 1, tzinfo=UTC),
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(name=f'{plan_code.title()} Project', language='ru', owner_user_id=user.id, client_account_id=account.id)
    fake_db.add(project)
    fake_db.refresh(project)
    return account, project


def test_trial_plan_blocks_second_channel(client, fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='trial')
    project.client_account = account

    first = client.post(
        f'/api/v1/projects/{project.id}/channels',
        json={'channel_title': 'Channel 1', 'channel_id': 'trial-1', 'is_active': True},
    )
    assert first.status_code == 201

    second = client.post(
        f'/api/v1/projects/{project.id}/channels',
        json={'channel_title': 'Channel 2', 'channel_id': 'trial-2', 'is_active': True},
    )
    assert second.status_code == 403
    assert 'allows up to 1 channel' in second.json()['detail']


def test_trial_plan_blocks_editorial_agent_preset(client, fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='trial')
    project.client_account = account

    blocked = client.post(f'/api/v1/projects/{project.id}/agent-team-presets/editorial_7/apply')

    assert blocked.status_code == 403
    assert "Preset 'editorial_7' is not available on plan 'trial'" in blocked.json()['detail']


def test_trial_plan_blocks_balanced_preset_after_tariff_lock(client, fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='trial')
    project.client_account = account

    blocked = client.post(f'/api/v1/projects/{project.id}/agent-team-presets/balanced_5/apply')

    assert blocked.status_code == 403
    assert "Preset 'balanced_5' is not available on plan 'trial'" in blocked.json()['detail']


def test_trial_plan_blocks_tasks_above_daily_frequency_limit(client, fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='trial')
    project.client_account = account

    window_start = datetime.now(UTC).replace(hour=1, minute=0, second=0, microsecond=0)
    for index in range(3):
        task = ContentTask(project_id=project.id, title=f'Existing {index + 1}')
        task.project = project
        task.created_at = window_start + timedelta(minutes=index)
        fake_db.add(task)
        fake_db.refresh(task)

    blocked = client.post(
        f'/api/v1/projects/{project.id}/tasks',
        json={'title': 'One task too many'},
    )
    assert blocked.status_code == 403
    assert 'allows up to 3 task(s) per day' in blocked.json()['detail']


def test_plan_default_generation_quota_is_exposed_via_guardrails(fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='starter')
    project.client_account = account
    channel = TelegramChannel(project_id=project.id, channel_title='Starter Channel', is_active=True)
    channel.project = project
    fake_db.add(channel)
    fake_db.refresh(channel)

    task = ContentTask(project_id=project.id, title='Starter task')
    task.project = project
    fake_db.add(task)
    fake_db.refresh(task)

    event = LLMGenerationEvent(
        client_id=account.id,
        project_id=project.id,
        telegram_channel_id=channel.id,
        content_task_id=task.id,
        operation_type='draft',
        provider='openai',
        model='gpt-test',
        status='succeeded',
        total_tokens=900,
        estimated_cost_usd=Decimal('0.009000'),
    )
    fake_db.add(event)
    fake_db.refresh(event)

    snapshot = evaluate_generation_guardrails(fake_db, project=project, channel=channel, operation_type='draft')

    assert snapshot.client is not None
    monthly_window = next(item for item in snapshot.client.windows if item.window == 'monthly' and item.operation_type is None)
    assert monthly_window.generation_quota_limit == 300


def test_pricing_summary_exposes_tariff_limits(client, fake_db):
    response = client.get('/api/v1/users/me/client-account')
    account = fake_db.get(ClientAccount, response.json()['id'])
    account.subscription_plan_code = 'pro'
    account.subscription_status = 'active'

    pricing = client.get('/api/v1/users/me/client-account/pricing')
    assert pricing.status_code == 200

    body = pricing.json()
    pro_plan = next(item for item in body['plan_catalog'] if item['plan_code'] == 'pro')
    assert pro_plan['service_tier'] == 'standard'
    assert pro_plan['execution_mode'] == 'multi_stage'
    assert pro_plan['included_channels'] == 3
    assert pro_plan['included_generations'] == 1500
    assert pro_plan['max_tasks_per_day'] == 40
    assert pro_plan['allowed_preset_codes'] == ['starter_3', 'balanced_5', 'editorial_7']
    assert pro_plan['default_preset_code'] == 'balanced_5'
    assert pro_plan['access_flag'] == 'paid'
    assert 'rewrite_draft' in pro_plan['allowed_generation_operations']


def test_trial_plan_exposes_access_flag_and_generation_operations(client):
    response = client.get('/api/v1/users/me/client-account')
    assert response.status_code == 200
    body = response.json()
    assert body['access_flag'] == 'trial'

    pricing = client.get('/api/v1/users/me/client-account/pricing')
    assert pricing.status_code == 200
    trial_plan = next(item for item in pricing.json()['plan_catalog'] if item['plan_code'] == 'trial')
    assert trial_plan['access_flag'] == 'trial'
    assert trial_plan['service_tier'] == 'economy'
    assert trial_plan['execution_mode'] == 'single_pass'
    assert trial_plan['allowed_generation_operations'] == ['ideas', 'content_plan', 'draft']
    assert trial_plan['allowed_preset_codes'] == ['starter_3']


def test_trial_plan_blocks_rewrite_generation_operation(client, fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='trial')
    project.client_account = account

    task = ContentTask(project_id=project.id, title='Trial task')
    task.project = project
    fake_db.add(task)
    fake_db.refresh(task)

    draft = client.post(f'/api/v1/tasks/{task.id}/drafts', json={'text': 'Черновик', 'version': 1})
    assert draft.status_code == 201

    blocked = client.post(
        f"/api/v1/drafts/{draft.json()['id']}/rewrite",
        json={'rewrite_prompt': 'Сделай короче'},
    )
    assert blocked.status_code == 403
    assert "Generation operation 'rewrite_draft' is not available on plan 'trial'" in blocked.json()['detail']


def test_past_due_plan_blocks_all_generation_operations(client, fake_db):
    account, project = _bootstrap_client_with_plan(fake_db, plan_code='starter')
    account.subscription_status = 'past_due'
    project.client_account = account

    blocked = client.post(
        f'/api/v1/projects/{project.id}/content-plans',
        json={'period_type': 'week', 'start_date': '2026-03-16', 'end_date': '2026-03-22', 'status': 'generated'},
    )
    assert blocked.status_code == 403
    assert "subscription is unpaid" in blocked.json()['detail']
