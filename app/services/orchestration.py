from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.models.content_task import ContentTask
from app.services.agent_service import get_default_writer_agent


@dataclass(slots=True)
class OrchestrationStageResult:
    role: str
    agent_name: str
    content: str


@dataclass(slots=True)
class OrchestrationResult:
    task_id: str
    preset_code: str | None
    applied_agent_ids: list[str]
    stages: list[OrchestrationStageResult]
    final_text: str
    final_agent_name: str | None



def get_active_agents_for_task(db: Session, task: ContentTask) -> list[AgentProfile]:
    agents = [agent for agent in db.query(AgentProfile).all() if agent.project_id == task.project_id and agent.is_enabled]
    agents.sort(key=lambda item: (item.sort_order, item.priority, item.created_at))
    return agents



def _task_seed_text(task: ContentTask) -> str:
    parts = [task.title]
    if task.topic:
        parts.append(f"Topic: {task.topic}")
    if task.brief:
        parts.append(f"Brief: {task.brief}")
    if task.angle:
        parts.append(f"Angle: {task.angle}")
    return "\n".join(parts)



def run_linear_orchestration(db: Session, task: ContentTask) -> OrchestrationResult:
    agents = get_active_agents_for_task(db, task)
    if not agents:
        fallback = get_default_writer_agent(db, task.project_id)
        if fallback is not None:
            agents = [fallback]

    preset_code = agents[0].preset_code if agents else None
    current_text = _task_seed_text(task)
    applied_agent_ids = [str(agent.id) for agent in agents]
    stages: list[OrchestrationStageResult] = []

    for agent in agents:
        role = agent.role.value if hasattr(agent.role, 'value') else str(agent.role)
        agent_name = agent.display_name or agent.name
        stage_text = f"[{role}] {agent_name}\n{current_text}"
        if agent.custom_prompt:
            stage_text += f"\nPrompt: {agent.custom_prompt}"
        stages.append(
            OrchestrationStageResult(
                role=role,
                agent_name=agent_name,
                content=stage_text,
            )
        )
        current_text = stage_text

    final_agent_name = stages[-1].agent_name if stages else None
    return OrchestrationResult(
        task_id=str(task.id),
        preset_code=preset_code,
        applied_agent_ids=applied_agent_ids,
        stages=stages,
        final_text=current_text,
        final_agent_name=final_agent_name,
    )
