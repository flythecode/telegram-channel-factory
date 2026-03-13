def _create_approved_publication(client, scheduled: bool = False):
    project = client.post('/api/v1/projects', json={'name': 'Transition Project', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Transition Channel',
            'channel_id': f"transition-{'scheduled' if scheduled else 'immediate'}",
            'publish_mode': 'scheduled' if scheduled else 'manual',
            'is_active': True,
        },
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Transition Task'},
    ).json()
    draft = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={'text': 'Transition draft', 'version': 1},
    ).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")

    payload = {'telegram_channel_id': channel['id']}
    if scheduled:
        payload['scheduled_for'] = '2026-03-13T10:00:00Z'

    publication = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json=payload,
    ).json()
    return task, publication



def test_publication_transition_sent_marks_task_published(client):
    task, publication = _create_approved_publication(client, scheduled=False)

    response = client.patch(
        f"/api/v1/publications/{publication['id']}",
        json={'status': 'sent'},
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'sent'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'published'



def test_publication_transition_failed_marks_task_failed(client):
    task, publication = _create_approved_publication(client, scheduled=False)

    response = client.patch(
        f"/api/v1/publications/{publication['id']}",
        json={'status': 'failed', 'error_message': 'Telegram API timeout'},
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'failed'
    assert response.json()['error_message'] == 'Telegram API timeout'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'failed'



def test_publication_transition_canceled_returns_task_to_approved(client):
    task, publication = _create_approved_publication(client, scheduled=True)

    response = client.patch(
        f"/api/v1/publications/{publication['id']}",
        json={'status': 'canceled'},
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'canceled'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'approved'



def test_publication_transition_queued_keeps_task_scheduled(client):
    task, publication = _create_approved_publication(client, scheduled=True)

    response = client.patch(
        f"/api/v1/publications/{publication['id']}",
        json={'status': 'queued'},
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'queued'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'scheduled'
