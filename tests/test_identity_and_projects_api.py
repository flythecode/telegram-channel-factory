def test_get_current_user_from_telegram_identity(client):
    response = client.get('/api/v1/users/me')

    assert response.status_code == 200
    body = response.json()
    assert body['telegram_user_id'] == 'test-user-1'
    assert body['email'] == 'tg-test-user-1@telegram.local'


def test_get_current_workspace_from_telegram_identity(client):
    response = client.get('/api/v1/users/me/workspace')

    assert response.status_code == 200
    body = response.json()
    assert body['owner_user_id']
    assert body['name'].endswith('Workspace')


def test_projects_list_is_scoped_to_current_user(client):
    create_response = client.post('/api/v1/projects', json={'name': 'Scoped Project', 'language': 'ru'})
    assert create_response.status_code == 201

    list_response = client.get('/api/v1/projects')
    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]['name'] == 'Scoped Project'
    assert projects[0]['owner_user_id'] is not None
    assert projects[0]['workspace_id'] is not None

    other_headers = {
        'x-telegram-user-id': 'test-user-2',
        'x-telegram-username': 'otheruser',
    }
    empty_response = client.get('/api/v1/projects', headers=other_headers)
    assert empty_response.status_code == 200
    assert empty_response.json() == []


def test_create_project_from_wizard_endpoint(client):
    response = client.post(
        '/api/v1/projects/wizard',
        json={
            'name': 'Wizard Project',
            'language': 'ru',
            'topic': 'AI',
            'content_format': 'short_posts',
            'posting_frequency': 'daily',
            'operation_mode': 'semi_auto',
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Wizard Project'
    assert body['topic'] == 'AI'
    assert body['operation_mode'] == 'semi_auto'


def test_update_project_settings_after_create(client):
    created = client.post('/api/v1/projects', json={'name': 'Editable Project', 'language': 'ru'}).json()

    response = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={
            'tone_of_voice': 'formal-friendly',
            'goal': 'grow audience',
            'operation_mode': 'auto',
            'posting_frequency': 'twice_daily',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['tone_of_voice'] == 'formal-friendly'
    assert body['goal'] == 'grow audience'
    assert body['operation_mode'] == 'auto'
    assert body['posting_frequency'] == 'twice_daily'
