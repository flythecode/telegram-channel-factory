def test_new_agent_configuration_applies_only_to_new_generations(client):
    project = client.post('/api/v1/projects', json={'name': 'Freeze Project', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Freeze Task'}).json()

    draft_one = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'First draft', 'version': 1}).json()
    assert draft_one['generation_metadata']['preset_code'] == 'starter_3'
    assert draft_one['generation_metadata']['stage_roles'] == ['strategist', 'researcher', 'writer']

    writer_agent = next(agent for agent in applied.json() if agent['role'] == 'writer')
    updated_agent = client.patch(
        f"/api/v1/agents/{writer_agent['id']}/prompts",
        json={'custom_prompt': 'Use premium editorial tone'},
    )
    assert updated_agent.status_code == 200

    draft_two = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Second draft', 'version': 2}).json()
    assert draft_two['generation_metadata']['preset_code'] == 'starter_3'
    assert draft_two['generation_metadata']['applied_agent_ids'] == draft_one['generation_metadata']['applied_agent_ids']

    assert draft_one['generation_metadata']['preset_code'] == 'starter_3'
    assert draft_one['generation_metadata']['applied_agent_ids']
    assert draft_one['generation_metadata']['final_agent_name']
    assert draft_one['generation_metadata']['provider']
    assert draft_one['generation_metadata']['model']
