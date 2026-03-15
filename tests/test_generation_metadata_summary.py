def test_generation_metadata_summary_propagates_to_task_and_publication(client):
    project = client.post('/api/v1/projects', json={'name': 'Summary Project', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={'channel_title': 'Summary Channel', 'channel_username': 'summary_channel'},
    ).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Summary Task'}).json()

    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Seed draft', 'version': 1}).json()
    assert draft['generation_metadata']['usage_summary']['total_tokens'] >= 0
    assert draft['generation_metadata']['cost_summary']['currency'] == 'USD'

    task_read = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task_read['generation_metadata']['summary_scope'] == 'task'
    assert task_read['generation_metadata']['provider'] == draft['generation_metadata']['provider']
    assert task_read['generation_metadata']['usage_summary'] == draft['generation_metadata']['usage_summary']

    approved = client.post(f"/api/v1/drafts/{draft['id']}/approve")
    assert approved.status_code == 200

    publication = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={'telegram_channel_id': channel['id']},
    ).json()
    assert publication['generation_metadata']['summary_scope'] == 'publication'
    assert publication['generation_metadata']['provider'] == draft['generation_metadata']['provider']
    assert publication['generation_metadata']['usage_summary'] == draft['generation_metadata']['usage_summary']
    assert publication['generation_metadata']['source_draft_id'] == draft['id']
