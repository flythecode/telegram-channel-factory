from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.schemas.draft import DraftCreate, DraftRead, DraftRewriteRequest, DraftUpdate
from app.services.audit_service import create_audit_event, snapshot_entity
from app.services.crud import get_entity_or_404, update_entity
from app.services.generation_queue import enqueue_and_process_generation_job
from app.services.workflow import approve_draft, mark_task_as_drafted, reject_draft
from app.utils.enums import DraftStatus, GenerationJobOperation

router = APIRouter(tags=["drafts"])


@router.post("/tasks/{task_id}/drafts", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
def create_draft(task_id: UUID, payload: DraftCreate, db: Session = Depends(get_db)):
    task = get_entity_or_404(db, ContentTask, task_id, "Task not found")
    try:
        result = enqueue_and_process_generation_job(
            db,
            operation=GenerationJobOperation.CREATE_DRAFT,
            project_id=task.project_id,
            content_task_id=task.id,
            payload=payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    draft = result.draft
    assert draft is not None
    create_audit_event(
        db,
        project_id=task.project_id,
        entity_type='draft',
        entity_id=draft.id,
        action='create_draft',
        before_json=None,
        after_json=snapshot_entity(draft),
    )
    return draft


@router.get("/tasks/{task_id}/drafts", response_model=list[DraftRead])
def list_drafts(task_id: UUID, db: Session = Depends(get_db)):
    return db.query(Draft).filter(Draft.content_task_id == task_id).all()


@router.patch("/drafts/{draft_id}", response_model=DraftRead)
def update_draft(draft_id: UUID, payload: DraftUpdate, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, "Draft not found")
    update_payload = payload
    if payload.text is not None and payload.status is None:
        update_payload = DraftUpdate(**payload.model_dump(exclude_unset=True), status=DraftStatus.EDITED)
    return update_entity(db, draft, update_payload)


@router.post("/drafts/{draft_id}/approve", response_model=DraftRead)
def approve_draft_endpoint(draft_id: UUID, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, "Draft not found")

    task = draft.content_task
    before = snapshot_entity(draft)
    approve_draft(task, draft)
    db.add(draft)
    db.add(task)
    db.commit()
    db.refresh(draft)
    create_audit_event(
        db,
        project_id=task.project_id,
        entity_type='draft',
        entity_id=draft.id,
        action='approve_draft',
        before_json=before,
        after_json=snapshot_entity(draft),
    )
    return draft


@router.post("/drafts/{draft_id}/reject", response_model=DraftRead)
def reject_draft_endpoint(draft_id: UUID, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, "Draft not found")

    task = draft.content_task
    before = snapshot_entity(draft)
    reject_draft(task, draft)
    db.add(draft)
    db.add(task)
    db.commit()
    db.refresh(draft)
    create_audit_event(
        db,
        project_id=task.project_id,
        entity_type='draft',
        entity_id=draft.id,
        action='reject_draft',
        before_json=before,
        after_json=snapshot_entity(draft),
    )
    return draft


@router.post('/drafts/{draft_id}/regenerate', response_model=DraftRead)
def regenerate_draft(draft_id: UUID, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, 'Draft not found')
    before = snapshot_entity(draft)
    try:
        result = enqueue_and_process_generation_job(
            db,
            operation=GenerationJobOperation.REGENERATE_DRAFT,
            project_id=draft.content_task.project_id,
            content_task_id=draft.content_task_id,
            draft_id=draft.id,
            payload={},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    draft = result.draft
    assert draft is not None
    create_audit_event(
        db,
        project_id=draft.content_task.project_id,
        entity_type='draft',
        entity_id=draft.id,
        action='regenerate_draft',
        before_json=before,
        after_json=snapshot_entity(draft),
    )
    return draft


@router.post('/drafts/{draft_id}/rewrite', response_model=DraftRead)
def rewrite_draft(draft_id: UUID, payload: DraftRewriteRequest, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, 'Draft not found')
    before = snapshot_entity(draft)
    try:
        result = enqueue_and_process_generation_job(
            db,
            operation=GenerationJobOperation.REWRITE_DRAFT,
            project_id=draft.content_task.project_id,
            content_task_id=draft.content_task_id,
            draft_id=draft.id,
            payload={'rewrite_prompt': payload.rewrite_prompt},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    draft = result.draft
    assert draft is not None
    create_audit_event(
        db,
        project_id=draft.content_task.project_id,
        entity_type='draft',
        entity_id=draft.id,
        action='rewrite_draft',
        before_json=before,
        after_json=snapshot_entity(draft),
        notes=f'rewrite_prompt={payload.rewrite_prompt.strip()[:500]}',
    )
    return draft
