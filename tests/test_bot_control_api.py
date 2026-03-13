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


def test_content_plan_task_draft_publication_control_api(client):
    project = client.post('/api/v1/projects', json={'name': 'Control Project', 'language': 'ru'}).json()
    client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    plan = client.post(
        f"/api/v1/projects/{project['id']}/content-plans",
        json={'period_type': 'week', 'start_date': '2026-03-16', 'end_date': '2026-03-22', 'status': 'generated'},
    ).json()

    regenerated = client.post(f"/api/v1/content-plans/{plan['id']}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()['status'] == 'regenerated'

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

    approved = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approved.status_code == 200

    channel = client.post(f"/api/v1/projects/{project['id']}/channels", json={'channel_title': 'Pub Channel'}).json()
    publication = client.post(f"/api/v1/drafts/{draft['id']}/publications", json={'telegram_channel_id': channel['id']}).json()

    publish_now = client.post(f"/api/v1/publications/{publication['id']}/publish-now")
    assert publish_now.status_code == 200

    canceled = client.post(f"/api/v1/publications/{publication['id']}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()['status'] == 'canceled'
