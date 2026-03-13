def test_api_pipeline_project_channel_task_draft_approve_publication(client):
    project_res = client.post(
        '/api/v1/projects',
        json={
            'name': 'Pipeline Project',
            'description': 'Fuller pipeline API test',
            'language': 'ru',
        },
    )
    assert project_res.status_code == 201
    project = project_res.json()
    project_id = project['id']

    channel_res = client.post(
        f'/api/v1/projects/{project_id}/channels',
        json={
            'channel_title': 'Pipeline Channel',
            'channel_username': 'pipeline_channel',
            'channel_id': 'pipeline-001',
            'publish_mode': 'manual',
            'is_active': True,
        },
    )
    assert channel_res.status_code == 201
    channel = channel_res.json()

    task_res = client.post(
        f'/api/v1/projects/{project_id}/tasks',
        json={
            'title': 'Pipeline Task',
            'topic': 'Market update',
            'format': 'post',
            'brief': 'Create a concise market brief',
        },
    )
    assert task_res.status_code == 201
    task = task_res.json()
    assert task['status'] == 'pending'

    draft_res = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={
            'text': 'BTC holds key support, ETH tracks higher.',
            'source_notes': 'Internal test notes',
            'created_by_agent': 'writer-agent',
            'version': 1,
        },
    )
    assert draft_res.status_code == 201
    draft = draft_res.json()
    assert draft['status'] == 'created'

    approve_res = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approve_res.status_code == 200
    approved_draft = approve_res.json()
    assert approved_draft['status'] == 'approved'

    publication_res = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={
            'telegram_channel_id': channel['id'],
        },
    )
    assert publication_res.status_code == 201
    publication = publication_res.json()
    assert publication['status'] == 'sending'
    assert publication['telegram_channel_id'] == channel['id']

    get_task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert get_task_res.status_code == 200
    assert get_task_res.json()['status'] == 'published'

    list_publications_res = client.get(f"/api/v1/drafts/{draft['id']}/publications")
    assert list_publications_res.status_code == 200
    publications = list_publications_res.json()
    assert len(publications) == 1
    assert publications[0]['id'] == publication['id']



def test_api_pipeline_scheduled_publication_branch(client):
    project = client.post(
        '/api/v1/projects',
        json={'name': 'Scheduled Project', 'language': 'ru'},
    ).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Scheduled Channel',
            'channel_id': 'scheduled-001',
            'publish_mode': 'scheduled',
            'is_active': True,
        },
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Scheduled Task'},
    ).json()
    draft = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={'text': 'Scheduled draft body', 'version': 1},
    ).json()

    approve_res = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approve_res.status_code == 200

    publication_res = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={
            'telegram_channel_id': channel['id'],
            'scheduled_for': '2026-03-13T10:00:00Z',
        },
    )
    assert publication_res.status_code == 201
    publication = publication_res.json()
    assert publication['status'] == 'queued'
    assert publication['scheduled_for'] == '2026-03-13T10:00:00Z'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'scheduled'



def test_api_pipeline_reject_branch(client):
    project = client.post(
        '/api/v1/projects',
        json={'name': 'Reject Project', 'language': 'ru'},
    ).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Reject Task'},
    ).json()
    draft = client.post(
        f"/api/v1/tasks/{task['id']}/drafts",
        json={'text': 'Draft to reject', 'version': 1},
    ).json()

    reject_res = client.post(f"/api/v1/drafts/{draft['id']}/reject")
    assert reject_res.status_code == 200
    rejected_draft = reject_res.json()
    assert rejected_draft['status'] == 'rejected'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'rejected'



def test_api_pipeline_with_content_plan_happy_path(client):
    project = client.post(
        '/api/v1/projects',
        json={'name': 'Plan Project', 'language': 'ru'},
    ).json()

    plan_res = client.post(
        f"/api/v1/projects/{project['id']}/content-plans",
        json={
            'period_type': 'week',
            'start_date': '2026-03-16',
            'end_date': '2026-03-22',
            'status': 'generated',
            'generated_by': 'strategist-agent',
        },
    )
    assert plan_res.status_code == 201
    plan = plan_res.json()

    list_plans_res = client.get(f"/api/v1/projects/{project['id']}/content-plans")
    assert list_plans_res.status_code == 200
    assert len(list_plans_res.json()) == 1

    task_res = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={
            'title': 'Planned Task',
            'content_plan_id': plan['id'],
            'topic': 'Weekly recap',
        },
    )
    assert task_res.status_code == 201
    task = task_res.json()
    assert task['content_plan_id'] == plan['id']
