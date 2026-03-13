from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.schemas.draft import DraftCreate, DraftRead, DraftUpdate
from app.services.agent_service import get_default_writer_agent
from app.services.crud import get_entity_or_404, update_entity
from app.services.orchestration import run_linear_orchestration
from app.services.workflow import approve_draft, mark_task_as_drafted, reject_draft
from app.utils.enums import DraftStatus

router = APIRouter(tags=["drafts"])


@router.post("/tasks/{task_id}/drafts", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
def create_draft(task_id: UUID, payload: DraftCreate, db: Session = Depends(get_db)):
    task = get_entity_or_404(db, ContentTask, task_id, "Task not found")
    data = payload.model_dump()
    orchestration = run_linear_orchestration(db, task)
    if not data.get('created_by_agent'):
        agent = get_default_writer_agent(db, task.project_id)
        if agent is not None:
            data['created_by_agent'] = agent.display_name or agent.name
        elif orchestration.final_agent_name is not None:
            data['created_by_agent'] = orchestration.final_agent_name
    data['generation_metadata'] = {
        'preset_code': orchestration.preset_code,
        'applied_agent_ids': orchestration.applied_agent_ids,
        'stage_roles': [stage.role for stage in orchestration.stages],
        'final_agent_name': orchestration.final_agent_name,
    }
    draft = Draft(content_task_id=task_id, **data)
    mark_task_as_drafted(task, draft)
    db.add(draft)
    db.add(task)
    db.commit()
    db.refresh(draft)
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
    approve_draft(task, draft)
    db.add(draft)
    db.add(task)
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/reject", response_model=DraftRead)
def reject_draft_endpoint(draft_id: UUID, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, "Draft not found")

    task = draft.content_task
    reject_draft(task, draft)
    db.add(draft)
    db.add(task)
    db.commit()
    db.refresh(draft)
    return draft


@router.post('/drafts/{draft_id}/regenerate', response_model=DraftRead)
def regenerate_draft(draft_id: UUID, db: Session = Depends(get_db)):
    draft = get_entity_or_404(db, Draft, draft_id, 'Draft not found')
    updated = DraftUpdate(text=draft.text + '\n\n[Regenerated]', status=DraftStatus.EDITED)
    return update_entity(db, draft, updated)
