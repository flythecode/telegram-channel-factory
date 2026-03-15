from decimal import Decimal

from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from app.services.cost_dashboard import build_cost_dashboard
from app.services.generation_admin import build_generation_cost_breakdown, summarize_generation_usage_admin
from app.services.generation_service import build_generation_service
from app.services.generation_events import create_generation_event, summarize_generation_usage



def test_generation_event_model_and_service_capture_generation_call(fake_db):
    owner = User(email='owner@example.com', telegram_user_id='owner-1')
    fake_db.add(owner)
    fake_db.refresh(owner)

    project = Project(name='Events Project', language='ru', owner_user_id=owner.id)
    fake_db.add(project)
    fake_db.refresh(project)

    task = ContentTask(project_id=project.id, title='Event Task', brief='Need a tracked draft')
    fake_db.add(task)
    fake_db.refresh(task)

    draft = Draft(content_task_id=task.id, text='Seed draft', version=1)
    fake_db.add(draft)
    fake_db.refresh(draft)

    result = build_generation_service(fake_db).generate_draft(task, source_text='Seed draft')
    event = create_generation_event(fake_db, result, task=task, draft=draft)
    fake_db.refresh(event)

    assert isinstance(event, LLMGenerationEvent)
    assert event.client_id == owner.id
    assert event.project_id == project.id
    assert event.content_task_id == task.id
    assert event.task_id == task.id
    assert event.draft_id == draft.id
    assert event.operation_type == 'draft'
    assert event.provider == 'stub'
    assert event.model
    assert event.status == 'succeeded'



def test_create_draft_api_persists_llm_generation_event(client, fake_db):
    project = client.post('/api/v1/projects', json={'name': 'Tracked Project', 'language': 'ru'}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Tracked Task'}).json()

    created = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Initial draft', 'version': 1})
    assert created.status_code == 201

    events = fake_db.query(LLMGenerationEvent).all()
    assert len(events) == 1
    event = events[0]
    assert event.client_id is not None
    assert str(event.project_id) == project['id']
    assert str(event.content_task_id) == task['id']
    assert str(event.draft_id) == created.json()['id']
    assert event.operation_type == 'draft'



def test_generation_event_captures_channel_context(fake_db):
    owner = User(email='channel-owner@example.com', telegram_user_id='owner-2')
    fake_db.add(owner)
    fake_db.refresh(owner)

    project = Project(name='Channel Events', language='ru', owner_user_id=owner.id)
    fake_db.add(project)
    fake_db.refresh(project)

    task = ContentTask(project_id=project.id, title='Channel task', brief='Need channel attribution')
    fake_db.add(task)
    fake_db.refresh(task)

    channel = TelegramChannel(project_id=project.id, channel_title='Channel title')
    fake_db.add(channel)
    fake_db.refresh(channel)
    project.telegram_channels = [channel]

    result = build_generation_service(fake_db).generate_draft(task, source_text='Seed draft')
    event = create_generation_event(fake_db, result, task=task)
    fake_db.refresh(event)

    assert event.client_id == owner.id
    assert event.telegram_channel_id == channel.id
    assert event.channel_id == channel.id
    assert event.request_id



def test_summarize_generation_usage_groups_by_client_project_channel_and_operation(fake_db):
    owner = User(email='economics-owner@example.com', telegram_user_id='owner-3')
    fake_db.add(owner)
    fake_db.refresh(owner)

    project = Project(name='Economics Project', language='ru', owner_user_id=owner.id)
    fake_db.add(project)
    fake_db.refresh(project)

    task = ContentTask(project_id=project.id, title='Economics task', brief='Need economics tracking')
    fake_db.add(task)
    fake_db.refresh(task)

    channel = TelegramChannel(project_id=project.id, channel_title='Economics Channel')
    fake_db.add(channel)
    fake_db.refresh(channel)
    project.telegram_channels = [channel]

    generation_service = build_generation_service(fake_db)
    first_result = generation_service.generate_draft(task, source_text='Seed draft')
    second_result = generation_service.generate_draft(task, source_text='Another seed')

    first_event = create_generation_event(fake_db, first_result, task=task, status='succeeded')
    second_event = create_generation_event(fake_db, second_result, task=task, status='failed')
    fake_db.refresh(first_event)
    fake_db.refresh(second_event)

    summaries = summarize_generation_usage(fake_db, billable_rates_usd={'draft': Decimal('0.050000')})

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.client_id == owner.id
    assert summary.project_id == project.id
    assert summary.channel_id == channel.id
    assert summary.operation_type == 'draft'
    assert summary.events_count == 2
    assert summary.successful_events_count == 1
    assert summary.total_prompt_tokens == (first_event.prompt_tokens or 0) + (second_event.prompt_tokens or 0)
    assert summary.total_completion_tokens == (first_event.completion_tokens or 0) + (second_event.completion_tokens or 0)
    assert summary.total_tokens == (first_event.total_tokens or 0) + (second_event.total_tokens or 0)
    expected_cost = Decimal(str(first_event.estimated_cost_usd or 0)) + Decimal(str(second_event.estimated_cost_usd or 0))
    expected_cost = expected_cost.quantize(Decimal('0.000001'))
    assert summary.total_cost_usd == expected_cost
    assert summary.billed_revenue_usd == Decimal('0.050000')
    assert summary.margin_usd == (Decimal('0.050000') - expected_cost).quantize(Decimal('0.000001'))
    assert summary.margin_pct == (((Decimal('0.050000') - expected_cost) / Decimal('0.050000')) * Decimal('100')).quantize(Decimal('0.01'))


def test_generation_event_supports_project_level_idea_runs(fake_db):
    owner = User(email='ideas-owner@example.com', telegram_user_id='owner-ideas')
    fake_db.add(owner)
    fake_db.refresh(owner)

    project = Project(name='Ideas Project', language='ru', owner_user_id=owner.id)
    fake_db.add(project)
    fake_db.refresh(project)

    result = build_generation_service(fake_db).generate_ideas(
        project.name,
        brief='контент для Telegram-канала про AI',
        count=4,
    )
    event = create_generation_event(fake_db, result, project=project)
    fake_db.refresh(event)

    assert event.client_id == owner.id
    assert event.project_id == project.id
    assert event.content_task_id is None
    assert event.operation_type == "ideas"


def test_backend_bridge_generates_tasks_via_generation_service(client, fake_db):
    project = client.post('/api/v1/projects', json={'name': 'AI Factory', 'language': 'ru', 'niche': 'AI automation'}).json()

    from app.bot.backend_bridge import BotBackendBridge
    from app.services.identity import TelegramIdentity

    bridge = BotBackendBridge(fake_db, TelegramIdentity(telegram_user_id='tg-owner', telegram_username='owner'))
    plan, tasks, drafts = bridge.ensure_sample_pipeline(project['id'], tasks_count=3, drafts_count=0)

    assert plan is not None
    assert drafts == []
    assert len(tasks) == 3
    assert all('AI automation' in task.title for task in tasks)

    idea_events = [event for event in fake_db.query(LLMGenerationEvent).all() if event.operation_type == "ideas"]
    assert len(idea_events) == 1
    assert str(idea_events[0].project_id) == project['id']


def test_admin_generation_dashboard_endpoint_returns_rollups_and_export(client, fake_db):
    from datetime import UTC, datetime

    primary_project = client.post('/api/v1/projects', json={'name': 'Admin Dashboard Primary', 'language': 'ru'}).json()
    primary_task = client.post(f"/api/v1/projects/{primary_project['id']}/tasks", json={'title': 'Primary Dashboard Task'}).json()
    secondary_project = client.post('/api/v1/projects', json={'name': 'Admin Dashboard Secondary', 'language': 'ru'}).json()
    secondary_task = client.post(f"/api/v1/projects/{secondary_project['id']}/tasks", json={'title': 'Secondary Dashboard Task'}).json()

    primary_channel = TelegramChannel(project_id=primary_project['id'], channel_title='Primary Dashboard Channel', channel_username='@admindashprimary')
    secondary_channel = TelegramChannel(project_id=secondary_project['id'], channel_title='Secondary Dashboard Channel', channel_username='@admindashsecondary')
    fake_db.add(primary_channel)
    fake_db.add(secondary_channel)
    fake_db.refresh(primary_channel)
    fake_db.refresh(secondary_channel)
    fake_db.get(Project, primary_project['id']).telegram_channels = [primary_channel]
    fake_db.get(Project, secondary_project['id']).telegram_channels = [secondary_channel]

    generation_service = build_generation_service(fake_db)
    primary_db_task = fake_db.get(ContentTask, primary_task['id'])
    secondary_db_task = fake_db.get(ContentTask, secondary_task['id'])

    first = create_generation_event(fake_db, generation_service.generate_draft(primary_db_task, source_text='Primary A'), task=primary_db_task, channel=primary_channel, status='succeeded')
    second = create_generation_event(fake_db, generation_service.generate_draft(primary_db_task, source_text='Primary B'), task=primary_db_task, channel=primary_channel, status='failed')
    third = create_generation_event(fake_db, generation_service.generate_ideas('Admin Dashboard Primary', brief='ideas', count=3), project=fake_db.get(Project, primary_project['id']), channel=primary_channel, status='succeeded')
    fourth = create_generation_event(fake_db, generation_service.generate_draft(secondary_db_task, source_text='Secondary A'), task=secondary_db_task, channel=secondary_channel, status='succeeded')

    first.created_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    third.created_at = datetime(2026, 2, 20, 8, 30, tzinfo=UTC)
    fourth.created_at = datetime(2026, 3, 16, 8, 30, tzinfo=UTC)

    dashboard = client.get('/api/v1/admin/generation/dashboard')
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload['totals']['events_count'] == 4
    assert payload['totals']['successful_events_count'] == 3
    assert payload['totals']['failed_events_count'] == 1
    assert len(payload['by_client']) == 1
    assert {item['key'] for item in payload['by_project']} == {primary_project['id'], secondary_project['id']}
    assert {item['key'] for item in payload['by_channel']} == {str(primary_channel.id), str(secondary_channel.id)}
    assert {item['key'] for item in payload['by_operation']} == {'draft', 'ideas'}
    assert payload['by_model'][0]['key'].startswith('stub:')
    assert [item['period_key'] for item in payload['by_period']] == ['2026-03', '2026-02']

    filtered = client.get(f"/api/v1/admin/generation/dashboard?project_id={primary_project['id']}")
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload['totals']['events_count'] == 3
    assert {item['key'] for item in filtered_payload['by_project']} == {primary_project['id']}

    export_response = client.get('/api/v1/admin/generation/dashboard/export')
    assert export_response.status_code == 200
    assert export_response.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="admin-generation-dashboard-report.csv"' == export_response.headers['content-disposition']
    assert 'section,key,label,events_count,successful_events_count,failed_events_count,total_prompt_tokens,total_completion_tokens,total_tokens,total_cost_usd,period_key,period_start,period_end' in export_response.text
    assert 'totals,total,All generation,4,3,1,' in export_response.text
    assert f'by_project,{primary_project["id"]},{primary_project["id"]},3,2,1,' in export_response.text
    assert 'by_period,2026-03,2026-03,3,2,1,' in export_response.text


def test_admin_generation_endpoints_return_history_usage_and_cost_breakdown(client, fake_db):
    from datetime import UTC, datetime

    project = client.post('/api/v1/projects', json={'name': 'Admin Metrics Project', 'language': 'ru'}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Admin Metrics Task'}).json()

    channel = TelegramChannel(project_id=project['id'], channel_title='Admin Metrics Channel', channel_username='@adminmetrics')
    fake_db.add(channel)
    fake_db.refresh(channel)
    db_project = fake_db.get(Project, project['id'])
    db_project.telegram_channels = [channel]

    generation_service = build_generation_service(fake_db)
    db_task = fake_db.get(ContentTask, task['id'])

    first = create_generation_event(fake_db, generation_service.generate_draft(db_task, source_text='Seed A'), task=db_task, channel=channel, status='succeeded')
    second = create_generation_event(fake_db, generation_service.generate_draft(db_task, source_text='Seed B'), task=db_task, channel=channel, status='failed')
    third = create_generation_event(fake_db, generation_service.generate_ideas('Admin Metrics Project', brief='ideas', count=3), project=fake_db.get(Project, project['id']), channel=channel, status='succeeded')
    first.created_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    third.created_at = datetime(2026, 2, 20, 8, 30, tzinfo=UTC)

    history = client.get(f"/api/v1/admin/generation/history?channel_id={channel.id}&limit=2")
    assert history.status_code == 200
    history_payload = history.json()
    assert len(history_payload['items']) == 2
    assert history_payload['items'][0]['status'] == 'failed'
    assert history_payload['items'][0]['channel_id'] == str(channel.id)

    usage = client.get(f"/api/v1/admin/generation/usage?channel_id={channel.id}")
    assert usage.status_code == 200
    usage_payload = usage.json()
    assert {item['operation_type'] for item in usage_payload['items']} == {'draft', 'ideas'}
    draft_usage = next(item for item in usage_payload['items'] if item['operation_type'] == 'draft')
    assert draft_usage['events_count'] == 2
    assert draft_usage['successful_events_count'] == 1
    assert draft_usage['failed_events_count'] == 1
    assert draft_usage['channel_id'] == str(channel.id)

    cost_breakdown = client.get(f"/api/v1/admin/generation/cost-breakdown?channel_id={channel.id}")
    assert cost_breakdown.status_code == 200
    breakdown_payload = cost_breakdown.json()
    assert any(item['group_by'] == 'channel' and item['key'] == str(channel.id) for item in breakdown_payload['items'])
    assert any(item['group_by'] == 'operation' and item['key'] == 'draft' for item in breakdown_payload['items'])
    assert any(item['group_by'] == 'model' and item['key'].startswith('stub:') for item in breakdown_payload['items'])

    usage_export = client.get(f"/api/v1/admin/generation/usage/export?channel_id={channel.id}")
    assert usage_export.status_code == 200
    assert usage_export.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="generation-usage-report.csv"' == usage_export.headers['content-disposition']
    assert 'operation_type,events_count,successful_events_count' in usage_export.text
    assert 'draft,2,1,1' in usage_export.text

    cost_export = client.get(f"/api/v1/admin/generation/cost-breakdown/export?channel_id={channel.id}")
    assert cost_export.status_code == 200
    assert cost_export.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="generation-cost-breakdown-report.csv"' == cost_export.headers['content-disposition']
    assert 'group_by,key,label,events_count,successful_events_count,total_tokens,total_cost_usd' in cost_export.text
    assert f'channel,{channel.id},{channel.id},3,2,' in cost_export.text


def test_cost_dashboard_endpoint_returns_breakdowns_by_channel_operation_model_and_period(client, fake_db):
    from datetime import UTC, datetime

    project = client.post('/api/v1/projects', json={'name': 'Dashboard Project', 'language': 'ru'}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Dashboard Task'}).json()

    channel = TelegramChannel(project_id=project['id'], channel_title='Dashboard Channel', channel_username='@dash')
    fake_db.add(channel)
    fake_db.refresh(channel)
    db_project = fake_db.get(Project, project['id'])
    db_project.telegram_channels = [channel]
    channel.created_at = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)

    generation_service = build_generation_service(fake_db)
    db_task = fake_db.get(ContentTask, task['id'])

    first = create_generation_event(fake_db, generation_service.generate_draft(db_task, source_text='Seed A'), task=db_task, channel=channel, status='succeeded')
    second = create_generation_event(fake_db, generation_service.generate_draft(db_task, source_text='Seed B'), task=db_task, channel=channel, status='failed')
    third = create_generation_event(fake_db, generation_service.generate_ideas('Dashboard Project', brief='ideas', count=3), project=fake_db.get(Project, project['id']), channel=channel, status='succeeded')
    first.created_at = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    third.created_at = datetime(2026, 2, 20, 8, 30, tzinfo=UTC)

    response = client.get('/api/v1/users/me/client-account/cost-dashboard')
    assert response.status_code == 200
    payload = response.json()

    assert payload['totals']['events_count'] == 3
    assert payload['totals']['successful_events_count'] == 2
    assert len(payload['by_channel']) == 1
    assert payload['by_channel'][0]['events_count'] == 3
    assert {item['key'] for item in payload['by_operation']} == {'draft', 'ideas'}
    assert payload['by_operation'][0]['total_cost_usd'] >= payload['by_operation'][1]['total_cost_usd']
    assert payload['by_model'][0]['key'].startswith('stub:')
    assert [item['period_key'] for item in payload['by_period']] == ['2026-03', '2026-02']

    export_response = client.get('/api/v1/users/me/client-account/cost-dashboard/export')
    assert export_response.status_code == 200
    assert export_response.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="client-cost-dashboard-report.csv"' == export_response.headers['content-disposition']
    assert 'section,key,label,events_count,successful_events_count,total_prompt_tokens,total_completion_tokens,total_tokens,total_cost_usd,period_key,period_start,period_end' in export_response.text
    assert 'totals,total,All generation,3,2,' in export_response.text
    assert f'by_channel,{channel.id},{channel.id},3,2,' in export_response.text
    assert 'by_operation,draft,draft,2,1,' in export_response.text
    assert 'by_period,2026-03,2026-03,2,1,' in export_response.text


def test_usage_and_cost_breakdown_stay_separated_by_client_channel_and_operation(fake_db):
    primary_owner = User(email='primary-owner@example.com', telegram_user_id='primary-owner')
    secondary_owner = User(email='secondary-owner@example.com', telegram_user_id='secondary-owner')
    fake_db.add(primary_owner)
    fake_db.add(secondary_owner)
    fake_db.refresh(primary_owner)
    fake_db.refresh(secondary_owner)

    primary_project = Project(name='Primary Project', language='ru', owner_user_id=primary_owner.id)
    secondary_project = Project(name='Secondary Project', language='ru', owner_user_id=secondary_owner.id)
    fake_db.add(primary_project)
    fake_db.add(secondary_project)
    fake_db.refresh(primary_project)
    fake_db.refresh(secondary_project)

    primary_task = ContentTask(project_id=primary_project.id, title='Primary task', brief='Track per-channel attribution')
    secondary_task = ContentTask(project_id=secondary_project.id, title='Secondary task', brief='Track per-client attribution')
    fake_db.add(primary_task)
    fake_db.add(secondary_task)
    fake_db.refresh(primary_task)
    fake_db.refresh(secondary_task)

    primary_channel_a = TelegramChannel(project_id=primary_project.id, channel_title='Primary A', is_active=True)
    primary_channel_b = TelegramChannel(project_id=primary_project.id, channel_title='Primary B')
    secondary_channel = TelegramChannel(project_id=secondary_project.id, channel_title='Secondary A', is_active=True)
    fake_db.add(primary_channel_a)
    fake_db.add(primary_channel_b)
    fake_db.add(secondary_channel)
    fake_db.refresh(primary_channel_a)
    fake_db.refresh(primary_channel_b)
    fake_db.refresh(secondary_channel)
    primary_project.telegram_channels = [primary_channel_a, primary_channel_b]
    secondary_project.telegram_channels = [secondary_channel]

    generation_service = build_generation_service(fake_db)

    primary_draft_success = create_generation_event(
        fake_db,
        generation_service.generate_draft(primary_task, source_text='Primary A succeeded'),
        task=primary_task,
        channel=primary_channel_a,
        status='succeeded',
    )
    primary_draft_failed = create_generation_event(
        fake_db,
        generation_service.generate_draft(primary_task, source_text='Primary A failed'),
        task=primary_task,
        channel=primary_channel_a,
        status='failed',
    )
    primary_ideas_success = create_generation_event(
        fake_db,
        generation_service.generate_ideas(primary_project.name, brief='Primary channel B ideas', count=3),
        project=primary_project,
        channel=primary_channel_b,
        status='succeeded',
    )
    secondary_draft_success = create_generation_event(
        fake_db,
        generation_service.generate_draft(secondary_task, source_text='Secondary succeeded'),
        task=secondary_task,
        channel=secondary_channel,
        status='succeeded',
    )

    usage_rows = summarize_generation_usage_admin(fake_db)
    assert len(usage_rows) == 3

    primary_draft_row = next(
        row for row in usage_rows
        if row.client_id == primary_owner.id and row.channel_id == primary_channel_a.id and row.operation_type == 'draft'
    )
    assert primary_draft_row.project_id == primary_project.id
    assert primary_draft_row.events_count == 2
    assert primary_draft_row.successful_events_count == 1
    assert primary_draft_row.failed_events_count == 1
    assert primary_draft_row.total_tokens == int(primary_draft_success.total_tokens or 0) + int(primary_draft_failed.total_tokens or 0)
    expected_primary_draft_cost = (
        Decimal(str(primary_draft_success.estimated_cost_usd or 0))
        + Decimal(str(primary_draft_failed.estimated_cost_usd or 0))
    ).quantize(Decimal('0.000001'))
    assert primary_draft_row.total_cost_usd == expected_primary_draft_cost

    primary_ideas_row = next(
        row for row in usage_rows
        if row.client_id == primary_owner.id and row.channel_id == primary_channel_b.id and row.operation_type == 'ideas'
    )
    assert primary_ideas_row.events_count == 1
    assert primary_ideas_row.total_cost_usd == Decimal(str(primary_ideas_success.estimated_cost_usd or 0)).quantize(Decimal('0.000001'))

    secondary_row = next(
        row for row in usage_rows
        if row.client_id == secondary_owner.id and row.channel_id == secondary_channel.id and row.operation_type == 'draft'
    )
    assert secondary_row.events_count == 1
    assert secondary_row.total_tokens == int(secondary_draft_success.total_tokens or 0)

    cost_rows = build_generation_cost_breakdown(fake_db, client_id=primary_owner.id)
    channel_rows = [row for row in cost_rows if row.group_by == 'channel']
    operation_rows = [row for row in cost_rows if row.group_by == 'operation']
    assert {row.key for row in channel_rows} == {str(primary_channel_a.id), str(primary_channel_b.id)}
    assert {row.key for row in operation_rows} == {'draft', 'ideas'}
    assert all(row.key != str(secondary_channel.id) for row in channel_rows)

    billed_usage = summarize_generation_usage(fake_db, billable_rates_usd={'draft': Decimal('0.070000'), 'ideas': Decimal('0.020000')})
    primary_draft_billed = next(
        row for row in billed_usage
        if row.client_id == primary_owner.id and row.channel_id == primary_channel_a.id and row.operation_type == 'draft'
    )
    assert primary_draft_billed.billed_revenue_usd == Decimal('0.070000')
    assert primary_draft_billed.margin_usd == (Decimal('0.070000') - expected_primary_draft_cost).quantize(Decimal('0.000001'))



def test_cost_dashboard_merges_legacy_owner_and_client_account_usage_without_leaking_other_clients(fake_db):
    workspace = Workspace(name='Metrics Workspace')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    owner = User(email='dashboard-owner@example.com', telegram_user_id='dashboard-owner')
    outsider = User(email='dashboard-outsider@example.com', telegram_user_id='dashboard-outsider')
    fake_db.add(owner)
    fake_db.add(outsider)
    fake_db.refresh(owner)
    fake_db.refresh(outsider)

    client_account = ClientAccount(name='Dashboard Client', owner_user_id=owner.id, workspace_id=workspace.id)
    outsider_account = ClientAccount(name='Outsider Client', owner_user_id=outsider.id, workspace_id=workspace.id)
    fake_db.add(client_account)
    fake_db.add(outsider_account)
    fake_db.refresh(client_account)
    fake_db.refresh(outsider_account)

    project = Project(name='Dashboard Attribution', language='ru', owner_user_id=owner.id, client_account_id=client_account.id)
    outsider_project = Project(name='Outsider Attribution', language='ru', owner_user_id=outsider.id, client_account_id=outsider_account.id)
    fake_db.add(project)
    fake_db.add(outsider_project)
    fake_db.refresh(project)
    fake_db.refresh(outsider_project)

    task = ContentTask(project_id=project.id, title='Dashboard task', brief='Owner + account attribution')
    outsider_task = ContentTask(project_id=outsider_project.id, title='Outsider task', brief='Must stay isolated')
    fake_db.add(task)
    fake_db.add(outsider_task)
    fake_db.refresh(task)
    fake_db.refresh(outsider_task)

    channel = TelegramChannel(project_id=project.id, channel_title='Dashboard channel', is_active=True)
    outsider_channel = TelegramChannel(project_id=outsider_project.id, channel_title='Outsider channel', is_active=True)
    fake_db.add(channel)
    fake_db.add(outsider_channel)
    fake_db.refresh(channel)
    fake_db.refresh(outsider_channel)
    project.telegram_channels = [channel]
    outsider_project.telegram_channels = [outsider_channel]

    generation_service = build_generation_service(fake_db)

    legacy_owner_event = create_generation_event(
        fake_db,
        generation_service.generate_draft(task, source_text='Legacy owner event'),
        task=task,
        channel=channel,
        status='succeeded',
    )
    account_event = create_generation_event(
        fake_db,
        generation_service.generate_ideas(project.name, brief='Account-scoped ideas', count=3),
        project=project,
        channel=channel,
        status='succeeded',
    )
    account_event.client_id = client_account.id

    outsider_event = create_generation_event(
        fake_db,
        generation_service.generate_draft(outsider_task, source_text='Outsider event'),
        task=outsider_task,
        channel=outsider_channel,
        status='succeeded',
    )
    outsider_event.client_id = outsider_account.id

    dashboard = build_cost_dashboard(fake_db, client_account)

    assert dashboard.client_id == client_account.id
    assert dashboard.totals.events_count == 2
    assert dashboard.totals.successful_events_count == 2
    assert dashboard.by_channel[0].key == str(channel.id)
    assert {row.key for row in dashboard.by_operation} == {'draft', 'ideas'}
    assert all(row.key != str(outsider_channel.id) for row in dashboard.by_channel)
    assert dashboard.totals.total_tokens == int(legacy_owner_event.total_tokens or 0) + int(account_event.total_tokens or 0)
    expected_total_cost = (
        Decimal(str(legacy_owner_event.estimated_cost_usd or 0))
        + Decimal(str(account_event.estimated_cost_usd or 0))
    ).quantize(Decimal('0.000001'))
    assert dashboard.totals.total_cost_usd == expected_total_cost
