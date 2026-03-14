from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.schemas.audit_event import AuditEventRead
from app.services.audit_service import list_audit_events_for_project
from app.services.crud import get_entity_or_404
from app.services.identity import TelegramIdentity, get_or_create_current_user, get_telegram_identity

router = APIRouter(tags=['audit-events'])


@router.get('/projects/{project_id}/audit-events', response_model=list[AuditEventRead])
def get_project_audit_events(
    project_id: UUID,
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    project = get_entity_or_404(db, Project, project_id, 'Project not found')
    if project.owner_user_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail='Project not found')
    return list_audit_events_for_project(db, project_id, action=action, entity_type=entity_type, limit=limit)
