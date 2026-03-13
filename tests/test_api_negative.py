def test_create_channel_for_missing_project_returns_404(client):
    response = client.post(
        '/api/v1/projects/00000000-0000-0000-0000-000000000001/channels',
        json={
            'channel_title': 'Ghost Channel',
            'channel_id': 'ghost-001',
            'publish_mode': 'manual',
            'is_active': True,
        },
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Project not found'



def test_create_task_for_missing_project_returns_404(client):
    response = client.post(
        '/api/v1/projects/00000000-0000-0000-0000-000000000002/tasks',
        json={
            'title': 'Ghost Task',
        },
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Project not found'



def test_create_draft_for_missing_task_returns_404(client):
    response = client.post(
        '/api/v1/tasks/00000000-0000-0000-0000-000000000003/drafts',
        json={
            'text': 'Missing task draft',
            'version': 1,
        },
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Task not found'



def test_approve_missing_draft_returns_404(client):
    response = client.post('/api/v1/drafts/00000000-0000-0000-0000-000000000004/approve')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Draft not found'



def test_create_publication_for_missing_draft_returns_404(client):
    response = client.post(
        '/api/v1/drafts/00000000-0000-0000-0000-000000000005/publications',
        json={
            'telegram_channel_id': '00000000-0000-0000-0000-000000000006',
        },
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Draft not found'



def test_create_publication_for_non_approved_draft_returns_400(client):
    project = client.post('/api/v1/projects', json={'name': 'Neg Project', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Neg Channel',
            'channel_id': 'neg-001',
            'publish_mode': 'manual',
            'is_active': True,
        },
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Neg Task'},
    ).json()
    draft = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={'text': 'Draft without approval', 'version': 1},
    ).json()

    response = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={
            'telegram_channel_id': channel['id'],
        },
    )

    assert response.status_code == 400
    assert response.json()['detail'] == 'Only approved drafts can be queued for publication'



def test_create_publication_for_missing_channel_returns_404(client):
    project = client.post('/api/v1/projects', json={'name': 'Missing Channel Project', 'language': 'ru'}).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Task For Missing Channel'},
    ).json()
    draft = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={'text': 'Approved draft', 'version': 1},
    ).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")

    response = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={
            'telegram_channel_id': '00000000-0000-0000-0000-000000000007',
        },
    )

    assert response.status_code == 404
    assert response.json()['detail'] == 'Channel not found'
