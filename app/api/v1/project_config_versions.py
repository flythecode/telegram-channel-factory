from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.schemas.project_config_version import ProjectConfigVersionRead
from app.services.crud import get_entity_or_404
from app.services.identity import TelegramIdentity, get_or_create_current_user, get_telegram_identity
from app.services.config_versioning import list_project_config_versions

router = APIRouter(tags=['project-config-versions'])


@router.get('/projects/{project_id}/config-versions', response_model=list[ProjectConfigVersionRead])
def get_project_config_versions(
    project_id: UUID,
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    project = get_entity_or_404(db, Project, project_id, 'Project not found')
    if project.owner_user_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail='Project not found')
    return list_project_config_versions(db, project_id)
