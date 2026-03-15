from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.content_task import ContentTask
from app.core.config import settings
from app.services.execution_context import AgentExecutionProfile, ProjectExecutionContext, resolve_project_execution_context
from app.services.llm_provider import LLMGenerationRequest, LLMGenerationResult, generate_with_failover, get_llm_adapter


@dataclass(slots=True)
class OrchestrationStageResult:
    role: str
    agent_name: str
    content: str
    generation: LLMGenerationResult | None = None


@dataclass(slots=True)
class OrchestrationResult:
    task_id: str
    preset_code: str | None
    applied_agent_ids: list[str]
    stages: list[OrchestrationStageResult]
    final_text: str
    final_agent_name: str | None
    generation: LLMGenerationResult
    execution_context: ProjectExecutionContext


ROLE_INSTRUCTIONS = {
    'strategist': 'Act as the content strategist. Define the angle, hook, audience promise, and structure for the post.',
    'researcher': 'Act as the researcher. Add supporting facts, examples, and useful context without inventing client-external knowledge.',
    'writer': 'Act as the writer. Turn the approved context into a strong publication-ready Telegram post draft.',
    'editor': 'Act as the editor. Tighten clarity, flow, readability, and Telegram formatting while preserving facts and intent.',
    'fact_checker': 'Act as the fact checker. Flag weak claims, keep only defensible statements, and strengthen precision.',
    'publisher': 'Act as the publishing editor. Produce the final polished Telegram-ready version with strong readability.',
}

SINGLE_PASS_ROLE_PRIORITY = {
    'publisher': 0,
    'writer': 1,
    'editor': 2,
    'strategist': 3,
    'researcher': 4,
    'fact_checker': 5,
}


def get_active_agents_for_task(db: Session, task: ContentTask) -> list[AgentExecutionProfile]:
    return resolve_project_execution_context(db, task=task).agents



def _select_single_pass_agent(agents: list[AgentExecutionProfile]) -> AgentExecutionProfile:
    return sorted(
        agents,
        key=lambda item: (
            SINGLE_PASS_ROLE_PRIORITY.get(item.role, 99),
            item.sort_order,
            item.priority,
            item.name,
        ),
    )[0]



def _build_final_generation_prompt(
    task: ContentTask,
    execution_context: ProjectExecutionContext,
    stages: list[OrchestrationStageResult],
) -> tuple[str, str]:
    project_settings = execution_context.project_settings
    system_parts = [
        'You generate production-ready Telegram channel drafts.',
        'Return only the final draft text without chain-of-thought or meta commentary.',
        f"Tenant runtime scope: {execution_context.runtime_scope}={execution_context.project_id}.",
        f"Project language: {project_settings.get('language') or 'ru'}.",
        'Never use prompts, settings, facts, or channel identity from any other client, project, or channel.',
    ]
    if project_settings.get('tone_of_voice'):
        system_parts.append(f"Tone of voice: {project_settings['tone_of_voice']}")
    if project_settings.get('goal'):
        system_parts.append(f"Project goal: {project_settings['goal']}")
    if project_settings.get('content_rules'):
        system_parts.append(f"Content rules: {project_settings['content_rules']}")
    if stages:
        system_parts.append('Follow the active multi-agent roles in order when composing the final draft.')
        system_parts.append('Roles: ' + ', '.join(f'{stage.role}:{stage.agent_name}' for stage in stages))

    user_parts = [
        'Task context:',
        _task_seed_text(task),
        f"Execution fingerprint: {execution_context.settings_fingerprint}",
    ]
    if stages:
        user_parts.append('Agent stage guidance:')
        user_parts.extend(stage.content for stage in stages)
    user_parts.append('Write a concise, publication-ready Telegram post draft in Russian.')
    return '\n'.join(system_parts), '\n\n'.join(part for part in user_parts if part)



def _resolve_stage_model(agent: AgentExecutionProfile) -> str | None:
    model = (agent.model or '').strip()
    if not model:
        return settings.llm_model_default
    if model.endswith('-default'):
        return settings.llm_model_default
    return model



def _build_stage_request(
    *,
    task: ContentTask,
    execution_context: ProjectExecutionContext,
    agent: AgentExecutionProfile,
    previous_stages: list[OrchestrationStageResult],
    current_text: str,
) -> LLMGenerationRequest:
    project_settings = execution_context.project_settings
    system_parts = [
        f"You are the {agent.role} stage inside a tenant-isolated Telegram content pipeline.",
        ROLE_INSTRUCTIONS.get(agent.role, 'Produce the best next-stage output for the active role.'),
        f"Tenant runtime scope: {execution_context.runtime_scope}={execution_context.project_id}.",
        f"Execution fingerprint: {execution_context.settings_fingerprint}",
        'Use only the active project/channel context. Never mix in other tenant context.',
        'Return only the stage output without explanations.',
    ]
    if project_settings.get('language'):
        system_parts.append(f"Project language: {project_settings['language']}")
    if project_settings.get('tone_of_voice'):
        system_parts.append(f"Tone of voice: {project_settings['tone_of_voice']}")
    if project_settings.get('goal'):
        system_parts.append(f"Project goal: {project_settings['goal']}")
    if project_settings.get('content_rules'):
        system_parts.append(f"Content rules: {project_settings['content_rules']}")

    prompt_parts = []
    if agent.model:
        prompt_parts.append(f"Model profile: {agent.model}")
    prompt_parts.append(f"Agent name: {agent.name}")
    prompt_parts.append(f"Prompt fingerprint: {agent.prompt_fingerprint}")
    if agent.config:
        prompt_parts.append(f"Agent config: {agent.config}")

    user_parts = [
        'Task context:',
        _task_seed_text(task),
        f'Current working text:\n{current_text}',
    ]
    if prompt_parts:
        user_parts.append('\n'.join(prompt_parts))
    if previous_stages:
        user_parts.append('Previous stage outputs:')
        user_parts.extend(
            f"[{stage.role}] {stage.agent_name}\n{stage.content}"
            for stage in previous_stages
        )
    user_parts.append(f'Now execute the {agent.role} stage and return the resulting text.')

    temperature = 0.7
    max_tokens = 900
    if agent.config:
        temperature = float(agent.config.get('temperature', temperature))
        max_tokens = int(agent.config.get('max_tokens', max_tokens))

    return LLMGenerationRequest(
        system_prompt='\n'.join(system_parts),
        user_prompt='\n\n'.join(part for part in user_parts if part),
        model=_resolve_stage_model(agent),
        max_tokens=max_tokens,
        temperature=temperature,
    )



def _task_seed_text(task: ContentTask) -> str:
    parts = [task.title]
    if task.topic:
        parts.append(f'Topic: {task.topic}')
    if task.brief:
        parts.append(f'Brief: {task.brief}')
    if task.angle:
        parts.append(f'Angle: {task.angle}')
    return '\n'.join(parts)



def _aggregate_generation(stages: list[OrchestrationStageResult]) -> LLMGenerationResult:
    stage_generations = [stage.generation for stage in stages if stage.generation is not None]
    if not stage_generations:
        return LLMGenerationResult(
            provider='stub',
            model='stage-less',
            output_text='',
            finish_reason='stop',
            request_id=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=0,
            raw_error=None,
        )

    last = stage_generations[-1]

    def _sum_or_none(values: list[int | None]) -> int | None:
        numeric = [value for value in values if value is not None]
        if not numeric:
            return None
        return sum(numeric)

    return LLMGenerationResult(
        provider=last.provider,
        model=last.model,
        output_text=last.output_text,
        finish_reason=last.finish_reason,
        request_id=last.request_id,
        prompt_tokens=_sum_or_none([item.prompt_tokens for item in stage_generations]),
        completion_tokens=_sum_or_none([item.completion_tokens for item in stage_generations]),
        total_tokens=_sum_or_none([item.total_tokens for item in stage_generations]),
        latency_ms=sum(item.latency_ms for item in stage_generations),
        raw_error=last.raw_error,
    )



def run_linear_orchestration(db: Session, task: ContentTask) -> OrchestrationResult:
    execution_context = resolve_project_execution_context(db, task=task)
    preset_code = execution_context.agents[0].preset_code if execution_context.agents else None
    current_text = _task_seed_text(task)
    applied_agent_ids = [agent.id for agent in execution_context.agents]
    stages: list[OrchestrationStageResult] = []
    generation_mode = execution_context.agent_team_runtime.generation_mode
    adapter = get_llm_adapter()

    if generation_mode == 'single-pass' and execution_context.agents:
        single_pass_agent = _select_single_pass_agent(execution_context.agents)
        request = _build_stage_request(
            task=task,
            execution_context=execution_context,
            agent=single_pass_agent,
            previous_stages=[],
            current_text=current_text,
        )
        generation = adapter.generate(request)
        final_text = (generation.output_text or '').strip() or current_text
        stages.append(
            OrchestrationStageResult(
                role=single_pass_agent.role,
                agent_name=single_pass_agent.name,
                content=final_text,
                generation=generation,
            )
        )
        final_generation = generation
        final_agent_name = single_pass_agent.name
    else:
        for agent in execution_context.agents:
            request = _build_stage_request(
                task=task,
                execution_context=execution_context,
                agent=agent,
                previous_stages=stages,
                current_text=current_text,
            )
            generation = adapter.generate(request)
            stage_text = (generation.output_text or '').strip() or current_text
            stages.append(
                OrchestrationStageResult(
                    role=agent.role,
                    agent_name=agent.name,
                    content=stage_text,
                    generation=generation,
                )
            )
            current_text = stage_text

        final_generation = _aggregate_generation(stages)
        final_text = current_text
        if not stages:
            system_prompt, user_prompt = _build_final_generation_prompt(task, execution_context, stages)
            final_generation = generate_with_failover(
                LLMGenerationRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            )
            final_text = final_generation.output_text.strip() or current_text
        final_agent_name = stages[-1].agent_name if stages else None
    return OrchestrationResult(
        task_id=str(task.id),
        preset_code=preset_code,
        applied_agent_ids=applied_agent_ids,
        stages=stages,
        final_text=final_text,
        final_agent_name=final_agent_name,
        generation=final_generation,
        execution_context=execution_context,
    )
