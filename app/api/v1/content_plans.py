from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.content_plan import ContentPlan
from app.models.project import Project
from app.schemas.content_plan import ContentPlanCreate, ContentPlanRead, ContentPlanUpdate
from app.services.crud import create_entity, get_entity_or_404, update_entity
from app.services.generation_queue import enqueue_and_process_generation_job
from app.utils.enums import GenerationJobOperation

router = APIRouter(tags=["content-plans"])


@router.post("/projects/{project_id}/content-plans", response_model=ContentPlanRead, status_code=status.HTTP_201_CREATED)
def create_content_plan(project_id: UUID, payload: ContentPlanCreate, db: Session = Depends(get_db)):
    project = get_entity_or_404(db, Project, project_id, "Project not found")
    plan = create_entity(db, ContentPlan, payload, project_id=project_id)
    try:
        result = enqueue_and_process_generation_job(
            db,
            operation=GenerationJobOperation.GENERATE_CONTENT_PLAN,
            project_id=project.id,
            content_plan_id=plan.id,
            payload={'status': payload.status},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    generated = result.content_plan
    assert generated is not None
    return generated


@router.get("/projects/{project_id}/content-plans", response_model=list[ContentPlanRead])
def list_content_plans(project_id: UUID, db: Session = Depends(get_db)):
    return db.query(ContentPlan).filter(ContentPlan.project_id == project_id).all()


@router.patch("/content-plans/{plan_id}", response_model=ContentPlanRead)
def update_content_plan(plan_id: UUID, payload: ContentPlanUpdate, db: Session = Depends(get_db)):
    plan = get_entity_or_404(db, ContentPlan, plan_id, "Content plan not found")
    return update_entity(db, plan, payload)


@router.post('/content-plans/{plan_id}/regenerate', response_model=ContentPlanRead)
def regenerate_content_plan(plan_id: UUID, db: Session = Depends(get_db)):
    plan = get_entity_or_404(db, ContentPlan, plan_id, 'Content plan not found')
    project = get_entity_or_404(db, Project, plan.project_id, 'Project not found')
    try:
        result = enqueue_and_process_generation_job(
            db,
            operation=GenerationJobOperation.GENERATE_CONTENT_PLAN,
            project_id=project.id,
            content_plan_id=plan.id,
            payload={'status': 'regenerated'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    regenerated = result.content_plan
    assert regenerated is not None
    return regenerated
