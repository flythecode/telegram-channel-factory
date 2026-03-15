from datetime import UTC, datetime
from decimal import Decimal

from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.services.identity import TelegramIdentity, get_or_create_client_account_for_user, get_or_create_current_user, get_or_create_workspace_for_user


def test_identity_bootstrap_creates_client_account(fake_db):
    identity = TelegramIdentity(telegram_user_id='client-1', telegram_username='clientone', first_name='Client')
    user = get_or_create_current_user(fake_db, identity)
    workspace = get_or_create_workspace_for_user(fake_db, user, identity)

    account = get_or_create_client_account_for_user(fake_db, user, workspace, identity)

    assert isinstance(account, ClientAccount)
    assert account.owner_user_id == user.id
    assert account.workspace_id == workspace.id
    assert account.subscription_plan_code == 'trial'
    assert account.subscription_status == 'trial'
    assert account.access_flag == 'trial'


def test_create_project_attaches_client_account(client):
    project = client.post('/api/v1/projects', json={'name': 'Billing Project', 'language': 'ru'}).json()

    assert project['client_account_id'] is not None


def test_users_me_client_account_endpoint_returns_subscription_context(client):
    response = client.get('/api/v1/users/me/client-account')

    assert response.status_code == 200
    body = response.json()
    assert body['owner_user_id']
    assert body['subscription_plan_code'] == 'trial'
    assert body['subscription_status'] == 'trial'
    assert body['access_flag'] == 'trial'


def test_pricing_summary_endpoint_returns_recommended_rate_card_and_plan_catalog(client, fake_db):
    response = client.get('/api/v1/users/me/client-account')
    account_id = response.json()['id']
    client_account = fake_db.get(ClientAccount, account_id)
    client_account.subscription_plan_code = 'starter'
    client_account.settings = {
        'pricing_model': {
            'target_margin_pct': '65',
            'contingency_pct': '10',
            'platform_overhead_usd': '12',
            'channel_overhead_usd': '3',
        }
    }

    project = Project(name='Pricing Project', language='ru', owner_user_id=client_account.owner_user_id, client_account_id=client_account.id)
    fake_db.add(project)
    fake_db.refresh(project)

    channel = TelegramChannel(project_id=project.id, channel_title='Pricing Channel', is_active=True)
    fake_db.add(channel)
    fake_db.refresh(channel)

    task = ContentTask(project_id=project.id, title='Pricing task')
    fake_db.add(task)
    fake_db.refresh(task)

    event = LLMGenerationEvent(
        client_id=client_account.id,
        project_id=project.id,
        telegram_channel_id=channel.id,
        content_task_id=task.id,
        operation_type='draft',
        provider='openai',
        model='gpt-test',
        status='succeeded',
        prompt_tokens=1200,
        completion_tokens=600,
        total_tokens=1800,
        estimated_cost_usd=Decimal('0.018000'),
        latency_ms=2500,
    )
    event.created_at = datetime(2026, 3, 14, 17, 0, tzinfo=UTC)
    fake_db.add(event)
    fake_db.refresh(event)

    pricing = client.get('/api/v1/users/me/client-account/pricing')
    assert pricing.status_code == 200
    body = pricing.json()
    assert body['active_plan_code'] == 'starter'
    assert body['target_margin_pct'] == '65.00'
    assert body['platform_overhead_usd'] == '12.00'
    assert len(body['operation_rates']) >= 5
    draft_row = next(item for item in body['operation_rates'] if item['operation_type'] == 'draft')
    assert draft_row['successful_events_count'] == 1
    assert draft_row['average_cost_usd'] == '0.018000'
    assert Decimal(draft_row['recommended_unit_price_usd']) > Decimal('0.018000')
    assert Decimal(draft_row['delta_vs_average_cost_usd']) > Decimal('0')
    assert Decimal(draft_row['recommended_unit_margin_usd']) > Decimal('0')
    assert Decimal(draft_row['observed_share_pct']) > Decimal('0')
    starter = next(item for item in body['plan_catalog'] if item['plan_code'] == 'starter')
    assert starter['included_channels'] == 1
    assert starter['included_generations'] == 300
    assert Decimal(starter['monthly_fee_usd']) > Decimal('0')
    assert Decimal(starter['projected_gross_margin_pct']) >= Decimal('64.00')
    assert Decimal(starter['observed_blended_generation_cost_usd']) > Decimal('0')
    assert Decimal(starter['projected_sample_total_cogs_usd']) > Decimal('0')
    assert Decimal(starter['projected_sample_gross_margin_pct']) is not None
    assert Decimal(body['assumptions']['observed_blended_generation_cost_usd']) > Decimal('0')
