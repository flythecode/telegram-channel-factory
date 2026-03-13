from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.content_task import ContentTask
from app.models.project import Project
from app.schemas.task import ContentTaskCreate, ContentTaskRead, ContentTaskUpdate
from app.services.crud import create_entity, get_entity_or_404, update_entity

router = APIRouter(tags=["tasks"])


@router.post("/projects/{project_id}/tasks", response_model=ContentTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(project_id: UUID, payload: ContentTaskCreate, db: Session = Depends(get_db)):
    get_entity_or_404(db, Project, project_id, "Project not found")
    return create_entity(db, ContentTask, payload, project_id=project_id)


@router.get("/projects/{project_id}/tasks", response_model=list[ContentTaskRead])
def list_tasks(project_id: UUID, db: Session = Depends(get_db)):
    return db.query(ContentTask).filter(ContentTask.project_id == project_id).all()


@router.get("/tasks/{task_id}", response_model=ContentTaskRead)
def get_task(task_id: UUID, db: Session = Depends(get_db)):
    return get_entity_or_404(db, ContentTask, task_id, "Task not found")


@router.patch("/tasks/{task_id}", response_model=ContentTaskRead)
def update_task(task_id: UUID, payload: ContentTaskUpdate, db: Session = Depends(get_db)):
    task = get_entity_or_404(db, ContentTask, task_id, "Task not found")
    return update_entity(db, task, payload)


@router.get('/content-plans/{plan_id}/tasks', response_model=list[ContentTaskRead])
def list_tasks_for_content_plan(plan_id: UUID, db: Session = Depends(get_db)):
    return [task for task in db.query(ContentTask).all() if str(task.content_plan_id) == str(plan_id)]
