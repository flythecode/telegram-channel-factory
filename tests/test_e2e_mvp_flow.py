def test_e2e_project_plan_task_draft_approve_publication(client):
    project = client.post('/api/v1/projects/wizard', json={'name': 'E2E Project', 'language': 'ru'}).json()
    client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    plan = client.post(
        f"/api/v1/projects/{project['id']}/content-plans",
        json={'period_type': 'week', 'start_date': '2026-03-16', 'end_date': '2026-03-22', 'status': 'generated'},
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'E2E Task', 'content_plan_id': plan['id'], 'brief': 'Short post'},
    ).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Draft text', 'version': 1}).json()

    approved = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approved.status_code == 200
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={'channel_title': 'E2E Channel', 'is_connected': True, 'bot_is_admin': True, 'can_post_messages': True},
    ).json()
    publication = client.post(f"/api/v1/drafts/{draft['id']}/publications", json={'telegram_channel_id': channel['id']})
    assert publication.status_code == 201
    body = publication.json()
    assert body['telegram_channel_id'] == channel['id']
    assert body['status'] in ['sending', 'queued']


def test_e2e_draft_edit_approve_queue_flow(client):
    project = client.post('/api/v1/projects/wizard', json={'name': 'Queue Flow Project', 'language': 'ru'}).json()
    client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    plan = client.post(
        f"/api/v1/projects/{project['id']}/content-plans",
        json={'period_type': 'week', 'start_date': '2026-03-16', 'end_date': '2026-03-22', 'status': 'generated'},
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Queued Task', 'content_plan_id': plan['id'], 'brief': 'Queue-ready post'},
    ).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Initial draft', 'version': 1}).json()

    edited = client.patch(f"/api/v1/drafts/{draft['id']}", json={'text': 'Edited draft for approval'})
    assert edited.status_code == 200
    assert edited.json()['status'] == 'edited'

    approved = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'

    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={'channel_title': 'Queued Channel', 'is_connected': True, 'bot_is_admin': True, 'can_post_messages': True},
    ).json()
    queued = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={'telegram_channel_id': channel['id'], 'scheduled_for': '2026-03-20T10:00:00Z'},
    )
    assert queued.status_code == 201
    body = queued.json()
    assert body['telegram_channel_id'] == channel['id']
    assert body['status'] == 'queued'
    assert body['scheduled_for'] == '2026-03-20T10:00:00Z'

    task_after = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_after.status_code == 200
    assert task_after.json()['status'] == 'scheduled'


def test_e2e_return_later_open_channel_change_settings_and_regenerate(client):
    project = client.post('/api/v1/projects/wizard', json={'name': 'Return Later Project', 'language': 'ru'}).json()
    client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    plan = client.post(
        f"/api/v1/projects/{project['id']}/content-plans",
        json={'period_type': 'week', 'start_date': '2026-03-16', 'end_date': '2026-03-22', 'status': 'generated'},
    ).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Later Channel',
            'channel_username': 'later_channel',
            'publish_mode': 'manual',
            'is_connected': True,
            'bot_is_admin': True,
            'can_post_messages': True,
        },
    ).json()

    reopened = client.get(f"/api/v1/channels/{channel['id']}")
    assert reopened.status_code == 200
    assert reopened.json()['id'] == channel['id']
    assert reopened.json()['publish_mode'] == 'manual'

    updated = client.patch(
        f"/api/v1/channels/{channel['id']}",
        json={
            'channel_title': 'Later Channel Updated',
            'publish_mode': 'scheduled',
            'connection_notes': {'regeneration_mode': 'fresh'},
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body['channel_title'] == 'Later Channel Updated'
    assert updated_body['publish_mode'] == 'scheduled'
    assert updated_body['connection_notes']['regeneration_mode'] == 'fresh'

    regenerated = client.post(f"/api/v1/content-plans/{plan['id']}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()['status'] == 'regenerated'
