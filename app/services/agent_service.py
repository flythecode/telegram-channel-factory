from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.models.agent_team_preset import AgentTeamPreset
from app.models.project import Project
from app.services.crud import get_entity_or_404
from app.utils.enums import AgentRole


ROLE_TO_MODEL = {
    'strategist': 'strategist-default',
    'researcher': 'researcher-default',
    'writer': 'writer-default',
    'editor': 'editor-default',
    'fact_checker': 'fact-checker-default',
    'publisher': 'publisher-default',
}



def list_presets(db: Session):
    return db.query(AgentTeamPreset).all()



def ensure_default_presets(db: Session):
    existing = {preset.code for preset in db.query(AgentTeamPreset).all()}
    defaults = [
        ('starter_3', 'Starter 3', 3, ['strategist', 'researcher', 'writer'], False),
        ('balanced_5', 'Balanced 5', 5, ['strategist', 'researcher', 'writer', 'editor', 'publisher'], True),
        ('editorial_7', 'Editorial 7', 7, ['strategist', 'researcher', 'writer', 'editor', 'fact_checker', 'publisher', 'editor'], False),
    ]
    created = []
    for code, title, count, roles, recommended in defaults:
        if code in existing:
            continue
        preset = AgentTeamPreset(
            code=code,
            title=title,
            description=title,
            agent_count=count,
            roles_json=roles,
            is_recommended=recommended,
        )
        db.add(preset)
        created.append(preset)
    db.commit()
    for preset in created:
        db.refresh(preset)
    return db.query(AgentTeamPreset).all()



def apply_preset_to_project(db: Session, project_id, preset_code: str):
    project = get_entity_or_404(db, Project, project_id, 'Project not found')
    preset = next((p for p in db.query(AgentTeamPreset).all() if p.code == preset_code), None)
    if preset is None:
        raise ValueError('Preset not found')

    for agent in list(db.query(AgentProfile).all()):
        if agent.project_id == project.id:
            agent.is_enabled = False
            db.add(agent)

    roles = preset.roles_json if isinstance(preset.roles_json, list) else preset.roles_json.get('roles', [])
    created = []
    for index, role_name in enumerate(roles, start=1):
        agent = AgentProfile(
            project_id=project.id,
            preset_code=preset.code,
            role=AgentRole(role_name),
            name=f'{role_name}-{index}',
            display_name=role_name.replace('_', ' ').title(),
            description=f'{role_name} agent from preset {preset.code}',
            model=ROLE_TO_MODEL.get(role_name, 'generic-default'),
            sort_order=index,
            priority=index * 10,
        )
        db.add(agent)
        created.append(agent)
    db.commit()
    for agent in created:
        db.refresh(agent)
    return created



def get_default_writer_agent(db: Session, project_id):
    agents = [agent for agent in db.query(AgentProfile).all() if agent.project_id == project_id and agent.is_enabled]
    agents.sort(key=lambda item: (item.sort_order, item.priority))
    for agent in agents:
        if agent.role == AgentRole.WRITER:
            return agent
    return agents[0] if agents else None
