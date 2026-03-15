from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.client_account import ClientAccount
from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.llm_generation_event import LLMGenerationEvent
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.services.generation_queue import drain_generation_queue, enqueue_generation_job, list_generation_jobs
from app.services import generation_queue as generation_queue_service
from app.utils.enums import ContentPlanPeriod, ContentTaskStatus, GenerationJobOperation, GenerationJobStatus, ProjectStatus, SubscriptionStatus


def test_generation_queue_processes_create_draft_job(fake_db, monkeypatch):
    project = Project(name='Queue Project', language='ru', status=ProjectStatus.ACTIVE)
    fake_db.add(project)
    task = ContentTask(project_id=project.id, title='Task 1', status=ContentTaskStatus.PENDING)
    fake_db.add(task)

    job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task.id,
        payload={'text': 'Seed text', 'version': 1},
    )

    processed = drain_generation_queue(fake_db)

    assert len(processed) == 1
    assert processed[0].draft is not None
    assert processed[0].draft.text
    assert job.status == GenerationJobStatus.SUCCEEDED
    assert task.status == ContentTaskStatus.DRAFTED


def test_generation_queue_processes_content_plan_job(fake_db):
    project = Project(name='Queue Project', language='ru', status=ProjectStatus.ACTIVE)
    fake_db.add(project)
    plan = ContentPlan(project_id=project.id, period_type=ContentPlanPeriod.WEEK, start_date='2026-03-16', end_date='2026-03-22', status='draft')
    fake_db.add(plan)

    job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.GENERATE_CONTENT_PLAN,
        project_id=project.id,
        content_plan_id=plan.id,
        payload={'status': 'generated'},
    )

    processed = drain_generation_queue(fake_db)

    assert len(processed) == 1
    assert processed[0].content_plan is not None
    assert processed[0].content_plan.summary
    assert job.status == GenerationJobStatus.SUCCEEDED
    assert processed[0].content_plan.status == 'generated'


def test_generation_queue_marks_job_failed_when_hard_stop_limit_exceeded(fake_db):
    user = User(email='queue-hard-stop@example.com', telegram_user_id='queue-hard-stop-user')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Queue Hard Stop WS', slug='queue-hard-stop-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    now = datetime.now(timezone.utc)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Queue Hard Stop Account',
        subscription_plan_code='business',
        subscription_status=SubscriptionStatus.ACTIVE,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        settings={
            'generation_guardrails': {
                'client_budget_limit_usd': '0.010000',
                'client_generation_quota_limit': 3,
                'client_token_quota_limit': 10000,
            }
        },
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(name='Queue Hard Stop Project', language='ru', status=ProjectStatus.ACTIVE, client_account_id=account.id)
    fake_db.add(project)
    fake_db.refresh(project)
    project.client_account = account

    task = ContentTask(project_id=project.id, title='Blocked task', status=ContentTaskStatus.PENDING)
    fake_db.add(task)
    fake_db.refresh(task)
    task.project = project

    fake_db.add(
        LLMGenerationEvent(
            client_id=account.id,
            project_id=project.id,
            operation_type='draft',
            provider='stub',
            model='stub',
            status='succeeded',
            total_tokens=12000,
            estimated_cost_usd='0.011000',
            created_at=now,
            updated_at=now,
        )
    )

    job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task.id,
        payload={'text': 'Seed text', 'version': 1},
    )

    with pytest.raises(ValueError, match='Generation hard-stopped'):
        drain_generation_queue(fake_db)

    assert job.status == GenerationJobStatus.FAILED
    assert 'Generation hard-stopped' in (job.error_message or '')


def test_generation_queue_can_order_large_backlog_without_losing_priority(fake_db):
    projects: list[Project] = []
    queued_jobs = []
    for index in range(24):
        project = Project(name=f'Load Project {index}', language='ru', status=ProjectStatus.ACTIVE)
        fake_db.add(project)
        fake_db.refresh(project)
        projects.append(project)

        for job_index in range(4):
            task = ContentTask(
                project_id=project.id,
                title=f'Load Task {index}-{job_index}',
                status=ContentTaskStatus.PENDING,
            )
            fake_db.add(task)
            fake_db.refresh(task)
            queued_jobs.append(
                enqueue_generation_job(
                    fake_db,
                    operation=GenerationJobOperation.REWRITE_DRAFT if job_index == 0 else GenerationJobOperation.CREATE_DRAFT,
                    project_id=project.id,
                    content_task_id=task.id,
                    payload={
                        'text': f'seed-{index}-{job_index}',
                        'rewrite_prompt': 'urgent refresh' if job_index == 0 else None,
                        'is_urgent': index == 0 and job_index == 0,
                    },
                )
            )

    ordered_jobs = list_generation_jobs(fake_db)

    assert len(ordered_jobs) == len(queued_jobs) == 96
    assert ordered_jobs[0].priority == 0
    assert ordered_jobs[0].payload.get('is_urgent') is True
    assert sum(1 for job in ordered_jobs if job.status == GenerationJobStatus.QUEUED) == 96
    assert min(job.priority for job in ordered_jobs[1:24]) <= min(job.priority for job in ordered_jobs[24:])


class _FastQueueProcessedResult:
    def __init__(self, job):
        self.job = job
        self.draft = None
        self.content_plan = None



def test_generation_queue_can_drain_sustained_large_backlog_without_leaking_order(fake_db, monkeypatch):
    processed_order: list[tuple[int, str]] = []

    def _fast_process_claimed_job(db, job):
        job.status = GenerationJobStatus.SUCCEEDED
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        processed_order.append((job.priority, str(job.id)))
        return _FastQueueProcessedResult(job)

    monkeypatch.setattr(generation_queue_service, 'process_claimed_generation_job', _fast_process_claimed_job)

    total_jobs = 0
    for project_index in range(30):
        project = Project(name=f'Sustained Queue Project {project_index}', language='ru', status=ProjectStatus.ACTIVE)
        fake_db.add(project)
        fake_db.refresh(project)
        for job_index in range(5):
            task = ContentTask(
                project_id=project.id,
                title=f'Sustained Queue Task {project_index}-{job_index}',
                status=ContentTaskStatus.PENDING,
            )
            fake_db.add(task)
            fake_db.refresh(task)
            enqueue_generation_job(
                fake_db,
                operation=GenerationJobOperation.REWRITE_DRAFT if job_index % 3 == 0 else GenerationJobOperation.CREATE_DRAFT,
                project_id=project.id,
                content_task_id=task.id,
                payload={
                    'text': f'load-{project_index}-{job_index}',
                    'rewrite_prompt': 'urgent refresh' if job_index % 3 == 0 else None,
                    'is_urgent': project_index < 2 and job_index == 0,
                },
            )
            total_jobs += 1

    processed = drain_generation_queue(fake_db)

    assert len(processed) == total_jobs == 150
    assert len(processed_order) == total_jobs
    assert processed_order[:2] == sorted(processed_order[:2], key=lambda item: item[0])
    assert all(earlier[0] <= later[0] for earlier, later in zip(processed_order, processed_order[1:]))
    assert all(job.status == GenerationJobStatus.SUCCEEDED for job in list_generation_jobs(fake_db))
