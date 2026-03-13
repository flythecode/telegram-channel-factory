from app.services.stub_publisher import stub_publisher



def _create_publication(client):
    project = client.post('/api/v1/projects', json={'name': 'Stub Project', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Stub Channel',
            'channel_id': 'stub-001',
            'publish_mode': 'manual',
            'is_active': True,
        },
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Stub Task'},
    ).json()
    draft = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={'text': 'Stub draft', 'version': 1},
    ).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")
    publication = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={'telegram_channel_id': channel['id']},
    ).json()
    return task, publication



def test_stub_publisher_publish_marks_sent_and_sets_message_id(client, fake_db):
    task, publication = _create_publication(client)

    result = stub_publisher.publish(fake_db, publication['id'])

    assert result.status.value == 'sent'
    assert result.external_message_id.startswith('stub-')
    assert result.published_at is not None

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'published'



def test_stub_publisher_fail_marks_failed(client, fake_db):
    task, publication = _create_publication(client)

    result = stub_publisher.fail(fake_db, publication['id'], 'stub network failure')

    assert result.status.value == 'failed'
    assert result.error_message == 'stub network failure'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'failed'
