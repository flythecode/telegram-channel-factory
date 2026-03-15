from sqlalchemy.orm import Session

from app.models.client_account import ClientAccount
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.audit_service import create_audit_event, snapshot_entity
from app.services.config_versioning import create_project_config_version
from app.services.crud import update_entity



def list_projects_for_owner(db: Session, owner_user_id):
    if hasattr(db, 'storage'):
        return [
            project
            for project in db.query(Project).all()
            if project.owner_user_id == owner_user_id
        ]
    return db.query(Project).filter(Project.owner_user_id == owner_user_id).all()



def create_project_for_owner(db: Session, payload: ProjectCreate, owner: User, workspace: Workspace, client_account: ClientAccount | None = None) -> Project:
    project = Project(
        **payload.model_dump(),
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        workspace_id=workspace.id,
        client_account_id=getattr(client_account, "id", None),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    create_project_config_version(db, project, created_by_user_id=owner.id, change_summary='Initial project config')
    create_audit_event(
        db,
        project_id=project.id,
        user_id=owner.id,
        entity_type='project',
        entity_id=project.id,
        action='create_project',
        before_json=None,
        after_json=snapshot_entity(project),
    )
    return project



def update_project_settings(db: Session, project: Project, payload: ProjectUpdate, created_by_user_id=None) -> Project:
    before = snapshot_entity(project)
    updated = update_entity(db, project, payload)
    if payload.model_dump(exclude_unset=True):
        create_project_config_version(
            db,
            updated,
            created_by_user_id=created_by_user_id,
            change_summary='Project settings updated',
        )
        create_audit_event(
            db,
            project_id=updated.id,
            user_id=created_by_user_id,
            entity_type='project',
            entity_id=updated.id,
            action='update_project_settings',
            before_json=before,
            after_json=snapshot_entity(updated),
        )
    return updated
