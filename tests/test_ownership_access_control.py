def test_other_user_cannot_get_foreign_project(client):
    created = client.post('/api/v1/projects', json={'name': 'Private Project', 'language': 'ru'}).json()

    response = client.get(
        f"/api/v1/projects/{created['id']}",
        headers={
            'x-telegram-user-id': 'foreign-user',
            'x-telegram-username': 'foreign',
        },
    )

    assert response.status_code == 404


def test_other_user_cannot_patch_foreign_project(client):
    created = client.post('/api/v1/projects', json={'name': 'Private Patch Project', 'language': 'ru'}).json()

    response = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={'goal': 'hijack'},
        headers={
            'x-telegram-user-id': 'foreign-user-2',
            'x-telegram-username': 'foreign2',
        },
    )

    assert response.status_code == 404


def test_workspace_is_reused_for_same_current_user(client):
    workspace_one = client.get('/api/v1/users/me/workspace')
    assert workspace_one.status_code == 200

    workspace_two = client.get('/api/v1/users/me/workspace')
    assert workspace_two.status_code == 200

    assert workspace_one.json()['id'] == workspace_two.json()['id']


def test_created_project_is_linked_to_current_users_workspace(client):
    workspace = client.get('/api/v1/users/me/workspace').json()
    project = client.post('/api/v1/projects', json={'name': 'Workspace Linked Project', 'language': 'ru'}).json()

    assert project['workspace_id'] == workspace['id']
    assert project['owner_user_id'] == workspace['owner_user_id']
