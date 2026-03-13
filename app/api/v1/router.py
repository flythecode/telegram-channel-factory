from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.channels import router as channels_router
from app.api.v1.content_plans import router as content_plans_router
from app.api.v1.drafts import router as drafts_router
from app.api.v1.projects import router as projects_router
from app.api.v1.publications import router as publications_router
from app.api.v1.audit_events import router as audit_events_router
from app.api.v1.project_config_versions import router as project_config_versions_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(project_config_versions_router)
api_router.include_router(audit_events_router)
api_router.include_router(projects_router)
api_router.include_router(channels_router)
api_router.include_router(agents_router)
api_router.include_router(content_plans_router)
api_router.include_router(tasks_router)
api_router.include_router(drafts_router)
api_router.include_router(publications_router)
