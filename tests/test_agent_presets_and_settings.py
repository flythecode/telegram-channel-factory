from app.models.client_account import ClientAccount



def _set_current_plan(client, fake_db, plan_code: str) -> None:
    response = client.get('/api/v1/users/me/client-account')
    account = fake_db.get(ClientAccount, response.json()['id'])
    account.subscription_plan_code = plan_code
    account.subscription_status = 'active' if plan_code != 'trial' else 'trial'



def test_agent_presets_return_expected_team_sizes_and_order(client, fake_db):
    _set_current_plan(client, fake_db, 'business')
    project = client.post('/api/v1/projects', json={'name': 'Preset Size Project', 'language': 'ru'}).json()

    starter = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert starter.status_code == 200
    starter_agents = starter.json()
    assert len(starter_agents) == 3
    assert [agent['role'] for agent in starter_agents] == ['strategist', 'researcher', 'writer']

    balanced = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/balanced_5/apply")
    assert balanced.status_code == 200
    balanced_agents = balanced.json()
    assert len(balanced_agents) == 5
    assert [agent['role'] for agent in balanced_agents] == ['strategist', 'researcher', 'writer', 'editor', 'publisher']

    editorial = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/editorial_7/apply")
    assert editorial.status_code == 200
    editorial_agents = editorial.json()
    assert len(editorial_agents) == 7
    assert editorial_agents[4]['role'] == 'fact_checker'


def test_agent_settings_update_is_predictable(client, fake_db):
    _set_current_plan(client, fake_db, 'starter')
    project = client.post('/api/v1/projects', json={'name': 'Agent Settings Project', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/balanced_5/apply")
    assert applied.status_code == 200
    writer = next(agent for agent in applied.json() if agent['role'] == 'writer')

    updated = client.patch(
        f"/api/v1/agents/{writer['id']}",
        json={
            'display_name': 'Lead Writer',
            'description': 'Main content writer',
            'sort_order': 99,
            'priority': 5,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body['display_name'] == 'Lead Writer'
    assert body['description'] == 'Main content writer'
    assert body['sort_order'] == 99
    assert body['priority'] == 5


def test_disabling_agent_is_reflected_in_project_agent_list(client):
    project = client.post('/api/v1/projects', json={'name': 'Disable Agent Project', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200
    target = applied.json()[1]

    disabled = client.post(f"/api/v1/agents/{target['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()['is_enabled'] is False

    agents = client.get(f"/api/v1/projects/{project['id']}/agents")
    assert agents.status_code == 200
    listed = agents.json()
    same_agent = next(agent for agent in listed if agent['id'] == target['id'])
    assert same_agent['is_enabled'] is False


def test_prompt_overrides_are_saved_exactly(client):
    project = client.post('/api/v1/projects', json={'name': 'Prompt Override Project', 'language': 'ru'}).json()
    applied = client.post(f"/api/v1/projects/{project['id']}/agent-team-presets/starter_3/apply")
    assert applied.status_code == 200
    writer = next(agent for agent in applied.json() if agent['role'] == 'writer')

    prompts = client.patch(
        f"/api/v1/agents/{writer['id']}/prompts",
        json={
            'system_prompt': 'System rule',
            'style_prompt': 'Style rule',
            'custom_prompt': 'Custom rule',
            'config': {'tone': 'sharp'},
        },
    )
    assert prompts.status_code == 200
    body = prompts.json()
    assert body['system_prompt'] == 'System rule'
    assert body['style_prompt'] == 'Style rule'
    assert body['custom_prompt'] == 'Custom rule'
    assert body['config'] == {'tone': 'sharp'}
