from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.client_account import ClientAccount
from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.schemas.content_plan import ContentPlanUpdate
from app.schemas.draft import DraftUpdate
from app.services.crud import get_entity_or_404, update_entity
from app.services.generation_events import create_generation_event
from app.services.generation_metadata import build_task_generation_metadata
from app.services.generation_observability import build_job_trace, emit_generation_event, emit_generation_exception, queue_depth_snapshot
from app.services.generation_service import build_generation_service
from app.services.workflow import mark_task_as_drafted
from app.utils.enums import DraftStatus, GenerationJobOperation, GenerationJobStatus, SubscriptionStatus


GENERATION_JOB_BASE_PRIORITY = 100
GENERATION_JOB_OPERATION_PRIORITY = {
    GenerationJobOperation.REWRITE_DRAFT: 10,
    GenerationJobOperation.REGENERATE_DRAFT: 20,
    GenerationJobOperation.CREATE_DRAFT: 40,
    GenerationJobOperation.GENERATE_CONTENT_PLAN: 80,
}
ACTIVE_SUBSCRIPTION_BONUS = -20
PREMIUM_PLAN_CODES = {"pro", "business", "growth", "premium", "scale", "enterprise"}
PREMIUM_PLAN_BONUS = -10
URGENT_PRIORITY = 0


@dataclass(slots=True)
class GenerationJobProcessingResult:
    job: GenerationJob
    draft: Draft | None = None
    content_plan: ContentPlan | None = None


def enqueue_generation_job(
    db: Session,
    *,
    operation: GenerationJobOperation,
    payload: dict,
    project_id=None,
    content_task_id=None,
    draft_id=None,
    content_plan_id=None,
    client_account_id=None,
    priority: int | None = None,
) -> GenerationJob:
    resolved_project = _resolve_project(db, project_id=project_id, content_task_id=content_task_id, draft_id=draft_id, content_plan_id=content_plan_id)
    resolved_client_account_id = client_account_id or getattr(resolved_project, "client_account_id", None)
    resolved_priority = _resolve_generation_job_priority(
        db,
        operation=operation,
        payload=payload,
        client_account_id=resolved_client_account_id,
        explicit_priority=priority,
    )
    job = GenerationJob(
        operation=operation,
        status=GenerationJobStatus.QUEUED,
        priority=resolved_priority,
        payload=payload,
        project_id=project_id or getattr(resolved_project, "id", None),
        content_task_id=content_task_id,
        draft_id=draft_id,
        content_plan_id=content_plan_id,
        client_account_id=resolved_client_account_id,
        queued_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    emit_generation_event('generation job enqueued', **build_job_trace(job), queue_snapshot=queue_depth_snapshot(list_generation_jobs(db)))
    return job


def _resolve_project(
    db: Session,
    *,
    project_id=None,
    content_task_id=None,
    draft_id=None,
    content_plan_id=None,
) -> Project | None:
    if project_id is not None:
        return db.get(Project, project_id)
    if content_task_id is not None:
        task = db.get(ContentTask, content_task_id)
        if task is not None:
            return db.get(Project, task.project_id)
    if draft_id is not None:
        draft = db.get(Draft, draft_id)
        if draft is not None and draft.content_task_id is not None:
            task = db.get(ContentTask, draft.content_task_id)
            if task is not None:
                return db.get(Project, task.project_id)
    if content_plan_id is not None:
        plan = db.get(ContentPlan, content_plan_id)
        if plan is not None:
            return db.get(Project, plan.project_id)
    return None


def _resolve_generation_job_priority(
    db: Session,
    *,
    operation: GenerationJobOperation,
    payload: dict | None,
    client_account_id=None,
    explicit_priority: int | None = None,
) -> int:
    payload = payload or {}
    if explicit_priority is not None:
        return max(0, int(explicit_priority))
    if payload.get("is_urgent") or payload.get("priority") == "urgent":
        return URGENT_PRIORITY

    priority = GENERATION_JOB_OPERATION_PRIORITY.get(operation, GENERATION_JOB_BASE_PRIORITY)
    if client_account_id is None:
        return priority

    client_account = db.get(ClientAccount, client_account_id)
    if client_account is None:
        return priority

    if getattr(client_account, "subscription_status", None) == SubscriptionStatus.ACTIVE:
        priority += ACTIVE_SUBSCRIPTION_BONUS
    plan_code = (getattr(client_account, "subscription_plan_code", "") or "").strip().lower()
    if plan_code in PREMIUM_PLAN_CODES:
        priority += PREMIUM_PLAN_BONUS
    return max(0, priority)


def list_generation_jobs(db: Session) -> list[GenerationJob]:
    items = db.query(GenerationJob).all()
    sorted_items = sorted(
        items,
        key=lambda item: (item.status != GenerationJobStatus.QUEUED, item.priority, item.queued_at, str(item.id)),
    )
    emit_generation_event('generation queue snapshot', **queue_depth_snapshot(sorted_items))
    return sorted_items


def claim_generation_job(db: Session) -> GenerationJob | None:
    for job in list_generation_jobs(db):
        claimed = claim_generation_job_by_id(db, job_id=job.id)
        if claimed is not None:
            return claimed
    return None


def claim_generation_job_by_id(db: Session, *, job_id) -> GenerationJob | None:
    job = db.get(GenerationJob, job_id)
    if job is None or job.status != GenerationJobStatus.QUEUED:
        return None
    job.status = GenerationJobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    job.lease_token = uuid4().hex
    db.add(job)
    db.commit()
    db.refresh(job)
    emit_generation_event('generation job claimed', **build_job_trace(job))
    return job


def process_next_generation_job(db: Session) -> GenerationJobProcessingResult | None:
    job = claim_generation_job(db)
    if job is None:
        return None
    return process_claimed_generation_job(db, job)


def process_claimed_generation_job(db: Session, job: GenerationJob) -> GenerationJobProcessingResult:
    if job.status == GenerationJobStatus.QUEUED:
        job.status = GenerationJobStatus.PROCESSING
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.lease_token = job.lease_token or uuid4().hex
        db.add(job)
        db.commit()
        db.refresh(job)
    try:
        emit_generation_event('generation job processing started', **build_job_trace(job))
        result = _process_claimed_job(db, job)
        job.status = GenerationJobStatus.SUCCEEDED
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)
        emit_generation_event('generation job processing succeeded', **build_job_trace(job), result_payload=job.result_payload)
        result.job = job
        return result
    except Exception as exc:
        job.status = GenerationJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = str(exc)
        db.add(job)
        db.commit()
        db.refresh(job)
        emit_generation_exception('generation job processing failed', **build_job_trace(job), error=str(exc))
        raise


def drain_generation_queue(db: Session, *, limit: int | None = None) -> list[GenerationJobProcessingResult]:
    processed: list[GenerationJobProcessingResult] = []
    while True:
        if limit is not None and len(processed) >= limit:
            break
        item = process_next_generation_job(db)
        if item is None:
            break
        processed.append(item)
    return processed


def enqueue_and_process_generation_job(db: Session, **kwargs) -> GenerationJobProcessingResult:
    job = enqueue_generation_job(db, **kwargs)
    if hasattr(db, "storage"):
        result = process_next_generation_job(db)
        assert result is not None
        return result
    result = _process_claimed_job(db, job)
    job.status = GenerationJobStatus.SUCCEEDED
    job.started_at = job.started_at or datetime.now(timezone.utc)
    job.finished_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()
    db.refresh(job)
    result.job = job
    return result


def _process_claimed_job(db: Session, job: GenerationJob) -> GenerationJobProcessingResult:
    payload = job.payload or {}
    if job.operation == GenerationJobOperation.CREATE_DRAFT:
        return _process_create_draft(db, job, payload)
    if job.operation == GenerationJobOperation.REGENERATE_DRAFT:
        return _process_regenerate_draft(db, job)
    if job.operation == GenerationJobOperation.REWRITE_DRAFT:
        return _process_rewrite_draft(db, job, payload)
    if job.operation == GenerationJobOperation.GENERATE_CONTENT_PLAN:
        return _process_generate_content_plan(db, job)
    raise ValueError(f"Unsupported generation job operation: {job.operation}")


def _process_create_draft(db: Session, job: GenerationJob, payload: dict) -> GenerationJobProcessingResult:
    task = get_entity_or_404(db, ContentTask, job.content_task_id, "Task not found")
    generation_result = build_generation_service(db).generate_draft(task, source_text=payload.get("text"))
    author = payload.get("created_by_agent") or generation_result.created_by_agent
    task.generation_metadata = build_task_generation_metadata(generation_result, task=task)
    draft = Draft(
        content_task_id=task.id,
        text=generation_result.output_text,
        version=payload.get("version") or 1,
        created_by_agent=author,
        generation_metadata=generation_result.metadata(),
    )
    mark_task_as_drafted(task, draft)
    db.add(draft)
    db.add(task)
    db.commit()
    db.refresh(draft)
    create_generation_event(db, generation_result, task=task, draft=draft)
    job.result_payload = {"draft_id": str(draft.id), "task_id": str(task.id)}
    db.add(job)
    db.commit()
    db.refresh(draft)
    return GenerationJobProcessingResult(job=job, draft=draft)


def _process_regenerate_draft(db: Session, job: GenerationJob) -> GenerationJobProcessingResult:
    draft = get_entity_or_404(db, Draft, job.draft_id, "Draft not found")
    generation_result = build_generation_service(db).regenerate_draft(draft)
    draft = update_entity(
        db,
        draft,
        DraftUpdate(
            text=generation_result.output_text,
            created_by_agent=generation_result.created_by_agent,
            generation_metadata=generation_result.metadata(),
            status=DraftStatus.EDITED,
        ),
    )
    draft.content_task.generation_metadata = build_task_generation_metadata(generation_result, task=draft.content_task, draft=draft)
    create_generation_event(db, generation_result, task=draft.content_task, draft=draft)
    job.result_payload = {"draft_id": str(draft.id), "task_id": str(draft.content_task_id)}
    db.add(job)
    db.commit()
    db.refresh(draft)
    return GenerationJobProcessingResult(job=job, draft=draft)


def _process_rewrite_draft(db: Session, job: GenerationJob, payload: dict) -> GenerationJobProcessingResult:
    draft = get_entity_or_404(db, Draft, job.draft_id, "Draft not found")
    generation_result = build_generation_service(db).rewrite_draft(draft, rewrite_prompt=payload["rewrite_prompt"])
    draft = update_entity(
        db,
        draft,
        DraftUpdate(
            text=generation_result.output_text,
            created_by_agent=generation_result.created_by_agent,
            generation_metadata=generation_result.metadata(),
            status=DraftStatus.EDITED,
        ),
    )
    draft.content_task.generation_metadata = build_task_generation_metadata(generation_result, task=draft.content_task, draft=draft)
    create_generation_event(db, generation_result, task=draft.content_task, draft=draft)
    job.result_payload = {"draft_id": str(draft.id), "task_id": str(draft.content_task_id)}
    db.add(job)
    db.commit()
    db.refresh(draft)
    return GenerationJobProcessingResult(job=job, draft=draft)


def _build_planning_brief(project: Project, plan: ContentPlan) -> str:
    parts = [
        f"канал {project.name}",
        f"ниша: {project.niche or project.topic or project.name}",
        f"язык: {project.language}",
        f"период плана: {plan.start_date} → {plan.end_date}",
    ]
    if project.goal:
        parts.append(f"цель: {project.goal}")
    if project.tone_of_voice:
        parts.append(f"тон: {project.tone_of_voice}")
    if project.content_rules:
        parts.append(f"правила контента: {project.content_rules}")
    return "; ".join(parts)


def _process_generate_content_plan(db: Session, job: GenerationJob) -> GenerationJobProcessingResult:
    plan = get_entity_or_404(db, ContentPlan, job.content_plan_id, "Content plan not found")
    project = get_entity_or_404(db, Project, job.project_id or plan.project_id, "Project not found")
    generation_result = build_generation_service(db).generate_content_plan(
        plan,
        planning_brief=_build_planning_brief(project, plan),
    )
    plan = update_entity(
        db,
        plan,
        ContentPlanUpdate(
            status=(job.payload or {}).get("status") or plan.status,
            generated_by=generation_result.created_by_agent,
            summary=generation_result.output_text,
        ),
    )
    create_generation_event(db, generation_result, project=project)
    job.result_payload = {"content_plan_id": str(plan.id), "project_id": str(project.id)}
    db.add(job)
    db.commit()
    db.refresh(plan)
    return GenerationJobProcessingResult(job=job, content_plan=plan)
