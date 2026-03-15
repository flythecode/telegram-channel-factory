from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.services.generation_guardrails import enforce_generation_hard_stop, evaluate_generation_guardrails
from app.services.generation_observability import emit_generation_event
from app.services.llm_provider import LLMGenerationRequest, LLMGenerationResult, generate_with_failover
from app.services.tariff_policy import enforce_generation_operation_access
from app.services.orchestration import OrchestrationResult, run_linear_orchestration

GenerationOperation = Literal[
    'ideas',
    'content_plan',
    'draft',
    'regenerate_draft',
    'rewrite_draft',
    'agent_stage',
]


@dataclass(slots=True)
class GenerationExecutionResult:
    operation_type: GenerationOperation
    output_text: str
    created_by_agent: str | None
    orchestration: OrchestrationResult | None
    generation: LLMGenerationResult
    guardrails: dict | None = None

    def metadata(self) -> dict:
        orchestration = self.orchestration
        stage_roles = [stage.role for stage in orchestration.stages] if orchestration else []
        execution_context = orchestration.execution_context.metadata() if orchestration else None
        stage_generations = [
            {
                'role': stage.role,
                'agent_name': stage.agent_name,
                'content': stage.content,
                'provider': stage.generation.provider if stage.generation else None,
                'model': stage.generation.model if stage.generation else None,
                'request_id': stage.generation.request_id if stage.generation else None,
                'prompt_tokens': stage.generation.prompt_tokens if stage.generation else None,
                'completion_tokens': stage.generation.completion_tokens if stage.generation else None,
                'total_tokens': stage.generation.total_tokens if stage.generation else None,
                'latency_ms': stage.generation.latency_ms if stage.generation else None,
            }
            for stage in (orchestration.stages if orchestration else [])
        ]
        return {
            'operation_type': self.operation_type,
            'preset_code': orchestration.preset_code if orchestration else None,
            'applied_agent_ids': orchestration.applied_agent_ids if orchestration else [],
            'stage_roles': stage_roles,
            'stage_generations': stage_generations,
            'final_agent_name': orchestration.final_agent_name if orchestration else self.created_by_agent,
            'provider': self.generation.provider,
            'model': self.generation.model,
            'finish_reason': self.generation.finish_reason,
            'request_id': self.generation.request_id,
            'prompt_tokens': self.generation.prompt_tokens,
            'completion_tokens': self.generation.completion_tokens,
            'total_tokens': self.generation.total_tokens,
            'latency_ms': self.generation.latency_ms,
            'failover': self.generation.failover,
            'usage_summary': self.usage_summary(),
            'cost_summary': self.cost_summary(),
            'execution_context': execution_context,
            'guardrails': self.guardrails,
        }

    def usage_summary(self) -> dict:
        return {
            'prompt_tokens': self.generation.prompt_tokens or 0,
            'completion_tokens': self.generation.completion_tokens or 0,
            'total_tokens': self.generation.total_tokens or 0,
            'latency_ms': self.generation.latency_ms,
        }

    def cost_summary(self) -> dict:
        estimated_cost_usd = None
        if self.generation.total_tokens is not None:
            estimated_cost_usd = f"{(Decimal(self.generation.total_tokens) * Decimal('0.000001')).quantize(Decimal('0.000001'))}"
        return {
            'estimated_cost_usd': estimated_cost_usd,
            'currency': 'USD',
            'estimation_model': 'flat_usd_per_token_v1',
        }

    def summary_metadata(self, **extra_fields) -> dict:
        summary = {
            'operation_type': self.operation_type,
            'provider': self.generation.provider,
            'model': self.generation.model,
            'request_id': self.generation.request_id,
            'finish_reason': self.generation.finish_reason,
            'failover': self.generation.failover,
            'usage_summary': self.usage_summary(),
            'cost_summary': self.cost_summary(),
        }
        summary.update({key: value for key, value in extra_fields.items() if value is not None})
        return summary


class GenerationService:
    def __init__(self, db: Session):
        self.db = db

    def _log_generation_completed(self, result: GenerationExecutionResult, *, project_id=None, task_id=None, draft_id=None, content_plan_id=None) -> None:
        emit_generation_event(
            'generation completed',
            operation_type=result.operation_type,
            provider=result.generation.provider,
            model=result.generation.model,
            request_id=result.generation.request_id,
            finish_reason=result.generation.finish_reason,
            latency_ms=result.generation.latency_ms,
            prompt_tokens=result.generation.prompt_tokens,
            completion_tokens=result.generation.completion_tokens,
            total_tokens=result.generation.total_tokens,
            failover=result.generation.failover,
            project_id=str(project_id) if project_id is not None else None,
            task_id=str(task_id) if task_id is not None else None,
            draft_id=str(draft_id) if draft_id is not None else None,
            content_plan_id=str(content_plan_id) if content_plan_id is not None else None,
            stage_roles=result.metadata().get('stage_roles'),
            guardrails=(result.guardrails or {}).get('blocking_reasons') if result.guardrails else None,
        )

    def generate_draft(self, task: ContentTask, *, source_text: str | None = None) -> GenerationExecutionResult:
        enforce_generation_operation_access(self.db, project=task.project, operation_type='draft')
        enforce_generation_hard_stop(self.db, project=task.project, operation_type='draft')
        orchestration = run_linear_orchestration(self.db, task)
        created_by_agent = self._resolve_author(orchestration)
        output_text = self._normalize_output(orchestration.final_text, fallback=source_text or task.title)
        guardrails = evaluate_generation_guardrails(self.db, project=task.project, operation_type='draft').metadata()
        result = GenerationExecutionResult(
            operation_type='draft',
            output_text=output_text,
            created_by_agent=created_by_agent,
            orchestration=orchestration,
            generation=orchestration.generation,
            guardrails=guardrails,
        )
        self._log_generation_completed(result, project_id=task.project_id, task_id=task.id)
        return result

    def regenerate_draft(self, draft: Draft) -> GenerationExecutionResult:
        task = draft.content_task
        enforce_generation_operation_access(self.db, project=task.project, operation_type='regenerate_draft')
        enforce_generation_hard_stop(self.db, project=task.project, operation_type='regenerate_draft')
        orchestration = run_linear_orchestration(self.db, task)
        created_by_agent = self._resolve_author(orchestration)
        fallback = draft.text
        output_text = self._normalize_output(orchestration.final_text, fallback=fallback)
        if '[Regenerated]' not in output_text:
            output_text = f'{output_text}\n\n[Regenerated]'
        guardrails = evaluate_generation_guardrails(self.db, project=task.project, operation_type='regenerate_draft').metadata()
        result = GenerationExecutionResult(
            operation_type='regenerate_draft',
            output_text=output_text,
            created_by_agent=created_by_agent,
            orchestration=orchestration,
            generation=orchestration.generation,
            guardrails=guardrails,
        )
        self._log_generation_completed(result, project_id=task.project_id, task_id=task.id, draft_id=draft.id)
        return result

    def rewrite_draft(self, draft: Draft, *, rewrite_prompt: str) -> GenerationExecutionResult:
        task = draft.content_task
        enforce_generation_operation_access(self.db, project=task.project, operation_type='rewrite_draft')
        enforce_generation_hard_stop(self.db, project=task.project, operation_type='rewrite_draft')
        system_prompt = (
            'You rewrite Telegram post drafts for publication. '
            'Return only the rewritten draft text without explanations.'
        )
        user_prompt = (
            f'Rewrite instruction:\n{rewrite_prompt.strip()}\n\n'
            f'Current draft:\n{draft.text.strip()}'
        )
        generation = generate_with_failover(
            LLMGenerationRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        output_text = self._normalize_output(generation.output_text, fallback=draft.text)
        created_by_agent = draft.created_by_agent
        guardrails = evaluate_generation_guardrails(self.db, project=task.project, operation_type='rewrite_draft').metadata()
        result = GenerationExecutionResult(
            operation_type='rewrite_draft',
            output_text=output_text,
            created_by_agent=created_by_agent,
            orchestration=None,
            generation=generation,
            guardrails=guardrails,
        )
        self._log_generation_completed(result, project_id=task.project_id, task_id=task.id, draft_id=draft.id)
        return result

    def generate_ideas(self, project_name: str, *, brief: str, count: int = 10, project=None) -> GenerationExecutionResult:
        enforce_generation_operation_access(self.db, project=project, operation_type='ideas')
        system_prompt = 'You generate concise Telegram content ideas. Return one idea per line in Russian.'
        user_prompt = (
            f'Project: {project_name}\n'
            f'Brief: {brief}\n'
            f'Need {count} distinct ideas for future channel posts.'
        )
        generation = generate_with_failover(
            LLMGenerationRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        result = GenerationExecutionResult(
            operation_type='ideas',
            output_text=self._normalize_output(generation.output_text, fallback=brief),
            created_by_agent='generation-service',
            orchestration=None,
            generation=generation,
            guardrails=evaluate_generation_guardrails(self.db, project=None, operation_type='ideas').metadata(),
        )
        self._log_generation_completed(result, project_id=getattr(project, 'id', None))
        return result

    def generate_content_plan(self, plan: ContentPlan, *, planning_brief: str) -> GenerationExecutionResult:
        project = getattr(plan, 'project', None)
        if project is None and getattr(plan, 'project_id', None) is not None:
            from app.models.project import Project
            project = self.db.get(Project, plan.project_id)
        enforce_generation_operation_access(self.db, project=project, operation_type='content_plan')
        enforce_generation_hard_stop(self.db, project=project, operation_type='content_plan')
        system_prompt = 'You generate a Telegram content plan in Russian. Return only the plan.'
        user_prompt = (
            f'Planning period: {plan.period_type} {plan.start_date} - {plan.end_date}\n'
            f'Context: {planning_brief}'
        )
        generation = generate_with_failover(
            LLMGenerationRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        result = GenerationExecutionResult(
            operation_type='content_plan',
            output_text=self._normalize_output(generation.output_text, fallback=planning_brief),
            created_by_agent='generation-service',
            orchestration=None,
            generation=generation,
            guardrails=evaluate_generation_guardrails(self.db, project=project, operation_type='content_plan').metadata(),
        )
        self._log_generation_completed(result, project_id=getattr(project, 'id', None), content_plan_id=plan.id)
        return result

    @staticmethod
    def _resolve_author(orchestration: OrchestrationResult) -> str | None:
        if orchestration.final_agent_name:
            return orchestration.final_agent_name
        if orchestration.execution_context.agents:
            return orchestration.execution_context.agents[-1].name
        return None

    @staticmethod
    def _normalize_output(output_text: str | None, *, fallback: str) -> str:
        normalized = (output_text or '').strip()
        return normalized or fallback.strip()


def build_generation_service(db: Session) -> GenerationService:
    return GenerationService(db)
