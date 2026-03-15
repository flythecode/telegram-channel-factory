def test_channel_connect_and_check_api(client):
    project = client.post('/api/v1/projects', json={'name': 'Connect Project', 'language': 'ru'}).json()
    channel = client.post(f"/api/v1/projects/{project['id']}/channels", json={'channel_title': 'Connect Channel'}).json()

    connected = client.post(
        f"/api/v1/channels/{channel['id']}/connect",
        json={'is_connected': True, 'bot_is_admin': True, 'can_post_messages': True},
    )
    assert connected.status_code == 200
    assert connected.json()['is_connected'] is True

    checked = client.get(f"/api/v1/channels/{channel['id']}/connection-check")
    assert checked.status_code == 200
    assert checked.json()['status'] == 'connected'


def test_operation_mode_api(client):
    project = client.post('/api/v1/projects', json={'name': 'Mode Project', 'language': 'ru'}).json()

    current_mode = client.get(f"/api/v1/projects/{project['id']}/operation-mode")
    assert current_mode.status_code == 200
    assert current_mode.json()['operation_mode'] == 'manual'

    updated = client.patch(f"/api/v1/projects/{project['id']}/operation-mode", json={'operation_mode': 'semi_auto'})
    assert updated.status_code == 200
    assert updated.json()['operation_mode'] == 'semi_auto'


def test_agent_presets_apply_and_agent_control_api(client):
    project = client.post('/api/v1/projects', json={'name': 'Preset Project', 'language': 'ru'}).json()

    presets = client.get('/api/v1/agent-team-presets')
    assert presets.status_code == 200
    assert len(presets.json()) >= 3

    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/balanced_5/apply")
    assert applied.status_code == 200
    agents = applied.json()
    assert len(agents) == 5

    agent_id = agents[0]['id']
    disabled = client.post(f"/api/v1/agents/{agent_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()['is_enabled'] is False

    prompts = client.patch(
        f"/api/v1/agents/{agent_id}/prompts",
        json={'system_prompt': 'System', 'style_prompt': 'Style', 'custom_prompt': 'Custom'},
    )
    assert prompts.status_code == 200
    assert prompts.json()['custom_prompt'] == 'Custom'


from datetime import datetime, timedelta, timezone

from app.models.client_account import ClientAccount
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.utils.enums import SubscriptionStatus


def test_content_plan_task_draft_publication_control_api(client):
    project = client.post('/api/v1/projects', json={'name': 'Control Project', 'language': 'ru'}).json()
    client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    plan = client.post(
        f"/api/v1/projects/{project['id']}/content-plans",
        json={'period_type': 'week', 'start_date': '2026-03-16', 'end_date': '2026-03-22', 'status': 'generated'},
    ).json()
    assert plan['generated_by'] == 'generation-service'
    assert plan['summary']

    regenerated = client.post(f"/api/v1/content-plans/{plan['id']}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()['status'] == 'regenerated'
    assert regenerated.json()['generated_by'] == 'generation-service'
    assert regenerated.json()['summary']

    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Bot Task', 'content_plan_id': plan['id']},
    ).json()
    tasks_for_plan = client.get(f"/api/v1/content-plans/{plan['id']}/tasks")
    assert tasks_for_plan.status_code == 200
    assert len(tasks_for_plan.json()) == 1

    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Draft body', 'version': 1}).json()
    assert draft['created_by_agent'] is not None

    edited = client.patch(f"/api/v1/drafts/{draft['id']}", json={'text': 'Edited body'})
    assert edited.status_code == 200
    assert edited.json()['status'] == 'edited'

    regenerated_draft = client.post(f"/api/v1/drafts/{draft['id']}/regenerate")
    assert regenerated_draft.status_code == 200
    assert '[Regenerated]' in regenerated_draft.json()['text']
    assert regenerated_draft.json()['generation_metadata']['operation_type'] == 'regenerate_draft'

    rewritten_draft = client.post(
        f"/api/v1/drafts/{draft['id']}/rewrite",
        json={'rewrite_prompt': 'Сделай текст короче и добавь CTA'},
    )
    assert rewritten_draft.status_code == 200
    assert 'Сделай текст короче и добавь CTA' in rewritten_draft.json()['text']
    assert rewritten_draft.json()['generation_metadata']['operation_type'] == 'rewrite_draft'

    approved = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approved.status_code == 200

    channel = client.post(f"/api/v1/projects/{project['id']}/channels", json={'channel_title': 'Pub Channel'}).json()
    publication = client.post(f"/api/v1/drafts/{draft['id']}/publications", json={'telegram_channel_id': channel['id']}).json()

    publish_now = client.post(f"/api/v1/publications/{publication['id']}/publish-now")
    assert publish_now.status_code == 200

    canceled = client.post(f"/api/v1/publications/{publication['id']}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()['status'] == 'canceled'


def test_draft_create_api_returns_400_when_generation_hard_stopped(client, fake_db):
    user = User(email='api-hard-stop@example.com', telegram_user_id='api-hard-stop-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='API Hard Stop WS', slug='api-hard-stop-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='API Hard Stop Account',
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

    project = client.post('/api/v1/projects', json={'name': 'Blocked API Project', 'language': 'ru'}).json()
    api_project = fake_db.get(Project, project['id'])
    assert api_project is not None
    api_project.client_account_id = account.id
    api_project.client_account = account

    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Blocked API Task'},
    ).json()

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project['id'],
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

    blocked = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Draft body', 'version': 1})
    assert blocked.status_code == 400
    assert 'Generation hard-stopped' in blocked.json()['detail']
