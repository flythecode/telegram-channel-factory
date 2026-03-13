def test_project_config_versions_created_on_create_and_update(client):
    created = client.post(
        '/api/v1/projects',
        json={
            'name': 'Versioned Project',
            'language': 'ru',
            'topic': 'AI',
        },
    )
    assert created.status_code == 201
    project = created.json()

    versions_after_create = client.get(f"/api/v1/projects/{project['id']}/config-versions")
    assert versions_after_create.status_code == 200
    created_versions = versions_after_create.json()
    assert len(created_versions) == 1
    assert created_versions[0]['version'] == 1
    assert created_versions[0]['change_summary'] == 'Initial project config'

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={'posting_frequency': 'daily', 'operation_mode': 'semi_auto'},
    )
    assert updated.status_code == 200

    versions_after_update = client.get(f"/api/v1/projects/{project['id']}/config-versions")
    assert versions_after_update.status_code == 200
    updated_versions = versions_after_update.json()
    assert len(updated_versions) == 2
    assert updated_versions[-1]['version'] == 2
    assert updated_versions[-1]['snapshot_json']['posting_frequency'] == 'daily'
    assert updated_versions[-1]['snapshot_json']['operation_mode'] == 'semi_auto'


def test_project_config_version_created_on_operation_mode_change(client):
    created = client.post('/api/v1/projects', json={'name': 'Mode Version Project', 'language': 'ru'}).json()

    mode_update = client.patch(
        f"/api/v1/projects/{created['id']}/operation-mode",
        json={'operation_mode': 'auto'},
    )
    assert mode_update.status_code == 200

    versions = client.get(f"/api/v1/projects/{created['id']}/config-versions")
    assert versions.status_code == 200
    items = versions.json()
    assert len(items) == 2
    assert items[-1]['snapshot_json']['operation_mode'] == 'auto'
