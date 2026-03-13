from app.models.agent_team_preset import AgentTeamPreset
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.agent_profile import AgentProfile
from app.utils.enums import AgentRole, OperationMode, PublishMode


def test_project_strategy_fields_have_expected_defaults(fake_db):
    project = Project(name='Strategy Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    assert project.operation_mode == OperationMode.MANUAL
    assert project.topic is None
    assert project.content_format is None
    assert project.posting_frequency is None


def test_channel_connection_fields_have_expected_defaults(fake_db, client):
    project = client.post('/api/v1/projects', json={'name': 'Channel Defaults', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={'channel_title': 'Channel Defaults'},
    ).json()

    assert channel['bot_is_admin'] is False
    assert channel['can_post_messages'] is False
    assert channel['is_connected'] is False
    assert channel['publish_mode'] == PublishMode.MANUAL.value


def test_agent_profile_extended_fields_roundtrip(client):
    project = client.post('/api/v1/projects', json={'name': 'Agent Project', 'language': 'ru'}).json()
    agent = client.post(
        f"/api/v1/projects/{project['id']}/agents",
        json={
            'role': 'writer',
            'name': 'writer-agent',
            'display_name': 'Writer Agent',
            'description': 'Draft author',
            'model': 'gpt-test',
            'system_prompt': 'Write clearly',
            'style_prompt': 'Use concise tone',
            'custom_prompt': 'Focus on crypto',
            'preset_code': 'balanced_5',
            'sort_order': 10,
        },
    )

    assert agent.status_code == 201
    body = agent.json()
    assert body['display_name'] == 'Writer Agent'
    assert body['description'] == 'Draft author'
    assert body['style_prompt'] == 'Use concise tone'
    assert body['custom_prompt'] == 'Focus on crypto'
    assert body['preset_code'] == 'balanced_5'
    assert body['sort_order'] == 10


def test_agent_team_preset_model_exists(fake_db):
    preset = AgentTeamPreset(
        code='balanced_5',
        title='Balanced 5',
        description='Default team',
        agent_count=5,
        roles_json=['strategist', 'researcher', 'writer', 'editor', 'publisher'],
        is_recommended=True,
    )
    fake_db.add(preset)
    fake_db.refresh(preset)

    assert preset.code == 'balanced_5'
    assert preset.agent_count == 5
    assert preset.is_recommended is True
