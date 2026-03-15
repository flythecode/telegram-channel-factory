from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.models.project import Project
from app.models.project_config_version import ProjectConfigVersion
from app.models.prompt_template import PromptTemplate


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



def _normalize_value(value):
    if hasattr(value, 'value'):
        return value.value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if value is not None and not isinstance(value, (str, int, float, bool, dict, list)):
        return str(value)
    return value


AGENT_TRACKED_FIELDS = [
    'id',
    'channel_id',
    'preset_code',
    'role',
    'name',
    'display_name',
    'description',
    'model',
    'system_prompt',
    'style_prompt',
    'custom_prompt',
    'config',
    'is_enabled',
    'priority',
    'sort_order',
]


PROMPT_TEMPLATE_TRACKED_FIELDS = [
    'id',
    'title',
    'scope',
    'role_code',
    'system_prompt',
    'style_prompt',
    'notes',
    'is_active',
]


def _serialize_model(item, fields: list[str]) -> dict:
    return {field: _normalize_value(getattr(item, field, None)) for field in fields}


def _build_agent_snapshot(db: Session, project_id) -> list[dict]:
    agents = [item for item in db.query(AgentProfile).all() if item.project_id == project_id]
    agents.sort(key=lambda item: (getattr(item, 'sort_order', 0), getattr(item, 'priority', 0), str(getattr(item, 'id', ''))))
    return [_serialize_model(agent, AGENT_TRACKED_FIELDS) for agent in agents]


def _build_prompt_template_snapshot(db: Session, project_id) -> list[dict]:
    templates = [
        item for item in db.query(PromptTemplate).all()
        if item.project_id in {None, project_id}
    ]
    templates.sort(key=lambda item: (item.scope or '', item.role_code or '', item.title or '', str(getattr(item, 'id', ''))))
    return [_serialize_model(template, PROMPT_TEMPLATE_TRACKED_FIELDS) for template in templates]


def build_project_config_snapshot(db: Session, project: Project) -> dict:
    project_snapshot = {}
    for field in TRACKED_PROJECT_FIELDS:
        project_snapshot[field] = _normalize_value(getattr(project, field))
    return {
        'project': project_snapshot,
        'agent_team': _build_agent_snapshot(db, project.id),
        'prompt_templates': _build_prompt_template_snapshot(db, project.id),
    }



def _next_version_number(db: Session, project_id) -> int:
    versions = [item.version for item in db.query(ProjectConfigVersion).all() if item.project_id == project_id]
    return (max(versions) if versions else 0) + 1



def create_project_config_version(db: Session, project: Project, created_by_user_id=None, change_summary: str | None = None):
    version = ProjectConfigVersion(
        project_id=project.id,
        created_by_user_id=created_by_user_id,
        version=_next_version_number(db, project.id),
        snapshot_json=build_project_config_snapshot(db, project),
        change_summary=change_summary,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version



def create_project_config_version_for_project_id(
    db: Session,
    project_id,
    *,
    created_by_user_id=None,
    change_summary: str | None = None,
):
    project = next((item for item in db.query(Project).all() if item.id == project_id), None)
    if project is None:
        project = db.get(Project, project_id)
    if project is None:
        raise ValueError('Project not found for config versioning')
    return create_project_config_version(
        db,
        project,
        created_by_user_id=created_by_user_id,
        change_summary=change_summary,
    )


def list_project_config_versions(db: Session, project_id):
    versions = [item for item in db.query(ProjectConfigVersion).all() if item.project_id == project_id]
    versions.sort(key=lambda item: item.version)
    return versions
