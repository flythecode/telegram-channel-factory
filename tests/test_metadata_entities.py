from app.models.audit_event import AuditEvent
from app.models.project import Project
from app.models.project_config_version import ProjectConfigVersion
from app.models.prompt_template import PromptTemplate
from app.models.user import User


def test_prompt_template_model_exists(fake_db):
    template = PromptTemplate(
        title='Writer Default',
        scope='preset',
        role_code='writer',
        system_prompt='Write clearly',
        style_prompt='Use concise tone',
    )
    fake_db.add(template)
    fake_db.refresh(template)

    assert template.title == 'Writer Default'
    assert template.scope == 'preset'
    assert template.role_code == 'writer'


def test_project_config_version_model_exists(fake_db):
    user = User(email='config@example.com')
    fake_db.add(user)
    fake_db.refresh(user)

    project = Project(name='Config Project', language='ru', created_by_user_id=user.id)
    fake_db.add(project)
    fake_db.refresh(project)

    version = ProjectConfigVersion(
        project_id=project.id,
        created_by_user_id=user.id,
        version=1,
        snapshot_json={'operation_mode': 'manual'},
        change_summary='Initial config',
    )
    fake_db.add(version)
    fake_db.refresh(version)

    assert version.project_id == project.id
    assert version.version == 1
    assert version.snapshot_json['operation_mode'] == 'manual'


def test_audit_event_model_exists(fake_db):
    user = User(email='audit@example.com')
    fake_db.add(user)
    fake_db.refresh(user)

    event = AuditEvent(
        user_id=user.id,
        entity_type='project',
        action='update_settings',
        before_json={'mode': 'manual'},
        after_json={'mode': 'semi_auto'},
    )
    fake_db.add(event)
    fake_db.refresh(event)

    assert event.entity_type == 'project'
    assert event.action == 'update_settings'
    assert event.after_json['mode'] == 'semi_auto'
