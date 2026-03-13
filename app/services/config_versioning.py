from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_config_version import ProjectConfigVersion


TRACKED_PROJECT_FIELDS = [
    'name',
    'description',
    'topic',
    'niche',
    'language',
    'tone_of_voice',
    'goal',
    'content_format',
    'posting_frequency',
    'operation_mode',
    'content_rules',
    'status',
    'workspace_id',
    'owner_user_id',
    'created_by_user_id',
]



def build_project_config_snapshot(project: Project) -> dict:
    snapshot = {}
    for field in TRACKED_PROJECT_FIELDS:
        value = getattr(project, field)
        if hasattr(value, 'value'):
            value = value.value
        elif hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif value is not None and not isinstance(value, (str, int, float, bool, dict, list)):
            value = str(value)
        snapshot[field] = value
    return snapshot



def _next_version_number(db: Session, project_id) -> int:
    versions = [item.version for item in db.query(ProjectConfigVersion).all() if item.project_id == project_id]
    return (max(versions) if versions else 0) + 1



def create_project_config_version(db: Session, project: Project, created_by_user_id=None, change_summary: str | None = None):
    version = ProjectConfigVersion(
        project_id=project.id,
        created_by_user_id=created_by_user_id,
        version=_next_version_number(db, project.id),
        snapshot_json=build_project_config_snapshot(project),
        change_summary=change_summary,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version



def list_project_config_versions(db: Session, project_id):
    versions = [item for item in db.query(ProjectConfigVersion).all() if item.project_id == project_id]
    versions.sort(key=lambda item: item.version)
    return versions
