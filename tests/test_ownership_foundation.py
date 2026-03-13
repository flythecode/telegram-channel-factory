from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


def test_project_read_exposes_ownership_fields(client):
    response = client.post(
        '/api/v1/projects',
        json={
            'name': 'Ownership Project',
            'language': 'ru',
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert 'owner_user_id' in body
    assert 'workspace_id' in body
    assert 'created_by_user_id' in body
    assert body['owner_user_id'] is not None
    assert body['workspace_id'] is not None
    assert body['created_by_user_id'] is not None


def test_user_workspace_project_relationship_foundation(fake_db):
    user = User(
        email='owner@example.com',
        full_name='Owner User',
        telegram_user_id='123456',
    )
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Owner Workspace',
        slug='owner-workspace',
    )
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    project = Project(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Owned Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)

    assert project.owner_user_id == user.id
    assert project.workspace_id == workspace.id
    assert project.created_by_user_id == user.id
    assert fake_db.get(User, user.id) is user
    assert fake_db.get(Workspace, workspace.id) is workspace
    assert fake_db.get(Project, project.id) is project
