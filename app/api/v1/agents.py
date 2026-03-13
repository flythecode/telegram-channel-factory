from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.agent_profile import AgentProfile
from app.models.project import Project
from app.schemas.agent import AgentProfileCreate, AgentProfileRead, AgentProfileUpdate
from app.schemas.agent_team_preset import AgentTeamPresetRead
from app.services.agent_service import apply_preset_to_project, ensure_default_presets, list_presets
from app.services.audit_service import create_audit_event, snapshot_entity
from app.services.crud import create_entity, get_entity_or_404, update_entity

router = APIRouter(tags=["agents"])


@router.post("/projects/{project_id}/agents", response_model=AgentProfileRead, status_code=status.HTTP_201_CREATED)
def create_agent(project_id: UUID, payload: AgentProfileCreate, db: Session = Depends(get_db)):
    get_entity_or_404(db, Project, project_id, "Project not found")
    return create_entity(db, AgentProfile, payload, project_id=project_id)


@router.get("/projects/{project_id}/agents", response_model=list[AgentProfileRead])
def list_agents(project_id: UUID, db: Session = Depends(get_db)):
    return db.query(AgentProfile).filter(AgentProfile.project_id == project_id).all()


@router.patch("/agents/{agent_id}", response_model=AgentProfileRead)
def update_agent(agent_id: UUID, payload: AgentProfileUpdate, db: Session = Depends(get_db)):
    agent = get_entity_or_404(db, AgentProfile, agent_id, "Agent not found")
    before = snapshot_entity(agent)
    updated = update_entity(db, agent, payload)
    create_audit_event(
        db,
        project_id=updated.project_id,
        entity_type='agent',
        entity_id=updated.id,
        action='update_agent',
        before_json=before,
        after_json=snapshot_entity(updated),
    )
    return updated


@router.get('/agent-team-presets', response_model=list[AgentTeamPresetRead])
def get_agent_team_presets(db: Session = Depends(get_db)):
    ensure_default_presets(db)
    return list_presets(db)


@router.post('/projects/{project_id}/agent-team-presets/{preset_code}/apply', response_model=list[AgentProfileRead])
def apply_agent_team_preset(project_id: UUID, preset_code: str, db: Session = Depends(get_db)):
    try:
        ensure_default_presets(db)
        return apply_preset_to_project(db, project_id, preset_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/agents/{agent_id}/enable', response_model=AgentProfileRead)
def enable_agent(agent_id: UUID, db: Session = Depends(get_db)):
    agent = get_entity_or_404(db, AgentProfile, agent_id, 'Agent not found')
    before = snapshot_entity(agent)
    updated = update_entity(db, agent, AgentProfileUpdate(is_enabled=True))
    create_audit_event(db, project_id=updated.project_id, entity_type='agent', entity_id=updated.id, action='enable_agent', before_json=before, after_json=snapshot_entity(updated))
    return updated


@router.post('/agents/{agent_id}/disable', response_model=AgentProfileRead)
def disable_agent(agent_id: UUID, db: Session = Depends(get_db)):
    agent = get_entity_or_404(db, AgentProfile, agent_id, 'Agent not found')
    before = snapshot_entity(agent)
    updated = update_entity(db, agent, AgentProfileUpdate(is_enabled=False))
    create_audit_event(db, project_id=updated.project_id, entity_type='agent', entity_id=updated.id, action='disable_agent', before_json=before, after_json=snapshot_entity(updated))
    return updated


@router.patch('/agents/{agent_id}/prompts', response_model=AgentProfileRead)
def update_agent_prompts(agent_id: UUID, payload: AgentProfileUpdate, db: Session = Depends(get_db)):
    agent = get_entity_or_404(db, AgentProfile, agent_id, 'Agent not found')
    before = snapshot_entity(agent)
    updated = update_entity(db, agent, AgentProfileUpdate(
        system_prompt=payload.system_prompt,
        style_prompt=payload.style_prompt,
        custom_prompt=payload.custom_prompt,
        config=payload.config,
    ))
    create_audit_event(db, project_id=updated.project_id, entity_type='agent', entity_id=updated.id, action='update_agent_prompts', before_json=before, after_json=snapshot_entity(updated))
    return updated
