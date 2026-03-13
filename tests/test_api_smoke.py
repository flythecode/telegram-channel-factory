def test_healthcheck(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'



def test_projects_create_and_list_smoke(client):
    create_response = client.post(
        '/api/v1/projects',
        json={
            'name': 'Smoke Project',
            'description': 'API smoke test',
            'language': 'ru',
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created['name'] == 'Smoke Project'
    assert created['language'] == 'ru'

    list_response = client.get('/api/v1/projects')

    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]['name'] == 'Smoke Project'
