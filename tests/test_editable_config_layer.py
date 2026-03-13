def test_project_operation_mode_change_affects_new_config_versions_only(client):
    project = client.post(
        '/api/v1/projects',
        json={
            'name': 'Editable Config Project',
            'language': 'ru',
            'operation_mode': 'manual',
            'posting_frequency': 'weekly',
        },
    ).json()

    versions_before = client.get(f"/api/v1/projects/{project['id']}/config-versions")
    assert versions_before.status_code == 200
    before_items = versions_before.json()
    assert before_items[-1]['snapshot_json']['operation_mode'] == 'manual'
    assert before_items[-1]['snapshot_json']['posting_frequency'] == 'weekly'

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={'operation_mode': 'semi_auto', 'posting_frequency': 'daily'},
    )
    assert updated.status_code == 200

    versions_after = client.get(f"/api/v1/projects/{project['id']}/config-versions")
    assert versions_after.status_code == 200
    after_items = versions_after.json()
    assert len(after_items) == len(before_items) + 1
    assert after_items[-1]['snapshot_json']['operation_mode'] == 'semi_auto'
    assert after_items[-1]['snapshot_json']['posting_frequency'] == 'daily'
    assert before_items[-1]['snapshot_json']['operation_mode'] == 'manual'


def test_agent_prompt_change_affects_new_generation_but_not_existing_draft_metadata(client):
    project = client.post('/api/v1/projects', json={'name': 'Editable Agent Config', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200

    task_one = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Task One'}).json()
    draft_one = client.post(f"/api/v1/tasks/{task_one['id']}/drafts", json={'text': 'Draft One', 'version': 1}).json()

    writer_agent = next(agent for agent in applied.json() if agent['role'] == 'writer')
    prompt_update = client.patch(
        f"/api/v1/agents/{writer_agent['id']}/prompts",
        json={'custom_prompt': 'Use a sharper market tone'},
    )
    assert prompt_update.status_code == 200

    task_two = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Task Two'}).json()
    draft_two = client.post(f"/api/v1/tasks/{task_two['id']}/drafts", json={'text': 'Draft Two', 'version': 1}).json()

    assert draft_one['generation_metadata']['stage_roles'] == ['strategist', 'researcher', 'writer']
    assert draft_two['generation_metadata']['stage_roles'] == ['strategist', 'researcher', 'writer']
    assert draft_one['generation_metadata'] == {
        'preset_code': 'starter_3',
        'applied_agent_ids': draft_one['generation_metadata']['applied_agent_ids'],
        'stage_roles': ['strategist', 'researcher', 'writer'],
        'final_agent_name': draft_one['generation_metadata']['final_agent_name'],
    }
    assert draft_two['generation_metadata']['applied_agent_ids'] == draft_one['generation_metadata']['applied_agent_ids']


def test_project_setting_change_is_applied_to_new_task_generation_context(client):
    project = client.post(
        '/api/v1/projects',
        json={
            'name': 'Generation Context Project',
            'language': 'ru',
            'topic': 'Crypto',
            'posting_frequency': 'weekly',
        },
    ).json()
    client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")

    task_before = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'Before Change', 'topic': 'BTC'},
    ).json()
    draft_before = client.post(f"/api/v1/tasks/{task_before['id']}/drafts", json={'text': 'Before draft', 'version': 1}).json()

    update_project = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={'topic': 'AI', 'posting_frequency': 'daily', 'tone_of_voice': 'formal'},
    )
    assert update_project.status_code == 200

    task_after = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={'title': 'After Change', 'topic': 'LLMs'},
    ).json()
    draft_after = client.post(f"/api/v1/tasks/{task_after['id']}/drafts", json={'text': 'After draft', 'version': 1}).json()

    assert draft_before['generation_metadata']['preset_code'] == 'starter_3'
    assert draft_after['generation_metadata']['preset_code'] == 'starter_3'
    assert draft_before['generation_metadata']['stage_roles'] == draft_after['generation_metadata']['stage_roles']
