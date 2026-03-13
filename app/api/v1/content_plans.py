from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.content_plan import ContentPlan
from app.models.project import Project
from app.schemas.content_plan import ContentPlanCreate, ContentPlanRead, ContentPlanUpdate
from app.services.crud import create_entity, get_entity_or_404, update_entity

router = APIRouter(tags=["content-plans"])


@router.post("/projects/{project_id}/content-plans", response_model=ContentPlanRead, status_code=status.HTTP_201_CREATED)
def create_content_plan(project_id: UUID, payload: ContentPlanCreate, db: Session = Depends(get_db)):
    get_entity_or_404(db, Project, project_id, "Project not found")
    return create_entity(db, ContentPlan, payload, project_id=project_id)


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
    return update_entity(db, plan, ContentPlanUpdate(status='regenerated'))
