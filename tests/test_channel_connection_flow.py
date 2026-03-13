def test_channel_connection_flow_needs_attention_until_permissions_are_set(client):
    project = client.post('/api/v1/projects', json={'name': 'Channel Flow', 'language': 'ru'}).json()
    channel = client.post(f"/api/v1/projects/{project['id']}/channels", json={'channel_title': 'Flow Channel'}).json()

    check_one = client.get(f"/api/v1/channels/{channel['id']}/connection-check")
    assert check_one.status_code == 200
    assert check_one.json()['status'] == 'needs_attention'

    connect = client.post(
        f"/api/v1/channels/{channel['id']}/connect",
        json={'is_connected': True, 'bot_is_admin': True, 'can_post_messages': True},
    )
    assert connect.status_code == 200

    check_two = client.get(f"/api/v1/channels/{channel['id']}/connection-check")
    assert check_two.status_code == 200
    assert check_two.json()['status'] == 'connected'


def test_channel_connection_flow_detects_missing_permission_branch(client):
    project = client.post('/api/v1/projects', json={'name': 'Channel Flow 2', 'language': 'ru'}).json()
    channel = client.post(f"/api/v1/projects/{project['id']}/channels", json={'channel_title': 'Flow Channel 2'}).json()

    connect = client.post(
        f"/api/v1/channels/{channel['id']}/connect",
        json={'is_connected': True, 'bot_is_admin': True, 'can_post_messages': False},
    )
    assert connect.status_code == 200

    check = client.get(f"/api/v1/channels/{channel['id']}/connection-check")
    assert check.status_code == 200
    assert check.json()['status'] == 'needs_attention'
    assert check.json()['can_post_messages'] is False
