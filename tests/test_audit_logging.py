import logging


def test_project_update_creates_audit_event(client):
    project = client.post('/api/v1/projects', json={'name': 'Audit Project', 'language': 'ru'}).json()

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={'goal': 'grow audience', 'operation_mode': 'semi_auto'},
    )
    assert updated.status_code == 200

    events = client.get(f"/api/v1/projects/{project['id']}/audit-events")
    assert events.status_code == 200
    items = events.json()
    assert any(event['action'] == 'update_project_settings' for event in items)



def test_agent_and_publication_actions_create_audit_events(client):
    project = client.post('/api/v1/projects', json={'name': 'Agent Audit', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200
    agent_id = applied.json()[0]['id']

    disabled = client.post(f"/api/v1/agents/{agent_id}/disable")
    assert disabled.status_code == 200

    prompt_update = client.patch(
        f"/api/v1/agents/{agent_id}/prompts",
        json={'custom_prompt': 'New prompt'},
    )
    assert prompt_update.status_code == 200

    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Audit Task'}).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Draft body', 'version': 1}).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")
    channel = client.post(f"/api/v1/projects/{project['id']}/channels", json={'channel_title': 'Audit Channel'}).json()
    publication = client.post(f"/api/v1/drafts/{draft['id']}/publications", json={'telegram_channel_id': channel['id']}).json()

    canceled = client.post(f"/api/v1/publications/{publication['id']}/cancel")
    assert canceled.status_code == 200

    events = client.get(f"/api/v1/projects/{project['id']}/audit-events")
    assert events.status_code == 200
    actions = [event['action'] for event in events.json()]
    assert 'disable_agent' in actions
    assert 'update_agent_prompts' in actions
    assert 'cancel_publication' in actions



def test_request_observability_logs_request_lifecycle_and_sets_request_id(client, caplog):
    with caplog.at_level(logging.INFO):
        response = client.get('/health', headers={'x-request-id': 'req-123'})

    assert response.status_code == 200
    assert response.headers['x-request-id'] == 'req-123'

    started = [record for record in caplog.records if record.message == 'request started']
    completed = [record for record in caplog.records if record.message == 'request completed']

    assert started
    assert completed
    assert started[-1].request_id == 'req-123'
    assert started[-1].path == '/health'
    assert completed[-1].request_id == 'req-123'
    assert completed[-1].status_code == 200
    assert completed[-1].duration_ms >= 0



def test_request_observability_logs_unauthorized_api_requests(client, caplog):
    with caplog.at_level(logging.INFO):
        response = client.get('/api/v1/users/me', headers={'x-telegram-user-id': ''})

    assert response.status_code == 401
    assert 'x-request-id' in response.headers

    completed = [record for record in caplog.records if record.message == 'request completed']
    assert completed
    assert completed[-1].path == '/api/v1/users/me'
    assert completed[-1].status_code == 401
