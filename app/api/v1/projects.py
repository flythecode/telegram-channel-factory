from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.schemas.operation_mode import OperationModeRead, OperationModeUpdate
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.api.v1.project_config_versions import router as project_config_versions_router
from app.services.crud import get_entity_or_404
from app.services.identity import (
    TelegramIdentity,
    get_or_create_current_user,
    get_or_create_workspace_for_user,
    get_telegram_identity,
)
from app.services.project_service import (
    create_project_for_owner,
    list_projects_for_owner,
    update_project_settings,
)

router = APIRouter(prefix="/projects", tags=["projects"])
router.include_router(project_config_versions_router)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    workspace = get_or_create_workspace_for_user(db, user, identity)
    return create_project_for_owner(db, payload, user, workspace)


@router.post("/wizard", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project_from_wizard(
    payload: ProjectCreate,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    workspace = get_or_create_workspace_for_user(db, user, identity)
    return create_project_for_owner(db, payload, user, workspace)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    return list_projects_for_owner(db, user.id)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: UUID,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    project = get_entity_or_404(db, Project, project_id, "Project not found")
    if project.owner_user_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    project = get_entity_or_404(db, Project, project_id, "Project not found")
    if project.owner_user_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Project not found")
    return update_project_settings(db, project, payload, created_by_user_id=user.id)


@router.get('/{project_id}/operation-mode', response_model=OperationModeRead)
def get_project_operation_mode(
    project_id: UUID,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    project = get_entity_or_404(db, Project, project_id, 'Project not found')
    if project.owner_user_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail='Project not found')
    return {'operation_mode': project.operation_mode}


@router.patch('/{project_id}/operation-mode', response_model=OperationModeRead)
def update_project_operation_mode(
    project_id: UUID,
    payload: OperationModeUpdate,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    project = get_entity_or_404(db, Project, project_id, 'Project not found')
    if project.owner_user_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail='Project not found')
    update_project_settings(db, project, ProjectUpdate(operation_mode=payload.operation_mode), created_by_user_id=user.id)
    return {'operation_mode': project.operation_mode}
