from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.publication import Publication
from app.schemas.publication import PublicationCreate, PublicationRead, PublicationUpdate
from app.services.audit_service import create_audit_event, snapshot_entity
from app.services.crud import get_entity_or_404
from app.services.publish_service import queue_publication, update_publication_state

router = APIRouter(tags=["publications"])


@router.post("/drafts/{draft_id}/publications", response_model=PublicationRead, status_code=status.HTTP_201_CREATED)
def create_publication(draft_id: UUID, payload: PublicationCreate, db: Session = Depends(get_db)):
    try:
        return queue_publication(db, draft_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/drafts/{draft_id}/publications", response_model=list[PublicationRead])
def list_publications_for_draft(draft_id: UUID, db: Session = Depends(get_db)):
    return db.query(Publication).filter(Publication.draft_id == draft_id).all()


@router.get("/publications/{publication_id}", response_model=PublicationRead)
def get_publication(publication_id: UUID, db: Session = Depends(get_db)):
    return get_entity_or_404(db, Publication, publication_id, "Publication not found")


@router.patch("/publications/{publication_id}", response_model=PublicationRead)
def update_publication(publication_id: UUID, payload: PublicationUpdate, db: Session = Depends(get_db)):
    publication = get_entity_or_404(db, Publication, publication_id, 'Publication not found')
    before = snapshot_entity(publication)
    updated = update_publication_state(db, publication_id, payload)
    create_audit_event(db, project_id=updated.draft.content_task.project_id, entity_type='publication', entity_id=updated.id, action='update_publication', before_json=before, after_json=snapshot_entity(updated))
    return updated


@router.post('/publications/{publication_id}/publish-now', response_model=PublicationRead)
def publish_now(publication_id: UUID, db: Session = Depends(get_db)):
    publication = get_entity_or_404(db, Publication, publication_id, 'Publication not found')
    before = snapshot_entity(publication)
    updated = update_publication_state(db, publication_id, PublicationUpdate(status='sending', scheduled_for=None))
    create_audit_event(db, project_id=updated.draft.content_task.project_id, entity_type='publication', entity_id=updated.id, action='publish_now', before_json=before, after_json=snapshot_entity(updated))
    return updated


@router.post('/publications/{publication_id}/cancel', response_model=PublicationRead)
def cancel_publication(publication_id: UUID, db: Session = Depends(get_db)):
    publication = get_entity_or_404(db, Publication, publication_id, 'Publication not found')
    before = snapshot_entity(publication)
    updated = update_publication_state(db, publication_id, PublicationUpdate(status='canceled'))
    create_audit_event(db, project_id=updated.draft.content_task.project_id, entity_type='publication', entity_id=updated.id, action='cancel_publication', before_json=before, after_json=snapshot_entity(updated))
    return updated
