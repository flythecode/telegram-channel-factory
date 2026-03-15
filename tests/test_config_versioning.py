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
    assert updated_versions[-1]['snapshot_json']['project']['posting_frequency'] == 'daily'
    assert updated_versions[-1]['snapshot_json']['project']['operation_mode'] == 'semi_auto'


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
    assert items[-1]['snapshot_json']['project']['operation_mode'] == 'auto'


def test_agent_prompt_updates_create_reproducible_project_config_versions(client):
    project = client.post('/api/v1/projects', json={'name': 'Agent Version Project', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200

    versions_after_apply = client.get(f"/api/v1/projects/{project['id']}/config-versions")
    assert versions_after_apply.status_code == 200
    apply_items = versions_after_apply.json()
    assert len(apply_items) == 2
    assert apply_items[-1]['change_summary'] == 'Agent team preset applied: starter_3'
    assert len(apply_items[-1]['snapshot_json']['agent_team']) == 3
    assert apply_items[-1]['snapshot_json']['prompt_templates'] == []

    writer_agent = next(agent for agent in applied.json() if agent['role'] == 'writer')
    updated = client.patch(
        f"/api/v1/agents/{writer_agent['id']}/prompts",
        json={
            'system_prompt': 'Пиши как редактор premium-канала',
            'custom_prompt': 'Добавляй сильный хук в первом абзаце',
            'config': {'temperature': 0.3},
        },
    )
    assert updated.status_code == 200

    versions_after_prompt_update = client.get(f"/api/v1/projects/{project['id']}/config-versions")
    assert versions_after_prompt_update.status_code == 200
    prompt_items = versions_after_prompt_update.json()
    assert len(prompt_items) == 3
    assert prompt_items[-1]['change_summary'] == 'Agent prompts updated: writer'

    writer_snapshot = next(
        item for item in prompt_items[-1]['snapshot_json']['agent_team']
        if item['id'] == writer_agent['id']
    )
    assert writer_snapshot['system_prompt'] == 'Пиши как редактор premium-канала'
    assert writer_snapshot['custom_prompt'] == 'Добавляй сильный хук в первом абзаце'
    assert writer_snapshot['config'] == {'temperature': 0.3}
